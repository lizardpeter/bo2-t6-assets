#!/usr/bin/env python3
"""Comparative current-client structural probe for XZoneInfo-like rows.

The exact PC dedicated-server proof establishes a 12-byte XZoneInfo layout
(name,+0; allocFlags,+4; freeFlags,+8) for that server build. This script does
NOT assume retail/current-client equivalence. Instead it searches the
SHA-classified current Plutonium client for byte-supported construction of the
same structural shape tied to exact mapped zone/name string pointers.

A candidate row is admitted only when decoded instructions store an exact target
string VA and then store values at the same effective memory base +4 (and
optionally +8) within one straight-line basic block. Register constants and ESP
movement are propagated conservatively; unknown state invalidates a candidate.
No function identity, zone priority, or Technique winner is promoted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_GRP_JUMP, CS_GRP_RET, CS_MODE_32
from capstone.x86_const import (
    X86_INS_ADD,
    X86_INS_LEA,
    X86_INS_MOV,
    X86_INS_POP,
    X86_INS_PUSH,
    X86_INS_SUB,
    X86_INS_XOR,
    X86_OP_IMM,
    X86_OP_MEM,
    X86_OP_REG,
    X86_REG_ESP,
)


EXPECTED_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS = (
    "common_mp",
    "common_patch_mp",
    "patch_mp",
    "code_post_gfx_mp",
    "localized_code_post_gfx_mp",
    "code_post_gfx",
    "localized_code_post_gfx",
    "common",
    "patch",
    "_mp",
    "mp_nuketown_2020",
)
SERVER_REFERENCE_FLAGS = {0x2, 0x8, 0x80, 0x8000}
LOOKAHEAD = 24


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


def offset_to_va(sections, off: int):
    for sec in sections:
        if sec["rawOffset"] <= off < sec["rawOffset"] + sec["rawSize"]:
            return sec["va"] + off - sec["rawOffset"]
    return None


def occurrences(raw: bytes, needle: bytes):
    out = []
    pos = 0
    while True:
        pos = raw.find(needle, pos)
        if pos < 0:
            return out
        out.append(pos)
        pos += 1


def disassembler():
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    return md


def insn_row(insn):
    return {
        "address": f"0x{insn.address:08x}",
        "bytes": insn.bytes.hex(),
        "mnemonic": insn.mnemonic,
        "opStr": insn.op_str,
    }


def source_constant(insn, op, regs):
    if op.type == X86_OP_IMM:
        return int(op.imm) & 0xFFFFFFFF
    if op.type == X86_OP_REG:
        return regs.get(op.reg)
    return None


def normalized_mem(insn, op, esp_delta):
    if op.type != X86_OP_MEM:
        return None
    mem = op.mem
    # Only admit simple base+disp addressing. Indexed rows cannot be proven to
    # have a stable +0/+4/+8 relationship by this local tracker.
    if mem.index:
        return None
    base = mem.base
    disp = int(mem.disp)
    if base == X86_REG_ESP:
        disp += esp_delta
    return {
        "baseRegId": int(base),
        "baseReg": insn.reg_name(base) if base else None,
        "normalizedDisp": disp,
        "segmentReg": insn.reg_name(mem.segment) if mem.segment else None,
    }


def update_state(insn, regs, esp_delta):
    ops = getattr(insn, "operands", ())
    # Handle exact constant-producing forms first.
    if insn.id == X86_INS_MOV and len(ops) >= 2 and ops[0].type == X86_OP_REG:
        regs[ops[0].reg] = source_constant(insn, ops[1], regs)
    elif insn.id == X86_INS_LEA and len(ops) >= 2 and ops[0].type == X86_OP_REG and ops[1].type == X86_OP_MEM:
        mem = ops[1].mem
        if mem.base == 0 and mem.index == 0:
            regs[ops[0].reg] = int(mem.disp) & 0xFFFFFFFF
        else:
            regs[ops[0].reg] = None
    elif insn.id == X86_INS_XOR and len(ops) >= 2 and ops[0].type == X86_OP_REG and ops[1].type == X86_OP_REG and ops[0].reg == ops[1].reg:
        regs[ops[0].reg] = 0
    else:
        try:
            _, writes = insn.regs_access()
        except Exception:
            writes = ()
        for reg in writes:
            if reg != X86_REG_ESP:
                regs[reg] = None

    # Track the stack pointer only for exact simple arithmetic forms.
    if insn.id == X86_INS_PUSH:
        esp_delta -= 4
    elif insn.id == X86_INS_POP:
        esp_delta += 4
    elif len(ops) >= 2 and ops[0].type == X86_OP_REG and ops[0].reg == X86_REG_ESP and ops[1].type == X86_OP_IMM:
        value = int(ops[1].imm)
        if insn.id == X86_INS_SUB:
            esp_delta -= value
        elif insn.id == X86_INS_ADD:
            esp_delta += value
    return esp_delta


def same_row(a, b, delta):
    return (
        a is not None
        and b is not None
        and a["baseRegId"] == b["baseRegId"]
        and a["segmentReg"] == b["segmentReg"]
        and b["normalizedDisp"] == a["normalizedDisp"] + delta
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = args.exe.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    if sha256 != EXPECTED_SHA256:
        raise SystemExit(f"unexpected current-client SHA-256 {sha256}")
    image_base, sections = parse_pe(raw)

    va_names = {}
    literal_summary = {}
    for name in TARGETS:
        rows = []
        for off in occurrences(raw, name.encode("ascii") + b"\0"):
            va = offset_to_va(sections, off)
            if va is None:
                continue
            rows.append({"fileOffset": off, "va": f"0x{va:08x}"})
            va_names.setdefault(va, []).append(name)
        literal_summary[name] = rows

    candidates = []
    for sec in sections:
        if not sec["executable"]:
            continue
        blob = raw[sec["rawOffset"] : sec["rawOffset"] + sec["rawSize"]]
        block = []
        regs = {}
        esp_delta = 0

        def flush():
            nonlocal block, regs, esp_delta
            if block:
                analyze_block(block)
            block = []
            regs = {}
            esp_delta = 0

        def analyze_block(items):
            # items already carry state snapshots captured before each instruction.
            for i, item in enumerate(items):
                insn = item["insn"]
                ops = getattr(insn, "operands", ())
                if insn.id != X86_INS_MOV or len(ops) < 2 or ops[0].type != X86_OP_MEM:
                    continue
                dest = normalized_mem(insn, ops[0], item["espDelta"])
                if dest is None:
                    continue
                value = source_constant(insn, ops[1], item["regs"])
                if value not in va_names:
                    continue
                for zone_name in va_names[value]:
                    alloc = None
                    free = None
                    context = [insn_row(insn)]
                    for nxt in items[i + 1 : min(len(items), i + LOOKAHEAD + 1)]:
                        ninsn = nxt["insn"]
                        context.append(insn_row(ninsn))
                        nops = getattr(ninsn, "operands", ())
                        if ninsn.id != X86_INS_MOV or len(nops) < 2 or nops[0].type != X86_OP_MEM:
                            continue
                        ndest = normalized_mem(ninsn, nops[0], nxt["espDelta"])
                        nvalue = source_constant(ninsn, nops[1], nxt["regs"])
                        if same_row(dest, ndest, 4) and nvalue is not None and alloc is None:
                            alloc = {
                                "instruction": insn_row(ninsn),
                                "value": int(nvalue) & 0xFFFFFFFF,
                                "valueHex": f"0x{int(nvalue) & 0xFFFFFFFF:08x}",
                                "matchesExactServerReferenceFlag": (int(nvalue) & 0xFFFFFFFF) in SERVER_REFERENCE_FLAGS,
                            }
                        if same_row(dest, ndest, 8) and nvalue is not None and free is None:
                            free = {
                                "instruction": insn_row(ninsn),
                                "value": int(nvalue) & 0xFFFFFFFF,
                                "valueHex": f"0x{int(nvalue) & 0xFFFFFFFF:08x}",
                            }
                    if alloc is not None:
                        candidates.append(
                            {
                                "zoneString": zone_name,
                                "zoneStringVa": f"0x{value:08x}",
                                "section": sec["name"],
                                "nameStore": insn_row(insn),
                                "rowAddressing": {
                                    "baseReg": dest["baseReg"],
                                    "normalizedNameDisp": dest["normalizedDisp"],
                                    "normalizedAllocDisp": dest["normalizedDisp"] + 4,
                                    "normalizedFreeDisp": dest["normalizedDisp"] + 8,
                                    "segmentReg": dest["segmentReg"],
                                },
                                "allocFlagsStore": alloc,
                                "freeFlagsStore": free,
                                "straightLineContext": context,
                            }
                        )

        md = disassembler()
        for insn in md.disasm(blob, sec["va"]):
            if insn.id == 0:
                flush()
                continue
            snapshot = {"insn": insn, "regs": dict(regs), "espDelta": esp_delta}
            block.append(snapshot)
            esp_delta = update_state(insn, regs, esp_delta)
            # Basic-block terminators make the +0/+4/+8 relationship conservative.
            if insn.group(CS_GRP_JUMP) or insn.group(CS_GRP_RET):
                flush()
        flush()

    candidates.sort(key=lambda x: int(x["nameStore"]["address"], 16))
    by_name = {name: 0 for name in TARGETS}
    for c in candidates:
        by_name[c["zoneString"]] += 1

    output = {
        "format": "t6-current-client-xzoneinfo-row-probe-v1",
        "authority": "current Plutonium CDN object only; comparative structural discovery, not historical-retail authority",
        "serverReferenceOnly": {
            "shape": "name@+0, allocFlags@+4, freeFlags@+8, stride 12",
            "knownExactServerFlagsHex": [f"0x{x:08x}" for x in sorted(SERVER_REFERENCE_FLAGS)],
            "policy": "The server layout/flags are comparison targets only; client equivalence is not assumed.",
        },
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": sha256,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "literalOccurrences": literal_summary,
        "candidateCount": len(candidates),
        "candidateCountByString": by_name,
        "candidates": candidates,
        "status": "comparative_structural_rows_only_no_xzoneinfo_identity_or_winner_promoted",
        "proofBoundary": (
            "A candidate requires decoded straight-line stores tying an exact mapped target string pointer to the same "
            "effective memory row at +0 and a concrete value at +4. ESP-relative offsets are normalized only through "
            "exact push/pop/add/sub forms. This can demonstrate a current-client 12-byte-row-like construction but does "
            "not prove that the row is XZoneInfo, that +4 has retail allocFlags semantics, that server flag priorities "
            "apply, or that any historical-retail Technique winner is selected."
        ),
    }

    payload = (json.dumps(output, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(
        json.dumps(
            {
                "candidateCount": len(candidates),
                "candidateCountByString": by_name,
                "proofBytes": len(payload),
                "proofSha256": hashlib.sha256(payload).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
