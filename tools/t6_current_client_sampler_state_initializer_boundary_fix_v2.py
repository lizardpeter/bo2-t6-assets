#!/usr/bin/env python3
"""Correct the current-client sampler initializer boundary and trace direct callers.

This proof intentionally replaces the older INT3-bounded interpretation around
0x004555A6. The preceding 0x004550E0 function returns at 0x004550FF; the
sampler-state initializer begins at 0x00455100 and returns with ret 0xC at
0x00455610.

The proof establishes:
- exact SHA-pinned bytes for 0x00455100..0x00455613,
- ECX is the initializer object pointer and is aliased into EAX,
- ECX is zeroed at 0x00455108 and is not written again before 0x004555A6,
- the dword write at object+0x1610 therefore writes zero,
- every decoded direct CALL to 0x00455100 and bounded caller context.

It does not assign the object the semantic name GfxCmdBufSourceState without
independent object-identity evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT = "t6-current-client-sampler-state-initializer-boundary-fix-v2"
START = 0x00455100
END = 0x00455613
ZERO_ECX = 0x00455108
SLOT4_PACKED_WRITE = 0x004555A6
CALLER_CONTEXT = 48


class ProofError(RuntimeError):
    pass


def require(cond: bool, message: str) -> None:
    if not cond:
        raise ProofError(message)


def parse_pe(raw: bytes):
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    require(raw[pe:pe + 4] == b"PE\0\0", "bad PE signature")
    coff = pe + 4
    section_count = struct.unpack_from("<H", raw, coff + 2)[0]
    optional_size = struct.unpack_from("<H", raw, coff + 16)[0]
    optional = coff + 20
    image_base = struct.unpack_from("<I", raw, optional + 28)[0]
    section_off = optional + optional_size
    sections = []
    for i in range(section_count):
        p = section_off + i * 40
        name = raw[p:p + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        virtual_size, rva, raw_size, raw_off = struct.unpack_from("<IIII", raw, p + 8)
        chars = struct.unpack_from("<I", raw, p + 36)[0]
        sections.append({
            "name": name,
            "va": image_base + rva,
            "virtualSize": virtual_size,
            "rawSize": raw_size,
            "rawOffset": raw_off,
            "executable": bool(chars & 0x20000000),
        })
    return image_base, sections


def section_for(sections, va):
    for s in sections:
        if s["va"] <= va < s["va"] + s["rawSize"]:
            return s
    raise ProofError(f"VA 0x{va:08X} is not backed by a section")


def record(ins):
    return {
        "address": f"0x{ins.address:08X}",
        "bytes": ins.bytes.hex(),
        "mnemonic": ins.mnemonic,
        "opStr": ins.op_str,
    }


def disasm_section(raw, section):
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    data = raw[section["rawOffset"]:section["rawOffset"] + section["rawSize"]]
    return md, [i for i in md.disasm(data, section["va"]) if i.id]


def ecx_writers(md, instructions):
    out = []
    for ins in instructions:
        _reads, writes = ins.regs_access()
        if any(md.reg_name(r) == "ecx" for r in writes):
            out.append(record(ins))
    return out


def direct_callers(raw, sections, target):
    calls = []
    for section in sections:
        if not section["executable"]:
            continue
        md, instructions = disasm_section(raw, section)
        for idx, ins in enumerate(instructions):
            if ins.mnemonic != "call" or len(ins.operands) != 1:
                continue
            if ins.operands[0].type != X86_OP_IMM:
                continue
            if (int(ins.operands[0].imm) & 0xFFFFFFFF) != target:
                continue
            lo = max(0, idx - CALLER_CONTEXT)
            hi = min(len(instructions), idx + CALLER_CONTEXT + 1)
            before = instructions[lo:idx]
            after = instructions[idx + 1:hi]
            prior_ecx = ecx_writers(md, before)
            calls.append({
                "call": record(ins),
                "section": section["name"],
                "lastEcxWriterInContext": prior_ecx[-1] if prior_ecx else None,
                "contextBefore": [record(x) for x in before],
                "contextAfter": [record(x) for x in after],
            })
    return calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = args.exe.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == SHA, f"SHA drift: {digest}")

    image_base, sections = parse_pe(raw)
    section = section_for(sections, START)
    require(section_for(sections, END - 1)["name"] == section["name"], "range crosses sections")

    raw_off = section["rawOffset"] + START - section["va"]
    blob = raw[raw_off:raw_off + (END - START)]

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    instructions = list(md.disasm(blob, START))
    require(instructions and instructions[0].address == START, "failed to decode function start")
    by_address = {i.address: i for i in instructions}

    def gate(va, mnemonic, op_str):
        ins = by_address.get(va)
        require(ins is not None, f"missing instruction 0x{va:08X}")
        require(ins.mnemonic == mnemonic and ins.op_str == op_str,
                f"instruction drift at 0x{va:08X}: {ins.mnemonic} {ins.op_str}")
        return ins

    gate(START, "mov", "eax, ecx")
    gate(ZERO_ECX, "xor", "ecx, ecx")
    gate(SLOT4_PACKED_WRITE, "mov", "dword ptr [eax + 0x1610], ecx")
    gate(0x00455610, "ret", "0xc")

    between = [i for i in instructions if ZERO_ECX <= i.address <= SLOT4_PACKED_WRITE]
    writers = ecx_writers(md, between)
    require([x["address"] for x in writers] == [f"0x{ZERO_ECX:08X}"],
            f"unexpected ECX writes before slot4 packed write: {writers}")

    calls = direct_callers(raw, sections, START)

    document = {
        "format": FORMAT,
        "authority": "SHA-pinned current-client exact function boundary, register dataflow, and decoded direct-call census",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": digest,
            "imageBaseHex": f"0x{image_base:08X}",
        },
        "function": {
            "startVa": f"0x{START:08X}",
            "endVaExclusive": f"0x{END:08X}",
            "section": section["name"],
            "instructionCount": len(instructions),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "callingConventionObservation": "ECX object pointer; ret 0xC pops three stack arguments",
            "entryObjectAlias": {
                "instruction": record(by_address[START]),
                "meaning": "EAX becomes an exact alias of incoming ECX object pointer",
            },
            "slot4PackedStateZero": {
                "zeroInstruction": record(by_address[ZERO_ECX]),
                "writeInstruction": record(by_address[SLOT4_PACKED_WRITE]),
                "interveningEcxWriterCount": 0,
                "result": "dword at object+0x1610 is exactly zero at this initializer point",
                "byte4Projection": "codeImageSamplerStates[4] byte is zero if and only if this object is independently proven to be the generic source-state object",
            },
            "instructions": [record(i) for i in instructions],
        },
        "directCallers": calls,
        "summary": {
            "functionStartVa": f"0x{START:08X}",
            "functionEndVaExclusive": f"0x{END:08X}",
            "directCallerCount": len(calls),
            "slot4PackedWriteVa": f"0x{SLOT4_PACKED_WRITE:08X}",
            "slot4PackedDwordValue": 0,
            "ecxWritesFromZeroThroughSlot4Write": [x["address"] for x in writers],
        },
        "proofBoundary": (
            "Exact current-client boundary/value proof and decoded direct CALL census. "
            "It proves the initializer writes zero to object+0x1610. It does not by itself "
            "name the object GfxCmdBufSourceState, prove indirect callers absent, or prove "
            "that this initialization remains the final runtime value for lightmapSamplerPrimary."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(document["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
