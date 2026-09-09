#!/usr/bin/env python3
"""Structurally locate possible T6 DObj duplicate-part constructors in a comparison client.

NON-AUTHORITATIVE locator only.  This intentionally stops using diagnostic
strings after v6 proved that the retained strings have no direct/one-hop
instruction references in the exact current comparison executable.

The locator enumerates every executable `sub esp, imm` site with a substantial
stack allocation, decodes a bounded forward region, and records neutral features
that are useful for finding a DObjCreateDuplicateParts-like routine:

* large local workspace;
* immediate 0x20 (32 submodels) and 0xA0 (160-bone lineage-era ceiling) uses;
* 0xFF byte/sentinel uses;
* byte-width loads/stores and MOVZX operations;
* backward conditional/unconditional branches;
* direct calls;
* stores to the small positive displacements that match the public T6 DObj
  header field neighborhood (`duplicatePartsSize`, `numModels`, `numBones`).

Older-engine implementations and OpenT6 symbol names motivated which features
are *reported*, but they are not authority and are never used to auto-promote a
candidate.  All qualifying candidates are emitted.  The score is only a stable
sorting aid for human inspection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_ESP

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError

FORMAT = "t6-current-client-dobj-structural-locator-v7"
AUTHORITY = "NON_AUTHORITATIVE_CURRENT_CLIENT_STRUCTURAL_LOCATOR_ONLY"
RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fmt(insn) -> str:
    return f"0x{insn.address:08X}: {insn.bytes.hex():<24} {insn.mnemonic:<8} {insn.op_str}".rstrip()


def section_for_va(pe: PE, va: int) -> dict[str, Any] | None:
    for sec in pe.sections:
        if sec["va"] <= va < sec["va"] + sec["rawSize"]:
            return sec
    return None


def immediate_values(insn) -> list[int]:
    out: list[int] = []
    for op in insn.operands:
        if op.type == X86_OP_IMM:
            out.append(int(op.imm) & 0xFFFFFFFF)
    return out


def substantial_stack_alloc(insn, minimum: int) -> int | None:
    if insn.mnemonic != "sub" or len(insn.operands) != 2:
        return None
    a, b = insn.operands
    if a.type != X86_OP_REG or a.reg != X86_REG_ESP or b.type != X86_OP_IMM:
        return None
    n = int(b.imm)
    if n < minimum or n > 0x10000:
        return None
    return n


def small_positive_mem_disps(insn) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, op in enumerate(insn.operands):
        if op.type != X86_OP_MEM:
            continue
        m = op.mem
        disp = int(m.disp)
        if 0 <= disp <= 0x20:
            rows.append({
                "operandIndex": idx,
                "disp": disp,
                "size": int(op.size),
                "base": insn.reg_name(m.base) if m.base else None,
                "index": insn.reg_name(m.index) if m.index else None,
                "scale": int(m.scale),
            })
    return rows


def decode_candidate(pe: PE, data: bytes, md: Cs, start_va: int, stack_alloc: int, max_bytes: int) -> dict[str, Any]:
    sec = section_for_va(pe, start_va)
    if sec is None or not sec["executable"]:
        raise ProbeError(f"candidate 0x{start_va:x} not executable")
    max_end = min(sec["va"] + sec["rawSize"], start_va + max_bytes)
    off = pe.va_to_off(start_va)
    raw = data[off:off + (max_end - start_va)]

    insns = []
    ret_seen = False
    for insn in md.disasm(raw, start_va):
        insns.append(insn)
        if insn.mnemonic.startswith("ret"):
            ret_seen = True
            break
    if not insns:
        raise ProbeError(f"candidate 0x{start_va:x} decoded zero instructions")

    decoded_end = insns[-1].address + insns[-1].size
    candidate_raw = data[off:off + (decoded_end - start_va)]

    imm20 = []
    immA0 = []
    immFF = []
    direct_calls = []
    backward_branches = []
    movzx_byte_count = 0
    byte_mem_access_count = 0
    small_disp_accesses = []
    small_disp_writes = []

    for insn in insns:
        vals = immediate_values(insn)
        if 0x20 in vals:
            imm20.append(insn.address)
        if 0xA0 in vals:
            immA0.append(insn.address)
        if 0xFF in vals or 0xFFFFFFFF in vals:
            immFF.append(insn.address)

        if insn.mnemonic == "call" and insn.operands and insn.operands[0].type == X86_OP_IMM:
            direct_calls.append({"at": insn.address, "target": int(insn.operands[0].imm) & 0xFFFFFFFF})

        if (insn.mnemonic.startswith("j") or insn.mnemonic == "loop") and insn.operands and insn.operands[0].type == X86_OP_IMM:
            target = int(insn.operands[0].imm) & 0xFFFFFFFF
            if target < insn.address:
                backward_branches.append({"at": insn.address, "mnemonic": insn.mnemonic, "target": target})

        if insn.mnemonic.startswith("movzx"):
            for op in insn.operands:
                if op.type == X86_OP_MEM and int(op.size) == 1:
                    movzx_byte_count += 1

        for op in insn.operands:
            if op.type == X86_OP_MEM and int(op.size) == 1:
                byte_mem_access_count += 1

        for row in small_positive_mem_disps(insn):
            item = {"va": insn.address, "mnemonic": insn.mnemonic, "opStr": insn.op_str, **row}
            small_disp_accesses.append(item)
            # Destination memory operand is conventionally operand 0 for the
            # ordinary MOV/AND/OR forms of interest.  This is reported only.
            if row["operandIndex"] == 0 and insn.mnemonic in {"mov", "movzx", "and", "or", "xor", "inc", "dec"}:
                small_disp_writes.append(item)

    # Stable locator score.  It ranks but NEVER promotes.  The individual
    # features and complete candidate set remain authoritative only as facts
    # about this comparison executable.
    score = 0
    score += 4 if stack_alloc >= 0x400 else 2
    score += 5 if imm20 else 0
    score += 5 if immA0 else 0
    score += 3 if immFF else 0
    score += min(4, len(backward_branches))
    score += min(4, movzx_byte_count)
    # DObj header neighborhood from public T6 type declaration: report extra
    # weight when several byte-sized accesses target offsets 8..10, but do not
    # require the compiler to keep a stable base register.
    header_byte = [x for x in small_disp_accesses if x["size"] == 1 and x["disp"] in (8, 9, 10)]
    score += min(6, 2 * len({x["disp"] for x in header_byte}))

    return {
        "startVa": start_va,
        "section": sec["name"],
        "stackAllocation": stack_alloc,
        "retSeenWithinBound": ret_seen,
        "decodedEndVaExclusive": decoded_end,
        "decodedBytes": decoded_end - start_va,
        "decodedInstructionCount": len(insns),
        "candidateSha256": sha256(candidate_raw),
        "locatorScore": score,
        "features": {
            "imm0x20Sites": imm20,
            "imm0xA0Sites": immA0,
            "imm0xFFSites": immFF,
            "directCallCount": len(direct_calls),
            "directCalls": direct_calls,
            "backwardBranchCount": len(backward_branches),
            "backwardBranches": backward_branches,
            "movzxByteCount": movzx_byte_count,
            "byteMemoryAccessCount": byte_mem_access_count,
            "smallPositiveMemoryAccesses": small_disp_accesses,
            "smallPositiveMemoryWrites": small_disp_writes,
            "dobjHeaderNeighborhoodByteOffsetsObserved": sorted({x["disp"] for x in header_byte}),
        },
        "instructions": [fmt(i) for i in insns],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--min-stack", type=lambda x: int(x, 0), default=0x200)
    ap.add_argument("--max-candidate-bytes", type=lambda x: int(x, 0), default=0x3000)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    args = ap.parse_args()

    data = args.exe.read_bytes()
    actual_sha = sha256(data)
    if len(data) != args.expected_bytes or actual_sha.lower() != args.expected_sha256.lower():
        raise ProbeError(f"comparison identity mismatch bytes={len(data)} sha256={actual_sha}")
    pe = PE(data)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    starts: list[tuple[int, int]] = []
    executable_decoded_instruction_count = 0
    for sec in pe.sections:
        if not sec["executable"] or not sec["rawSize"]:
            continue
        raw = data[sec["rawOff"]:sec["rawOff"] + sec["rawSize"]]
        for insn in md.disasm(raw, sec["va"]):
            executable_decoded_instruction_count += 1
            n = substantial_stack_alloc(insn, args.min_stack)
            if n is not None:
                starts.append((insn.address, n))

    candidates = [decode_candidate(pe, data, md, va, n, args.max_candidate_bytes) for va, n in starts]
    candidates.sort(key=lambda x: (-x["locatorScore"], -x["stackAllocation"], x["startVa"]))

    # Full JSON preserves every candidate; the text file keeps the top-ranked
    # windows readable without implying that rank 0 is the correct function.
    dis_lines = []
    for rank, row in enumerate(candidates[:25]):
        dis_lines.append(
            f"===== NON-AUTHORITATIVE candidate rank={rank} score={row['locatorScore']} "
            f"start=0x{row['startVa']:08X} stack=0x{row['stackAllocation']:X} "
            f"sha256={row['candidateSha256']} ====="
        )
        dis_lines.extend(row["instructions"])
        dis_lines.append("")

    compact_candidates = []
    for rank, row in enumerate(candidates):
        compact = {k: v for k, v in row.items() if k != "instructions"}
        compact["rank"] = rank
        compact_candidates.append(compact)

    doc = {
        "format": FORMAT,
        "authority": AUTHORITY,
        "comparisonExecutable": {
            "bytes": len(data),
            "sha256": actual_sha,
            "imageBaseHex": f"0x{pe.image_base:08X}",
        },
        "retailAuthorityTarget": {
            "bytes": 12850328,
            "sha256": RETAIL_SHA256,
            "presentInProbe": False,
        },
        "publicT6LocatorFacts": {
            "source": "uhhashe/OpenT6 code/src/all_types.h and code/src/xanim/dobj.cpp",
            "symbol": "DObjCreateDuplicateParts",
            "symbolImplementationAvailable": False,
            "dobjHeaderFieldsInOrder": ["duplicateParts", "entnum", "duplicatePartsSize", "numModels", "numBones", "ignoreCollision"],
            "authorityUse": "names/type layout are locator metadata only; no OpenT6 function semantics are imported"
        },
        "lineageUse": {
            "usedOnlyToChooseReportedFeatures": True,
            "semanticAuthority": False,
            "features": ["32-entry submodel-era arrays/limit", "160-bone-era limit", "0xFF parent sentinel", "large duplicate-part workspace"]
        },
        "scan": {
            "minimumStackAllocation": args.min_stack,
            "maximumCandidateBytes": args.max_candidate_bytes,
            "executableDecodedInstructionCount": executable_decoded_instruction_count,
            "substantialStackSiteCount": len(starts),
            "candidateCount": len(compact_candidates),
        },
        "candidates": compact_candidates,
        "proofBoundary": (
            "Every candidate is retained. Locator score, stack size, 0x20/0xA0/0xFF constants, DObj-layout-like "
            "memory accesses, loops, calls, source-order resemblance, or older-engine lineage cannot identify the "
            "retail T6 constructor or promote model order, duplicate mapping, modelParent assignment, or hierarchy. "
            "Promotion requires independently retail-authoritative bytes/runtime evidence tied to t6mp.exe SHA-256 "
            + RETAIL_SHA256 + "."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(dis_lines) + "\n", encoding="utf-8")

    summary = [{
        "rank": i,
        "startVa": f"0x{c['startVa']:08X}",
        "stack": f"0x{c['stackAllocation']:X}",
        "score": c["locatorScore"],
        "imm20": len(c["features"]["imm0x20Sites"]),
        "immA0": len(c["features"]["imm0xA0Sites"]),
        "immFF": len(c["features"]["imm0xFFSites"]),
        "headerOffsets": c["features"]["dobjHeaderNeighborhoodByteOffsetsObserved"],
        "loops": c["features"]["backwardBranchCount"],
        "calls": c["features"]["directCallCount"],
    } for i, c in enumerate(candidates[:12])]
    print(json.dumps({
        "candidateCount": len(candidates),
        "substantialStackSiteCount": len(starts),
        "topCandidates": summary,
        "manifestSha256": sha256(payload.encode("utf-8")),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
