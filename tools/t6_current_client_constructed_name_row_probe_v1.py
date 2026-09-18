#!/usr/bin/env python3
"""Find current-client 12-byte load-row candidates tied to constructed name buffers.

Input authority comes from t6-current-client-fastfile-name-construction-probe-v1:
the exact SHA-classified current client and the exact destination buffer VAs used
by its fastfile-name constructor.

This probe searches executable code for a straight-line store of one of those
buffer pointers into a row, followed by a concrete store at the same effective
base +4 and optionally +8. The 12-byte shape is a comparison against the exact
PC dedicated-server XZoneInfo proof only; no client field semantics, priority,
historical-retail equivalence, or Technique winner is promoted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from capstone import CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_RET
from capstone.x86_const import X86_INS_MOV, X86_OP_MEM, X86_REG_ESP

import t6_current_client_xzoneinfo_row_probe_v1 as base


FORMAT = "t6-current-client-constructed-name-row-probe-v1"
CONSTRUCTOR_FORMAT = "t6-current-client-fastfile-name-construction-probe-v1"
LOOKAHEAD = 24


def row(insn):
    return base.insn_row(insn)


def scan(raw: bytes, sections, target_vas: dict[int, dict]):
    candidates = []
    for sec in sections:
        if not sec["executable"]:
            continue
        blob = raw[sec["rawOffset"] : sec["rawOffset"] + sec["rawSize"]]
        block = []
        regs = {}
        esp_delta = 0

        def analyze(items):
            for i, item in enumerate(items):
                insn = item["insn"]
                ops = getattr(insn, "operands", ())
                if insn.id != X86_INS_MOV or len(ops) < 2 or ops[0].type != X86_OP_MEM:
                    continue
                dest = base.normalized_mem(insn, ops[0], item["espDelta"])
                if dest is None:
                    continue
                value = base.source_constant(insn, ops[1], item["regs"])
                if value not in target_vas:
                    continue

                alloc = None
                free = None
                context = [row(insn)]
                for nxt in items[i + 1 : min(len(items), i + LOOKAHEAD + 1)]:
                    ninsn = nxt["insn"]
                    context.append(row(ninsn))
                    if (
                        dest["baseRegId"]
                        and dest["baseRegId"] != X86_REG_ESP
                        and base.writes_register(ninsn, dest["baseRegId"])
                    ):
                        break
                    nops = getattr(ninsn, "operands", ())
                    if ninsn.id != X86_INS_MOV or len(nops) < 2 or nops[0].type != X86_OP_MEM:
                        continue
                    ndest = base.normalized_mem(ninsn, nops[0], nxt["espDelta"])
                    nvalue = base.source_constant(ninsn, nops[1], nxt["regs"])
                    if base.same_row(dest, ndest, 4) and nvalue is not None and alloc is None:
                        alloc = {
                            "instruction": row(ninsn),
                            "value": int(nvalue) & 0xFFFFFFFF,
                            "valueHex": f"0x{int(nvalue) & 0xFFFFFFFF:08x}",
                        }
                    if base.same_row(dest, ndest, 8) and nvalue is not None and free is None:
                        free = {
                            "instruction": row(ninsn),
                            "value": int(nvalue) & 0xFFFFFFFF,
                            "valueHex": f"0x{int(nvalue) & 0xFFFFFFFF:08x}",
                        }
                if alloc is not None:
                    meta = target_vas[value]
                    candidates.append(
                        {
                            "constructedNameBufferVa": f"0x{value:08x}",
                            "constructorBufferInitialMappedCString": meta.get("initialMappedCString"),
                            "section": sec["name"],
                            "namePointerStore": row(insn),
                            "rowAddressing": {
                                "baseReg": dest["baseReg"],
                                "normalizedNameDisp": dest["normalizedDisp"],
                                "normalizedAllocDisp": dest["normalizedDisp"] + 4,
                                "normalizedFreeDisp": dest["normalizedDisp"] + 8,
                                "segmentReg": dest["segmentReg"],
                            },
                            "plus4Store": alloc,
                            "plus8Store": free,
                            "straightLineContext": context,
                        }
                    )

        def flush():
            nonlocal block, regs, esp_delta
            if block:
                analyze(block)
            block = []
            regs = {}
            esp_delta = 0

        for insn in base.disassembler().disasm(blob, sec["va"]):
            if insn.id == 0:
                flush()
                continue
            snapshot = {"insn": insn, "regs": dict(regs), "espDelta": esp_delta}
            block.append(snapshot)
            esp_known = base.known_esp_update(insn)
            esp_delta = base.update_state(insn, regs, esp_delta)
            if (
                not esp_known
                or insn.group(CS_GRP_CALL)
                or insn.group(CS_GRP_JUMP)
                or insn.group(CS_GRP_RET)
            ):
                flush()
        flush()
    return candidates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--constructor-proof", type=Path, required=True)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = args.exe.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != base.EXPECTED_SHA256:
        raise SystemExit(f"unexpected current-client SHA-256 {sha}")

    constructor = json.loads(args.constructor_proof.read_text())
    if constructor.get("format") != CONSTRUCTOR_FORMAT:
        raise SystemExit(f"unexpected constructor proof format {constructor.get('format')!r}")
    if constructor.get("client", {}).get("sha256") != sha:
        raise SystemExit("constructor proof/client SHA-256 mismatch")
    if str(constructor.get("client", {}).get("revision")) != str(args.revision):
        raise SystemExit("constructor proof/client revision mismatch")

    target_vas = {}
    for item in constructor.get("destinationBuffers", []):
        va = int(item["va"], 16)
        if va in target_vas:
            raise SystemExit(f"duplicate constructor destination {item['va']}")
        target_vas[va] = item
    if not target_vas:
        raise SystemExit("constructor proof has no destination buffers")

    image_base, sections = base.parse_pe(raw)
    candidates = scan(raw, sections, target_vas)
    candidates.sort(key=lambda x: int(x["namePointerStore"]["address"], 16))

    counts = {f"0x{x:08x}": 0 for x in target_vas}
    for item in candidates:
        counts[item["constructedNameBufferVa"]] += 1

    result = {
        "format": FORMAT,
        "authority": "current Plutonium CDN object only; comparative structural discovery, not historical-retail authority",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": sha,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "constructorProof": {
            "format": constructor["format"],
            "path": str(args.constructor_proof),
            "sha256": hashlib.sha256(args.constructor_proof.read_bytes()).hexdigest(),
            "destinationBufferCount": len(target_vas),
        },
        "candidateCount": len(candidates),
        "candidateCountByBuffer": counts,
        "candidates": candidates,
        "status": "comparative_constructed_name_rows_only_no_xzoneinfo_identity_or_winner_promoted",
        "proofBoundary": (
            "A candidate requires a decoded straight-line store of an exact constructor destination-buffer pointer at row +0 "
            "and a concrete value at the same effective row +4, with the row-base register stable; +8 is retained when concrete. "
            "This tests the server-proven 12-byte shape without importing server flag values or priorities. A shape match does not "
            "prove the current-client row is XZoneInfo, does not name its +4/+8 fields, and cannot select a historical-retail winner."
        ),
    }

    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({
        "candidateCount": len(candidates),
        "candidateCountByBuffer": counts,
        "proofBytes": len(payload),
        "proofSha256": hashlib.sha256(payload).hexdigest(),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
