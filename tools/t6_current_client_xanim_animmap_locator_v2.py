#!/usr/bin/env python3
"""Locate the T6 XAnim anim-to-model map builder using the Treyarch 160-part sentinel.

v1 deliberately tested the older 128-part/IW-family sentinel 0x7f and found zero
instruction-aligned stores in the exact current comparison client.  v2 preserves
that negative and changes exactly one semantic locator premise: BO1-family source
uses the last slot of a 160-part namespace (159 / 0x9f) for an unmapped animation
bone, while BO2 headers independently expose bitarray<160> in XAnim calculation.

This remains NON-AUTHORITATIVE comparison-client locator evidence.  A hit cannot
be promoted to retail behavior until matched/data-flow-proven against the exact
retail executable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from bisect import bisect_left, bisect_right
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError, fmt_insn

FORMAT = "t6-current-client-xanim-animmap-locator-v2"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
SENTINEL = 159


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_sentinel_store(insn) -> bool:
    if insn.mnemonic != "mov" or len(insn.operands) != 2:
        return False
    dst, src = insn.operands
    return dst.type == X86_OP_MEM and src.type == X86_OP_IMM and int(src.imm) == SENTINEL


def mem_scale4(insn) -> bool:
    return any(op.type == X86_OP_MEM and int(op.mem.scale) == 4 for op in insn.operands)


def mem_indexed(insn) -> bool:
    return any(op.type == X86_OP_MEM and int(op.mem.index) != 0 for op in insn.operands)


def word_mem(insn) -> bool:
    return any(op.type == X86_OP_MEM and int(op.size) == 2 for op in insn.operands)


def is_cond_jump(insn) -> bool:
    return insn.mnemonic.startswith("j") and insn.mnemonic != "jmp"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    ap.add_argument("--radius", type=lambda x: int(x, 0), default=0x180)
    args = ap.parse_args()

    data = args.exe.read_bytes()
    actual_sha = sha256(data)
    if len(data) != args.expected_bytes or actual_sha.lower() != args.expected_sha256.lower():
        raise ProbeError(f"comparison client identity mismatch bytes={len(data)} sha256={actual_sha}")

    pe = PE(data)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    insns = []
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        insns.extend(md.disasm(raw, sec["va"]))
    addrs = [i.address for i in insns]
    seeds = [i for i in insns if is_sentinel_store(i)]

    ranked = []
    dis_lines = []
    for seed in seeds:
        lo = bisect_left(addrs, seed.address - args.radius)
        hi = bisect_right(addrs, seed.address + args.radius)
        window = insns[lo:hi]

        indexed_byte_stores = [i for i in window if i.mnemonic == "mov" and i.operands and i.operands[0].type == X86_OP_MEM and int(i.operands[0].size) == 1 and int(i.operands[0].mem.index) != 0]
        scale4 = [i for i in window if mem_scale4(i)]
        movzx_word = [i for i in window if i.mnemonic == "movzx" and word_mem(i)]
        indexed = [i for i in window if mem_indexed(i)]
        cond = [i for i in window if is_cond_jump(i)]
        backward = [i for i in window if i.mnemonic.startswith("j") and i.operands and i.operands[0].type == X86_OP_IMM and int(i.operands[0].imm) < i.address]

        score = 0
        score += 8 if int(seed.operands[0].size) == 1 else 0
        score += 8 if int(seed.operands[0].mem.index) != 0 else 0
        score += min(len(indexed_byte_stores), 4) * 4
        score += min(len(scale4), 5) * 4
        score += min(len(movzx_word), 5) * 4
        score += min(len(indexed), 8)
        score += min(len(cond), 8)
        score += min(len(backward), 4) * 2

        start_va = window[0].address if window else seed.address
        end_va = window[-1].address + window[-1].size if window else seed.address + seed.size
        try:
            off = pe.va_to_off(start_va)
            raw_window = data[off:off + (end_va - start_va)]
            wsha = sha256(raw_window)
        except ProbeError:
            wsha = None

        row = {
            "storeVaHex": f"0x{seed.address:08X}",
            "storeInstruction": fmt_insn(seed),
            "storeOperandSize": int(seed.operands[0].size),
            "storeIndexed": bool(int(seed.operands[0].mem.index) != 0),
            "score": score,
            "windowStartVaHex": f"0x{start_va:08X}",
            "windowEndVaHex": f"0x{end_va:08X}",
            "windowSha256": wsha,
            "features": {
                "indexedByteStores": len(indexed_byte_stores),
                "scale4MemoryOperands": len(scale4),
                "movzxWordLoads": len(movzx_word),
                "indexedMemoryOperands": len(indexed),
                "conditionalJumps": len(cond),
                "backwardJumps": len(backward),
            },
        }
        ranked.append((row, window))

    ranked.sort(key=lambda x: (-x[0]["score"], int(x[0]["storeVaHex"], 16)))
    rows = []
    for rank, (row, window) in enumerate(ranked, 1):
        row = dict(row)
        row["rank"] = rank
        rows.append(row)
        dis_lines.append(f"===== rank={rank} score={row['score']} store={row['storeVaHex']} window_sha256={row['windowSha256']} =====")
        dis_lines.extend(fmt_insn(i) for i in window)
        dis_lines.append("")

    doc = {
        "format": FORMAT,
        "authority": "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY",
        "comparisonExecutable": {"file": args.exe.name, "bytes": len(data), "sha256": actual_sha, "imageBaseHex": f"0x{pe.image_base:08X}"},
        "retailTarget": {"sha256": RETAIL_SHA256, "requiredForSemanticPromotion": True},
        "locatorPremises": {
            "v1Older128PartSentinelStoreCount": 0,
            "t6AnimationPartNamespace": 160,
            "candidateMissingBoneSentinel": SENTINEL,
            "candidateMissingBoneSentinelHex": "0x9F",
            "t6XModelNameMapBytes": 4,
            "t6XModelNameMapFields": ["uint16 name", "uint16 index"],
            "lineageOnlyHypothesis": "BO1-family XAnimGetAnimMap maps absent animation names to the final 160-part slot; this is locator input, not T6 retail authority",
        },
        "seedStoreCount": len(seeds),
        "candidateCount": len(rows),
        "candidates": rows,
        "proofBoundary": (
            "Comparison-client structural locator only. The 159/0x9f hypothesis is intentionally not a retail semantic claim. "
            "Even a unique candidate cannot authorize skipping j_mms_flip until the exact retail executable proves the same "
            "mapping/sentinel dataflow."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")
    print(json.dumps({"seedStoreCount": len(seeds), "candidateCount": len(rows), "topCandidates": rows[:12], "manifestSha256": sha256(payload.encode())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
