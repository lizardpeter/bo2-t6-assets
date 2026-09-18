#!/usr/bin/env python3
"""Instruction-operand xref census for exact T6 current-client zone/name strings.

This replaces the older raw packed-address byte search. A reference is admitted
only when a decoded executable instruction contains the exact mapped string VA
as an immediate operand or as an absolute memory displacement.

Authority is limited to the SHA-classified current Plutonium client and is
comparative only. No historical-retail DB function or Technique winner is
promoted from this output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import deque
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM


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
    "_zm",
    "mp_nuketown_2020",
)
PRE_CONTEXT = 12
POST_CONTEXT = 24


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
            return sec["va"] + (off - sec["rawOffset"])
    return None


def va_to_offset(sections, va: int):
    for sec in sections:
        if sec["va"] <= va < sec["va"] + sec["rawSize"]:
            return sec["rawOffset"] + (va - sec["va"])
    return None


def section_for_va(sections, va: int):
    for sec in sections:
        if sec["va"] <= va < sec["va"] + sec["rawSize"]:
            return sec
    return None


def all_occurrences(raw: bytes, needle: bytes):
    out = []
    pos = 0
    while True:
        pos = raw.find(needle, pos)
        if pos < 0:
            return out
        out.append(pos)
        pos += 1


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


def operand_refs(insn):
    refs = []
    for idx, op in enumerate(getattr(insn, "operands", ())):
        if op.type == X86_OP_IMM:
            refs.append(
                {
                    "operandIndex": idx,
                    "kind": "immediate",
                    "value": int(op.imm) & 0xFFFFFFFF,
                }
            )
        elif op.type == X86_OP_MEM:
            mem = op.mem
            if mem.base == 0 and mem.index == 0:
                refs.append(
                    {
                        "operandIndex": idx,
                        "kind": "absolute-memory-displacement",
                        "value": int(mem.disp) & 0xFFFFFFFF,
                    }
                )
    return refs


def following(raw: bytes, sections, va: int):
    off = va_to_offset(sections, va)
    sec = section_for_va(sections, va)
    if off is None or sec is None or not sec["executable"]:
        return []
    end = min(sec["rawOffset"] + sec["rawSize"], off + 256)
    out = []
    for insn in md().disasm(raw[off:end], va):
        if insn.id == 0:
            continue
        out.append(row(insn))
        if len(out) >= POST_CONTEXT:
            break
    return out


def raw_packed_hits_in_exec(raw: bytes, sections, va: int):
    packed = struct.pack("<I", va)
    hits = []
    for sec in sections:
        if not sec["executable"]:
            continue
        blob = raw[sec["rawOffset"] : sec["rawOffset"] + sec["rawSize"]]
        pos = 0
        while True:
            pos = blob.find(packed, pos)
            if pos < 0:
                break
            hits.append(
                {
                    "fileOffset": sec["rawOffset"] + pos,
                    "vaIfByteAligned": f"0x{sec['va'] + pos:08x}",
                    "section": sec["name"],
                }
            )
            pos += 1
    return hits


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

    occurrences = {}
    va_to_targets = {}
    for text in TARGETS:
        needle = text.encode("ascii") + b"\0"
        rows = []
        for off in all_occurrences(raw, needle):
            va = offset_to_va(sections, off)
            if va is None:
                continue
            sec = section_for_va(sections, va)
            rec = {
                "fileOffset": off,
                "va": f"0x{va:08x}",
                "section": None if sec is None else sec["name"],
                "sectionExecutable": bool(sec and sec["executable"]),
            }
            rows.append(rec)
            va_to_targets.setdefault(va, []).append(text)
        occurrences[text] = rows

    xrefs = {text: [] for text in TARGETS}
    previous = deque(maxlen=PRE_CONTEXT)

    for sec in sections:
        if not sec["executable"]:
            continue
        previous.clear()
        blob = raw[sec["rawOffset"] : sec["rawOffset"] + sec["rawSize"]]
        dis = md()
        for insn in dis.disasm(blob, sec["va"]):
            if insn.id == 0:
                previous.clear()
                continue
            matches = []
            for ref in operand_refs(insn):
                names = va_to_targets.get(ref["value"], ())
                for name in names:
                    matches.append((name, ref))
            if matches:
                current = row(insn)
                after = following(raw, sections, insn.address)
                for name, ref in matches:
                    xrefs[name].append(
                        {
                            "instruction": current,
                            "section": sec["name"],
                            "operand": {
                                "index": ref["operandIndex"],
                                "kind": ref["kind"],
                                "targetVa": f"0x{ref['value']:08x}",
                            },
                            "precedingDecodedInstructions": list(previous),
                            "followingDecodedInstructions": after,
                        }
                    )
            previous.append(row(insn))

    targets = {}
    summary = {}
    for text in TARGETS:
        literal_rows = occurrences[text]
        raw_hits = []
        for occ in literal_rows:
            raw_hits.extend(raw_packed_hits_in_exec(raw, sections, int(occ["va"], 16)))
        # Deduplicate packed hits when the same target text has repeated identical
        # mapped occurrences in a section.
        raw_unique = {
            (x["fileOffset"], x["vaIfByteAligned"], x["section"]): x for x in raw_hits
        }
        raw_hits = [raw_unique[k] for k in sorted(raw_unique)]
        decoded = xrefs[text]
        targets[text] = {
            "literalOccurrences": literal_rows,
            "rawPackedVaExecutableHitsOldMethod": raw_hits,
            "decodedOperandXrefs": decoded,
        }
        summary[text] = {
            "literalOccurrenceCount": len(literal_rows),
            "rawPackedVaExecutableHitCountOldMethod": len(raw_hits),
            "decodedOperandXrefCount": len(decoded),
        }

    output = {
        "format": "t6-current-client-instruction-operand-xref-probe-v1",
        "authority": "current Plutonium CDN object only; comparative discovery, not historical-retail authority",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": sha256,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "summary": summary,
        "targets": targets,
        "status": "decoded_operand_xrefs_only_no_db_identity_or_winner_promoted",
        "proofBoundary": (
            "Only decoded executable instruction operands equal to an exact mapped target-string VA are admitted as xrefs. "
            "Raw packed-address byte hits are retained solely to measure the prior method's false-positive surface and are "
            "never treated as references. String use, proximity, formatting, or a nearby call does not establish DB load "
            "semantics, XZoneInfo ownership, historical-retail behavior, or a Technique winner."
        ),
    }

    payload = (json.dumps(output, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(
        json.dumps(
            {
                "proofBytes": len(payload),
                "proofSha256": hashlib.sha256(payload).hexdigest(),
                "summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
