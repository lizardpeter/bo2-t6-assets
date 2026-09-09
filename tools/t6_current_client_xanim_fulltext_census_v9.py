#!/usr/bin/env python3
"""Complete executable-section XAnim locator census for the pinned current T6 client.

Earlier v3-v7 locators used Capstone's default section-wide linear disassembly.
The v8 target audit proved that this is incomplete: a valid direct target at
0x00654520 lies in executable .text but is not reached by the default sweep,
because decoding stops at an earlier undecodable byte and never resumes.

v9 repairs only that tooling defect.  It uses Capstone skip-data mode to account
for every raw byte in every IMAGE_SCN_MEM_EXECUTE section, then reruns the
strongest public-lineage locator signatures:
  * 0x1ff ScriptString hash-mask candidates;
  * 0x800-byte 512 x 4-byte XModelNameMap candidates;
  * 0x9f (159) byte-store candidates, including a bounded register-materialized
    form;
  * nearby 160-part, +21-header, 16-bit-name, scale-4-entry, loop and bit-op
    features.

This is still NON-AUTHORITATIVE current-client locator evidence.  Skip-data can
walk embedded data that happens to decode as x86, so candidate promotion requires
both structural corroboration and ultimately exact-retail bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from bisect import bisect_left, bisect_right
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

from t6_current_client_dobj_diff_probe_v1 import PE, fmt_insn

FORMAT = "t6-current-client-xanim-fulltext-census-v9"
AUTHORITY = "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
HASH_MASK = 0x1FF
MAP_BYTES = 0x800
PART_LIMIT = 0xA0
MISSING_SENTINEL = 0x9F
HEADER_BYTES = 21


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise RuntimeError(msg)


def is_real(insn) -> bool:
    return getattr(insn, "id", 0) != 0 and insn.mnemonic != ".byte"


def imm_values(insn):
    if not is_real(insn):
        return []
    return [int(op.imm) for op in insn.operands if op.type == X86_OP_IMM]


def mem_ops(insn):
    if not is_real(insn):
        return []
    return [op for op in insn.operands if op.type == X86_OP_MEM]


def has_imm(insn, value: int) -> bool:
    return any((x & 0xFFFFFFFF) == value for x in imm_values(insn))


def is_direct_branch(insn) -> bool:
    return is_real(insn) and (insn.mnemonic == "call" or insn.mnemonic.startswith("j")) and insn.operands and insn.operands[0].type == X86_OP_IMM


def is_backward_jump(insn) -> bool:
    return is_real(insn) and insn.mnemonic.startswith("j") and insn.operands and insn.operands[0].type == X86_OP_IMM and int(insn.operands[0].imm) < insn.address


def byte_store_imm9f(insn) -> bool:
    if not is_real(insn) or insn.mnemonic != "mov" or len(insn.operands) != 2:
        return False
    dst, src = insn.operands
    return dst.type == X86_OP_MEM and int(dst.size) == 1 and src.type == X86_OP_IMM and (int(src.imm) & 0xFF) == MISSING_SENTINEL


def reg_load_9f(insn) -> int | None:
    if not is_real(insn) or insn.mnemonic != "mov" or len(insn.operands) != 2:
        return None
    dst, src = insn.operands
    if dst.type == X86_OP_REG and src.type == X86_OP_IMM and (int(src.imm) & 0xFF) == MISSING_SENTINEL:
        return int(dst.reg)
    return None


def byte_store_from_reg(insn, reg: int) -> bool:
    if not is_real(insn) or insn.mnemonic != "mov" or len(insn.operands) != 2:
        return False
    dst, src = insn.operands
    return dst.type == X86_OP_MEM and int(dst.size) == 1 and src.type == X86_OP_REG and int(src.reg) == reg


def overwritten_reg(insn, reg: int) -> bool:
    if not is_real(insn) or not insn.operands:
        return False
    dst = insn.operands[0]
    return dst.type == X86_OP_REG and int(dst.reg) == reg and insn.mnemonic not in ("cmp", "test")


def full_exec_disasm(data: bytes, pe: PE):
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    real = []
    coverage = []
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        rows = list(md.disasm(raw, sec["va"]))
        real_rows = [x for x in rows if is_real(x)]
        skipped = [x for x in rows if not is_real(x)]
        accounted = sum(int(x.size) for x in rows)
        coverage.append({
            "name": sec["name"],
            "startVaHex": f"0x{sec['va']:08X}",
            "rawBytes": sec["rawSize"],
            "accountedBytes": accounted,
            "rawFullyAccounted": accounted == sec["rawSize"],
            "realInstructionCount": len(real_rows),
            "skipDataPseudoInstructionCount": len(skipped),
            "lastDecodedEndVaHex": f"0x{(rows[-1].address + rows[-1].size) if rows else sec['va']:08X}",
        })
        real.extend(real_rows)
    real.sort(key=lambda x: x.address)
    return md, real, coverage


def old_linear_coverage(data: bytes, pe: PE):
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    out = []
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        rows = list(md.disasm(raw, sec["va"]))
        accounted = sum(int(x.size) for x in rows)
        out.append({
            "name": sec["name"],
            "rawBytes": sec["rawSize"],
            "oldLinearAccountedBytes": accounted,
            "oldLinearCoverageFraction": accounted / sec["rawSize"] if sec["rawSize"] else 1.0,
            "oldLinearLastDecodedEndVaHex": f"0x{(rows[-1].address + rows[-1].size) if rows else sec['va']:08X}",
        })
    return out


def feature_row(window):
    word_mem = [x for x in window if any(int(op.size) == 2 for op in mem_ops(x))]
    indexed_word = [x for x in window if any(int(op.size) == 2 and int(op.mem.index) != 0 for op in mem_ops(x))]
    scale4 = [x for x in window if any(int(op.mem.scale) == 4 and int(op.mem.index) != 0 for op in mem_ops(x))]
    scale4_word = [x for x in window if any(int(op.size) == 2 and int(op.mem.scale) == 4 and int(op.mem.index) != 0 for op in mem_ops(x))]
    byte_stores = [x for x in window if is_real(x) and x.mnemonic == "mov" and x.operands and x.operands[0].type == X86_OP_MEM and int(x.operands[0].size) == 1]
    bitops = [x for x in window if x.mnemonic in ("or", "and", "shl", "shr", "sar", "bt", "bts", "btr")]
    return {
        "hashMaskCount": sum(has_imm(x, HASH_MASK) for x in window),
        "mapBytesCount": sum(has_imm(x, MAP_BYTES) for x in window),
        "partLimitCount": sum(has_imm(x, PART_LIMIT) for x in window),
        "header21Count": sum(has_imm(x, HEADER_BYTES) for x in window),
        "wordMemoryCount": len(word_mem),
        "indexedWordMemoryCount": len(indexed_word),
        "scale4MemoryCount": len(scale4),
        "scale4WordMemoryCount": len(scale4_word),
        "byteStoreCount": len(byte_stores),
        "backwardJumpCount": sum(is_backward_jump(x) for x in window),
        "bitOpCount": len(bitops),
        "directBranchCount": sum(is_direct_branch(x) for x in window),
    }


def score(f):
    return (
        55 * min(f["hashMaskCount"], 2)
        + 55 * min(f["mapBytesCount"], 1)
        + 30 * min(f["partLimitCount"], 1)
        + 25 * min(f["header21Count"], 1)
        + 9 * min(f["indexedWordMemoryCount"], 6)
        + 8 * min(f["scale4MemoryCount"], 6)
        + 10 * min(f["byteStoreCount"], 5)
        + 7 * min(f["backwardJumpCount"], 4)
        + 4 * min(f["bitOpCount"], 8)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    args = ap.parse_args()

    data = args.exe.read_bytes()
    actual = sha256(data)
    require(len(data) == args.expected_bytes, f"comparison bytes changed: {len(data)}")
    require(actual.lower() == args.expected_sha256.lower(), f"comparison SHA changed: {actual}")
    pe = PE(data)
    _, insns, coverage = full_exec_disasm(data, pe)
    old_cov = old_linear_coverage(data, pe)
    require(all(x["rawFullyAccounted"] for x in coverage), "skip-data disassembly failed complete raw-byte accounting")

    addrs = [x.address for x in insns]
    mask_seeds = [x for x in insns if has_imm(x, HASH_MASK)]
    map_seeds = [x for x in insns if has_imm(x, MAP_BYTES)]
    direct_sentinel = [x for x in insns if byte_store_imm9f(x)]

    reg_sentinel = []
    for i, x in enumerate(insns):
        reg = reg_load_9f(x)
        if reg is None:
            continue
        for y in insns[i + 1:i + 9]:
            if y.address - x.address > 0x40:
                break
            if byte_store_from_reg(y, reg):
                reg_sentinel.append({"load": x, "store": y})
                break
            if overwritten_reg(y, reg):
                break

    # Build ranked windows around every high-signal seed, deduplicated by a
    # coarse address bucket.  This is locator ranking, not function inference.
    seed_rows = []
    seen = set()
    seed_items = [("hash1ff", x) for x in mask_seeds] + [("map800", x) for x in map_seeds] + [("sentinel9f", x) for x in direct_sentinel] + [("sentinel9f_reg", r["store"]) for r in reg_sentinel]
    for kind, seed in seed_items:
        bucket = seed.address // 0x100
        key = (kind, bucket)
        if key in seen:
            continue
        seen.add(key)
        lo = bisect_left(addrs, seed.address - 0x280)
        hi = bisect_right(addrs, seed.address + 0x380)
        window = insns[lo:hi]
        if not window:
            continue
        f = feature_row(window)
        row = {
            "seedKind": kind,
            "seedVaHex": f"0x{seed.address:08X}",
            "seedInstruction": fmt_insn(seed),
            "score": score(f) + (100 if kind.startswith("sentinel9f") else 0),
            "features": f,
            "windowStartVaHex": f"0x{window[0].address:08X}",
            "windowEndVaHex": f"0x{window[-1].address + window[-1].size:08X}",
            "instructions": [fmt_insn(x) for x in window],
        }
        seed_rows.append(row)
    seed_rows.sort(key=lambda r: (-r["score"], int(r["seedVaHex"], 16)))

    dis = []
    for rank, row in enumerate(seed_rows[:40], 1):
        dis.append(f"===== rank={rank} kind={row['seedKind']} score={row['score']} seed={row['seedVaHex']} =====")
        dis.extend(row["instructions"])
        dis.append("")

    doc = {
        "format": FORMAT,
        "authority": AUTHORITY,
        "comparisonExecutable": {"bytes": len(data), "sha256": actual, "imageBaseHex": f"0x{pe.image_base:08X}"},
        "retailTarget": {"sha256": RETAIL_SHA256, "requiredForSemanticPromotion": True},
        "toolingCorrection": {
            "oldDefaultCapstoneLinearSweepWasComplete": False,
            "v8ValidTextTargetMissedByOldSweepVaHex": "0x00654520",
            "correctedMethod": "Capstone skip-data over every raw byte of every IMAGE_SCN_MEM_EXECUTE section",
            "skipDataCandidatesRequireStructuralCorroboration": True,
        },
        "oldLinearCoverage": old_cov,
        "correctedCoverage": coverage,
        "hashMask1ffInstructionCount": len(mask_seeds),
        "mapBytes800InstructionCount": len(map_seeds),
        "directByteStore9fCount": len(direct_sentinel),
        "registerMaterializedByteStore9fCount": len(reg_sentinel),
        "directByteStore9f": [fmt_insn(x) for x in direct_sentinel],
        "registerMaterializedByteStore9f": [{"load": fmt_insn(r["load"]), "store": fmt_insn(r["store"])} for r in reg_sentinel],
        "rankedCandidateCount": len(seed_rows),
        "rankedCandidates": seed_rows[:100],
        "proofBoundary": (
            "Pinned current-client locator only. This corrects an incomplete disassembly census but does not make skip-data "
            "decodes authoritative code, does not promote public family XAnim semantics, and does not establish retail "
            "missing-bone behavior, duplicate-name precedence, model order, modelParent assignment, or j_mms_flip handling. "
            "Retail promotion still requires exact-retail bytes and complete instruction/data-flow accounting."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis) + "\n", encoding="utf-8")
    print(json.dumps({
        "oldLinearCoverage": old_cov,
        "correctedCoverage": coverage,
        "hashMask1ffInstructionCount": len(mask_seeds),
        "mapBytes800InstructionCount": len(map_seeds),
        "directByteStore9fCount": len(direct_sentinel),
        "registerMaterializedByteStore9fCount": len(reg_sentinel),
        "topCandidates": [{k: r[k] for k in ("seedKind", "seedVaHex", "seedInstruction", "score", "features")} for r in seed_rows[:20]],
        "manifestSha256": sha256(payload.encode()),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
