#!/usr/bin/env python3
"""Exact current-client shared zone-row sink and built-in-map row probe.

Authority is limited to the SHA-classified current Plutonium revision 5346
client. The target 0x004174b0 is selected only because independently recovered
constructed 12-byte rows flow to it at multiple exact call sites.

The probe:
  * recovers a bounded CFG for 0x004174b0;
  * inventories every exact direct call to that target;
  * records call-site decoded context;
  * searches only those call-site contexts for byte-explicit ESP-row triples
    whose +4 field is 0x8000 and +8 field is 0;
  * traces a register-sourced row name to the nearest prior writer in the same
    decoded context when possible;
  * inventories exact 12-byte stride operations in the sink CFG.

No source symbol, XZoneInfo field name, priority rule, historical-retail
equivalence, or Technique winner is promoted by this probe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, deque
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_GRP_CALL, CS_MODE_32
from capstone.x86_const import (
    X86_INS_ADD,
    X86_INS_LEA,
    X86_INS_MOV,
    X86_OP_IMM,
    X86_OP_MEM,
    X86_OP_REG,
    X86_REG_ESP,
)

import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfgmod


EXPECTED_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
SINK = 0x004174B0
PREVIOUS = 72
MAP_FLAG = 0x00008000


def md():
    d = Cs(CS_ARCH_X86, CS_MODE_32)
    d.detail = True
    d.skipdata = True
    return d


def j(insn):
    return cfgmod.insn_json(insn)


def direct_target(insn):
    if not getattr(insn, "operands", None):
        return None
    op = insn.operands[0]
    if op.type != X86_OP_IMM:
        return None
    return int(op.imm) & 0xFFFFFFFF


def simple_esp_store(insn):
    ops = getattr(insn, "operands", ())
    if insn.id != X86_INS_MOV or len(ops) < 2 or ops[0].type != X86_OP_MEM:
        return None
    mem = ops[0].mem
    if mem.base != X86_REG_ESP or mem.index:
        return None
    src = ops[1]
    if src.type == X86_OP_IMM:
        source = {"kind": "immediate", "value": int(src.imm) & 0xFFFFFFFF, "valueHex": f"0x{int(src.imm) & 0xFFFFFFFF:08x}"}
    elif src.type == X86_OP_REG:
        source = {"kind": "register", "register": insn.reg_name(src.reg), "regId": int(src.reg)}
    elif src.type == X86_OP_MEM:
        source = {
            "kind": "memory",
            "base": insn.reg_name(src.mem.base) if src.mem.base else None,
            "index": insn.reg_name(src.mem.index) if src.mem.index else None,
            "scale": int(src.mem.scale),
            "disp": int(src.mem.disp),
            "dispHex": f"0x{int(src.mem.disp) & 0xFFFFFFFF:08x}",
        }
    else:
        source = {"kind": f"other:{src.type}"}
    return {"disp": int(mem.disp), "source": source, "instruction": j(insn)}


def nearest_prior_writer(context_insns, before_index, reg_id):
    for idx in range(before_index - 1, -1, -1):
        insn = context_insns[idx]
        try:
            _, writes = insn.regs_access()
        except Exception:
            writes = ()
        if reg_id in writes:
            return {"index": idx, "instruction": j(insn)}
    return None


def find_map_rows(context_insns):
    stores = []
    for idx, insn in enumerate(context_insns):
        st = simple_esp_store(insn)
        if st is not None:
            st["index"] = idx
            stores.append(st)

    candidates = []
    by_disp = {}
    for st in stores:
        by_disp.setdefault(st["disp"], []).append(st)

    for flag in stores:
        src = flag["source"]
        if src.get("kind") != "immediate" or src.get("value") != MAP_FLAG:
            continue
        name_disp = flag["disp"] - 4
        free_disp = flag["disp"] + 4
        names = [x for x in by_disp.get(name_disp, []) if x["index"] < flag["index"]]
        frees = [
            x for x in by_disp.get(free_disp, [])
            if x["index"] > flag["index"]
            and x["source"].get("kind") == "immediate"
            and x["source"].get("value") == 0
        ]
        if not names or not frees:
            continue
        name = names[-1]
        free = frees[0]
        trace = None
        nsrc = name["source"]
        if nsrc.get("kind") == "register":
            trace = nearest_prior_writer(context_insns, name["index"], nsrc["regId"])
        candidates.append(
            {
                "nameStore": name["instruction"],
                "nameSource": {k:v for k,v in nsrc.items() if k != "regId"},
                "nearestPriorNameRegisterWriter": trace,
                "flagStore": flag["instruction"],
                "flagHex": f"0x{MAP_FLAG:08x}",
                "freeStore": free["instruction"],
                "rowEspDispAtStores": name_disp,
            }
        )
    return candidates


def sink_stride_evidence(cfg_doc):
    rows = []
    for block in cfg_doc["blocks"]:
        for item in block["instructions"]:
            ops = item.get("operands", [])
            # Exact immediate 12 participating in ADD reg,12 or LEA reg,[reg+12].
            if item["mnemonic"] == "add" and len(ops) >= 2:
                if ops[0].get("type") == "reg" and ops[1].get("type") == "imm" and ops[1].get("value") == 12:
                    rows.append({"kind": "add-register-12", "instruction": item})
            if item["mnemonic"] == "lea" and len(ops) >= 2:
                mem = ops[1]
                if (
                    ops[0].get("type") == "reg"
                    and mem.get("type") == "mem"
                    and mem.get("disp") == 12
                    and mem.get("index") is None
                ):
                    rows.append({"kind": "lea-register-plus-12", "instruction": item})
            # Record multiply-by-12 forms where immediate operand is exact 12.
            if item["mnemonic"] == "imul":
                if any(op.get("type") == "imm" and op.get("value") == 12 for op in ops):
                    rows.append({"kind": "imul-by-12", "instruction": item})
    return rows


def scan_inbound(raw, sections):
    calls = []
    recent = deque(maxlen=PREVIOUS)
    for sec in sections:
        if not sec["executable"]:
            continue
        recent.clear()
        blob = raw[sec["rawOffset"]:sec["rawOffset"] + sec["rawSize"]]
        for insn in md().disasm(blob, sec["va"]):
            if insn.id == 0:
                recent.clear()
                continue
            if insn.group(CS_GRP_CALL) and direct_target(insn) == SINK:
                ctx = list(recent)
                map_rows = find_map_rows(ctx)
                calls.append(
                    {
                        "section": sec["name"],
                        "call": j(insn),
                        "precedingInstructions": [j(x) for x in ctx],
                        "mapFlagRowCandidates": map_rows,
                    }
                )
            recent.append(insn)
    return calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = args.exe.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != EXPECTED_SHA256:
        raise SystemExit(f"unexpected current-client SHA-256 {sha}")

    image_base, sections = cfgmod.parse_pe(raw)
    if not cfgmod.is_executable_va(sections, SINK):
        raise SystemExit("sink target is not executable")

    sink_cfg, _ = cfgmod.build_cfg(raw, sections, SINK)
    inbound = scan_inbound(raw, sections)
    stride = sink_stride_evidence(sink_cfg)

    map_candidates = []
    for call in inbound:
        for cand in call["mapFlagRowCandidates"]:
            map_candidates.append(
                {
                    "callSite": call["call"]["address"],
                    "section": call["section"],
                    **cand,
                }
            )

    outbound = Counter(
        row["target"]
        for row in sink_cfg["directCalls"]
        if row["direct"] and row["target"] is not None
    )

    result = {
        "format": "t6-current-client-zone-row-sink-probe-v1",
        "authority": "current Plutonium CDN object only; comparative exact-byte discovery, not historical-retail authority",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": sha,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "sink": {
            "address": f"0x{SINK:08x}",
            "cfg": sink_cfg,
            "exactStride12Evidence": stride,
            "topOutboundDirectCallTargets": [
                {"target": target, "count": count}
                for target, count in outbound.most_common(32)
            ],
        },
        "inboundDirectCalls": inbound,
        "summary": {
            "inboundDirectCallCount": len(inbound),
            "sinkInstructionCount": sink_cfg["instructionCount"],
            "sinkBasicBlockCount": sink_cfg["basicBlockCount"],
            "sinkRetCount": len(sink_cfg["retSites"]),
            "sinkExternalOrIndirectJumpCount": len(sink_cfg["externalOrIndirectJumps"]),
            "sinkCfgTruncated": sink_cfg["truncated"],
            "stride12EvidenceCount": len(stride),
            "mapFlag8000RowCandidateCount": len(map_candidates),
        },
        "mapFlag8000RowCandidates": map_candidates,
        "status": "comparative_sink_and_map_row_only_no_source_symbol_or_winner_promoted",
        "proofBoundary": (
            "0x004174b0 is selected only as the exact common direct-call target of independently recovered current-client "
            "constructed 12-byte rows. CFG instructions, direct-call edges, exact 12-byte arithmetic, and call-site stack "
            "stores are byte-derived from the SHA-classified current client. A 0x8000 row candidate requires an explicit "
            "ESP-relative name store followed at +4 by immediate 0x8000 and at +8 by immediate zero in the same decoded "
            "pre-call context. None of this assigns a source symbol, proves XZoneInfo field semantics, imports server "
            "priority rules, establishes historical-retail behavior, or selects any Technique winner."
        ),
    }

    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({
        "inboundDirectCallCount": len(inbound),
        "sinkInstructionCount": sink_cfg["instructionCount"],
        "sinkBasicBlockCount": sink_cfg["basicBlockCount"],
        "sinkRetCount": len(sink_cfg["retSites"]),
        "sinkExternalOrIndirectJumpCount": len(sink_cfg["externalOrIndirectJumps"]),
        "sinkCfgTruncated": sink_cfg["truncated"],
        "stride12EvidenceCount": len(stride),
        "mapFlag8000RowCandidateCount": len(map_candidates),
        "mapFlag8000RowCandidateSites": [x["callSite"] for x in map_candidates],
        "proofBytes": len(payload),
        "proofSha256": hashlib.sha256(payload).hexdigest(),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
