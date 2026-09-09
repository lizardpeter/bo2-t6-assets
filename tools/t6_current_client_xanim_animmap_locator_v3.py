#!/usr/bin/env python3
"""Locate T6 XAnim anim-to-DObj mapping by compiler-resistant structure.

v1/v2 searched literal missing-bone sentinel stores (0x7f / 0x9f) and both
returned zero instruction-aligned candidates in the exact current comparison
client.  v3 deliberately removes that brittle premise.

The locator is motivated by independently reviewed Treyarch-family source where
XAnimGetAnimMap probes a 512-entry XModelNameMap {u16 name,u16 index} with
ScriptString & 0x1ff, linearly re-probes with the same mask, writes an animation
bone-index byte, and marks a 160-bit part mask only on a successful match.  It
also looks for the distinctive diagnostic text
"animToModel.boneCount == boneCount" when present.

ALL output remains non-authoritative comparison-client locator evidence.  No
family-source semantic is promoted to T6 retail without exact-retail bytes and
instruction/data-flow proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from bisect import bisect_left, bisect_right
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError, find_all, fmt_insn

FORMAT = "t6-current-client-xanim-animmap-locator-v3"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
MASK = 0x1FF
NEEDLES = {
    "animMapBoneCountAssert": b"animToModel.boneCount == boneCount",
    "xanimSourcePath": b"xanim\\xanim.cpp",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def imm_values(insn) -> list[int]:
    return [int(op.imm) for op in insn.operands if op.type == X86_OP_IMM]


def has_imm(insn, value: int) -> bool:
    return value in imm_values(insn)


def mem_ops(insn):
    return [op for op in insn.operands if op.type == X86_OP_MEM]


def is_cond_jump(insn) -> bool:
    return insn.mnemonic.startswith("j") and insn.mnemonic != "jmp"


def is_backward_jump(insn) -> bool:
    if not insn.mnemonic.startswith("j") or not insn.operands:
        return False
    op = insn.operands[0]
    return op.type == X86_OP_IMM and int(op.imm) < insn.address


def is_and_511(insn) -> bool:
    return insn.mnemonic == "and" and has_imm(insn, MASK)


def feature_row(window, nearby_string_xrefs: list[dict]) -> dict:
    and511 = [i for i in window if is_and_511(i)]
    indexed = [i for i in window if any(int(op.mem.index) != 0 for op in mem_ops(i))]
    scale4 = [i for i in window if any(int(op.mem.scale) == 4 and int(op.mem.index) != 0 for op in mem_ops(i))]
    word_mem = [i for i in window if any(int(op.size) == 2 for op in mem_ops(i))]
    scale4_word = [i for i in window if any(int(op.size) == 2 and int(op.mem.scale) == 4 and int(op.mem.index) != 0 for op in mem_ops(i))]
    indexed_byte_stores = [
        i for i in window
        if i.mnemonic == "mov" and i.operands
        and i.operands[0].type == X86_OP_MEM
        and int(i.operands[0].size) == 1
        and int(i.operands[0].mem.index) != 0
    ]
    cond = [i for i in window if is_cond_jump(i)]
    backward = [i for i in window if is_backward_jump(i)]
    bit_ops = [i for i in window if i.mnemonic in ("bts", "bt", "or", "shl", "shr", "sar")]
    calls = [i for i in window if i.mnemonic == "call"]
    size21 = [i for i in window if has_imm(i, 21)]

    score = 0
    score += min(len(and511), 3) * 12
    score += min(len(scale4_word), 4) * 10
    score += min(len(indexed_byte_stores), 4) * 7
    score += min(len(word_mem), 6) * 3
    score += min(len(scale4), 6) * 3
    score += min(len(indexed), 10)
    score += min(len(cond), 8)
    score += min(len(backward), 4) * 3
    score += min(len(bit_ops), 6) * 2
    score += min(len(size21), 2) * 5
    score += len(nearby_string_xrefs) * 40
    if len(and511) >= 2:
        score += 20

    return {
        "score": score,
        "and511Count": len(and511),
        "scale4WordMemoryCount": len(scale4_word),
        "indexedByteStoreCount": len(indexed_byte_stores),
        "wordMemoryCount": len(word_mem),
        "scale4MemoryCount": len(scale4),
        "indexedMemoryCount": len(indexed),
        "conditionalJumpCount": len(cond),
        "backwardJumpCount": len(backward),
        "bitOpCount": len(bit_ops),
        "immediate21Count": len(size21),
        "callCount": len(calls),
        "nearbyStringXrefs": nearby_string_xrefs,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    ap.add_argument("--radius", type=lambda x: int(x, 0), default=0x1C0)
    args = ap.parse_args()

    data = args.exe.read_bytes()
    actual_sha = sha256(data)
    if len(data) != args.expected_bytes or actual_sha.lower() != args.expected_sha256.lower():
        raise ProbeError(f"comparison client identity mismatch bytes={len(data)} sha256={actual_sha}")

    pe = PE(data)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    all_insns = []
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        all_insns.extend(md.disasm(raw, sec["va"]))
    all_insns.sort(key=lambda i: i.address)
    addrs = [i.address for i in all_insns]

    target_vas: dict[int, list[str]] = {}
    string_rows = []
    for label, needle in NEEDLES.items():
        occs = []
        for off in find_all(data, needle):
            va = pe.off_to_va(off)
            occs.append({"fileOffset": off, "vaHex": None if va is None else f"0x{va:08X}"})
            if va is not None:
                target_vas.setdefault(va, []).append(label)
        string_rows.append({"label": label, "needle": needle.decode("ascii"), "occurrenceCount": len(occs), "occurrences": occs})

    string_xrefs = []
    for insn in all_insns:
        labels = []
        for op in insn.operands:
            if op.type == X86_OP_IMM and int(op.imm) in target_vas:
                labels.extend(target_vas[int(op.imm)])
        if labels:
            string_xrefs.append({"va": insn.address, "vaHex": f"0x{insn.address:08X}", "labels": sorted(set(labels)), "instruction": fmt_insn(insn)})

    seeds = [i for i in all_insns if is_and_511(i)]
    # Cluster nearby mask operations so one hash loop does not create many rows.
    clusters = []
    for seed in seeds:
        if clusters and seed.address - clusters[-1][-1].address <= 0x220:
            clusters[-1].append(seed)
        else:
            clusters.append([seed])

    ranked = []
    dis_lines = []
    for cluster in clusters:
        center = cluster[0].address
        lo = bisect_left(addrs, center - args.radius)
        hi = bisect_right(addrs, cluster[-1].address + args.radius)
        window = all_insns[lo:hi]
        if not window:
            continue
        start_va = window[0].address
        end_va = window[-1].address + window[-1].size
        nearby = [x for x in string_xrefs if start_va <= x["va"] < end_va]
        features = feature_row(window, nearby)
        try:
            off = pe.va_to_off(start_va)
            raw_window = data[off:off + (end_va - start_va)]
            wsha = sha256(raw_window)
        except ProbeError:
            wsha = None
        row = {
            "seedVasHex": [f"0x{i.address:08X}" for i in cluster],
            "seedInstructions": [fmt_insn(i) for i in cluster],
            "windowStartVaHex": f"0x{start_va:08X}",
            "windowEndVaHex": f"0x{end_va:08X}",
            "windowSha256": wsha,
            **features,
        }
        ranked.append((row, window))

    ranked.sort(key=lambda item: (-item[0]["score"], int(item[0]["windowStartVaHex"], 16)))
    rows = []
    for rank, (row, window) in enumerate(ranked, 1):
        row = dict(row)
        row["rank"] = rank
        rows.append(row)
        if rank <= 20:
            dis_lines.append(f"===== rank={rank} score={row['score']} seeds={','.join(row['seedVasHex'])} window_sha256={row['windowSha256']} =====")
            dis_lines.extend(fmt_insn(i) for i in window)
            dis_lines.append("")

    doc = {
        "format": FORMAT,
        "authority": "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY",
        "comparisonExecutable": {"file": args.exe.name, "bytes": len(data), "sha256": actual_sha, "imageBaseHex": f"0x{pe.image_base:08X}"},
        "retailTarget": {"sha256": RETAIL_SHA256, "requiredForSemanticPromotion": True},
        "lineageLocatorPremises": {
            "t6XModelNameMapBytes": 4,
            "t6XModelNameMapFields": ["uint16 name", "uint16 index"],
            "hashMask": MASK,
            "hashTableEntries": 512,
            "animationPartNamespace": 160,
            "familyMissingIndexByte": 159,
            "familyMissingIndexSignedByte": -97,
            "v1Literal0x7fStoreCount": 0,
            "v2Literal0x9fStoreCount": 0,
            "familyDiagnosticNeedle": "animToModel.boneCount == boneCount",
            "semanticPromotionFromFamilySource": False,
        },
        "strings": string_rows,
        "stringXrefCount": len(string_xrefs),
        "stringXrefs": string_xrefs,
        "and511SeedCount": len(seeds),
        "clusterCount": len(rows),
        "candidates": rows,
        "proofBoundary": (
            "This is comparison-client locator evidence only. The 512-entry open-address hash shape and family "
            "0x9f missing-index behavior are locator premises, not T6 retail conclusions. Candidate ranking cannot "
            "authorize skipping j_mms_flip. Exact retail executable bytes, instruction-aligned accounting, and "
            "mapping dataflow are required for semantic promotion."
        ),
    }

    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "stringXrefCount": len(string_xrefs),
        "and511SeedCount": len(seeds),
        "clusterCount": len(rows),
        "topCandidates": rows[:12],
        "manifestSha256": sha256(payload.encode()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
