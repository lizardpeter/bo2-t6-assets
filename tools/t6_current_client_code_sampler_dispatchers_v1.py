#!/usr/bin/env python3
"""Seal the current-client generic code-pixel-sampler dispatcher functions.

The generic array contract is already proven independently:
  image = source + codeSampler*4 + 0x1530
  state = source + codeSampler   + 0x160C

This probe starts from the two exact generic consumer sites already established
by T6_CURRENT_CLIENT_CODE_PIXEL_SAMPLER_ARRAY_SEMANTICS_V1, discovers their
INT3-bounded containing functions in the exact SHA-pinned client, retains the
complete bodies, and enumerates direct calls plus all code-image/state accesses.

It is intentionally a machine-code topology/dataflow locator. Cross-build names
such as R_SetPassShaderStableArguments and R_SetSampler remain separate evidence
until joined by an explicit semantic/cross-build proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_INVALID

FORMAT = "t6-current-client-code-sampler-dispatchers-v1"
EXPECTED_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
KNOWN_CONSUMERS = (
    {
        "label": "genericCodeSamplerConsumerA",
        "imageVa": 0x0077D758,
        "imageBytes": "8bbc8130150000",
        "imageOp": "edi, dword ptr [ecx + eax*4 + 0x1530]",
        "stateVa": 0x0077D75F,
        "stateBytes": "8a94010c160000",
        "stateOp": "dl, byte ptr [ecx + eax + 0x160c]",
    },
    {
        "label": "genericCodeSamplerConsumerB",
        "imageVa": 0x0077DE62,
        "imageBytes": "8bbc8630150000",
        "imageOp": "edi, dword ptr [esi + eax*4 + 0x1530]",
        "stateVa": 0x0077DE69,
        "stateBytes": "8a94060c160000",
        "stateOp": "dl, byte ptr [esi + eax + 0x160c]",
    },
)
CODE_IMAGES_BASE = 0x1530
SAMPLER_STATES_BASE = 0x160C
SAMPLER_COUNT = 55
SEARCH_RADIUS = 0x1800
MIN_INT3_RUN = 8
CALL_CONTEXT = 20


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def parse_pe(raw: bytes) -> tuple[int, list[dict]]:
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    require(raw[pe : pe + 4] == b"PE\0\0", "invalid PE signature")
    coff = pe + 4
    section_count = struct.unpack_from("<H", raw, coff + 2)[0]
    optional_size = struct.unpack_from("<H", raw, coff + 16)[0]
    optional = coff + 20
    image_base = struct.unpack_from("<I", raw, optional + 28)[0]
    section_table = optional + optional_size
    sections = []
    for index in range(section_count):
        off = section_table + index * 40
        name = raw[off : off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        virtual_size, rva, raw_size, raw_offset = struct.unpack_from("<IIII", raw, off + 8)
        characteristics = struct.unpack_from("<I", raw, off + 36)[0]
        sections.append(
            {
                "name": name,
                "va": image_base + rva,
                "virtualSize": virtual_size,
                "rawSize": raw_size,
                "rawOffset": raw_offset,
                "executable": bool(characteristics & 0x20000000),
            }
        )
    return image_base, sections


def section_for(sections: list[dict], va: int) -> dict:
    for section in sections:
        if section["va"] <= va < section["va"] + section["rawSize"]:
            return section
    raise ProbeError(f"VA 0x{va:08x} is not file-backed")


def va_to_offset(section: dict, va: int) -> int:
    return section["rawOffset"] + va - section["va"]


def row(insn) -> dict:
    return {
        "address": f"0x{insn.address:08x}",
        "bytes": insn.bytes.hex(),
        "mnemonic": insn.mnemonic,
        "opStr": insn.op_str,
    }


def disassemble_range(raw: bytes, section: dict, start: int, end: int, *, detail: bool = False):
    require(section["va"] <= start < end <= section["va"] + section["rawSize"], "range escapes section")
    off = va_to_offset(section, start)
    blob = raw[off : off + end - start]
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = detail
    md.skipdata = True
    return list(md.disasm(blob, start))


def raw_int3_runs(raw: bytes, section: dict, start: int, end: int) -> list[tuple[int, int]]:
    require(section["va"] <= start < end <= section["va"] + section["rawSize"], "INT3 scan escapes section")
    off = va_to_offset(section, start)
    data = raw[off : off + end - start]
    runs = []
    index = 0
    while index < len(data):
        if data[index] != 0xCC:
            index += 1
            continue
        run_start = index
        while index < len(data) and data[index] == 0xCC:
            index += 1
        if index - run_start >= MIN_INT3_RUN:
            runs.append((start + run_start, start + index))
    return runs


def discover_bounds(raw: bytes, section: dict, anchor: int) -> tuple[int, int, list]:
    lo = max(section["va"], anchor - SEARCH_RADIUS)
    hi = min(section["va"] + section["rawSize"], anchor + SEARCH_RADIUS)
    # Scan raw bytes for padding first. Starting an x86 disassembler at
    # anchor-SEARCH_RADIUS could begin in the middle of an instruction and
    # fabricate or miss a boundary.
    runs = raw_int3_runs(raw, section, lo, hi)
    before = [run for run in runs if run[1] <= anchor]
    after = [run for run in runs if run[0] > anchor]
    require(before, f"0x{anchor:08x}: no preceding INT3 boundary")
    require(after, f"0x{anchor:08x}: no following INT3 boundary")
    start = before[-1][1]
    end = after[0][0]
    require(start < anchor < end, f"0x{anchor:08x}: invalid INT3 bounds")
    body = disassemble_range(raw, section, start, end, detail=True)
    require(body and body[0].address == start, f"0x{anchor:08x}: body does not decode from boundary")
    require(any(insn.address == anchor for insn in body), f"0x{anchor:08x}: anchor absent from body")
    require(any(insn.mnemonic.startswith("ret") for insn in body), f"0x{anchor:08x}: bounded body has no RET")
    return start, end, body


def gate(by_address: dict[int, object], va: int, raw_hex: str, mnemonic: str, op_str: str) -> None:
    insn = by_address.get(va)
    require(insn is not None, f"missing gate 0x{va:08x}")
    actual = (insn.bytes.hex(), insn.mnemonic, insn.op_str)
    expected = (raw_hex, mnemonic, op_str)
    require(actual == expected, f"gate drift at 0x{va:08x}: {actual!r} != {expected!r}")


def memory_accesses(instructions) -> list[dict]:
    out = []
    for insn in instructions:
        for operand_index, operand in enumerate(insn.operands):
            if operand.type != X86_OP_MEM:
                continue
            mem = operand.mem
            disp = int(mem.disp)
            array = None
            slot_shape = None
            if disp == CODE_IMAGES_BASE and mem.scale == 4 and mem.index != X86_REG_INVALID:
                array = "codeImages"
                slot_shape = "base + index*4 + 0x1530"
            elif disp == SAMPLER_STATES_BASE and mem.scale in (0, 1) and mem.index != X86_REG_INVALID:
                array = "codeImageSamplerStates"
                slot_shape = "base + index + 0x160C"
            elif CODE_IMAGES_BASE <= disp < CODE_IMAGES_BASE + SAMPLER_COUNT * 4:
                array = "codeImagesFixedBand"
            elif SAMPLER_STATES_BASE <= disp < SAMPLER_STATES_BASE + SAMPLER_COUNT:
                array = "codeImageSamplerStatesFixedBand"
            if array is None:
                continue
            out.append(
                {
                    "instruction": row(insn),
                    "operandIndex": operand_index,
                    "array": array,
                    "slotShape": slot_shape,
                    "baseReg": insn.reg_name(mem.base) if mem.base != X86_REG_INVALID else None,
                    "indexReg": insn.reg_name(mem.index) if mem.index != X86_REG_INVALID else None,
                    "scale": mem.scale,
                    "disp": disp,
                }
            )
    return out


def direct_calls(instructions) -> list[dict]:
    calls = []
    for index, insn in enumerate(instructions):
        if insn.mnemonic != "call" or len(insn.operands) != 1 or insn.operands[0].type != X86_OP_IMM:
            continue
        target = int(insn.operands[0].imm) & 0xFFFFFFFF
        lo = max(0, index - CALL_CONTEXT)
        hi = min(len(instructions), index + CALL_CONTEXT + 1)
        calls.append(
            {
                "call": row(insn),
                "targetVa": f"0x{target:08x}",
                "contextBefore": [row(x) for x in instructions[lo:index]],
                "contextAfter": [row(x) for x in instructions[index + 1 : hi]],
            }
        )
    return calls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("--revision", default="transport-metadata-unpinned")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    raw = args.exe.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == EXPECTED_SHA256, f"exact current-client SHA drift: {digest}")
    image_base, sections = parse_pe(raw)

    functions = []
    seen_bounds = set()
    for consumer in KNOWN_CONSUMERS:
        section = section_for(sections, consumer["imageVa"])
        require(section["executable"], f"{consumer['label']}: anchor is not executable")
        start, end, body = discover_bounds(raw, section, consumer["imageVa"])
        by_address = {insn.address: insn for insn in body}
        gate(
            by_address,
            consumer["imageVa"],
            consumer["imageBytes"],
            "mov",
            consumer["imageOp"],
        )
        gate(
            by_address,
            consumer["stateVa"],
            consumer["stateBytes"],
            "mov",
            consumer["stateOp"],
        )

        bounds = (start, end)
        require(bounds not in seen_bounds, "known consumers unexpectedly occupy the same bounded function")
        seen_bounds.add(bounds)
        blob_off = va_to_offset(section, start)
        blob = raw[blob_off : blob_off + end - start]
        calls = direct_calls(body)
        accesses = memory_accesses(body)
        functions.append(
            {
                "label": consumer["label"],
                "startVa": f"0x{start:08x}",
                "endVaExclusive": f"0x{end:08x}",
                "bytes": end - start,
                "sha256": hashlib.sha256(blob).hexdigest(),
                "section": section["name"],
                "knownImageReadVa": f"0x{consumer['imageVa']:08x}",
                "knownStateReadVa": f"0x{consumer['stateVa']:08x}",
                "instructions": [row(insn) for insn in body],
                "genericArrayAccesses": accesses,
                "directCalls": calls,
                "rSetSamplerLineageAnchorCalls": [
                    item for item in calls if item["targetVa"] == "0x00740500"
                ],
            }
        )

    document = {
        "format": FORMAT,
        "authority": "SHA-pinned current T6 client exact INT3-bounded generic code-sampler dispatcher census",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": digest,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "genericArrayContract": {
            "codeImagesBaseOffset": CODE_IMAGES_BASE,
            "codeImageSamplerStatesBaseOffset": SAMPLER_STATES_BASE,
            "codeSamplerCount": SAMPLER_COUNT,
        },
        "functions": functions,
        "summary": {
            "functionCount": len(functions),
            "genericArrayAccessCount": sum(len(item["genericArrayAccesses"]) for item in functions),
            "directCallCount": sum(len(item["directCalls"]) for item in functions),
            "rSetSamplerLineageAnchorCallCount": sum(
                len(item["rSetSamplerLineageAnchorCalls"]) for item in functions
            ),
        },
        "proofBoundary": (
            "Closes exact current-client bounded function bodies containing the two already-proven "
            "generic code-pixel-sampler array consumers and retains their complete direct-call topology. "
            "The label R_SetSampler is used only as a lineage-anchor field name for target 0x00740500; "
            "this artifact does not independently promote that human symbol, cross-build equivalence, "
            "a final sampler-state byte for any specific code sampler, or framebuffer behavior. A later "
            "semantic projector must join exact source enum/index provenance and reached state-byte dataflow."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
