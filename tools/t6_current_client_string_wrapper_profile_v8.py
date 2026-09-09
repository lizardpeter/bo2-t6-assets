#!/usr/bin/env python3
"""Profile the two-argument target reached by the sole current-client type=11 PUSH site.

v7 proved only that 0x00B691D3 is not the public five-argument PUSH/cdecl form.
It also established that its direct target 0x00654520 has ten direct callsites.
This probe asks a narrower locator question: is that target consistently called as
(value, small-type-enum), making it a plausible optimized/wrapper string path?

All output remains comparison-client locator evidence only.  No target identity,
argument meaning, current-client behavior, or address is promoted to retail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_REG

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError, fmt_insn

FORMAT = "t6-current-client-string-wrapper-profile-v8"
AUTHORITY = "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
TARGET = 0x00654520
KNOWN_TYPE11_SITE = 0x00B691D3


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise RuntimeError(msg)


def is_direct_call(insn) -> bool:
    return insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM


def target(insn) -> int:
    return int(insn.operands[0].imm)


def is_push(insn) -> bool:
    return insn.mnemonic == "push" and len(insn.operands) == 1


def cleanup_bytes(insns, i: int) -> int | None:
    for x in insns[i + 1:i + 6]:
        if x.mnemonic in ("ret", "retn", "jmp", "call"):
            return None
        if x.mnemonic == "add" and len(x.operands) == 2:
            a, b = x.operands
            if a.type == X86_OP_REG and x.reg_name(a.reg) == "esp" and b.type == X86_OP_IMM:
                return int(b.imm)
    return None


def prefix(insns, i: int, limit: int = 24):
    rows = []
    for x in reversed(insns[max(0, i - limit):i]):
        if x.mnemonic in ("call", "ret", "retn", "jmp") or x.mnemonic.startswith("j"):
            break
        rows.append(x)
    rows.reverse()
    return rows


def push_value(x):
    op = x.operands[0]
    if op.type == X86_OP_IMM:
        return {"kind": "imm", "value": int(op.imm), "valueHex": f"0x{int(op.imm) & 0xFFFFFFFF:X}"}
    if op.type == X86_OP_REG:
        return {"kind": "reg", "reg": x.reg_name(op.reg)}
    return {"kind": "other", "instruction": fmt_insn(x)}


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
    by_va = {x.address: i for i, x in enumerate(insns)}

    sites = [(i, x) for i, x in enumerate(insns) if is_direct_call(x) and target(x) == TARGET]
    require(len(sites) == 10, f"target direct-callsite count changed: {len(sites)}")
    require(any(x.address == KNOWN_TYPE11_SITE for _, x in sites), "known type=11 site missing")

    rows = []
    type_counter = Counter()
    two_arg_cleanup8 = 0
    for i, call in sites:
        pre = prefix(insns, i)
        ps = [x for x in pre if is_push(x)]
        last2 = ps[-2:] if len(ps) >= 2 else []
        cleanup = cleanup_bytes(insns, i)
        inferred_type = None
        if len(last2) == 2 and last2[0].operands[0].type == X86_OP_IMM:
            inferred_type = int(last2[0].operands[0].imm)
            type_counter[inferred_type] += 1
        if len(ps) == 2 and cleanup == 8:
            two_arg_cleanup8 += 1
        rows.append({
            "callVaHex": f"0x{call.address:08X}",
            "callerCleanupBytes": cleanup,
            "straightLinePushCount": len(ps),
            "lastTwoPushes": [fmt_insn(x) for x in last2],
            "lastTwoValues": [push_value(x) for x in last2],
            "oldestOfLastTwoImmediateTypeCandidate": inferred_type,
            "knownType11Site": call.address == KNOWN_TYPE11_SITE,
            "prefixInstructions": [fmt_insn(x) for x in pre],
            "postInstructions": [fmt_insn(x) for x in insns[i + 1:i + 5]],
        })

    ti = by_va.get(TARGET)
    require(ti is not None, f"target 0x{TARGET:08X} is not an instruction boundary")
    body_window = insns[ti:min(len(insns), ti + 180)]
    # Stop display at the first RET only for a compact view.  This is not asserted
    # to be a complete function boundary.
    compact_body = []
    for x in body_window:
        compact_body.append(x)
        if x.mnemonic in ("ret", "retn"):
            break
    body_start = compact_body[0].address
    body_end = compact_body[-1].address + compact_body[-1].size
    try:
        off = pe.va_to_off(body_start)
        body_sha = sha256(data[off:off + (body_end - body_start)])
    except ProbeError:
        body_sha = None

    target_calls = [x for x in compact_body if is_direct_call(x)]
    doc = {
        "format": FORMAT,
        "authority": AUTHORITY,
        "comparisonExecutable": {"bytes": len(data), "sha256": actual_sha, "imageBaseHex": f"0x{pe.image_base:08X}"},
        "retailTarget": {"sha256": RETAIL_SHA256, "requiredForSemanticPromotion": True},
        "profiledTargetVaHex": f"0x{TARGET:08X}",
        "directCallsiteCount": len(rows),
        "allCallsitesExactlyTwoStraightLinePushesAndCleanup8": two_arg_cleanup8 == len(rows),
        "twoArgCleanup8Count": two_arg_cleanup8,
        "oldestPushImmediateDistribution": {str(k): v for k, v in sorted(type_counter.items())},
        "callsites": rows,
        "targetCompactBody": {
            "startVaHex": f"0x{body_start:08X}",
            "endVaHex": f"0x{body_end:08X}",
            "sha256": body_sha,
            "instructionCountThroughFirstRet": len(compact_body),
            "directCallTargetsHex": [f"0x{target(x):08X}" for x in target_calls],
            "instructions": [fmt_insn(x) for x in compact_body],
            "completeFunctionBoundaryClaimed": False,
        },
        "proofBoundary": (
            "Pinned current-client profile only. A consistent two-argument enum-like call shape can strengthen a locator "
            "hypothesis but does not identify SL_GetStringOfSize, XAnimGetAnimMap, or any retail function. No current-client "
            "address, inferred argument meaning, wrapper behavior, missing-bone sentinel, or absent-channel behavior is "
            "promoted to the exact retail executable."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")

    dis = []
    for row in rows:
        dis.append(f"===== caller {row['callVaHex']} typeCandidate={row['oldestOfLastTwoImmediateTypeCandidate']} cleanup={row['callerCleanupBytes']} =====")
        dis.extend(row["prefixInstructions"])
        dis.append(f"{row['callVaHex']}: call     0x{TARGET:08X}")
        dis.extend(row["postInstructions"])
        dis.append("")
    dis.append(f"===== target compact body 0x{TARGET:08X} =====")
    dis.extend(fmt_insn(x) for x in compact_body)
    dis.append("")
    args.disasm_out.write_text("\n".join(dis) + "\n", encoding="utf-8")

    print(json.dumps({
        "directCallsiteCount": len(rows),
        "twoArgCleanup8Count": two_arg_cleanup8,
        "oldestPushImmediateDistribution": {str(k): v for k, v in sorted(type_counter.items())},
        "targetCompactBody": doc["targetCompactBody"],
        "manifestSha256": sha256(payload.encode()),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
