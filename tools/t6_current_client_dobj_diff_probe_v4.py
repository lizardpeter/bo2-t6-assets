#!/usr/bin/env python3
"""Map the two homologous current-client T6 skeleton-consumer paths.

NON-AUTHORITATIVE for retail semantics.  This is a locator pass only.

The exact retail proof already retained five skeleton-helper byte witnesses.  A
prior differential pass showed that all five have unique current-client matches
at one uniform +0x5810 relocation, while the surrounding functions changed.
This pass uses only those matched helper targets to find their direct callers,
groups the six calls into the two consumer paths, and emits instruction-aligned
windows plus memory/immediate access summaries for locating the higher-level
multi-XModel/DObj merge code.

Nothing discovered only in the comparison client may be promoted as retail
behavior without a separate exact-retail witness.
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
from t6_current_client_dobj_diff_probe_v2 import ANCHORS

FORMAT = "t6-current-client-dobj-differential-probe-v4"
EXPECTED_SHIFT = 0x5810
RETAIL_HELPER_VA = {
    "rootNoParent": 0x8D6100,
    "rootWithParent": 0x8D6220,
    "nonRoot": 0x8D6B50,
}
RETAIL_ANCHOR_VA = {
    "rootNoParentPrologue": 0x8D6100,
    "rootWithParentPrologue": 0x8D6220,
    "nonRootPrologue": 0x8D6B50,
    "nonRootParentListLookup": 0x8D6C20,
    "nonRootBindTranslationAdd": 0x8D7016,
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fmt(insn) -> str:
    return f"0x{insn.address:08X}: {insn.bytes.hex():<24} {insn.mnemonic:<8} {insn.op_str}".rstrip()


def all_text_insns(pe: PE, data: bytes):
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    rows = []
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        rows.extend(md.disasm(raw, sec["va"]))
    rows.sort(key=lambda x: x.address)
    return rows


def raw_rel32_callers(pe: PE, data: bytes, target: int) -> list[int]:
    out: list[int] = []
    for sec in pe.sections:
        if not sec["executable"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        for i in range(max(0, len(raw) - 4)):
            if raw[i] != 0xE8:
                continue
            rel = struct.unpack_from("<i", raw, i + 1)[0]
            va = sec["va"] + i
            if va + 5 + rel == target:
                out.append(va)
    return sorted(out)


def group_calls(calls: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    rows = sorted(calls, key=lambda x: x["callVa"])
    groups: list[list[dict[str, Any]]] = []
    for row in rows:
        if not groups or row["callVa"] - groups[-1][-1]["callVa"] > 0x300:
            groups.append([row])
        else:
            groups[-1].append(row)
    return groups


def operand_summary(insn) -> dict[str, Any]:
    mem = []
    imms = []
    for op in insn.operands:
        if op.type == X86_OP_MEM:
            m = op.mem
            mem.append({
                "base": insn.reg_name(m.base) if m.base else None,
                "index": insn.reg_name(m.index) if m.index else None,
                "scale": m.scale,
                "disp": m.disp,
                "dispHex": f"0x{m.disp & 0xFFFFFFFF:X}",
            })
        elif op.type == X86_OP_IMM:
            imms.append(int(op.imm))
    return {"memory": mem, "immediates": imms}


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
    if len(data) != args.expected_bytes or actual != args.expected_sha256.lower():
        raise ProbeError(f"comparison identity mismatch bytes={len(data)} sha256={actual}")
    pe = PE(data)

    anchor_occurrences: dict[str, list[int]] = {}
    shifts: list[int] = []
    for label, hx in ANCHORS.items():
        vas = []
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

    targets = {label: va + EXPECTED_SHIFT for label, va in RETAIL_HELPER_VA.items()}
    calls: list[dict[str, Any]] = []
    for label, target in targets.items():
        callers = raw_rel32_callers(pe, data, target)
        if len(callers) != 2:
            raise ProbeError(f"{label} caller count {len(callers)} != 2")
        for va in callers:
            calls.append({"helper": label, "targetVa": target, "callVa": va})

    groups = group_calls(calls)
    if len(groups) != 2 or any(sorted(x["helper"] for x in g) != ["nonRoot", "rootNoParent", "rootWithParent"] for g in groups):
        raise ProbeError(f"caller grouping is not two complete 3-helper consumers: {groups!r}")

    insns = all_text_insns(pe, data)
    addr_to_index = {insn.address: i for i, insn in enumerate(insns)}
    doc_groups = []
    lines = []
    for gi, group in enumerate(groups):
        call_indices = []
        for row in group:
            idx = addr_to_index.get(row["callVa"])
            if idx is None:
                raise ProbeError(f"call 0x{row['callVa']:x} not on Capstone instruction boundary")
            call_indices.append(idx)
        lo = max(0, min(call_indices) - 110)
        hi = min(len(insns), max(call_indices) + 111)
        window = insns[lo:hi]
        if not window:
            raise ProbeError("empty consumer window")

        access_rows = []
        direct_calls = []
        branches = []
        for insn in window:
            ops = operand_summary(insn)
            if ops["memory"] or ops["immediates"]:
                access_rows.append({
                    "va": insn.address,
                    "mnemonic": insn.mnemonic,
                    "opStr": insn.op_str,
                    **ops,
                })
            if insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM:
                direct_calls.append({"va": insn.address, "targetVa": int(insn.operands[0].imm)})
            if insn.mnemonic.startswith("j") and insn.operands and insn.operands[0].type == X86_OP_IMM:
                branches.append({"va": insn.address, "mnemonic": insn.mnemonic, "targetVa": int(insn.operands[0].imm)})

        raw_start = pe.va_to_off(window[0].address)
        raw_end = pe.va_to_off(window[-1].address) + window[-1].size
        raw = data[raw_start:raw_end]
        row = {
            "group": gi,
            "helperCalls": sorted(group, key=lambda x: x["callVa"]),
            "windowStartVa": window[0].address,
            "windowEndVaExclusive": window[-1].address + window[-1].size,
            "instructionCount": len(window),
            "windowSha256": sha256(raw),
            "directCalls": direct_calls,
            "conditionalAndUnconditionalBranches": branches,
            "operandAccesses": access_rows,
        }
        doc_groups.append(row)
        lines.append(
            f"===== CURRENT COMPARISON CONSUMER {gi} "
            f"0x{window[0].address:08X}-0x{window[-1].address + window[-1].size:08X} "
            f"sha256={row['windowSha256']} ====="
        )
        lines.append("helper calls: " + ", ".join(
            f"{x['helper']}@0x{x['callVa']:08X}->0x{x['targetVa']:08X}" for x in sorted(group, key=lambda y: y["callVa"])
        ))
        for insn in window:
            marker = " <== HELPER CALL" if any(insn.address == x["callVa"] for x in group) else ""
            lines.append(fmt(insn) + marker)
        lines.append("")

    doc = {
        "format": FORMAT,
        "authority": "NON_AUTHORITATIVE_CURRENT_CLIENT_DIFFERENTIAL_ONLY",
        "comparisonExecutable": {"bytes": len(data), "sha256": actual},
        "retailAuthorityReference": {
            "sha256": "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1",
            "manifest": "manifests/xanim/T6_RETAIL_XANIM_ROOT_TRANSLATION_PROOF_V1.json",
        },
        "validatedUniformRelocationDelta": EXPECTED_SHIFT,
        "validatedUniformRelocationDeltaHex": f"0x{EXPECTED_SHIFT:X}",
        "anchorOccurrences": anchor_occurrences,
        "shiftedHelperTargets": targets,
        "helperCalls": sorted(calls, key=lambda x: x["callVa"]),
        "consumerGroups": doc_groups,
        "summary": {
            "uniqueAnchorCount": len(anchor_occurrences),
            "helperCallerCount": len(calls),
            "consumerGroupCount": len(groups),
            "eachConsumerCallsAllThreeHelpers": True,
        },
        "proofBoundary": (
            "This pass is a locator over the exact SHA-pinned comparison client. The five anchors are tied to "
            "retail only because their short byte witnesses were independently retained from the pinned retail "
            "executable. Surrounding comparison-client bytes, fields, loops, call graph, and inferred meanings "
            "are non-authoritative until separately matched to exact-retail bytes or runtime evidence."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "uniformShift": f"0x{EXPECTED_SHIFT:X}",
        "helperCalls": len(calls),
        "consumerGroups": len(groups),
        "groupCallVas": [[f"0x{x['callVa']:X}" for x in g] for g in groups],
        "manifestSha256": sha256(payload.encode()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
