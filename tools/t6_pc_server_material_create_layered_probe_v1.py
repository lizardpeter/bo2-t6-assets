#!/usr/bin/env python3
"""Emit an exact, fail-closed disassembly/annotation of T6 Material_CreateLayered.

Authority is the SHA-pinned PC dedicated server executable and linker MAP. This
is a structural probe only: it records the complete function body, direct branch
and call targets, MAP labels, memory operands, immediates and raw-backed ASCII
references. It does not promote retail-client equivalence or infer semantics
from names.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import Counter
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_INVALID

EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
MAP_SHA256 = "34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf"
IMAGE_BASE = 0x00400000
START_VA = 0x00A4DA60
EXPECTED_END_VA = 0x00A4E100
EXPECTED_BODY_SHA256 = "505da556ae793f0a27a5e393dff0c9c1ff8f0be4a42c2935c5790c9c29535e42"
FORMAT = "t6-pc-server-material-create-layered-probe-v1"


class ProbeError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_sections(exe: bytes) -> list[dict]:
    pe = struct.unpack_from("<I", exe, 0x3C)[0]
    if exe[pe:pe+4] != b"PE\0\0":
        raise ProbeError("not a PE image")
    coff = pe + 4
    _machine, nsec, _ts, _sym, _nsym, opt_size, _chars = struct.unpack_from("<HHIIIHH", exe, coff)
    st = coff + 20 + opt_size
    out = []
    for i in range(nsec):
        o = st + i * 40
        name = exe[o:o+8].split(b"\0", 1)[0].decode("ascii", "replace")
        vsize, rva, raw_size, raw_off = struct.unpack_from("<IIII", exe, o + 8)
        chars = struct.unpack_from("<I", exe, o + 36)[0]
        out.append({
            "name": name,
            "va": IMAGE_BASE + rva,
            "virtualSize": vsize,
            "rawSize": raw_size,
            "rawOffset": raw_off,
            "characteristics": chars,
        })
    return out


def file_offset(sections: list[dict], va: int) -> int:
    for s in sections:
        if s["va"] <= va < s["va"] + s["rawSize"]:
            return s["rawOffset"] + va - s["va"]
    raise ProbeError(f"VA not raw-backed: 0x{va:08X}")


def section_for_va(sections: list[dict], va: int) -> dict | None:
    for s in sections:
        span = max(s["virtualSize"], s["rawSize"])
        if s["va"] <= va < s["va"] + span:
            return s
    return None


def parse_map(text: str) -> tuple[dict[int, list[dict]], list[int]]:
    line_re = re.compile(r"^\s*[0-9A-Fa-f]{4}:[0-9A-Fa-f]{8}\s+(\S+)\s+([0-9A-Fa-f]{8})(?:\s+f)?\s+(.+?\.obj)\s*$")
    by_va: dict[int, list[dict]] = {}
    for line in text.splitlines():
        m = line_re.match(line)
        if not m:
            continue
        va = int(m.group(2), 16)
        by_va.setdefault(va, []).append({
            "symbol": m.group(1),
            "object": m.group(3).strip(),
            "raw": line.strip(),
        })
    return by_va, sorted(by_va)


def ascii_at(exe: bytes, sections: list[dict], va: int) -> str | None:
    s = section_for_va(sections, va)
    if s is None or not (s["va"] <= va < s["va"] + s["rawSize"]):
        return None
    off = s["rawOffset"] + va - s["va"]
    chunk = exe[off:min(off + 256, s["rawOffset"] + s["rawSize"])]
    end = chunk.find(b"\0")
    if end < 0:
        return None
    raw = chunk[:end]
    if not (4 <= len(raw) <= 200):
        return None
    if any(b < 0x20 or b > 0x7E for b in raw):
        return None
    return raw.decode("ascii")


def build(exe_path: Path, map_path: Path) -> dict:
    exe = exe_path.read_bytes()
    map_bytes = map_path.read_bytes()
    if sha256(exe) != EXE_SHA256:
        raise ProbeError("executable SHA-256 gate failed")
    if sha256(map_bytes) != MAP_SHA256:
        raise ProbeError("MAP SHA-256 gate failed")
    sections = parse_sections(exe)
    by_va, sorted_vas = parse_map(map_bytes.decode("ascii", "replace"))

    start_labels = by_va.get(START_VA, [])
    if not start_labels:
        raise ProbeError("MAP has no exact symbol at Material_CreateLayered start")
    if not any("Material_CreateLayered" in row["symbol"] for row in start_labels):
        raise ProbeError(f"unexpected start labels: {start_labels!r}")
    next_vas = [va for va in sorted_vas if va > START_VA]
    if not next_vas:
        raise ProbeError("MAP has no symbol after Material_CreateLayered")
    map_next = next_vas[0]
    if map_next != EXPECTED_END_VA:
        raise ProbeError(f"Material_CreateLayered MAP end changed: 0x{map_next:08X}")

    start_off = file_offset(sections, START_VA)
    end_off = file_offset(sections, EXPECTED_END_VA - 1) + 1
    body = exe[start_off:end_off]
    if sha256(body) != EXPECTED_BODY_SHA256:
        raise ProbeError("Material_CreateLayered body SHA changed")

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    insns = list(md.disasm(body, START_VA))
    if not insns:
        raise ProbeError("empty disassembly")
    cursor = START_VA
    rows = []
    call_targets = Counter()
    direct_branch_targets = Counter()
    absolute_refs = Counter()
    ascii_refs: dict[int, str] = {}

    for ins in insns:
        if ins.address != cursor:
            raise ProbeError(f"disassembly gap at 0x{cursor:08X}; next 0x{ins.address:08X}")
        cursor += ins.size
        is_call = ins.mnemonic == "call"
        is_jump = ins.mnemonic.startswith("j")
        operands = []
        direct_targets = []
        for op in ins.operands:
            if op.type == X86_OP_IMM:
                value = op.imm & 0xFFFFFFFF
                sec = section_for_va(sections, value)
                text = ascii_at(exe, sections, value)
                if text is not None:
                    ascii_refs[value] = text
                operands.append({
                    "type": "imm",
                    "value": f"0x{value:08X}",
                    "section": None if sec is None else sec["name"],
                    "mapSymbols": by_va.get(value, []),
                    "ascii": text,
                })
                if is_call or is_jump:
                    direct_targets.append(value)
            elif op.type == X86_OP_MEM:
                mem = op.mem
                base = None if mem.base == X86_REG_INVALID else ins.reg_name(mem.base)
                index = None if mem.index == X86_REG_INVALID else ins.reg_name(mem.index)
                disp = mem.disp & 0xFFFFFFFF
                absolute = base is None and index is None
                sec = section_for_va(sections, disp) if absolute else None
                text = ascii_at(exe, sections, disp) if absolute else None
                if absolute:
                    absolute_refs[disp] += 1
                    if text is not None:
                        ascii_refs[disp] = text
                operands.append({
                    "type": "mem",
                    "base": base,
                    "index": index,
                    "scale": mem.scale,
                    "dispSigned": mem.disp,
                    "dispU32": f"0x{disp:08X}",
                    "absolute": absolute,
                    "section": None if sec is None else sec["name"],
                    "mapSymbols": by_va.get(disp, []) if absolute else [],
                    "ascii": text,
                })
            else:
                operands.append({"type": "reg_or_other"})

        for t in direct_targets:
            if is_call:
                call_targets[t] += 1
            elif is_jump:
                direct_branch_targets[t] += 1

        rows.append({
            "address": f"0x{ins.address:08X}",
            "size": ins.size,
            "bytes": ins.bytes.hex(),
            "mnemonic": ins.mnemonic,
            "opStr": ins.op_str,
            "operands": operands,
            "directTargets": [
                {"va": f"0x{t:08X}", "mapSymbols": by_va.get(t, [])}
                for t in direct_targets
            ],
        })

    if cursor != EXPECTED_END_VA:
        raise ProbeError(f"disassembly ended at 0x{cursor:08X}, expected 0x{EXPECTED_END_VA:08X}")
    if insns[-1].address + insns[-1].size != EXPECTED_END_VA:
        raise ProbeError("terminal instruction does not end on MAP boundary")

    def target_rows(counter: Counter) -> list[dict]:
        out = []
        for va, count in sorted(counter.items()):
            sec = section_for_va(sections, va)
            out.append({
                "va": f"0x{va:08X}",
                "count": count,
                "section": None if sec is None else sec["name"],
                "mapSymbols": by_va.get(va, []),
                "ascii": ascii_at(exe, sections, va),
            })
        return out

    return {
        "format": FORMAT,
        "authority": {
            "executable": exe_path.name,
            "executableSha256": EXE_SHA256,
            "map": map_path.name,
            "mapSha256": MAP_SHA256,
            "imageBase": f"0x{IMAGE_BASE:08X}",
        },
        "function": {
            "startVa": f"0x{START_VA:08X}",
            "endVaExclusive": f"0x{EXPECTED_END_VA:08X}",
            "sizeBytes": len(body),
            "sha256": sha256(body),
            "mapStartSymbols": start_labels,
            "mapNextSymbolVa": f"0x{map_next:08X}",
            "instructionCount": len(rows),
        },
        "calls": target_rows(call_targets),
        "directBranches": target_rows(direct_branch_targets),
        "absoluteReferences": target_rows(absolute_refs),
        "asciiReferences": [
            {"va": f"0x{va:08X}", "text": text, "mapSymbols": by_va.get(va, [])}
            for va, text in sorted(ascii_refs.items())
        ],
        "instructions": rows,
        "proofBoundary": (
            "Exact structural disassembly of SHA-pinned CoDMPServer_PC.exe Material_CreateLayered only. "
            "Symbol labels come from the independently SHA-pinned linker MAP. No retail-client equivalence, "
            "high-level semantic inference, or generated-Material reconstruction is promoted by this probe."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("map", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    doc = build(args.exe, args.map)
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(json.dumps({
        "format": doc["format"],
        "function": doc["function"],
        "callTargetCount": len(doc["calls"]),
        "absoluteReferenceCount": len(doc["absoluteReferences"]),
        "asciiReferenceCount": len(doc["asciiReferences"]),
        "outputSha256": sha256(payload),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
