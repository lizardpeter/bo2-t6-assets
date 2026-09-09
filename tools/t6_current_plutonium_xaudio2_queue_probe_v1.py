#!/usr/bin/env python3
"""Fail-closed current-Plutonium XAudio2 callback queue probe.

This tool is intentionally pinned to the exact revision-5346 client identity already
admitted by the audio proof chain. It does not claim historical retail equivalence.

It performs a complete executable-section Capstone pass with skip-data enabled and
also a byte-exact raw pointer census. The two views are retained separately so an
instruction xref is never invented merely because four pointer bytes occur in code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_INVALID

EXPECTED_BYTES = 13_263_640
EXPECTED_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
EXPECTED_IMAGE_BASE = 0x00400000

TARGETS = {
    "voice_vtable": 0x00C5E724,
    "callback_object": 0x01016B04,
    "signal_object": 0x01016B08,
    "pending_count": 0x01016B0C,
    "on_buffer_end": 0x00479280,
    "set_event_wrapper": 0x00651C30,
}

EXPECTED_VTABLE = [
    0x006CD320,
    0x00569CD0,
    0x00569CD0,
    0x006CD320,
    0x00479280,
    0x006CD320,
    0x005069C0,
]


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def u32(raw: bytes, off: int) -> int:
    return struct.unpack_from("<I", raw, off)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("client", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ns = ap.parse_args()

    raw = ns.client.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    require(len(raw) == EXPECTED_BYTES, f"client size mismatch: {len(raw)}")
    require(sha256 == EXPECTED_SHA256, f"client SHA-256 mismatch: {sha256}")

    pe = pefile.PE(data=raw, fast_load=False)
    base = pe.OPTIONAL_HEADER.ImageBase
    require(base == EXPECTED_IMAGE_BASE, f"image base mismatch: {base:#x}")

    sections = []
    for sec in pe.sections:
        sections.append(
            {
                "name": sec.Name.rstrip(b"\0").decode("ascii", "replace"),
                "rawOffset": sec.PointerToRawData,
                "rawSize": sec.SizeOfRawData,
                "rva": sec.VirtualAddress,
                "va": base + sec.VirtualAddress,
                "virtualSize": sec.Misc_VirtualSize,
                "characteristics": sec.Characteristics,
            }
        )

    def vaoff(va: int) -> int | None:
        for s in sections:
            if s["va"] <= va < s["va"] + s["rawSize"]:
                return s["rawOffset"] + va - s["va"]
        return None

    def offloc(off: int) -> dict:
        for s in sections:
            if s["rawOffset"] <= off < s["rawOffset"] + s["rawSize"]:
                return {
                    "fileOffset": off,
                    "section": s["name"],
                    "rva": s["rva"] + off - s["rawOffset"],
                    "va": s["va"] + off - s["rawOffset"],
                }
        return {"fileOffset": off}

    # Reassert the exact vtable/object facts before doing any wider search.
    vto = vaoff(TARGETS["voice_vtable"])
    require(vto is not None, "voice vtable is not raw-backed")
    actual_vtable = [u32(raw, vto + i * 4) for i in range(7)]
    require(actual_vtable == EXPECTED_VTABLE, f"voice vtable changed: {actual_vtable}")
    cbo = vaoff(TARGETS["callback_object"])
    require(cbo is not None, "callback object is not raw-backed")
    require(u32(raw, cbo) == TARGETS["voice_vtable"], "callback object vptr mismatch")

    imports: dict[int, dict] = {}
    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        for desc in pe.DIRECTORY_ENTRY_IMPORT:
            dll = desc.dll.decode("ascii", "replace") if desc.dll else ""
            for imp in desc.imports:
                imports[imp.address] = {
                    "dll": dll,
                    "name": imp.name.decode("ascii", "replace") if imp.name else None,
                    "ordinal": imp.ordinal,
                    "iatVa": imp.address,
                }

    exec_sections = [s for s in sections if (s["characteristics"] & 0x20000000) and s["rawSize"]]

    # Raw byte-exact pointer census across every raw-backed executable section.
    raw_refs: dict[str, list[dict]] = {k: [] for k in TARGETS}
    for name, value in TARGETS.items():
        needle = struct.pack("<I", value)
        for s in exec_sections:
            blob = raw[s["rawOffset"] : s["rawOffset"] + s["rawSize"]]
            p = 0
            while True:
                p = blob.find(needle, p)
                if p < 0:
                    break
                fo = s["rawOffset"] + p
                raw_refs[name].append(offloc(fo))
                p += 1

    # Complete executable pass. skipdata prevents embedded tables/alignment from
    # truncating the census. Capstone marks skipdata pseudo-rows with id == 0;
    # those rows are retained but never queried for operand metadata.
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    decoded: list[dict] = []
    for s in exec_sections:
        blob = raw[s["rawOffset"] : s["rawOffset"] + s["rawSize"]]
        for ins in md.disasm(blob, s["va"]):
            target_hits: list[str] = []
            import_hits: list[dict] = []
            is_skipdata = ins.id == 0
            if not is_skipdata:
                for op in ins.operands:
                    values = []
                    if op.type == X86_OP_IMM:
                        values.append(op.imm & 0xFFFFFFFF)
                    elif (
                        op.type == X86_OP_MEM
                        and op.mem.base == X86_REG_INVALID
                        and op.mem.index == X86_REG_INVALID
                    ):
                        values.append(op.mem.disp & 0xFFFFFFFF)
                    for value in values:
                        for name, target in TARGETS.items():
                            if value == target:
                                target_hits.append(name)
                        if value in imports:
                            import_hits.append(imports[value])
            decoded.append(
                {
                    "va": ins.address,
                    "size": ins.size,
                    "bytes": bytes(ins.bytes).hex(),
                    "mnemonic": ins.mnemonic,
                    "opStr": ins.op_str,
                    "skipdata": is_skipdata,
                    "targetHits": sorted(set(target_hits)),
                    "importHits": import_hits,
                }
            )

    insn_refs: dict[str, list[dict]] = {k: [] for k in TARGETS}
    hit_indices: dict[str, list[int]] = {k: [] for k in TARGETS}
    for idx, row in enumerate(decoded):
        for name in row["targetHits"]:
            insn_refs[name].append({k: row[k] for k in ("va", "size", "bytes", "mnemonic", "opStr")})
            hit_indices[name].append(idx)

    # Windows around every instruction-level target hit. Windows are diagnostic,
    # but exact instruction bytes and addresses are retained for independent audit.
    windows: dict[str, list[dict]] = {k: [] for k in TARGETS}
    for name, indices in hit_indices.items():
        for idx in indices:
            lo = max(0, idx - 10)
            hi = min(len(decoded), idx + 11)
            windows[name].append(
                {
                    "hitVa": decoded[idx]["va"],
                    "instructions": decoded[lo:hi],
                }
            )

    # Cross-check every instruction-level reference against a raw literal occurrence
    # somewhere inside that instruction. This prevents Capstone metadata alone from
    # creating a promoted pointer reference.
    raw_offsets_by_name = {
        name: {x["fileOffset"] for x in refs} for name, refs in raw_refs.items()
    }
    for name, refs in insn_refs.items():
        target_bytes = struct.pack("<I", TARGETS[name])
        for ref in refs:
            io = vaoff(ref["va"])
            require(io is not None, f"instruction ref {ref['va']:#x} not raw-backed")
            body = raw[io : io + ref["size"]]
            rel = body.find(target_bytes)
            require(rel >= 0, f"decoded ref lacks exact literal bytes: {name} @ {ref['va']:#x}")
            require(io + rel in raw_offsets_by_name[name], f"decoded/raw census disagreement: {name} @ {ref['va']:#x}")

    result = {
        "format": "t6-current-plutonium-xaudio2-queue-probe-v1",
        "authority": "exact current Plutonium revision 5346 client only; not historical retail-equivalent",
        "client": {"bytes": len(raw), "sha256": sha256, "imageBase": base},
        "targets": dict(TARGETS),
        "voiceVtableEntries": actual_vtable,
        "rawExecutablePointerRefs": raw_refs,
        "instructionPointerRefs": insn_refs,
        "instructionWindows": windows,
        "summary": {
            "rawRefCounts": {k: len(v) for k, v in raw_refs.items()},
            "instructionRefCounts": {k: len(v) for k, v in insn_refs.items()},
            "decodedExecutableRows": len(decoded),
            "skipdataRows": sum(1 for row in decoded if row["skipdata"]),
        },
        "proofBoundary": (
            "Instruction xrefs require both an exact decoded absolute immediate/displacement and the same "
            "four-byte target literal inside that instruction. Raw pointer occurrences remain a separate census. "
            "Capstone skipdata rows are retained only as accounting records and cannot become xrefs. "
            "Windows do not establish function boundaries or semantics beyond their exact instructions."
        ),
    }
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    for name in ("callback_object", "signal_object", "pending_count", "voice_vtable"):
        print(name)
        for window in windows[name]:
            print(" hit", hex(window["hitVa"]))
            for row in window["instructions"]:
                mark = "*" if name in row["targetHits"] else " "
                print(mark, hex(row["va"]), row["mnemonic"], row["opStr"])
    print("result_sha256", hashlib.sha256(ns.output.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
