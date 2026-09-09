#!/usr/bin/env python3
"""Strict structural locator for the T6 XAnim model-map / anim-map pair.

This pass corrects the weak locator premises used by v1-v5.  It does not search
for a missing-bone sentinel in isolation and it does not treat a string-intern
call shape as the semantic target.  Instead it uses a conjunction motivated by
public Treyarch-family implementation structure and independently known T6
layout facts:

  * XModelNameMap is a 4-byte {u16 name, u16 index} entry;
  * a 512-entry candidate map therefore occupies 0x800 bytes;
  * model/animation part space is 160 entries;
  * the family implementation hashes ScriptStrings with 0x1ff and linearly
    re-probes the 4-byte entries.

The family implementation is locator input only.  Every result from the current
comparison client remains NON-AUTHORITATIVE.  Retail semantic promotion still
requires instruction-aligned proof from the exact retail executable SHA-256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from bisect import bisect_left, bisect_right
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError, fmt_insn

FORMAT = "t6-current-client-xanim-modelmap-pair-locator-v6"
AUTHORITY = "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
MAP_BYTES = 0x800
HASH_MASK = 0x1FF
PART_LIMIT = 0xA0
ANIMMAP_HEADER_BYTES = 21


class LocatorError(RuntimeError):
    pass


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise LocatorError(msg)


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


def is_direct_call(insn) -> bool:
    return insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM


def direct_target(insn) -> int | None:
    return int(insn.operands[0].imm) if is_direct_call(insn) else None


def stack_sub_bytes(insn) -> int | None:
    if insn.mnemonic != "sub" or len(insn.operands) != 2:
        return None
    dst, src = insn.operands
    if dst.type != X86_OP_REG or src.type != X86_OP_IMM:
        return None
    if insn.reg_name(dst.reg) != "esp":
        return None
    n = int(src.imm)
    return n if 0 < n < 0x10000 else None


def window_by_va(insns, addrs, center_start: int, center_end: int, radius: int):
    lo = bisect_left(addrs, center_start - radius)
    hi = bisect_right(addrs, center_end + radius)
    return insns[lo:hi]


def window_sha(pe: PE, data: bytes, start: int, end: int) -> str | None:
    try:
        off = pe.va_to_off(start)
        return sha256(data[off:off + (end - start)])
    except ProbeError:
        return None


def features(window) -> dict:
    mask = [i for i in window if has_imm(i, HASH_MASK)]
    limit = [i for i in window if has_imm(i, PART_LIMIT)]
    map_bytes = [i for i in window if has_imm(i, MAP_BYTES)]
    header21 = [i for i in window if has_imm(i, ANIMMAP_HEADER_BYTES)]
    word_mem = [i for i in window if any(int(op.size) == 2 for op in mem_ops(i))]
    indexed_word = [i for i in window if any(int(op.size) == 2 and int(op.mem.index) != 0 for op in mem_ops(i))]
    scale4 = [i for i in window if any(int(op.mem.scale) == 4 and int(op.mem.index) != 0 for op in mem_ops(i))]
    scale4_word = [i for i in window if any(int(op.size) == 2 and int(op.mem.scale) == 4 and int(op.mem.index) != 0 for op in mem_ops(i))]
    byte_stores = [
        i for i in window
        if i.mnemonic == "mov" and i.operands and i.operands[0].type == X86_OP_MEM
        and int(i.operands[0].size) == 1
    ]
    indexed_byte_stores = [i for i in byte_stores if int(i.operands[0].mem.index) != 0]
    cond = [i for i in window if is_cond_jump(i)]
    backward = [i for i in window if is_backward_jump(i)]
    bit_ops = [i for i in window if i.mnemonic in ("bt", "bts", "btr", "or", "shl", "shr", "sar")]
    calls = [i for i in window if is_direct_call(i)]
    stack_subs = [stack_sub_bytes(i) for i in window]
    stack_subs = [n for n in stack_subs if n is not None]
    return {
        "mapBytesImmediateCount": len(map_bytes),
        "hashMaskImmediateCount": len(mask),
        "partLimitImmediateCount": len(limit),
        "header21ImmediateCount": len(header21),
        "wordMemoryCount": len(word_mem),
        "indexedWordMemoryCount": len(indexed_word),
        "scale4MemoryCount": len(scale4),
        "scale4WordMemoryCount": len(scale4_word),
        "byteStoreCount": len(byte_stores),
        "indexedByteStoreCount": len(indexed_byte_stores),
        "conditionalJumpCount": len(cond),
        "backwardJumpCount": len(backward),
        "bitOpCount": len(bit_ops),
        "directCallTargetsHex": [f"0x{direct_target(i):08X}" for i in calls],
        "stackSubBytes": stack_subs,
    }


def modelmap_score(f: dict) -> int:
    score = 0
    score += min(f["mapBytesImmediateCount"], 2) * 35
    score += min(f["hashMaskImmediateCount"], 3) * 45
    score += min(f["partLimitImmediateCount"], 2) * 25
    score += min(f["scale4WordMemoryCount"], 4) * 18
    score += min(f["indexedWordMemoryCount"], 6) * 8
    score += min(f["scale4MemoryCount"], 6) * 5
    score += min(f["backwardJumpCount"], 4) * 6
    score += min(f["conditionalJumpCount"], 8) * 2
    return score


def strict_modelmap_shape(f: dict) -> bool:
    return (
        f["mapBytesImmediateCount"] >= 1
        and f["hashMaskImmediateCount"] >= 1
        and f["partLimitImmediateCount"] >= 1
        and f["indexedWordMemoryCount"] >= 1
        and f["scale4MemoryCount"] >= 1
        and f["backwardJumpCount"] >= 1
    )


def animmap_score(f: dict) -> int:
    score = 0
    score += min(f["hashMaskImmediateCount"], 3) * 45
    score += min(f["header21ImmediateCount"], 2) * 30
    score += min(f["indexedWordMemoryCount"], 6) * 8
    score += min(f["scale4MemoryCount"], 6) * 6
    score += min(f["indexedByteStoreCount"], 5) * 12
    score += min(f["bitOpCount"], 6) * 5
    score += min(f["backwardJumpCount"], 4) * 6
    if any(0xA0 <= n <= 0x180 for n in f["stackSubBytes"]):
        score += 25
    return score


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    ap.add_argument("--model-radius", type=lambda x: int(x, 0), default=0x500)
    ap.add_argument("--neighbor-radius", type=lambda x: int(x, 0), default=0x3000)
    args = ap.parse_args()

    data = args.exe.read_bytes()
    actual_sha = sha256(data)
    require(len(data) == args.expected_bytes, f"comparison bytes changed: {len(data)}")
    require(actual_sha.lower() == args.expected_sha256.lower(), f"comparison SHA changed: {actual_sha}")

    pe = PE(data)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    insns = []
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        insns.extend(md.disasm(raw, sec["va"]))
    insns.sort(key=lambda x: x.address)
    addrs = [i.address for i in insns]

    map_seeds = [i for i in insns if has_imm(i, MAP_BYTES)]
    # Cluster nearby 0x800 immediates to avoid duplicate rows from one function.
    clusters = []
    for seed in map_seeds:
        if clusters and seed.address - clusters[-1][-1].address <= 0x300:
            clusters[-1].append(seed)
        else:
            clusters.append([seed])

    model_rows_with_windows = []
    for cluster in clusters:
        window = window_by_va(insns, addrs, cluster[0].address, cluster[-1].address, args.model_radius)
        if not window:
            continue
        f = features(window)
        start = window[0].address
        end = window[-1].address + window[-1].size
        row = {
            "seedVasHex": [f"0x{x.address:08X}" for x in cluster],
            "seedInstructions": [fmt_insn(x) for x in cluster],
            "windowStartVaHex": f"0x{start:08X}",
            "windowEndVaHex": f"0x{end:08X}",
            "windowSha256": window_sha(pe, data, start, end),
            "score": modelmap_score(f),
            "strictModelMapShape": strict_modelmap_shape(f),
            "features": f,
        }
        model_rows_with_windows.append((row, window))

    model_rows_with_windows.sort(key=lambda x: (-x[0]["strictModelMapShape"], -x[0]["score"], int(x[0]["windowStartVaHex"], 16)))
    model_rows = []
    dis_lines = []
    for rank, (row, window) in enumerate(model_rows_with_windows, 1):
        row = dict(row)
        row["rank"] = rank
        model_rows.append(row)
        if rank <= 30:
            dis_lines.append(f"===== model-map rank={rank} strict={row['strictModelMapShape']} score={row['score']} seeds={','.join(row['seedVasHex'])} =====")
            dis_lines.extend(fmt_insn(x) for x in window)
            dis_lines.append("")

    strict_models = [r for r in model_rows if r["strictModelMapShape"]]

    # Search only around strict model-map candidates for a second 0x1ff-bearing
    # hash/probe region compatible with anim-to-model construction.
    anim_candidates = []
    seen_centers = set()
    for model in strict_models:
        mstart = int(model["windowStartVaHex"], 16)
        mend = int(model["windowEndVaHex"], 16)
        nlo = bisect_left(addrs, mstart - args.neighbor_radius)
        nhi = bisect_right(addrs, mend + args.neighbor_radius)
        nearby = insns[nlo:nhi]
        mask_seeds = [i for i in nearby if has_imm(i, HASH_MASK)]
        mask_clusters = []
        for seed in mask_seeds:
            if mask_clusters and seed.address - mask_clusters[-1][-1].address <= 0x280:
                mask_clusters[-1].append(seed)
            else:
                mask_clusters.append([seed])
        for cluster in mask_clusters:
            center = cluster[0].address
            if center in seen_centers:
                continue
            seen_centers.add(center)
            window = window_by_va(insns, addrs, cluster[0].address, cluster[-1].address, 0x380)
            if not window:
                continue
            start = window[0].address
            end = window[-1].address + window[-1].size
            # Keep the model-map region itself as an explicit control but do not
            # rank it as an anim-map candidate.
            overlaps_model = not (end <= mstart or start >= mend)
            f = features(window)
            row = {
                "seedVasHex": [f"0x{x.address:08X}" for x in cluster],
                "windowStartVaHex": f"0x{start:08X}",
                "windowEndVaHex": f"0x{end:08X}",
                "windowSha256": window_sha(pe, data, start, end),
                "nearestStrictModelMapRank": model["rank"],
                "overlapsStrictModelMapWindow": overlaps_model,
                "score": animmap_score(f),
                "features": f,
            }
            if not overlaps_model:
                anim_candidates.append((row, window))

    anim_candidates.sort(key=lambda x: (-x[0]["score"], int(x[0]["windowStartVaHex"], 16)))
    anim_rows = []
    for rank, (row, window) in enumerate(anim_candidates, 1):
        row = dict(row)
        row["rank"] = rank
        anim_rows.append(row)
        if rank <= 30:
            dis_lines.append(f"===== anim-map-neighbor rank={rank} score={row['score']} modelRank={row['nearestStrictModelMapRank']} =====")
            dis_lines.extend(fmt_insn(x) for x in window)
            dis_lines.append("")

    doc = {
        "format": FORMAT,
        "authority": AUTHORITY,
        "comparisonExecutable": {
            "file": args.exe.name,
            "bytes": len(data),
            "sha256": actual_sha,
            "imageBaseHex": f"0x{pe.image_base:08X}",
        },
        "retailTarget": {"sha256": RETAIL_SHA256, "requiredForSemanticPromotion": True},
        "locatorPremises": {
            "independentlyKnownT6XModelNameMapEntryBytes": 4,
            "independentlyKnownT6XModelNameMapFields": ["uint16 name", "uint16 index"],
            "familyCandidateHashEntries": 512,
            "familyCandidateMapBytes": MAP_BYTES,
            "familyCandidateHashMask": HASH_MASK,
            "t6AnimationPartNamespace": PART_LIMIT,
            "familyCandidateAnimMapHeaderBytes": ANIMMAP_HEADER_BYTES,
            "familySourceSemanticsPromoted": False,
        },
        "priorNegativeControls": {
            "literal0x7fMissingStoreCandidates": 0,
            "literal0x9fMissingStoreCandidates": 0,
            "genericAnd0x1ffV3RegionsClassifiedAsUnrelated": True,
            "v5StrictFourArgStringInternCandidates": 0,
        },
        "mapBytesSeedCount": len(map_seeds),
        "modelMapCandidateCount": len(model_rows),
        "strictModelMapCandidateCount": len(strict_models),
        "modelMapCandidates": model_rows,
        "animMapNeighborCandidateCount": len(anim_rows),
        "animMapNeighborCandidates": anim_rows,
        "proofBoundary": (
            "Current-client structural locator only. The conjunction of 0x800 table size, 0x1ff probing, 160-part "
            "limit, 4-byte XModelNameMap access shape, and neighboring anim-map-like structure may locate the relevant "
            "functions but proves no retail semantics. It does not authorize a missing-bone sentinel, dropping "
            "j_mms_flip, duplicate ScriptString precedence, model order, or modelParent assignment. Every semantic "
            "promotion still requires exact-retail executable bytes with complete instruction/data-flow accounting."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "mapBytesSeedCount": len(map_seeds),
        "strictModelMapCandidateCount": len(strict_models),
        "topStrictModelMapCandidates": strict_models[:10],
        "animMapNeighborCandidateCount": len(anim_rows),
        "topAnimMapNeighborCandidates": anim_rows[:10],
        "manifestSha256": sha256(payload.encode()),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
