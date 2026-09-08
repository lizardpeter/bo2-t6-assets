#!/usr/bin/env python3
"""Locate T6 DObj duplicate/meld construction in a non-retail comparison client.

This tool is deliberately NON-AUTHORITATIVE for retail semantics.  It accepts an
explicit executable identity from the caller, finds DObj creation/meld diagnostic
strings, resolves direct absolute-address xrefs from executable sections, and
emits bounded disassembly windows plus code hashes.  The result is only a target
locator for matching against the pinned retail client later.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    from capstone.x86 import X86_OP_IMM
except Exception as exc:  # pragma: no cover - workflow dependency gate
    raise SystemExit(f"capstone required: {exc}")

FORMAT = "t6-current-client-dobj-differential-probe-v1"
IMAGE_BASE_DEFAULT = 0x400000

NEEDLES = {
    "partNotFound": b"WARNING: Part '%s' not found in model '%s' or any of its descendants",
    "rootMeldNotFound": b"WARNING: Attempting to meld model, but root part '%s' of model '%s' not found in model '%s' or any of its descendants",
    "tooManyBones": b"dobj for xmodel",
    "numModelsAssert": b"(unsigned)numModels <= DOBJ_MAX_SUBMODELS",
    "dobjSourcePath": b"xanim\\dobj.cpp",
}


class ProbeError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PE:
    def __init__(self, data: bytes):
        self.data = data
        if data[:2] != b"MZ":
            raise ProbeError("not MZ")
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe:pe+4] != b"PE\0\0":
            raise ProbeError("not PE")
        coff = pe + 4
        machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", data, coff)
        if machine != 0x14C:
            raise ProbeError(f"not i386: 0x{machine:x}")
        opt = coff + 20
        if struct.unpack_from("<H", data, opt)[0] != 0x10B:
            raise ProbeError("not PE32")
        self.image_base = struct.unpack_from("<I", data, opt + 28)[0]
        self.sections = []
        sec = opt + opt_size
        for i in range(nsects):
            off = sec + i * 40
            name = data[off:off+8].split(b"\0",1)[0].decode("ascii", "replace")
            vsize, vaddr, raw_size, raw_off = struct.unpack_from("<IIII", data, off+8)
            chars = struct.unpack_from("<I", data, off+36)[0]
            self.sections.append({
                "name": name,
                "va": self.image_base + vaddr,
                "vsize": vsize,
                "rawSize": raw_size,
                "rawOff": raw_off,
                "chars": chars,
                "executable": bool(chars & 0x20000000),
            })

    def va_to_off(self, va: int) -> int:
        for s in self.sections:
            start = s["va"]
            span = max(s["vsize"], s["rawSize"])
            if start <= va < start + span:
                d = va - start
                if d >= s["rawSize"]:
                    raise ProbeError(f"VA 0x{va:x} not file-backed")
                return s["rawOff"] + d
        raise ProbeError(f"unmapped VA 0x{va:x}")

    def off_to_va(self, off: int) -> int | None:
        for s in self.sections:
            if s["rawOff"] <= off < s["rawOff"] + s["rawSize"]:
                return s["va"] + (off - s["rawOff"])
        return None


def find_all(data: bytes, needle: bytes) -> list[int]:
    out = []
    p = 0
    while True:
        p = data.find(needle, p)
        if p < 0:
            return out
        out.append(p)
        p += 1


def fmt_insn(insn) -> str:
    return f"0x{insn.address:08X}: {insn.mnemonic:<8} {insn.op_str}".rstrip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    args = ap.parse_args()

    data = args.exe.read_bytes()
    actual_sha = sha256(data)
    if len(data) != args.expected_bytes or actual_sha.lower() != args.expected_sha256.lower():
        raise ProbeError(
            f"comparison client identity mismatch bytes={len(data)} sha256={actual_sha}"
        )
    pe = PE(data)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    string_rows = []
    target_vas: dict[int, list[str]] = {}
    for label, needle in NEEDLES.items():
        offs = find_all(data, needle)
        occurrences = []
        for off in offs:
            va = pe.off_to_va(off)
            occurrences.append({"fileOffset": off, "va": va})
            if va is not None:
                target_vas.setdefault(va, []).append(label)
        string_rows.append({
            "label": label,
            "needle": needle.decode("ascii"),
            "occurrenceCount": len(offs),
            "occurrences": occurrences,
        })

    xrefs = []
    for s in pe.sections:
        if not s["executable"] or not s["rawSize"]:
            continue
        raw = data[s["rawOff"]:s["rawOff"]+s["rawSize"]]
        for insn in md.disasm(raw, s["va"]):
            hits = []
            for op in insn.operands:
                if op.type == X86_OP_IMM and int(op.imm) in target_vas:
                    hits.extend(target_vas[int(op.imm)])
            if not hits:
                continue
            xrefs.append({
                "va": insn.address,
                "size": insn.size,
                "labels": sorted(set(hits)),
                "instruction": fmt_insn(insn),
            })

    # Bounded windows are evidence for comparison only.  They deliberately do
    # not pretend to infer exact function boundaries from generic x86 prologues.
    dis_lines = []
    windows = []
    for row in xrefs:
        center = row["va"]
        start = max(pe.image_base, center - 0x180)
        try:
            start_off = pe.va_to_off(start)
            end_off = min(len(data), start_off + 0x380)
        except ProbeError:
            continue
        raw = data[start_off:end_off]
        insns = list(md.disasm(raw, start))
        calls = []
        for insn in insns:
            if insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM:
                calls.append({"at": insn.address, "target": int(insn.operands[0].imm)})
        w = {
            "xrefVa": center,
            "labels": row["labels"],
            "windowStartVa": start,
            "windowBytes": len(raw),
            "windowSha256": sha256(raw),
            "directCallCount": len(calls),
            "directCalls": calls,
        }
        windows.append(w)
        dis_lines.append(
            f"===== xref 0x{center:08X} labels={','.join(row['labels'])} "
            f"window_sha256={w['windowSha256']} ====="
        )
        dis_lines.extend(fmt_insn(i) for i in insns)
        dis_lines.append("")

    doc = {
        "format": FORMAT,
        "authority": "NON_AUTHORITATIVE_CURRENT_CLIENT_DIFFERENTIAL_ONLY",
        "comparisonExecutable": {
            "file": args.exe.name,
            "bytes": len(data),
            "sha256": actual_sha,
            "imageBaseHex": f"0x{pe.image_base:08X}",
        },
        "sections": pe.sections,
        "strings": string_rows,
        "xrefCount": len(xrefs),
        "xrefs": xrefs,
        "windows": windows,
        "proofBoundary": (
            "This probe locates DObj/meld code in a non-retail comparison client only. It cannot promote retail "
            "DObj semantics, function addresses, model ordering, duplicate-part behavior, or hierarchy. Its only "
            "purpose is to produce exact comparison-client code/string targets for later matching against the "
            "pinned retail t6mp.exe SHA-256 11c7542f...24d5d1."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "stringOccurrences": {r["label"]: r["occurrenceCount"] for r in string_rows},
        "xrefCount": len(xrefs),
        "windowCount": len(windows),
        "manifestSha256": sha256(payload.encode()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
