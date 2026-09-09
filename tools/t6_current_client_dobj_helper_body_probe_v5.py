#!/usr/bin/env python3
"""Disassemble only retail-authoritative T6 skeleton helper bodies through a pinned comparison copy.

The exact retail proof pins three complete helper ranges by SHA-256.  The five
retail byte anchors also relocate uniquely into the exact current comparison
client at one uniform delta.  This probe requires the complete shifted helper
ranges to hash identically to the retail-pinned ranges before disassembling them.

Comparison-only xrefs are emitted strictly as NON-AUTHORITATIVE locator evidence.
An empty xref class is a valid negative result and is never promoted into a
failure or a guessed caller.
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

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError, find_all
from t6_current_client_dobj_diff_probe_v2 import ANCHORS, RETAIL_RANGES, RETAIL_SHA

FORMAT = "t6-current-client-dobj-helper-body-probe-v5"
AUTHORITY = "RETAIL_HELPER_BODIES_ONLY_COMPARISON_XREFS_NON_AUTHORITATIVE"
EXPECTED_SHIFT = 0x5810
RETAIL_ANCHOR_VA = {
    "rootNoParentPrologue": 0x8D6100,
    "rootWithParentPrologue": 0x8D6220,
    "nonRootPrologue": 0x8D6B50,
    "nonRootParentListLookup": 0x8D6C20,
    "nonRootBindTranslationAdd": 0x8D7016,
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_va(pe: PE, data: bytes, va: int, size: int) -> bytes:
    off = pe.va_to_off(va)
    raw = data[off:off + size]
    if len(raw) != size:
        raise ProbeError(f"short read at VA 0x{va:x}: {len(raw)} != {size}")
    return raw


def section_for_off(pe: PE, off: int) -> str | None:
    for sec in pe.sections:
        if sec["rawOff"] <= off < sec["rawOff"] + sec["rawSize"]:
            return sec["name"]
    return None


def fmt(insn, shift: int) -> str:
    retail_va = insn.address - shift
    return (
        f"retail=0x{retail_va:08X} comparison=0x{insn.address:08X}: "
        f"{insn.bytes.hex():<24} {insn.mnemonic:<8} {insn.op_str}"
    ).rstrip()


def helper_for_va(va: int, shifted_ranges: dict[str, dict[str, Any]]) -> str | None:
    for label, row in shifted_ranges.items():
        if row["comparisonStartVa"] <= va < row["comparisonEndVaExclusive"]:
            return label
    return None


def operand_row(insn) -> dict[str, Any]:
    imms: list[int] = []
    mem: list[dict[str, Any]] = []
    for op in insn.operands:
        if op.type == X86_OP_IMM:
            imms.append(int(op.imm))
        elif op.type == X86_OP_MEM:
            m = op.mem
            mem.append({
                "base": insn.reg_name(m.base) if m.base else None,
                "index": insn.reg_name(m.index) if m.index else None,
                "scale": int(m.scale),
                "disp": int(m.disp),
            })
    return {"immediates": imms, "memory": mem}


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
    if len(data) != args.expected_bytes or actual_sha != args.expected_sha256.lower():
        raise ProbeError(
            f"comparison identity mismatch bytes={len(data)} sha256={actual_sha}"
        )
    pe = PE(data)

    anchor_occurrences: dict[str, list[int]] = {}
    shifts: list[int] = []
    for label, hx in ANCHORS.items():
        vas: list[int] = []
        for off in find_all(data, bytes.fromhex(hx)):
            va = pe.off_to_va(off)
            if va is not None:
                vas.append(va)
        anchor_occurrences[label] = vas
        if len(vas) != 1:
            raise ProbeError(f"anchor {label} occurrence count {len(vas)} != 1")
        shifts.append(vas[0] - RETAIL_ANCHOR_VA[label])
    if sorted(set(shifts)) != [EXPECTED_SHIFT]:
        raise ProbeError(f"uniform relocation drift: {[hex(x) for x in shifts]}")

    shifted_ranges: dict[str, dict[str, Any]] = {}
    for label, (retail_start, retail_end, retail_hash) in RETAIL_RANGES.items():
        comparison_start = retail_start + EXPECTED_SHIFT
        size = retail_end - retail_start
        raw = read_va(pe, data, comparison_start, size)
        got = sha256(raw)
        if got != retail_hash:
            raise ProbeError(
                f"shifted whole helper {label} differs: {got} != retail {retail_hash}"
            )
        shifted_ranges[label] = {
            "retailStartVa": retail_start,
            "retailEndVaExclusive": retail_end,
            "comparisonStartVa": comparison_start,
            "comparisonEndVaExclusive": comparison_start + size,
            "bytes": size,
            "retailSha256": retail_hash,
            "comparisonShiftedSha256": got,
            "byteIdenticalToRetailPinnedRange": True,
        }

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    helper_docs: dict[str, Any] = {}
    dis_lines: list[str] = []
    for label, row in shifted_ranges.items():
        raw = read_va(pe, data, row["comparisonStartVa"], row["bytes"])
        insns = list(md.disasm(raw, row["comparisonStartVa"]))
        if not insns:
            raise ProbeError(f"helper {label} disassembled to zero instructions")
        decoded_bytes = sum(i.size for i in insns)
        if decoded_bytes != len(raw):
            raise ProbeError(
                f"helper {label} decode accounting {decoded_bytes} != {len(raw)} bytes"
            )
        branches = []
        calls = []
        operands = []
        for insn in insns:
            ops = operand_row(insn)
            if ops["immediates"] or ops["memory"]:
                operands.append({
                    "retailVa": insn.address - EXPECTED_SHIFT,
                    "comparisonVa": insn.address,
                    "mnemonic": insn.mnemonic,
                    "opStr": insn.op_str,
                    **ops,
                })
            if insn.mnemonic.startswith("j") and insn.operands and insn.operands[0].type == X86_OP_IMM:
                target = int(insn.operands[0].imm)
                branches.append({
                    "retailVa": insn.address - EXPECTED_SHIFT,
                    "comparisonVa": insn.address,
                    "mnemonic": insn.mnemonic,
                    "comparisonTargetVa": target,
                    "retailNormalizedTargetVa": target - EXPECTED_SHIFT,
                    "targetInsideSameHelper": row["comparisonStartVa"] <= target < row["comparisonEndVaExclusive"],
                })
            if insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM:
                target = int(insn.operands[0].imm)
                calls.append({
                    "retailVa": insn.address - EXPECTED_SHIFT,
                    "comparisonVa": insn.address,
                    "comparisonTargetVa": target,
                    "retailNormalizedTargetVa": target - EXPECTED_SHIFT,
                })
        helper_docs[label] = {
            **row,
            "instructionCount": len(insns),
            "decodedBytes": decoded_bytes,
            "directCalls": calls,
            "directBranches": branches,
            "operandAccesses": operands,
        }
        dis_lines.append(
            f"===== RETAIL-AUTHORITATIVE HELPER {label} "
            f"0x{row['retailStartVa']:08X}-0x{row['retailEndVaExclusive']:08X} "
            f"sha256={row['retailSha256']} ====="
        )
        dis_lines.extend(fmt(insn, EXPECTED_SHIFT) for insn in insns)
        dis_lines.append("")

    # Comparison-client locator only: enumerate decoded direct control-flow xrefs
    # into any byte of the three shifted helper ranges.  Do not require any count.
    decoded_xrefs: list[dict[str, Any]] = []
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        for insn in md.disasm(raw, sec["va"]):
            if insn.mnemonic != "call" and not insn.mnemonic.startswith("j"):
                continue
            if not insn.operands or insn.operands[0].type != X86_OP_IMM:
                continue
            target = int(insn.operands[0].imm)
            target_helper = helper_for_va(target, shifted_ranges)
            if target_helper is None:
                continue
            source_helper = helper_for_va(insn.address, shifted_ranges)
            decoded_xrefs.append({
                "sourceVa": insn.address,
                "mnemonic": insn.mnemonic,
                "targetVa": target,
                "targetHelper": target_helper,
                "sourceInsidePinnedHelper": source_helper,
                "externalToPinnedHelpers": source_helper is None,
            })

    # Comparison-only absolute pointer occurrences to helper starts can reveal
    # function tables or indirect dispatch, but are never treated as code xrefs.
    pointer_refs: list[dict[str, Any]] = []
    for label, row in shifted_ranges.items():
        target = row["comparisonStartVa"]
        for off in find_all(data, struct.pack("<I", target)):
            pointer_refs.append({
                "targetHelper": label,
                "targetVa": target,
                "fileOffset": off,
                "sourceVa": pe.off_to_va(off),
                "section": section_for_off(pe, off),
            })

    external_xrefs = [x for x in decoded_xrefs if x["externalToPinnedHelpers"]]
    doc = {
        "format": FORMAT,
        "authority": AUTHORITY,
        "comparisonExecutable": {
            "bytes": len(data),
            "sha256": actual_sha,
            "imageBaseHex": f"0x{pe.image_base:08X}",
        },
        "retailAuthorityReference": {
            "sha256": RETAIL_SHA,
            "manifest": "manifests/xanim/T6_RETAIL_XANIM_ROOT_TRANSLATION_PROOF_V1.json",
        },
        "validatedUniformRelocationDelta": EXPECTED_SHIFT,
        "validatedUniformRelocationDeltaHex": f"0x{EXPECTED_SHIFT:X}",
        "anchorOccurrences": anchor_occurrences,
        "retailAuthoritativeShiftedHelperBodies": helper_docs,
        "comparisonOnlyDecodedControlFlowXrefsIntoHelperBodies": decoded_xrefs,
        "comparisonOnlyAbsolutePointerRefsToHelperStarts": pointer_refs,
        "summary": {
            "allFiveAnchorsUnique": True,
            "allFiveAnchorsUniformlyShifted": True,
            "allThreeWholeHelperBodiesByteIdenticalToRetailPinnedRanges": True,
            "retailAuthoritativeHelperCount": len(helper_docs),
            "decodedControlFlowXrefCount": len(decoded_xrefs),
            "externalDecodedControlFlowXrefCount": len(external_xrefs),
            "absolutePointerRefCount": len(pointer_refs),
            "emptyXrefSetsAreValidNegativeEvidence": True,
            "comparisonOnlyXrefsPromotedToRetailSemantics": False,
        },
        "proofBoundary": (
            "Authority extends only to the three complete helper byte ranges because those exact ranges are "
            "independently SHA-pinned from the exact retail executable and this probe requires byte-for-byte "
            "identity at the uniformly relocated comparison addresses. Disassembly of those identical bytes may "
            "be interpreted as retail helper behavior after normalizing addresses by the validated shift. Every "
            "xref, pointer occurrence, surrounding instruction, caller, dispatch path, and function boundary found "
            "only in the comparison client remains locator evidence and cannot establish retail DObj assembly, "
            "model ordering, duplicate-name precedence, attachment parenting, or missing-channel behavior."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "uniformShift": f"0x{EXPECTED_SHIFT:X}",
        "wholeHelperBodiesExact": True,
        "helperInstructionCounts": {k: v["instructionCount"] for k, v in helper_docs.items()},
        "decodedControlFlowXrefs": len(decoded_xrefs),
        "externalDecodedControlFlowXrefs": len(external_xrefs),
        "absolutePointerRefs": len(pointer_refs),
        "manifestSha256": sha256(payload.encode()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
