#!/usr/bin/env python3
"""Triangulate the T6 XAnim animation-map path without sentinel literals.

Earlier locators established useful negatives in the exact current comparison
client:
  * no instruction-aligned memory store of 0x7f;
  * no instruction-aligned memory store of 0x9f;
  * generic `and reg,0x1ff` hits belong to an unrelated interpreter region.

v4 instead uses three independent, compiler-tolerant locator families:
  A) candidate calls shaped like T6 SL_GetStringOfSize(str,user,len,type), with
     type 11 and a variable length formed with a lineage header increment of 21
     (17 is retained as a lower-confidence lineage control);
  B) large stack workspaces compatible with a local XModelNameMap table; and
  C) byte-offset masks compatible with 4-byte hash entries (0x3fc/0x7fc/etc.).

All output is NON-AUTHORITATIVE comparison-client locator evidence only.  No
candidate, score, family-source behavior, or current-client address is a T6
retail semantic claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError, fmt_insn

FORMAT = "t6-current-client-xanim-animmap-locator-v4"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
MAP_TYPE = 11
HEADER_T6_LINEAGE = 21
HEADER_OLDER_CONTROL = 17
HASH_BYTE_MASKS = {0x3FC, 0x7FC, 0xFFC, 0x1FFC}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def imm_ops(insn):
    return [int(op.imm) for op in insn.operands if op.type == X86_OP_IMM]


def mem_ops(insn):
    return [op for op in insn.operands if op.type == X86_OP_MEM]


def has_const(insn, value: int) -> bool:
    if value in imm_ops(insn):
        return True
    return any(abs(int(op.mem.disp)) == value for op in mem_ops(insn))


def is_direct_call(insn) -> bool:
    return insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM


def direct_target(insn) -> int | None:
    return int(insn.operands[0].imm) if is_direct_call(insn) else None


def is_stack_sub(insn) -> int | None:
    if insn.mnemonic != "sub" or len(insn.operands) != 2:
        return None
    dst, src = insn.operands
    if dst.type != X86_OP_REG or src.type != X86_OP_IMM:
        return None
    # Capstone register name avoids hard-coding enum values.
    if insn.reg_name(dst.reg) != "esp":
        return None
    n = int(src.imm)
    return n if 0 < n < 0x10000 else None


def is_push_imm(insn, value: int) -> bool:
    return insn.mnemonic == "push" and len(insn.operands) == 1 and insn.operands[0].type == X86_OP_IMM and int(insn.operands[0].imm) == value


def is_zero_arg_materialization(insn) -> bool:
    # Common cdecl argument preparation forms for user=0.
    if is_push_imm(insn, 0):
        return True
    if insn.mnemonic == "xor" and len(insn.operands) == 2:
        a, b = insn.operands
        return a.type == X86_OP_REG and b.type == X86_OP_REG and a.reg == b.reg
    return False


def window_sha(pe: PE, data: bytes, start: int, end: int) -> str | None:
    try:
        off = pe.va_to_off(start)
        return sha256(data[off:off + (end - start)])
    except ProbeError:
        return None


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
    insns.sort(key=lambda x: x.address)
    index_by_va = {i.address: n for n, i in enumerate(insns)}

    # A) Call-site triangulation.  We intentionally rank rather than assert a
    # precise compiler sequence.  A high-confidence row needs type=11 and a
    # length-header materialization in the immediately preceding instructions.
    intern_rows = []
    call_target_counts = Counter(direct_target(i) for i in insns if is_direct_call(i))
    call_target_sites = defaultdict(list)
    for i in insns:
        if is_direct_call(i):
            call_target_sites[direct_target(i)].append(i.address)

    for n, insn in enumerate(insns):
        if not is_direct_call(insn):
            continue
        prior = insns[max(0, n - 18):n]
        type_push = any(is_push_imm(x, MAP_TYPE) for x in prior[-10:])
        type_const = any(has_const(x, MAP_TYPE) for x in prior[-12:])
        plus21 = [x for x in prior if has_const(x, HEADER_T6_LINEAGE)]
        plus17 = [x for x in prior if has_const(x, HEADER_OLDER_CONTROL)]
        zeroish = any(is_zero_arg_materialization(x) for x in prior[-12:])
        stack_addr = [x for x in prior[-12:] if x.mnemonic == "lea" and any(x.reg_name(op.mem.base) in ("esp", "ebp") for op in mem_ops(x))]
        pushes = [x for x in prior[-12:] if x.mnemonic == "push"]
        score = 0
        score += 30 if type_push else (8 if type_const else 0)
        score += 35 if plus21 else 0
        score += 12 if plus17 else 0
        score += 8 if zeroish else 0
        score += min(len(stack_addr), 2) * 8
        score += 8 if len(pushes) >= 3 else 0
        if score < 35:
            continue
        target = direct_target(insn)
        start = prior[0].address if prior else insn.address
        end = insn.address + insn.size
        intern_rows.append({
            "callVaHex": f"0x{insn.address:08X}",
            "targetVaHex": f"0x{target:08X}",
            "targetDirectCallsiteCount": call_target_counts[target],
            "score": score,
            "type11PushNearby": type_push,
            "type11ConstantNearby": type_const,
            "plus21Nearby": bool(plus21),
            "plus17Nearby": bool(plus17),
            "zeroUserCandidateNearby": zeroish,
            "stackAddressLeaCount": len(stack_addr),
            "pushCountLast12": len(pushes),
            "windowStartVaHex": f"0x{start:08X}",
            "windowEndVaHex": f"0x{end:08X}",
            "windowSha256": window_sha(pe, data, start, end),
            "instructions": [fmt_insn(x) for x in prior[-12:]] + [fmt_insn(insn)],
        })
    intern_rows.sort(key=lambda r: (-r["score"], int(r["callVaHex"], 16)))

    # B) Large local workspaces.  Use broad bounds because T6's exact model-map
    # table size is not promoted from BO1/COD4 lineage.
    stack_rows = []
    for n, insn in enumerate(insns):
        amount = is_stack_sub(insn)
        if amount is None or not (0x300 <= amount <= 0xA00):
            continue
        window = insns[n:min(len(insns), n + 90)]
        direct_calls = [x for x in window if is_direct_call(x)]
        stack_leas = [x for x in window if x.mnemonic == "lea" and any(x.reg_name(op.mem.base) in ("esp", "ebp") for op in mem_ops(x))]
        scale4_word = [x for x in window if any(int(op.size) == 2 and int(op.mem.scale) == 4 and int(op.mem.index) != 0 for op in mem_ops(x))]
        score = 0
        score += 18 if amount in (0x400, 0x800) else 8
        score += min(len(direct_calls), 6) * 3
        score += min(len(stack_leas), 6) * 3
        score += min(len(scale4_word), 4) * 8
        start = insn.address
        end = window[-1].address + window[-1].size if window else insn.address + insn.size
        stack_rows.append({
            "subVaHex": f"0x{insn.address:08X}",
            "stackBytesHex": f"0x{amount:X}",
            "stackBytes": amount,
            "score": score,
            "directCallTargetsHex": [f"0x{direct_target(x):08X}" for x in direct_calls],
            "stackAddressLeaCount": len(stack_leas),
            "scale4WordMemoryCount": len(scale4_word),
            "windowEndVaHex": f"0x{end:08X}",
            "windowSha256": window_sha(pe, data, start, end),
        })
    stack_rows.sort(key=lambda r: (-r["score"], int(r["subVaHex"], 16)))

    # C) 4-byte-entry byte-offset masks, a compiler alternative to index masking.
    mask_rows = []
    for n, insn in enumerate(insns):
        values = set(imm_ops(insn)) & HASH_BYTE_MASKS
        if not values:
            continue
        window = insns[max(0, n - 25):min(len(insns), n + 35)]
        scale4_word = [x for x in window if any(int(op.size) == 2 and int(op.mem.scale) == 4 and int(op.mem.index) != 0 for op in mem_ops(x))]
        word_indexed = [x for x in window if any(int(op.size) == 2 and int(op.mem.index) != 0 for op in mem_ops(x))]
        byte_stores = [x for x in window if x.mnemonic == "mov" and x.operands and x.operands[0].type == X86_OP_MEM and int(x.operands[0].size) == 1]
        calls = [x for x in window if is_direct_call(x)]
        score = 20 + min(len(scale4_word), 4) * 12 + min(len(word_indexed), 6) * 5 + min(len(byte_stores), 4) * 4
        start = window[0].address
        end = window[-1].address + window[-1].size
        mask_rows.append({
            "seedVaHex": f"0x{insn.address:08X}",
            "seedInstruction": fmt_insn(insn),
            "maskValuesHex": [f"0x{x:X}" for x in sorted(values)],
            "score": score,
            "scale4WordMemoryCount": len(scale4_word),
            "indexedWordMemoryCount": len(word_indexed),
            "byteStoreCount": len(byte_stores),
            "directCallTargetsHex": [f"0x{direct_target(x):08X}" for x in calls],
            "windowStartVaHex": f"0x{start:08X}",
            "windowEndVaHex": f"0x{end:08X}",
            "windowSha256": window_sha(pe, data, start, end),
        })
    mask_rows.sort(key=lambda r: (-r["score"], int(r["seedVaHex"], 16)))

    # Cross-reference call targets from intern-like sites against workspace/mask
    # windows.  This is locator metadata only.
    intern_targets = {r["targetVaHex"] for r in intern_rows}
    stack_call_hits = []
    for r in stack_rows:
        hits = sorted(set(r["directCallTargetsHex"]) & intern_targets)
        if hits:
            stack_call_hits.append({"subVaHex": r["subVaHex"], "targetsHex": hits})

    dis_lines = []
    for title, rows, key in (
        ("intern", intern_rows[:30], "callVaHex"),
        ("workspace", stack_rows[:30], "subVaHex"),
        ("hash-byte-mask", mask_rows[:30], "seedVaHex"),
    ):
        for rank, row in enumerate(rows, 1):
            va = int(row[key], 16)
            n = index_by_va.get(va)
            if n is None:
                continue
            w = insns[max(0, n - 35):min(len(insns), n + 80)]
            dis_lines.append(f"===== {title} rank={rank} score={row['score']} seed={row[key]} =====")
            dis_lines.extend(fmt_insn(x) for x in w)
            dis_lines.append("")

    doc = {
        "format": FORMAT,
        "authority": "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY",
        "comparisonExecutable": {"file": args.exe.name, "bytes": len(data), "sha256": actual_sha, "imageBaseHex": f"0x{pe.image_base:08X}"},
        "retailTarget": {"sha256": RETAIL_SHA256, "requiredForSemanticPromotion": True},
        "priorNegativeControls": {
            "literal0x7fStoreCandidates": 0,
            "literal0x9fStoreCandidates": 0,
            "and0x1ffV3RegionsClassifiedAsUnrelatedInterpreter": True,
        },
        "locatorPremises": {
            "t6SLGetStringOfSizeSignature": ["str", "user", "len", "type"],
            "modelPartMapTypeCandidate": MAP_TYPE,
            "t6LineageMapHeaderBytesCandidate": HEADER_T6_LINEAGE,
            "olderLineageHeaderBytesControl": HEADER_OLDER_CONTROL,
            "xmodelNameMapEntryBytes": 4,
            "xmodelNameMapFields": ["uint16 name", "uint16 index"],
            "largeWorkspacePromotedAsExactT6Size": False,
            "familyMissingBoneBehaviorPromoted": False,
        },
        "internCandidateCount": len(intern_rows),
        "internCandidates": intern_rows,
        "workspaceCandidateCount": len(stack_rows),
        "workspaceCandidates": stack_rows,
        "hashByteMaskCandidateCount": len(mask_rows),
        "hashByteMaskCandidates": mask_rows,
        "workspaceCallsInternCandidateTarget": stack_call_hits,
        "proofBoundary": (
            "Comparison-client locator only. These candidates are ranked from public T6 type/signature facts plus "
            "engine-lineage control-flow shapes. No current-client address, stack size, header size, hash mask, or "
            "missing-bone behavior is promoted to the pinned retail executable. Semantic closure requires exact "
            "retail bytes with complete instruction/data-flow accounting."
        ),
    }

    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "internCandidateCount": len(intern_rows),
        "topInternCandidates": intern_rows[:12],
        "workspaceCandidateCount": len(stack_rows),
        "topWorkspaceCandidates": stack_rows[:12],
        "hashByteMaskCandidateCount": len(mask_rows),
        "topHashByteMaskCandidates": mask_rows[:12],
        "workspaceCallsInternCandidateTarget": stack_call_hits[:20],
        "manifestSha256": sha256(payload.encode()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
