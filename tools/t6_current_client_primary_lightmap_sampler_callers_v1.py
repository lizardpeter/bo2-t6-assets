#!/usr/bin/env python3
"""Locate every direct current-client caller of the generic slot-4 sampler-state builders.

This is a locator/provenance probe for the remaining T6 primary-lightmap
sampler frontier. It deliberately does not assign lightmap semantics to either
builder. The executable must match the exact pinned current-client SHA.

Targets:
  0x009A7D00  initial packed codeImageSamplerStates[4..7] builder
  0x009A7D60  packed-state mutation/update builder

The output retains the exact target bodies plus bounded context around every
immediate CALL/JMP to either entry point. A later semantic projector can trace
the caller arguments and prove the reached low byte at source+0x1610.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM

FORMAT = "t6-current-client-primary-lightmap-sampler-callers-v1"
EXPECTED_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS = {
    0x009A7D00: {
        "label": "packedSamplerStateInitialBuilder",
        "end": 0x009A7D53,
        "gates": {
            0x009A7D00: ("8b44240c", "mov", "eax, dword ptr [esp + 0xc]"),
            0x009A7D2B: ("c7860c16000004000000", "mov", "dword ptr [esi + 0x160c], 4"),
            0x009A7D3F: ("898610160000", "mov", "dword ptr [esi + 0x1610], eax"),
            0x009A7D50: ("c20c00", "ret", "0xc"),
        },
    },
    0x009A7D60: {
        "label": "packedSamplerStateUpdateBuilder",
        "end": 0x009A7DE2,
        "gates": {
            0x009A7D60: ("56", "push", "esi"),
            0x009A7D71: ("c7860c16000000000000", "mov", "dword ptr [esi + 0x160c], 0"),
            0x009A7DD0: ("83c704", "add", "edi, 4"),
            0x009A7DD3: ("89be10160000", "mov", "dword ptr [esi + 0x1610], edi"),
            0x009A7DE1: ("c3", "ret", ""),
        },
    },
}
CONTEXT = 72


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


def locate(sections: list[dict], va: int, size: int) -> tuple[dict, int]:
    for section in sections:
        start = section["va"]
        end = start + section["rawSize"]
        if start <= va and va + size <= end:
            return section, section["rawOffset"] + va - start
    raise ProbeError(f"VA 0x{va:08x}+0x{size:x} is not file-backed")


def row(insn) -> dict:
    return {
        "address": f"0x{insn.address:08x}",
        "bytes": insn.bytes.hex(),
        "mnemonic": insn.mnemonic,
        "opStr": insn.op_str,
    }


def disassemble_target(raw: bytes, sections: list[dict], start: int, spec: dict) -> dict:
    end = int(spec["end"])
    section, offset = locate(sections, start, end - start)
    blob = raw[offset : offset + end - start]
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    instructions = list(md.disasm(blob, start))
    by_address = {insn.address: insn for insn in instructions}
    for va, expected in spec["gates"].items():
        insn = by_address.get(va)
        require(insn is not None, f"{spec['label']}: missing gate 0x{va:08x}")
        actual = (insn.bytes.hex(), insn.mnemonic, insn.op_str)
        require(actual == expected, f"{spec['label']}: gate drift at 0x{va:08x}: {actual!r}")
    return {
        "label": spec["label"],
        "startVa": f"0x{start:08x}",
        "endVaExclusive": f"0x{end:08x}",
        "section": section["name"],
        "sha256": hashlib.sha256(blob).hexdigest(),
        "instructions": [row(insn) for insn in instructions],
    }


def incoming_transfers(raw: bytes, sections: list[dict]) -> dict[int, list[dict]]:
    result = {target: [] for target in TARGETS}
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    for section in sections:
        if not section["executable"]:
            continue
        data = raw[section["rawOffset"] : section["rawOffset"] + section["rawSize"]]
        instructions = [insn for insn in md.disasm(data, section["va"]) if insn.id]
        for index, insn in enumerate(instructions):
            if insn.mnemonic not in {"call", "jmp"}:
                continue
            if len(insn.operands) != 1 or insn.operands[0].type != X86_OP_IMM:
                continue
            target = int(insn.operands[0].imm) & 0xFFFFFFFF
            if target not in result:
                continue
            lo = max(0, index - CONTEXT)
            hi = min(len(instructions), index + CONTEXT + 1)
            result[target].append(
                {
                    "transfer": row(insn),
                    "kind": insn.mnemonic,
                    "section": section["name"],
                    "contextBefore": [row(x) for x in instructions[lo:index]],
                    "contextAfter": [row(x) for x in instructions[index + 1 : hi]],
                }
            )
    return result


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

    target_functions = {
        f"0x{start:08x}": disassemble_target(raw, sections, start, spec)
        for start, spec in TARGETS.items()
    }
    incoming = incoming_transfers(raw, sections)

    rows = []
    for start, spec in TARGETS.items():
        transfers = incoming[start]
        rows.append(
            {
                "label": spec["label"],
                "targetVa": f"0x{start:08x}",
                "directCallCount": sum(item["kind"] == "call" for item in transfers),
                "directTailJumpCount": sum(item["kind"] == "jmp" for item in transfers),
                "incomingTransfers": transfers,
            }
        )

    document = {
        "format": FORMAT,
        "authority": "SHA-pinned current T6 client exact direct-control-transfer census",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": digest,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "targetFunctions": target_functions,
        "targets": rows,
        "summary": {
            "targetCount": len(TARGETS),
            "directCallCount": sum(row["directCallCount"] for row in rows),
            "directTailJumpCount": sum(row["directTailJumpCount"] for row in rows),
            "targetsWithIncomingDirectTransfer": sum(
                bool(row["incomingTransfers"]) for row in rows
            ),
        },
        "proofBoundary": (
            "Locator/provenance proof only. It closes exact target bodies and every "
            "decoded direct CALL/JMP into 0x009A7D00 and 0x009A7D60 in the SHA-pinned "
            "client. It does not name caller semantics, prove which path services "
            "lightmapSamplerPrimary, resolve indirect calls, or promote a final "
            "codeImageSamplerStates[4] byte. Those require a separate argument/dataflow "
            "projector over the reached caller path."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
