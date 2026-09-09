#!/usr/bin/env python3
"""Byte-accounted full-text DObj locator for the exact current T6 comparison client.

This supersedes the v6/v7 whole-section scans, which used Capstone without
skip-data and therefore could terminate at an undecodable byte.  v8 enables
skip-data, accounts for every raw byte of every executable PE section, and then
performs both locator passes in one traversal:

  1. diagnostic string direct/absolute/one-hop pointer references;
  2. substantial-stack structural candidate enumeration.

This remains NON-AUTHORITATIVE for retail semantics.  It only locates possible
comparison-client code for later matching to independently pinned retail bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_ESP

from t6_current_client_dobj_diff_probe_v1 import NEEDLES, PE, ProbeError, find_all

FORMAT = "t6-current-client-dobj-fulltext-locator-v8"
AUTHORITY = "NON_AUTHORITATIVE_CURRENT_CLIENT_FULLTEXT_LOCATOR_ONLY"
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
        if sec["va"] <= va < sec["va"] + max(sec["vsize"], sec["rawSize"]):
            return sec["name"]
    return None


def fmt(insn) -> str:
    return f"0x{insn.address:08X}: {insn.bytes.hex():<24} {insn.mnemonic:<8} {insn.op_str}".rstrip()


def is_skipdata(insn) -> bool:
    # Capstone skip-data pseudo instructions carry id == 0.
    return int(insn.id) == 0


def absolute_refs(insn) -> list[tuple[str, int]]:
    if is_skipdata(insn):
        return []
    out: list[tuple[str, int]] = []
    for op in insn.operands:
        if op.type == X86_OP_IMM:
            out.append(("immediate", int(op.imm) & 0xFFFFFFFF))
        elif op.type == X86_OP_MEM:
            m = op.mem
            if not m.base and not m.index:
                out.append(("absoluteMemory", int(m.disp) & 0xFFFFFFFF))
    return out


def stack_alloc(insn, minimum: int) -> int | None:
    if is_skipdata(insn) or insn.mnemonic != "sub" or len(insn.operands) != 2:
        return None
    a, b = insn.operands
    if a.type != X86_OP_REG or a.reg != X86_REG_ESP or b.type != X86_OP_IMM:
        return None
    n = int(b.imm)
    return n if minimum <= n <= 0x10000 else None


def imm_values(insn) -> list[int]:
    if is_skipdata(insn):
        return []
    return [int(op.imm) & 0xFFFFFFFF for op in insn.operands if op.type == X86_OP_IMM]


def candidate_window(pe: PE, data: bytes, md: Cs, start_va: int, alloc: int, max_bytes: int) -> dict[str, Any]:
    sec = next((s for s in pe.sections if s["executable"] and s["va"] <= start_va < s["va"] + s["rawSize"]), None)
    if sec is None:
        raise ProbeError(f"candidate 0x{start_va:x} not executable/file-backed")
    bound = min(max_bytes, sec["va"] + sec["rawSize"] - start_va)
    off = pe.va_to_off(start_va)
    raw = data[off:off + bound]

    real = []
    skipped_bytes = 0
    total = 0
    ret_seen = False
    end_va = start_va
    for insn in md.disasm(raw, start_va):
        total += insn.size
        end_va = insn.address + insn.size
        if is_skipdata(insn):
            skipped_bytes += insn.size
            continue
        real.append(insn)
        if insn.mnemonic.startswith("ret"):
            ret_seen = True
            break
    consumed = end_va - start_va
    cand_raw = data[off:off + consumed]

    sites20, sitesA0, sitesFF = [], [], []
    calls, back = [], []
    byte_accesses = []
    movzx_byte = 0
    for insn in real:
        vals = imm_values(insn)
        if 0x20 in vals:
            sites20.append(insn.address)
        if 0xA0 in vals:
            sitesA0.append(insn.address)
        if 0xFF in vals or 0xFFFFFFFF in vals:
            sitesFF.append(insn.address)
        if insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM:
            calls.append({"at": insn.address, "target": int(insn.operands[0].imm) & 0xFFFFFFFF})
        if insn.mnemonic.startswith("j") and insn.operands and insn.operands[0].type == X86_OP_IMM:
            target = int(insn.operands[0].imm) & 0xFFFFFFFF
            if target < insn.address:
                back.append({"at": insn.address, "mnemonic": insn.mnemonic, "target": target})
        for oi, op in enumerate(insn.operands):
            if op.type != X86_OP_MEM:
                continue
            m = op.mem
            if int(op.size) == 1:
                if insn.mnemonic.startswith("movzx"):
                    movzx_byte += 1
                disp = int(m.disp)
                if 0 <= disp <= 0x20:
                    byte_accesses.append({
                        "va": insn.address,
                        "mnemonic": insn.mnemonic,
                        "opStr": insn.op_str,
                        "operandIndex": oi,
                        "disp": disp,
                        "base": insn.reg_name(m.base) if m.base else None,
                        "index": insn.reg_name(m.index) if m.index else None,
                        "scale": int(m.scale),
                    })

    header_offsets = sorted({x["disp"] for x in byte_accesses if x["disp"] in (8, 9, 10)})
    score = 0
    score += 4 if alloc >= 0x400 else 2
    score += 5 if sites20 else 0
    score += 5 if sitesA0 else 0
    score += 3 if sitesFF else 0
    score += min(4, len(back))
    score += min(4, movzx_byte)
    score += 2 * len(header_offsets)
    return {
        "startVa": start_va,
        "section": sec["name"],
        "stackAllocation": alloc,
        "retSeenWithinBound": ret_seen,
        "consumedBytes": consumed,
        "realInstructionCount": len(real),
        "skipDataBytesBeforeStop": skipped_bytes,
        "candidateSha256": sha256(cand_raw),
        "locatorScore": score,
        "features": {
            "imm0x20Sites": sites20,
            "imm0xA0Sites": sitesA0,
            "imm0xFFSites": sitesFF,
            "directCalls": calls,
            "backwardBranches": back,
            "movzxByteCount": movzx_byte,
            "smallByteMemoryAccesses": byte_accesses,
            "dobjHeaderNeighborhoodByteOffsetsObserved": header_offsets,
        },
        "instructions": [fmt(i) for i in real],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--min-stack", type=lambda x: int(x, 0), default=0x100)
    ap.add_argument("--max-candidate-bytes", type=lambda x: int(x, 0), default=0x3000)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    args = ap.parse_args()

    data = args.exe.read_bytes()
    actual_sha = sha256(data)
    if len(data) != args.expected_bytes or actual_sha.lower() != args.expected_sha256.lower():
        raise ProbeError(f"comparison identity mismatch bytes={len(data)} sha256={actual_sha}")
    pe = PE(data)

    strings = []
    string_targets: dict[int, set[str]] = {}
    for label, needle in NEEDLES.items():
        occ = []
        for off in find_all(data, needle):
            va = pe.off_to_va(off)
            occ.append({"fileOffset": off, "va": va, "section": section_for_off(pe, off)})
            if va is not None:
                string_targets.setdefault(va, set()).add(label)
        strings.append({"label": label, "needle": needle.decode("ascii"), "occurrenceCount": len(occ), "occurrences": occ})

    pointer_targets: dict[int, dict[str, set[Any]]] = {}
    pointer_slots = []
    for string_va, labels in sorted(string_targets.items()):
        for off in find_all(data, struct.pack("<I", string_va)):
            slot_va = pe.off_to_va(off)
            pointer_slots.append({
                "fileOffset": off, "slotVa": slot_va, "slotSection": section_for_off(pe, off),
                "stringVa": string_va, "labels": sorted(labels),
            })
            if slot_va is not None:
                e = pointer_targets.setdefault(slot_va, {"strings": set(), "labels": set()})
                e["strings"].add(string_va)
                e["labels"].update(labels)

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True

    section_accounting = []
    xrefs = []
    stack_sites: list[tuple[int, int]] = []
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        total = real_bytes = skip_bytes = real_count = skip_count = 0
        last_end = sec["va"]
        for insn in md.disasm(raw, sec["va"]):
            total += insn.size
            last_end = insn.address + insn.size
            if is_skipdata(insn):
                skip_bytes += insn.size
                skip_count += 1
                continue
            real_bytes += insn.size
            real_count += 1

            n = stack_alloc(insn, args.min_stack)
            if n is not None:
                stack_sites.append((insn.address, n))

            for operand_kind, target in absolute_refs(insn):
                if target in string_targets:
                    xrefs.append({
                        "instructionVa": insn.address,
                        "instruction": fmt(insn),
                        "section": sec["name"],
                        "operandKind": operand_kind,
                        "referenceKind": "directStringVa",
                        "referencedVa": target,
                        "labels": sorted(string_targets[target]),
                    })
                if target in pointer_targets:
                    e = pointer_targets[target]
                    xrefs.append({
                        "instructionVa": insn.address,
                        "instruction": fmt(insn),
                        "section": sec["name"],
                        "operandKind": operand_kind,
                        "referenceKind": "oneHopPointerSlot",
                        "referencedVa": target,
                        "pointerSlotSection": section_for_va(pe, target),
                        "pointedStringVas": sorted(e["strings"]),
                        "labels": sorted(e["labels"]),
                    })

        if total != len(raw) or last_end != sec["va"] + len(raw):
            raise ProbeError(
                f"executable section {sec['name']} accounting failed total={total} raw={len(raw)} "
                f"lastEnd=0x{last_end:x} expected=0x{sec['va'] + len(raw):x}"
            )
        section_accounting.append({
            "name": sec["name"], "startVa": sec["va"], "rawBytes": len(raw),
            "accountedBytes": total, "realInstructionBytes": real_bytes,
            "skipDataBytes": skip_bytes, "realInstructionCount": real_count,
            "skipDataRecordCount": skip_count, "complete": True,
        })

    # Deduplicate exact xref forms.
    uniq = {}
    for row in xrefs:
        key = (row["instructionVa"], row["operandKind"], row["referenceKind"], row["referencedVa"], tuple(row["labels"]))
        uniq[key] = row
    xrefs = sorted(uniq.values(), key=lambda r: (r["instructionVa"], r["referenceKind"], r["referencedVa"]))

    candidates = [candidate_window(pe, data, md, va, n, args.max_candidate_bytes) for va, n in stack_sites]
    candidates.sort(key=lambda r: (-r["locatorScore"], -r["stackAllocation"], r["startVa"]))

    lines = []
    for rank, row in enumerate(candidates[:30]):
        lines.append(
            f"===== NON-AUTHORITATIVE rank={rank} score={row['locatorScore']} start=0x{row['startVa']:08X} "
            f"stack=0x{row['stackAllocation']:X} sha256={row['candidateSha256']} ====="
        )
        lines.extend(row["instructions"])
        lines.append("")

    compact_candidates = []
    for rank, row in enumerate(candidates):
        c = {k: v for k, v in row.items() if k != "instructions"}
        c["rank"] = rank
        compact_candidates.append(c)

    by_label = {label: 0 for label in NEEDLES}
    for row in xrefs:
        for label in row["labels"]:
            by_label[label] += 1

    doc = {
        "format": FORMAT,
        "authority": AUTHORITY,
        "comparisonExecutable": {"bytes": len(data), "sha256": actual_sha, "imageBaseHex": f"0x{pe.image_base:08X}"},
        "retailAuthorityTarget": {"bytes": 12850328, "sha256": RETAIL_SHA256, "presentInProbe": False},
        "supersedes": [
            {"probe": "t6-current-client-dobj-string-xref-probe-v6", "reason": "non-exhaustive whole-section disassembly without skip-data/full byte accounting"},
            {"probe": "t6-current-client-dobj-structural-locator-v7", "reason": "non-exhaustive whole-section disassembly without skip-data/full byte accounting"}
        ],
        "executableSectionAccounting": section_accounting,
        "allExecutableSectionsCompletelyAccounted": all(x["complete"] for x in section_accounting),
        "strings": strings,
        "pointerSlots": pointer_slots,
        "xrefCount": len(xrefs),
        "xrefCountByLabel": by_label,
        "xrefs": xrefs,
        "structuralScan": {
            "minimumStackAllocation": args.min_stack,
            "maximumCandidateBytes": args.max_candidate_bytes,
            "stackSiteCount": len(stack_sites),
            "candidateCount": len(compact_candidates),
            "candidates": compact_candidates,
        },
        "proofBoundary": (
            "Full executable-section byte accounting makes negative results exhaustive only for the exact reference "
            "forms and structural predicates implemented here. This is still a non-retail comparison-client locator. "
            "No candidate rank, current-client dataflow, string reference, OpenT6 symbol/type information, or lineage "
            "feature may promote retail model order, duplicate ScriptString precedence, modelParent assignment, or "
            "hierarchy without independently retail-authoritative evidence tied to SHA-256 " + RETAIL_SHA256 + "."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    top = [{
        "rank": i, "va": f"0x{r['startVa']:08X}", "stack": f"0x{r['stackAllocation']:X}",
        "score": r["locatorScore"], "imm20": len(r["features"]["imm0x20Sites"]),
        "immA0": len(r["features"]["imm0xA0Sites"]), "immFF": len(r["features"]["imm0xFFSites"]),
        "header": r["features"]["dobjHeaderNeighborhoodByteOffsetsObserved"],
        "loops": len(r["features"]["backwardBranches"]), "calls": len(r["features"]["directCalls"]),
    } for i, r in enumerate(candidates[:15])]
    print(json.dumps({
        "sectionAccounting": section_accounting,
        "xrefCount": len(xrefs), "xrefCountByLabel": by_label,
        "stackSiteCount": len(stack_sites), "candidateCount": len(candidates),
        "topCandidates": top, "manifestSha256": sha256(payload.encode("utf-8")),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
