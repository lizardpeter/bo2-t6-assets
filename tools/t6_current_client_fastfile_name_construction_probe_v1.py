#!/usr/bin/env python3
"""Targeted current-client fastfile-name construction and buffer-use probe.

This probe starts from the exact decoded current-client routine at 0x005806e0
that references code_post_gfx, patch, common, and _mp. It records the routine
bytes/instructions, recovers direct-call argument pushes without assigning source
function names, resolves immediate arguments to mapped C strings where possible,
and then scans executable sections for decoded instruction operands that exactly
reference destination-buffer VAs used by the two observed string helpers.

Authority is comparative current-client evidence only. A constructed string,
helper call, or destination-buffer consumer does not prove historical-retail
XZoneInfo semantics or select a Technique winner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import deque
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_GRP_CALL, CS_GRP_RET, CS_MODE_32
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG


EXPECTED_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
CONSTRUCTOR_START = 0x005806E0
HELPERS = {
    0x00424F00: "helper_00424f00",
    0x004C0830: "helper_004c0830",
}
MAX_CONSTRUCTOR_BYTES = 0x800
PRE_CONTEXT = 10
POST_CONTEXT = 18


class ProbeError(RuntimeError):
    pass


def parse_pe(raw: bytes):
    if raw[:2] != b"MZ":
        raise ProbeError("not MZ")
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    if raw[pe : pe + 4] != b"PE\0\0":
        raise ProbeError("not PE")
    coff = pe + 4
    machine, nsec, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", raw, coff)
    if machine != 0x14C:
        raise ProbeError(f"not i386: 0x{machine:04x}")
    opt = coff + 20
    if struct.unpack_from("<H", raw, opt)[0] != 0x10B:
        raise ProbeError("not PE32")
    image_base = struct.unpack_from("<I", raw, opt + 28)[0]
    sec_off = opt + opt_size
    sections = []
    for i in range(nsec):
        o = sec_off + i * 40
        name = raw[o : o + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        virtual_size, rva, raw_size, raw_off = struct.unpack_from("<IIII", raw, o + 8)
        characteristics = struct.unpack_from("<I", raw, o + 36)[0]
        sections.append(
            {
                "name": name,
                "va": image_base + rva,
                "virtualSize": virtual_size,
                "rawSize": raw_size,
                "rawOffset": raw_off,
                "executable": bool(characteristics & 0x20000000),
            }
        )
    return image_base, sections


def section_for_va(sections, va):
    for sec in sections:
        if sec["va"] <= va < sec["va"] + sec["rawSize"]:
            return sec
    return None


def va_to_offset(sections, va):
    sec = section_for_va(sections, va)
    if sec is None:
        return None
    return sec["rawOffset"] + va - sec["va"]


def read_cstr(raw, sections, va, limit=256):
    off = va_to_offset(sections, va)
    if off is None:
        return None
    sec = section_for_va(sections, va)
    end = min(off + limit, sec["rawOffset"] + sec["rawSize"])
    chunk = raw[off:end]
    nul = chunk.find(b"\0")
    if nul < 0:
        return None
    value = chunk[:nul]
    if not value:
        return ""
    if any(x < 0x20 or x > 0x7E for x in value):
        return None
    return value.decode("ascii")


def md():
    d = Cs(CS_ARCH_X86, CS_MODE_32)
    d.detail = True
    d.skipdata = True
    return d


def row(insn):
    return {
        "address": f"0x{insn.address:08x}",
        "bytes": insn.bytes.hex(),
        "mnemonic": insn.mnemonic,
        "opStr": insn.op_str,
    }


def direct_target(insn):
    ops = getattr(insn, "operands", ())
    if not ops or ops[0].type != X86_OP_IMM:
        return None
    return int(ops[0].imm) & 0xFFFFFFFF


def push_value(insn):
    ops = getattr(insn, "operands", ())
    if insn.mnemonic != "push" or not ops:
        return None
    op = ops[0]
    if op.type == X86_OP_IMM:
        return {"kind": "immediate", "value": int(op.imm) & 0xFFFFFFFF}
    if op.type == X86_OP_REG:
        return {"kind": "register", "register": insn.reg_name(op.reg)}
    if op.type == X86_OP_MEM:
        mem = op.mem
        return {
            "kind": "memory",
            "base": insn.reg_name(mem.base) if mem.base else None,
            "index": insn.reg_name(mem.index) if mem.index else None,
            "scale": int(mem.scale),
            "disp": int(mem.disp),
        }
    return {"kind": f"other:{op.type}"}


def operand_refs(insn):
    refs = []
    for index, op in enumerate(getattr(insn, "operands", ())):
        if op.type == X86_OP_IMM:
            refs.append((index, "immediate", int(op.imm) & 0xFFFFFFFF))
        elif op.type == X86_OP_MEM:
            mem = op.mem
            if mem.base == 0 and mem.index == 0:
                refs.append((index, "absolute-memory-displacement", int(mem.disp) & 0xFFFFFFFF))
    return refs


def constructor(raw, sections):
    off = va_to_offset(sections, CONSTRUCTOR_START)
    sec = section_for_va(sections, CONSTRUCTOR_START)
    if off is None or sec is None or not sec["executable"]:
        raise ProbeError("constructor start not executable")
    end = min(off + MAX_CONSTRUCTOR_BYTES, sec["rawOffset"] + sec["rawSize"])
    insns = []
    for insn in md().disasm(raw[off:end], CONSTRUCTOR_START):
        if insn.id == 0:
            raise ProbeError(f"skipdata inside constructor at 0x{insn.address:08x}")
        insns.append(insn)
        if insn.group(CS_GRP_RET):
            break
    if not insns or not insns[-1].group(CS_GRP_RET):
        raise ProbeError("constructor did not reach RET inside bounded window")
    return insns


def helper_call_rows(raw, sections, insns):
    calls = []
    destinations = set()
    for i, insn in enumerate(insns):
        if not insn.group(CS_GRP_CALL):
            continue
        target = direct_target(insn)
        if target not in HELPERS:
            continue
        pushes = []
        j = i - 1
        while j >= 0 and len(pushes) < 6 and insns[j].mnemonic == "push":
            pushes.append(insns[j])
            j -= 1
        pushes.reverse()
        cdecl = list(reversed(pushes))
        args = []
        for p in cdecl:
            v = push_value(p)
            rec = {"pushInstruction": row(p), **(v or {"kind": "unknown"})}
            if v and v.get("kind") == "immediate":
                value = v["value"]
                rec["valueHex"] = f"0x{value:08x}"
                rec["mappedCString"] = read_cstr(raw, sections, value)
            args.append(rec)
        if args and args[0].get("kind") == "immediate":
            destinations.add(args[0]["value"])
        calls.append(
            {
                "call": row(insn),
                "target": f"0x{target:08x}",
                "targetLabel": HELPERS[target],
                "contiguousPushCount": len(pushes),
                "cdeclArgumentsFromContiguousPushes": args,
            }
        )
    return calls, sorted(destinations)


def following_context(raw, sections, va, count):
    off = va_to_offset(sections, va)
    sec = section_for_va(sections, va)
    if off is None or sec is None or not sec["executable"]:
        return []
    end = min(off + 0x200, sec["rawOffset"] + sec["rawSize"])
    out = []
    for insn in md().disasm(raw[off:end], va):
        if insn.id == 0:
            continue
        out.append(row(insn))
        if len(out) >= count:
            break
    return out


def contexts_for_refs(raw, sections, wanted):
    matches = {va: [] for va in wanted}
    for sec in sections:
        if not sec["executable"]:
            continue
        blob = raw[sec["rawOffset"] : sec["rawOffset"] + sec["rawSize"]]
        previous = deque(maxlen=PRE_CONTEXT)
        for insn in md().disasm(blob, sec["va"]):
            if insn.id == 0:
                previous.clear()
                continue
            refs = [x for x in operand_refs(insn) if x[2] in matches]
            if refs:
                after = following_context(raw, sections, insn.address + insn.size, POST_CONTEXT)
                before = list(previous)
                for op_index, kind, value in refs:
                    matches[value].append(
                        {
                            "section": sec["name"],
                            "instruction": row(insn),
                            "operandIndex": op_index,
                            "operandKind": kind,
                            "insideConstructor": CONSTRUCTOR_START <= insn.address <= CONSTRUCTOR_START + MAX_CONSTRUCTOR_BYTES,
                            "before": before,
                            "after": after,
                        }
                    )
            previous.append(row(insn))
    return matches


def helper_disassembly(raw, sections, va, max_bytes=0x120):
    off = va_to_offset(sections, va)
    sec = section_for_va(sections, va)
    if off is None or sec is None or not sec["executable"]:
        return []
    end = min(off + max_bytes, sec["rawOffset"] + sec["rawSize"])
    out = []
    for insn in md().disasm(raw[off:end], va):
        if insn.id == 0:
            break
        out.append(row(insn))
        if insn.group(CS_GRP_RET):
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = args.exe.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != EXPECTED_SHA256:
        raise SystemExit(f"unexpected current-client SHA-256 {sha}")
    image_base, sections = parse_pe(raw)

    insns = constructor(raw, sections)
    calls, destinations = helper_call_rows(raw, sections, insns)
    refs = contexts_for_refs(raw, sections, destinations)

    destination_rows = []
    for va in destinations:
        destination_rows.append(
            {
                "va": f"0x{va:08x}",
                "initialMappedCString": read_cstr(raw, sections, va),
                "decodedOperandXrefCount": len(refs[va]),
                "decodedOperandXrefs": refs[va],
            }
        )

    result = {
        "format": "t6-current-client-fastfile-name-construction-probe-v1",
        "authority": "current Plutonium CDN object only; comparative discovery, not historical-retail authority",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": sha,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "constructor": {
            "start": f"0x{CONSTRUCTOR_START:08x}",
            "endExclusive": f"0x{insns[-1].address + insns[-1].size:08x}",
            "instructionCount": len(insns),
            "instructions": [row(x) for x in insns],
            "selectedHelperCalls": calls,
        },
        "helpers": {
            f"0x{va:08x}": {
                "label": label,
                "firstFunctionInstructions": helper_disassembly(raw, sections, va),
            }
            for va, label in HELPERS.items()
        },
        "destinationBuffers": destination_rows,
        "status": "comparative_exact_constructor_and_buffer_xrefs_no_db_identity_or_winner_promoted",
        "proofBoundary": (
            "The constructor range, direct calls, contiguous push arguments, mapped C strings, destination-buffer VAs, and "
            "decoded operand xrefs are exact for the SHA-classified current client. Cdecl argument ordering is recorded only "
            "for contiguous PUSH sequences immediately preceding a direct CALL. Helper behavior can be inspected from the "
            "included instructions, but no source symbol name is assigned. Buffer construction/use does not prove XZoneInfo "
            "semantics, allocFlags, precedence, historical-retail equivalence, or any Technique winner."
        ),
    }
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({
        "constructorStart": result["constructor"]["start"],
        "constructorEndExclusive": result["constructor"]["endExclusive"],
        "selectedHelperCallCount": len(calls),
        "destinationBufferCount": len(destinations),
        "destinationXrefCounts": {f"0x{x:08x}": len(refs[x]) for x in destinations},
        "proofBytes": len(payload),
        "proofSha256": hashlib.sha256(payload).hexdigest(),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
