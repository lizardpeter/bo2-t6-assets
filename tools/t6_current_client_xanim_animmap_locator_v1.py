#!/usr/bin/env python3
"""Locate the XAnim animation-to-DObj bone-map builder in the pinned current T6 client.

This is deliberately a NON-AUTHORITATIVE comparison-client locator.  The search
is motivated by a distinctive engine-family implementation shape, but no family
source semantics are promoted to T6 retail.  Candidates must contain an
instruction-aligned store of integer 127 and are ranked by nearby x86 structure
compatible with T6's independently known 4-byte XModelNameMap {u16 name,u16
index}: indexed byte stores, scale-4 memory probes, 16-bit loads, and short loop
control flow.

The output is only a bounded target list for later exact-retail matching.
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

FORMAT = "t6-current-client-xanim-animmap-locator-v1"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_imm_127_store(insn) -> bool:
    if insn.mnemonic != "mov" or len(insn.operands) != 2:
        return False
    dst, src = insn.operands
    return dst.type == X86_OP_MEM and src.type == X86_OP_IMM and int(src.imm) == 0x7F


def mem_scale4(insn) -> bool:
    return any(op.type == X86_OP_MEM and int(op.mem.scale) == 4 for op in insn.operands)


def mem_indexed(insn) -> bool:
    return any(op.type == X86_OP_MEM and int(op.mem.index) != 0 for op in insn.operands)


def has_word_mem_operand(insn) -> bool:
    return any(op.type == X86_OP_MEM and int(op.size) == 2 for op in insn.operands)


def is_conditional_jump(insn) -> bool:
    return insn.mnemonic.startswith("j") and insn.mnemonic not in ("jmp",)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    ap.add_argument("--radius", type=lambda x: int(x, 0), default=0x140)
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

    all_insns = []
    section_for_va = []
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        for insn in md.disasm(raw, sec["va"]):
            all_insns.append(insn)
            section_for_va.append(sec["name"])

    addrs = [i.address for i in all_insns]
    stores = [i for i in all_insns if is_imm_127_store(i)]
    candidates = []
    dis_lines = []

    for store in stores:
        lo = bisect_left(addrs, store.address - args.radius)
        hi = bisect_right(addrs, store.address + args.radius)
        window = all_insns[lo:hi]

        indexed_byte_stores = [
            i for i in window
            if i.mnemonic == "mov"
            and i.operands
            and i.operands[0].type == X86_OP_MEM
            and int(i.operands[0].size) == 1
            and int(i.operands[0].mem.index) != 0
        ]
        scale4 = [i for i in window if mem_scale4(i)]
        word_loads = [
            i for i in window
            if i.mnemonic.startswith("mov") and has_word_mem_operand(i)
        ]
        movzx_word = [
            i for i in window
            if i.mnemonic == "movzx" and has_word_mem_operand(i)
        ]
        indexed_mem = [i for i in window if mem_indexed(i)]
        cond_jumps = [i for i in window if is_conditional_jump(i)]
        backward_jumps = []
        for i in window:
            if not i.mnemonic.startswith("j") or not i.operands or i.operands[0].type != X86_OP_IMM:
                continue
            if int(i.operands[0].imm) < i.address:
                backward_jumps.append(i)

        # Structural ranking only.  No score is a semantic promotion.
        score = 0
        score += min(len(indexed_byte_stores), 3) * 3
        score += min(len(scale4), 4) * 3
        score += min(len(movzx_word), 4) * 3
        score += min(len(word_loads), 4)
        score += min(len(indexed_mem), 6)
        score += min(len(cond_jumps), 6)
        score += min(len(backward_jumps), 3) * 2
        if store.operands[0].size == 1:
            score += 5
        if int(store.operands[0].mem.index) != 0:
            score += 5

        start_va = window[0].address if window else store.address
        end_va = (window[-1].address + window[-1].size) if window else store.address + store.size
        try:
            start_off = pe.va_to_off(start_va)
            raw_window = data[start_off:start_off + (end_va - start_va)]
            window_sha = sha256(raw_window)
        except ProbeError:
            raw_window = b""
            window_sha = None

        row = {
            "storeVaHex": f"0x{store.address:08X}",
            "storeInstruction": fmt_insn(store),
            "storeOperandSize": int(store.operands[0].size),
            "storeIndexed": bool(int(store.operands[0].mem.index) != 0),
            "score": score,
            "windowStartVaHex": f"0x{start_va:08X}",
            "windowEndVaHex": f"0x{end_va:08X}",
            "windowSha256": window_sha,
            "features": {
                "indexedByteStores": len(indexed_byte_stores),
                "scale4MemoryOperands": len(scale4),
                "wordMemoryLoads": len(word_loads),
                "movzxWordLoads": len(movzx_word),
                "indexedMemoryOperands": len(indexed_mem),
                "conditionalJumps": len(cond_jumps),
                "backwardJumps": len(backward_jumps),
            },
        }
        candidates.append((row, window))

    candidates.sort(key=lambda item: (-item[0]["score"], int(item[0]["storeVaHex"], 16)))
    rows = []
    for rank, (row, window) in enumerate(candidates, 1):
        row = dict(row)
        row["rank"] = rank
        rows.append(row)
        dis_lines.append(
            f"===== rank={rank} score={row['score']} store={row['storeVaHex']} "
            f"window_sha256={row['windowSha256']} ====="
        )
        dis_lines.extend(fmt_insn(i) for i in window)
        dis_lines.append("")

    doc = {
        "format": FORMAT,
        "authority": "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY",
        "comparisonExecutable": {
            "file": args.exe.name,
            "bytes": len(data),
            "sha256": actual_sha,
            "imageBaseHex": f"0x{pe.image_base:08X}",
        },
        "retailTarget": {
            "sha256": RETAIL_SHA256,
            "requiredForSemanticPromotion": True,
        },
        "locatorPremises": {
            "t6XModelNameMapBytes": 4,
            "t6XModelNameMapFields": ["uint16 name", "uint16 index"],
            "candidateSeed": "instruction-aligned memory store of integer 127",
            "rankingOnly": [
                "indexed byte stores",
                "scale-4 memory probes compatible with 4-byte XModelNameMap",
                "16-bit memory loads compatible with ScriptString/index fields",
                "indexed memory accesses",
                "conditional/backward loop control flow",
            ],
        },
        "seedStoreCount": len(stores),
        "candidateCount": len(rows),
        "candidates": rows,
        "proofBoundary": (
            "This file contains comparison-client locator evidence only. The integer-127 seed and ranking "
            "shape are motivated by independently observed engine-family source and the T6 XModelNameMap "
            "layout, but they do not prove that T6 retail uses 127 for missing animation bones, do not prove "
            "XAnimGetAnimMap semantics, and do not authorize dropping j_mms_flip. Semantic promotion requires "
            "instruction-aligned matching/dataflow from the exact retail executable SHA-256 " + RETAIL_SHA256 + "."
        ),
    }

    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "seedStoreCount": len(stores),
        "candidateCount": len(rows),
        "topCandidates": rows[:10],
        "manifestSha256": sha256(payload.encode()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
