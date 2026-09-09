#!/usr/bin/env python3
"""Strict comparison-client locator for the T6 XAnim map string-intern call.

v4 deliberately used loose ranking and produced two false-positive call sites.
This pass records that correction and searches only for the public
SL_GetStringOfSize(str, user, len, type) cdecl shape when `type == 11` is
materialized with PUSH.  It is still a locator only: absence or presence in the
current comparison client is never promoted to pinned-retail semantics.

The two v4 candidates are retained as exact negative controls.  Both clean up
8 stack bytes after their calls, proving that those concrete sites are
2-argument call shapes rather than the required 4-argument cdecl shape.
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

FORMAT = "t6-current-client-xanim-animmap-locator-v5"
AUTHORITY = "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
MAP_TYPE = 11
V4_FALSE_CONTROLS = {
    0x00B691D3: {"target": 0x00654520, "cleanup": 8, "pushes": 2},
    0x00B69D68: {"target": 0x00543D60, "cleanup": 8, "pushes": 2},
}


class LocatorError(RuntimeError):
    pass


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise LocatorError(msg)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_direct_call(insn) -> bool:
    return insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM


def target(insn) -> int:
    return int(insn.operands[0].imm)


def is_push(insn) -> bool:
    return insn.mnemonic == "push" and len(insn.operands) == 1


def is_push_imm(insn, value: int) -> bool:
    return is_push(insn) and insn.operands[0].type == X86_OP_IMM and int(insn.operands[0].imm) == value


def cleanup_bytes(insns, call_index: int) -> int | None:
    # Accept a few non-control instructions between CALL and caller cleanup.
    for insn in insns[call_index + 1:call_index + 5]:
        if insn.mnemonic in ("ret", "jmp", "call"):
            return None
        if insn.mnemonic == "add" and len(insn.operands) == 2:
            dst, src = insn.operands
            if dst.type == X86_OP_REG and insn.reg_name(dst.reg) == "esp" and src.type == X86_OP_IMM:
                return int(src.imm)
    return None


def basic_block_prefix(insns, call_index: int, limit: int = 24):
    rows = []
    for insn in reversed(insns[max(0, call_index - limit):call_index]):
        # Any preceding call or branch terminates the straight-line argument region.
        if insn.mnemonic in ("call", "jmp", "ret", "retn") or insn.mnemonic.startswith("j"):
            break
        rows.append(insn)
    rows.reverse()
    return rows


def push_rows(rows):
    return [x for x in rows if is_push(x)]


def strict_four_arg_shape(rows, cleanup: int | None) -> bool:
    pushes = push_rows(rows)
    if cleanup != 16 or len(pushes) < 4:
        return False
    last4 = pushes[-4:]
    # cdecl right-to-left: fourth arg `type` is pushed before len/user/str.
    return is_push_imm(last4[0], MAP_TYPE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
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
    call_target_counts = Counter(target(x) for x in insns if is_direct_call(x))

    false_controls = []
    for va, expected in sorted(V4_FALSE_CONTROLS.items()):
        i = by_va.get(va)
        require(i is not None, f"v4 negative-control call missing at 0x{va:08X}")
        call = insns[i]
        require(is_direct_call(call), f"0x{va:08X} no longer direct CALL")
        require(target(call) == expected["target"], f"0x{va:08X} target changed")
        rows = basic_block_prefix(insns, i)
        pushes = push_rows(rows)
        cleanup = cleanup_bytes(insns, i)
        require(cleanup == expected["cleanup"], f"0x{va:08X} cleanup changed: {cleanup}")
        require(len(pushes) == expected["pushes"], f"0x{va:08X} straight-line push count changed: {len(pushes)}")
        false_controls.append({
            "callVaHex": f"0x{va:08X}",
            "targetVaHex": f"0x{target(call):08X}",
            "callerCleanupBytes": cleanup,
            "straightLinePushCount": len(pushes),
            "straightLinePushes": [fmt_insn(x) for x in pushes],
            "classification": "REJECTED_TWO_ARGUMENT_CALL_SHAPE",
            "instructions": [fmt_insn(x) for x in rows] + [fmt_insn(call)] + [fmt_insn(x) for x in insns[i + 1:i + 3]],
        })

    # Strict positive-locator census.  This intentionally covers only the PUSH
    # cdecl form; other compiler materializations remain unresolved rather than
    # being guessed.  A row is admitted only when type=11 is the oldest of the
    # final four straight-line pushes and the caller cleans exactly 16 bytes.
    strict_rows = []
    type11_near_call_rows = []
    for i, call in enumerate(insns):
        if not is_direct_call(call):
            continue
        rows = basic_block_prefix(insns, i)
        pushes = push_rows(rows)
        if not any(is_push_imm(x, MAP_TYPE) for x in pushes):
            continue
        cleanup = cleanup_bytes(insns, i)
        row = {
            "callVaHex": f"0x{call.address:08X}",
            "targetVaHex": f"0x{target(call):08X}",
            "targetDirectCallsiteCount": call_target_counts[target(call)],
            "callerCleanupBytes": cleanup,
            "straightLinePushCount": len(pushes),
            "straightLinePushes": [fmt_insn(x) for x in pushes],
            "fourArgPushCdeclShape": strict_four_arg_shape(rows, cleanup),
        }
        type11_near_call_rows.append(row)
        if row["fourArgPushCdeclShape"]:
            strict_rows.append(row)

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
        "requiredPublicShape": {
            "function": "SL_GetStringOfSize",
            "arguments": ["str", "user", "len", "type"],
            "candidateType": MAP_TYPE,
            "strictCompilerFormCovered": "four PUSH cdecl arguments with caller cleanup of 16 bytes",
            "otherCompilerFormsCovered": False,
        },
        "v4FalsePositiveControls": false_controls,
        "type11PushCallsiteCount": len(type11_near_call_rows),
        "type11PushCallsites": type11_near_call_rows,
        "strictFourArgCandidateCount": len(strict_rows),
        "strictFourArgCandidates": strict_rows,
        "proofBoundary": (
            "Comparison-client locator only. v5 proves only that the two concrete v4 call sites are two-argument "
            "shapes and therefore cannot be the four-argument PUSH/cdecl SL_GetStringOfSize shape. The strict "
            "census covers one compiler form only. No absence, candidate address, target, or current-client "
            "behavior is promoted to the exact retail executable."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "v4FalsePositiveControls": false_controls,
        "type11PushCallsiteCount": len(type11_near_call_rows),
        "strictFourArgCandidateCount": len(strict_rows),
        "strictFourArgCandidates": strict_rows[:20],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
