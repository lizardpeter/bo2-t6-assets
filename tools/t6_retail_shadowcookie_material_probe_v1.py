#!/usr/bin/env python3
"""Forensic T6 retail-executable probe for shadow-cookie/global Material evidence.

This is intentionally a *probe*, not an ownership promotion tool.  Input must be
one exact retail PC t6mp.exe build.  The probe:

* SHA/size/PE32 gates the executable;
* inventories exact renderer/material strings (shadowcookieoverlay, shadowoverlay,
  neighbors) and all printable shadow/cookie/overlay strings;
* records PE-section provenance for every string;
* records every physical 32-bit absolute pointer to each exact string;
* inspects 8-byte pair-table windows around those pointers, because historical
  CoD renderer lineage stored built-in Material rows as {name pointer, global
  Material** slot};
* optionally disassembles .text with Capstone and records exact instructions
  whose immediate/memory operands reference discovered string VAs.

The historical pair-table shape is used only to *collect candidates*.  Nothing
in this output proves that T6 uses the same struct, that a candidate slot is an
rgp field, or that any Material owns a particular Technique.  Promotion requires
an independently fail-closed adapter after the exact T6 layout/call path is
closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

EXPECTED_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
EXPECTED_BYTES = 12_850_328
EXPECTED_IMAGE_BASE = 0x00400000

EXACT_NAMES = [
    "$default",
    "white",
    "$additive",
    "clear_alpha_stencil",
    "depthprepass",
    "shadowclear",
    "shadowcookieoverlay",
    "shadowcookieblur",
    "shadowcaster",
    "shadowoverlay",
    "stencilshadow",
    "stencildisplay",
    "floatz_display",
]


class ProbeError(RuntimeError):
    pass


class PE:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if len(self.data) != EXPECTED_BYTES:
            raise ProbeError(f"unexpected executable size {len(self.data)} != {EXPECTED_BYTES}")
        sha = hashlib.sha256(self.data).hexdigest()
        if sha != EXPECTED_SHA256:
            raise ProbeError(f"unexpected executable SHA-256 {sha}")
        if self.data[:2] != b"MZ":
            raise ProbeError("not MZ")
        peoff = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[peoff:peoff+4] != b"PE\0\0":
            raise ProbeError("not PE")
        coff = peoff + 4
        machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", self.data, coff)
        if machine != 0x14C:
            raise ProbeError(f"unexpected machine 0x{machine:x}")
        opt = coff + 20
        magic = struct.unpack_from("<H", self.data, opt)[0]
        if magic != 0x10B:
            raise ProbeError(f"unexpected optional-header magic 0x{magic:x}")
        self.image_base = struct.unpack_from("<I", self.data, opt + 28)[0]
        if self.image_base != EXPECTED_IMAGE_BASE:
            raise ProbeError(f"unexpected image base 0x{self.image_base:x}")
        sec = opt + opt_size
        self.sections = []
        for i in range(nsects):
            off = sec + i * 40
            name = self.data[off:off+8].split(b"\0", 1)[0].decode("ascii", "replace")
            vsize, vaddr, raw_size, raw_off = struct.unpack_from("<IIII", self.data, off + 8)
            characteristics = struct.unpack_from("<I", self.data, off + 36)[0]
            self.sections.append({
                "name": name,
                "va": self.image_base + vaddr,
                "rva": vaddr,
                "virtualSize": vsize,
                "rawOffset": raw_off,
                "rawSize": raw_size,
                "characteristics": characteristics,
                "readable": bool(characteristics & 0x40000000),
                "writable": bool(characteristics & 0x80000000),
                "executable": bool(characteristics & 0x20000000),
            })

    def section_for_va(self, va: int):
        for s in self.sections:
            size = max(int(s["virtualSize"]), int(s["rawSize"]))
            if int(s["va"]) <= va < int(s["va"]) + size:
                return s
        return None

    def section_for_file_offset(self, off: int):
        for s in self.sections:
            start = int(s["rawOffset"])
            end = start + int(s["rawSize"])
            if start <= off < end:
                return s
        return None

    def file_offset_to_va(self, off: int):
        s = self.section_for_file_offset(off)
        if not s:
            return None
        return int(s["va"]) + (off - int(s["rawOffset"]))

    def va_to_file_offset(self, va: int):
        s = self.section_for_va(va)
        if not s:
            return None
        delta = va - int(s["va"])
        if delta >= int(s["rawSize"]):
            return None
        return int(s["rawOffset"]) + delta

    def cstr_at_va(self, va: int, maxn: int = 256):
        off = self.va_to_file_offset(va)
        if off is None:
            return None
        end = self.data.find(b"\0", off, min(len(self.data), off + maxn))
        if end < 0:
            return None
        raw = self.data[off:end]
        if not raw or any(b < 0x20 or b > 0x7E for b in raw):
            return None
        try:
            return raw.decode("ascii")
        except UnicodeDecodeError:
            return None


def _all_exact_strings(pe: PE, name: str):
    needle = name.encode("ascii") + b"\0"
    rows = []
    start = 0
    while True:
        off = pe.data.find(needle, start)
        if off < 0:
            break
        va = pe.file_offset_to_va(off)
        sec = pe.section_for_file_offset(off)
        rows.append({
            "fileOffset": off,
            "va": va,
            "vaHex": f"0x{va:08x}" if va is not None else None,
            "section": sec["name"] if sec else None,
        })
        start = off + 1
    return rows


def _keyword_strings(pe: PE):
    out = []
    seen = set()
    for m in re.finditer(rb"[ -~]{4,}\x00", pe.data):
        raw = m.group()[:-1]
        low = raw.lower()
        if not any(k in low for k in (b"shadow", b"cookie", b"overlay")):
            continue
        text = raw.decode("ascii", "replace")
        key = (m.start(), text)
        if key in seen:
            continue
        seen.add(key)
        va = pe.file_offset_to_va(m.start())
        sec = pe.section_for_file_offset(m.start())
        out.append({
            "text": text,
            "fileOffset": m.start(),
            "va": va,
            "vaHex": f"0x{va:08x}" if va is not None else None,
            "section": sec["name"] if sec else None,
        })
    return out


def _pointer_occurrences(pe: PE, target_va: int):
    needle = struct.pack("<I", target_va)
    rows = []
    start = 0
    while True:
        off = pe.data.find(needle, start)
        if off < 0:
            break
        va = pe.file_offset_to_va(off)
        sec = pe.section_for_file_offset(off)
        rows.append({
            "fileOffset": off,
            "va": va,
            "vaHex": f"0x{va:08x}" if va is not None else None,
            "section": sec["name"] if sec else None,
            "contextHex": pe.data[max(0, off-16):min(len(pe.data), off+20)].hex(),
        })
        start = off + 1
    return rows


def _pair_window(pe: PE, pointer_off: int, radius: int = 8):
    # Treat pointer_off as a potential first dword of an 8-byte row.  The caller
    # does not claim that this interpretation is correct; it is forensic output.
    rows = []
    base = pointer_off - radius * 8
    for rel_index in range(radius * 2 + 1):
        off = base + rel_index * 8
        if off < 0 or off + 8 > len(pe.data):
            continue
        name_ptr, slot_ptr = struct.unpack_from("<II", pe.data, off)
        name = pe.cstr_at_va(name_ptr)
        slot_sec = pe.section_for_va(slot_ptr)
        rows.append({
            "relativeRow": rel_index - radius,
            "fileOffset": off,
            "rowVa": pe.file_offset_to_va(off),
            "namePointerVa": name_ptr,
            "namePointerVaHex": f"0x{name_ptr:08x}",
            "resolvedName": name,
            "slotPointerVa": slot_ptr,
            "slotPointerVaHex": f"0x{slot_ptr:08x}",
            "slotSection": slot_sec["name"] if slot_sec else None,
            "slotSectionWritable": bool(slot_sec and slot_sec["writable"]),
        })
    score = sum(1 for r in rows if r["resolvedName"] and r["slotSection"])
    exact_hits = [r for r in rows if r["resolvedName"] in EXACT_NAMES]
    return {
        "scoreResolvedNameAndSlotSection": score,
        "exactKnownRows": exact_hits,
        "rows": rows,
    }


def _capstone_refs(pe: PE, target_vas: dict[str, set[int]]):
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
        from capstone.x86 import X86_OP_IMM, X86_OP_MEM
    except Exception as exc:
        return {"available": False, "error": repr(exc), "references": []}

    wanted = {}
    for label, vas in target_vas.items():
        for va in vas:
            wanted.setdefault(va, []).append(label)

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    refs = []
    for s in pe.sections:
        if not s["executable"] or not s["rawSize"]:
            continue
        raw_off = int(s["rawOffset"])
        raw = pe.data[raw_off:raw_off + int(s["rawSize"])]
        start_va = int(s["va"])
        for ins in md.disasm(raw, start_va):
            matched = set()
            for op in ins.operands:
                if op.type == X86_OP_IMM and (op.imm & 0xFFFFFFFF) in wanted:
                    matched.update(wanted[op.imm & 0xFFFFFFFF])
                elif op.type == X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                    disp = op.mem.disp & 0xFFFFFFFF
                    if disp in wanted:
                        matched.update(wanted[disp])
            if matched:
                refs.append({
                    "instructionVa": ins.address,
                    "instructionVaHex": f"0x{ins.address:08x}",
                    "section": s["name"],
                    "mnemonic": ins.mnemonic,
                    "opStr": ins.op_str,
                    "bytesHex": bytes(ins.bytes).hex(),
                    "targets": sorted(matched),
                })
    return {"available": True, "references": refs}


def build(path: Path):
    pe = PE(path)
    exact = {name: _all_exact_strings(pe, name) for name in EXACT_NAMES}

    ptrs = {}
    windows = []
    target_vas_for_disasm: dict[str, set[int]] = {}
    for name, occurrences in exact.items():
        ptr_rows = []
        for srow in occurrences:
            if srow["va"] is None:
                continue
            va = int(srow["va"])
            target_vas_for_disasm.setdefault(f"string:{name}", set()).add(va)
            for prow in _pointer_occurrences(pe, va):
                prow = dict(prow)
                prow["stringVa"] = va
                prow["stringVaHex"] = f"0x{va:08x}"
                ptr_rows.append(prow)
                if name in {"shadowcookieoverlay", "shadowoverlay", "shadowcookieblur", "shadowcaster", "shadowclear"}:
                    win = _pair_window(pe, int(prow["fileOffset"]))
                    if win["scoreResolvedNameAndSlotSection"] >= 3 or len(win["exactKnownRows"]) >= 3:
                        windows.append({
                            "anchorName": name,
                            "anchorPointerFileOffset": prow["fileOffset"],
                            "anchorPointerVa": prow["va"],
                            **win,
                        })
        ptrs[name] = ptr_rows

    # Deduplicate identical pair windows by the set of row file offsets.
    dedup = []
    seen = set()
    for w in windows:
        key = tuple(r["fileOffset"] for r in w["rows"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(w)

    capstone = _capstone_refs(pe, target_vas_for_disasm)
    return {
        "format": "t6-retail-shadowcookie-material-probe-v1",
        "retailExecutable": {
            "file": path.name,
            "bytes": len(pe.data),
            "sha256": hashlib.sha256(pe.data).hexdigest(),
            "imageBaseHex": f"0x{pe.image_base:08x}",
        },
        "sections": pe.sections,
        "exactStrings": exact,
        "keywordStrings": _keyword_strings(pe),
        "absolutePointerOccurrences": ptrs,
        "candidateEightBytePairWindows": dedup,
        "textReferences": capstone,
        "summary": {
            "exactStringOccurrenceCounts": {k: len(v) for k, v in exact.items()},
            "keywordStringCount": len(_keyword_strings(pe)),
            "pointerOccurrenceCounts": {k: len(v) for k, v in ptrs.items()},
            "candidatePairWindowCount": len(dedup),
            "textReferenceCount": len(capstone.get("references", [])),
        },
        "proofBoundary": (
            "Exact static-byte forensic probe of one SHA-pinned T6 retail PC executable. Exact string presence, PE-section placement, absolute pointer occurrences, and decoded x86 references are factual for this executable. Eight-byte pair windows are candidate collection only: historical renderer table shape is not promoted to T6 semantics. This output does not prove rgp field identity, runtime registration order, FastFile ownership, Material->TechniqueSet ownership, or the owner of pimp_technique_shadowoverlay_5255c888."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("exe", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(a.exe)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    for name in ("shadowcookieoverlay", "shadowoverlay", "shadowcookieblur", "shadowcaster", "shadowclear"):
        print(name, "strings", len(result["exactStrings"][name]), "ptrs", len(result["absolutePointerOccurrences"][name]))
    print("pair_windows", len(result["candidateEightBytePairWindows"]))
    print("text_refs", len(result["textReferences"].get("references", [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
