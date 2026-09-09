#!/usr/bin/env python3
"""Strict five-argument locator for the T6 XAnim anim-to-model map intern call.

v5 searched a four-argument cdecl shape and therefore used the wrong lineage ABI.
The reviewed Treyarch-family implementation calls:

    SL_GetStringOfSize(SCRIPTINSTANCE_SERVER, data, 0, boneCount + 21, 11)

where SCRIPTINSTANCE_SERVER is 0 in that public lineage.  This file uses that
shape only as NON-AUTHORITATIVE locator input.  Nothing found in the current
comparison client is promoted to T6 retail semantics without exact-retail bytes.

For a normal PUSH/cdecl materialization the reverse argument order is:

    push 11          ; type
    push length
    push 0           ; user
    push data
    push 0           ; SCRIPTINSTANCE_SERVER lineage value
    call target
    add esp, 20

The strict census requires the positional type/user/server constants and exact
20-byte caller cleanup.  A higher-confidence subset additionally requires a
nearby +21 length materialization and evidence that the data argument is formed
from a stack address.  Compiler forms that do not use five PUSHes remain outside
coverage rather than being guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError, fmt_insn

FORMAT = "t6-current-client-xanim-animmap-locator-v7"
AUTHORITY = "NON_AUTHORITATIVE_CURRENT_CLIENT_LOCATOR_ONLY"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
MAP_TYPE = 11
LINEAGE_SERVER_INSTANCE = 0
LINEAGE_USER = 0
LINEAGE_HEADER_BYTES = 21
V5_FALSE_CONTROLS = {
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
    for insn in insns[call_index + 1:call_index + 6]:
        if insn.mnemonic in ("ret", "retn", "jmp", "call"):
            return None
        if insn.mnemonic == "add" and len(insn.operands) == 2:
            dst, src = insn.operands
            if dst.type == X86_OP_REG and insn.reg_name(dst.reg) == "esp" and src.type == X86_OP_IMM:
                return int(src.imm)
    return None


def straight_line_prefix(insns, call_index: int, limit: int = 40):
    rows = []
    for insn in reversed(insns[max(0, call_index - limit):call_index]):
        if insn.mnemonic in ("call", "jmp", "ret", "retn") or insn.mnemonic.startswith("j"):
            break
        rows.append(insn)
    rows.reverse()
    return rows


def pushes(rows):
    return [x for x in rows if is_push(x)]


def has_plus21(rows) -> bool:
    for insn in rows:
        if LINEAGE_HEADER_BYTES not in [int(op.imm) for op in insn.operands if op.type == X86_OP_IMM]:
            continue
        if insn.mnemonic in ("add", "lea"):
            return True
    return False


def stack_address_registers(rows) -> set[int]:
    regs = set()
    for insn in rows:
        if insn.mnemonic != "lea" or len(insn.operands) != 2:
            continue
        dst, src = insn.operands
        if dst.type != X86_OP_REG or src.type != X86_OP_MEM:
            continue
        base = insn.reg_name(src.mem.base) if src.mem.base else ""
        if base in ("esp", "ebp"):
            regs.add(dst.reg)
    return regs


def pushed_reg(insn) -> int | None:
    if not is_push(insn) or insn.operands[0].type != X86_OP_REG:
        return None
    return int(insn.operands[0].reg)


def classify_shape(rows, cleanup: int | None) -> dict:
    ps = pushes(rows)
    last5 = ps[-5:] if len(ps) >= 5 else []
    positional = False
    if len(last5) == 5:
        positional = (
            is_push_imm(last5[0], MAP_TYPE)
            and is_push_imm(last5[2], LINEAGE_USER)
            and is_push_imm(last5[4], LINEAGE_SERVER_INSTANCE)
        )
    strict = cleanup == 20 and positional
    stack_regs = stack_address_registers(rows)
    data_reg = pushed_reg(last5[3]) if len(last5) == 5 else None
    stack_data = data_reg is not None and data_reg in stack_regs
    plus21 = has_plus21(rows)
    return {
        "straightLinePushCount": len(ps),
        "lastFivePushes": [fmt_insn(x) for x in last5],
        "callerCleanupBytes": cleanup,
        "positionalTypeUserServerShape": positional,
        "nearbyPlus21LengthMaterialization": plus21,
        "stackAddressDataArgument": stack_data,
        "strictFiveArgPushCdeclShape": strict,
        "highConfidenceLineageShape": bool(strict and plus21 and stack_data),
    }


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
    target_counts = Counter(target(x) for x in insns if is_direct_call(x))

    false_controls = []
    for va, expected in sorted(V5_FALSE_CONTROLS.items()):
        i = by_va.get(va)
        require(i is not None, f"negative-control call missing at 0x{va:08X}")
        call = insns[i]
        require(is_direct_call(call), f"0x{va:08X} is no longer direct CALL")
        require(target(call) == expected["target"], f"0x{va:08X} target changed")
        rows = straight_line_prefix(insns, i)
        ps = pushes(rows)
        cleanup = cleanup_bytes(insns, i)
        require(cleanup == expected["cleanup"], f"0x{va:08X} cleanup changed: {cleanup}")
        require(len(ps) == expected["pushes"], f"0x{va:08X} push count changed: {len(ps)}")
        false_controls.append({
            "callVaHex": f"0x{va:08X}",
            "targetVaHex": f"0x{target(call):08X}",
            "callerCleanupBytes": cleanup,
            "straightLinePushCount": len(ps),
            "classification": "REJECTED_TWO_ARGUMENT_CALL_SHAPE",
        })

    type11_rows = []
    strict_rows = []
    high_rows = []
    for i, call in enumerate(insns):
        if not is_direct_call(call):
            continue
        rows = straight_line_prefix(insns, i)
        ps = pushes(rows)
        if not any(is_push_imm(x, MAP_TYPE) for x in ps):
            continue
        shape = classify_shape(rows, cleanup_bytes(insns, i))
        row = {
            "callVaHex": f"0x{call.address:08X}",
            "targetVaHex": f"0x{target(call):08X}",
            "targetDirectCallsiteCount": target_counts[target(call)],
            **shape,
        }
        type11_rows.append(row)
        if shape["strictFiveArgPushCdeclShape"]:
            strict_rows.append(row)
        if shape["highConfidenceLineageShape"]:
            high_rows.append(row)

    type11_rows.sort(key=lambda r: int(r["callVaHex"], 16))
    strict_rows.sort(key=lambda r: int(r["callVaHex"], 16))
    high_rows.sort(key=lambda r: int(r["callVaHex"], 16))

    dis_lines = []
    selected = high_rows or strict_rows
    for rank, row in enumerate(selected[:20], 1):
        va = int(row["callVaHex"], 16)
        i = by_va[va]
        caller_window = insns[max(0, i - 60):min(len(insns), i + 20)]
        dis_lines.append(
            f"===== candidate rank={rank} high={row['highConfidenceLineageShape']} "
            f"call={row['callVaHex']} target={row['targetVaHex']} ====="
        )
        dis_lines.extend(fmt_insn(x) for x in caller_window)
        dis_lines.append("")
        tva = int(row["targetVaHex"], 16)
        ti = by_va.get(tva)
        if ti is not None:
            target_window = insns[max(0, ti - 4):min(len(insns), ti + 80)]
            dis_lines.append(f"===== direct target {row['targetVaHex']} =====")
            dis_lines.extend(fmt_insn(x) for x in target_window)
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
        "correctedLineageLocatorShape": {
            "function": "SL_GetStringOfSize",
            "sourceArgumentOrder": ["scriptInstance", "data", "user", "len", "type"],
            "lineageCall": [0, "stack-local animToModel", 0, "boneCount + 21", 11],
            "pushOrderForCdecl": [11, "len", 0, "data", 0],
            "expectedCallerCleanupBytes": 20,
            "publicLineageOnly": True,
        },
        "v5WrongArityCorrection": {
            "v5SearchedArgumentCount": 4,
            "v5ExpectedCleanupBytes": 16,
            "v7SearchedArgumentCount": 5,
            "v7ExpectedCleanupBytes": 20,
        },
        "v5FalsePositiveControls": false_controls,
        "type11PushCallsiteCount": len(type11_rows),
        "type11PushCallsites": type11_rows,
        "strictFiveArgCandidateCount": len(strict_rows),
        "strictFiveArgCandidates": strict_rows,
        "highConfidenceCandidateCount": len(high_rows),
        "highConfidenceCandidates": high_rows,
        "proofBoundary": (
            "Comparison-client locator only. The five-argument signature, server-instance value 0, user value 0, "
            "boneCount+21 layout, and type 11 are taken from reviewed public Treyarch-family source solely to locate "
            "a candidate in the pinned current client. No candidate address, call target, missing-bone sentinel, "
            "partBits behavior, model traversal order, duplicate-name precedence, or absent-channel behavior is "
            "promoted to the exact retail executable. Compiler forms that do not materialize five PUSH arguments "
            "are not covered."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "type11PushCallsiteCount": len(type11_rows),
        "strictFiveArgCandidateCount": len(strict_rows),
        "highConfidenceCandidateCount": len(high_rows),
        "strictFiveArgCandidates": strict_rows[:20],
        "highConfidenceCandidates": high_rows[:20],
        "manifestSha256": sha256(payload.encode()),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
