#!/usr/bin/env python3
"""Locate T6 DObj construction code in the exact current comparison client.

This is deliberately NON-AUTHORITATIVE for retail semantics.  v1 only tested
instruction immediate operands against diagnostic-string VAs.  That can miss
normal 32-bit x86 forms such as absolute memory operands and one-hop pointers
through .rdata/.data.  This probe therefore enumerates, with instruction-aligned
Capstone decoding:

  * direct immediate references to each retained DObj diagnostic string;
  * direct absolute-memory references to each string VA;
  * one-hop references to file-backed pointer slots that contain a string VA.

Every hit is preserved.  No hit count, nearest function, first hit, lineage
shape, or guessed function boundary is promoted to retail authority.  Bounded
windows are only locator material for later comparison with the pinned retail
`t6mp.exe` SHA-256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

from t6_current_client_dobj_diff_probe_v1 import NEEDLES, PE, ProbeError, find_all

FORMAT = "t6-current-client-dobj-string-xref-probe-v6"
AUTHORITY = "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def section_for_off(pe: PE, off: int) -> str | None:
    for sec in pe.sections:
        if sec["rawOff"] <= off < sec["rawOff"] + sec["rawSize"]:
            return sec["name"]
    return None


def section_for_va(pe: PE, va: int) -> str | None:
    for sec in pe.sections:
        start = sec["va"]
        if start <= va < start + max(sec["vsize"], sec["rawSize"]):
            return sec["name"]
    return None


def insn_text(insn) -> str:
    return f"0x{insn.address:08X}: {insn.bytes.hex():<24} {insn.mnemonic:<8} {insn.op_str}".rstrip()


def operand_refs(insn) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for op in insn.operands:
        if op.type == X86_OP_IMM:
            out.append(("immediate", int(op.imm) & 0xFFFFFFFF))
        elif op.type == X86_OP_MEM:
            m = op.mem
            # In 32-bit mode an absolute [disp32] has no base or index.  This
            # catches forms that v1 intentionally did not consider.
            if not m.base and not m.index:
                out.append(("absoluteMemory", int(m.disp) & 0xFFFFFFFF))
    return out


def bounded_window(pe: PE, data: bytes, md: Cs, center: int, before: int = 0x240, after: int = 0x340) -> dict[str, Any] | None:
    try:
        sec = next(s for s in pe.sections if s["executable"] and s["va"] <= center < s["va"] + s["rawSize"])
    except StopIteration:
        return None
    start = max(sec["va"], center - before)
    end = min(sec["va"] + sec["rawSize"], center + after)
    try:
        off = pe.va_to_off(start)
    except ProbeError:
        return None
    raw = data[off:off + (end - start)]
    insns = list(md.disasm(raw, start))
    return {
        "startVa": start,
        "endVaExclusive": start + len(raw),
        "bytes": len(raw),
        "sha256": sha256(raw),
        "instructionCount": len(insns),
        "decodedBytes": sum(i.size for i in insns),
        "instructions": [insn_text(i) for i in insns],
    }


def cluster_xrefs(xrefs: list[dict[str, Any]], max_gap: int = 0x500) -> list[dict[str, Any]]:
    if not xrefs:
        return []
    rows = sorted(xrefs, key=lambda x: x["instructionVa"])
    groups: list[list[dict[str, Any]]] = [[rows[0]]]
    for row in rows[1:]:
        if row["instructionVa"] - groups[-1][-1]["instructionVa"] <= max_gap:
            groups[-1].append(row)
        else:
            groups.append([row])
    out = []
    for i, group in enumerate(groups):
        out.append({
            "clusterIndex": i,
            "firstXrefVa": group[0]["instructionVa"],
            "lastXrefVa": group[-1]["instructionVa"],
            "xrefCount": len(group),
            "labels": sorted({label for row in group for label in row["labels"]}),
            "referenceKinds": sorted({row["referenceKind"] for row in group}),
            "xrefs": group,
        })
    return out


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
        raise ProbeError(f"comparison identity mismatch bytes={len(data)} sha256={actual_sha}")
    pe = PE(data)

    string_targets: dict[int, list[str]] = {}
    strings: list[dict[str, Any]] = []
    for label, needle in NEEDLES.items():
        occurrences = []
        for off in find_all(data, needle):
            va = pe.off_to_va(off)
            occurrences.append({"fileOffset": off, "va": va, "section": section_for_off(pe, off)})
            if va is not None:
                string_targets.setdefault(va, []).append(label)
        strings.append({
            "label": label,
            "needle": needle.decode("ascii"),
            "occurrenceCount": len(occurrences),
            "occurrences": occurrences,
        })

    # Find every file-backed little-endian pointer to every target string VA.
    # A pointer slot is locator evidence only.  It is not assumed to be unique,
    # typed, relocated, or code-referenced.
    pointer_targets: dict[int, dict[str, Any]] = {}
    pointer_slots: list[dict[str, Any]] = []
    for string_va, labels in sorted(string_targets.items()):
        for off in find_all(data, struct.pack("<I", string_va)):
            slot_va = pe.off_to_va(off)
            row = {
                "fileOffset": off,
                "slotVa": slot_va,
                "slotSection": section_for_off(pe, off),
                "stringVa": string_va,
                "labels": sorted(set(labels)),
            }
            pointer_slots.append(row)
            if slot_va is not None:
                ent = pointer_targets.setdefault(slot_va, {"stringVas": set(), "labels": set()})
                ent["stringVas"].add(string_va)
                ent["labels"].update(labels)

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    xrefs: list[dict[str, Any]] = []
    decoded_instruction_count = 0
    decoded_byte_count = 0
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        for insn in md.disasm(raw, sec["va"]):
            decoded_instruction_count += 1
            decoded_byte_count += insn.size
            for operand_kind, target in operand_refs(insn):
                if target in string_targets:
                    xrefs.append({
                        "instructionVa": insn.address,
                        "instructionSection": sec["name"],
                        "instruction": insn_text(insn),
                        "operandKind": operand_kind,
                        "referenceKind": "directStringVa",
                        "referencedVa": target,
                        "labels": sorted(set(string_targets[target])),
                    })
                if target in pointer_targets:
                    ent = pointer_targets[target]
                    xrefs.append({
                        "instructionVa": insn.address,
                        "instructionSection": sec["name"],
                        "instruction": insn_text(insn),
                        "operandKind": operand_kind,
                        "referenceKind": "oneHopPointerSlot",
                        "referencedVa": target,
                        "pointerSlotSection": section_for_va(pe, target),
                        "pointedStringVas": sorted(ent["stringVas"]),
                        "labels": sorted(ent["labels"]),
                    })

    # Deduplicate exact operand/reference hits while preserving different forms.
    uniq: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in xrefs:
        key = (
            row["instructionVa"], row["operandKind"], row["referenceKind"],
            row["referencedVa"], tuple(row["labels"]),
        )
        uniq[key] = row
    xrefs = sorted(uniq.values(), key=lambda x: (x["instructionVa"], x["referenceKind"], x["referencedVa"]))

    clusters = cluster_xrefs(xrefs)
    dis_lines: list[str] = []
    for cluster in clusters:
        center = cluster["firstXrefVa"]
        window = bounded_window(pe, data, md, center)
        if window is not None:
            cluster["boundedWindow"] = {k: v for k, v in window.items() if k != "instructions"}
            dis_lines.append(
                f"===== cluster {cluster['clusterIndex']} xrefs={cluster['xrefCount']} "
                f"first=0x{cluster['firstXrefVa']:08X} last=0x{cluster['lastXrefVa']:08X} "
                f"window_sha256={window['sha256']} ====="
            )
            dis_lines.extend(window["instructions"])
            dis_lines.append("")

    by_label = {label: 0 for label in NEEDLES}
    by_kind: dict[str, int] = {}
    for row in xrefs:
        for label in row["labels"]:
            by_label[label] += 1
        key = f"{row['referenceKind']}:{row['operandKind']}"
        by_kind[key] = by_kind.get(key, 0) + 1

    doc = {
        "format": FORMAT,
        "authority": AUTHORITY,
        "comparisonExecutable": {
            "bytes": len(data),
            "sha256": actual_sha,
            "imageBaseHex": f"0x{pe.image_base:08X}",
        },
        "retailAuthorityTarget": {
            "bytes": 12850328,
            "sha256": RETAIL_SHA256,
            "presentInThisProbe": False,
        },
        "strings": strings,
        "pointerSlotCount": len(pointer_slots),
        "pointerSlots": pointer_slots,
        "decodedExecutableInstructionCount": decoded_instruction_count,
        "decodedExecutableByteCount": decoded_byte_count,
        "xrefCount": len(xrefs),
        "xrefCountByLabel": by_label,
        "xrefCountByReferenceForm": dict(sorted(by_kind.items())),
        "xrefs": xrefs,
        "clusters": clusters,
        "proofBoundary": (
            "This result is only an instruction-aligned locator in the exact current comparison client. "
            "Direct string references, pointer-slot references, proximity, cluster membership, bounded-window "
            "hashes, older-engine lineage, or the symbol name DObjCreateDuplicateParts do not establish retail "
            "T6 function identity or semantics. Promotion requires independently retail-authoritative bytes or "
            "a retail runtime proof tied to t6mp.exe SHA-256 " + RETAIL_SHA256 + "."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "xrefCount": len(xrefs),
        "xrefCountByLabel": by_label,
        "xrefCountByReferenceForm": dict(sorted(by_kind.items())),
        "clusterCount": len(clusters),
        "manifestSha256": sha256(payload.encode("utf-8")),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
