#!/usr/bin/env python3
"""Exact current-client xref/data-flow probe for the runtime zone table classifier.

The SHA-classified current client has already proven:
- per-zone runtime record stride: 0x4c bytes;
- classifier is stored at record offset +0x40;
- table base arithmetic uses 0x01804908 + index*0x4c;
- classifier storage address is therefore 0x01804948 + index*0x4c.

This probe globally inventories executable reads/writes of those exact table
addresses and follows classifier loads locally into comparisons/masks/calls.
It does not import server symbol names or precedence semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from capstone import Cs, CsError, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg

EXPECTED_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TABLE_BASE = 0x01804908
CLASSIFIER_BASE = 0x01804948
ZONE_INDEX_GLOBAL = 0x0143329C
STRIDE = 0x4C
LOOKBACK = 14
LOOKAHEAD = 18


def insn_json(insn):
    return cfg.insn_json(insn)


def decode_exec(raw: bytes, sections):
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    md.skipdata = True
    out = []
    for sec in sections:
        if not sec["executable"]:
            continue
        blob = raw[sec["rawOffset"] : sec["rawOffset"] + sec["rawSize"]]
        for ins in md.disasm(blob, sec["va"]):
            try:
                _ = ins.operands
            except CsError:
                continue
            # Skip Capstone SKIPDATA pseudo-instructions.
            if not ins.bytes or ins.mnemonic == ".byte":
                continue
            out.append(ins)
    out.sort(key=lambda x: x.address)
    return out


def mem_matches(insn, disp: int):
    result = []
    for idx, op in enumerate(getattr(insn, "operands", ())):
        if op.type == X86_OP_MEM and (int(op.mem.disp) & 0xFFFFFFFF) == disp:
            result.append(idx)
    return result


def imm_matches(insn, value: int):
    result = []
    for idx, op in enumerate(getattr(insn, "operands", ())):
        if op.type == X86_OP_IMM and (int(op.imm) & 0xFFFFFFFF) == value:
            result.append(idx)
    return result


def written_register(insn):
    ops = getattr(insn, "operands", ())
    if not ops:
        return None
    if ops[0].type == X86_OP_REG:
        try:
            _, writes = insn.regs_access()
        except CsError:
            return None
        if ops[0].reg in writes:
            return insn.reg_name(ops[0].reg)
    return None


def classify_mem_access(insn, operand_index: int):
    try:
        _, writes = insn.regs_access()
    except CsError:
        writes = ()
    op = insn.operands[operand_index]
    if op.type != X86_OP_MEM:
        return "unknown"
    # Memory destination as first operand is normally a write; instructions like
    # cmp/test only read memory and never report a memory register write.
    if operand_index == 0 and insn.mnemonic not in {
        "cmp", "test", "push", "call", "jmp", "bt", "bts", "btr", "btc"
    }:
        return "write_or_rmw"
    return "read"


def local_flow(instructions, index: int, loaded_reg: str | None):
    before = [insn_json(x) for x in instructions[max(0, index - LOOKBACK) : index]]
    after_raw = instructions[index + 1 : min(len(instructions), index + LOOKAHEAD + 1)]
    flow = []
    if loaded_reg:
        reg_id = None
        for op in instructions[index].operands:
            if op.type == X86_OP_REG and instructions[index].reg_name(op.reg) == loaded_reg:
                reg_id = op.reg
                break
        for ins in after_raw:
            try:
                reads, writes = ins.regs_access()
            except CsError:
                reads, writes = (), ()
            if reg_id is not None and reg_id in reads:
                flow.append(insn_json(ins))
            if reg_id is not None and reg_id in writes:
                # Include overwrite if it also consumed the old value.
                if reg_id in reads and (not flow or flow[-1]["address"] != f"0x{ins.address:08x}"):
                    flow.append(insn_json(ins))
                break
    return before, [insn_json(x) for x in after_raw], flow


def nearest_stride_setup(instructions, index: int):
    out = []
    for ins in instructions[max(0, index - LOOKBACK) : index]:
        if STRIDE in [int(op.imm) & 0xFFFFFFFF for op in getattr(ins, "operands", ()) if op.type == X86_OP_IMM]:
            out.append(insn_json(ins))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = args.exe.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    if sha256 != EXPECTED_SHA256:
        raise SystemExit(f"unexpected current-client SHA-256 {sha256}")

    image_base, sections = cfg.parse_pe(raw)
    insns = decode_exec(raw, sections)

    xrefs = []
    for i, ins in enumerate(insns):
        hits = []
        for label, disp in (
            ("runtime_zone_table_base", TABLE_BASE),
            ("runtime_zone_classifier_base", CLASSIFIER_BASE),
            ("runtime_zone_index_global", ZONE_INDEX_GLOBAL),
        ):
            for op_index in mem_matches(ins, disp):
                hits.append((label, disp, op_index, "memory"))
            for op_index in imm_matches(ins, disp):
                hits.append((label, disp, op_index, "immediate"))
        if not hits:
            continue

        for label, value, op_index, kind in hits:
            loaded_reg = written_register(ins) if kind == "memory" else None
            before, after, flow = local_flow(insns, i, loaded_reg)
            xrefs.append(
                {
                    "label": label,
                    "valueHex": f"0x{value:08x}",
                    "kind": kind,
                    "operandIndex": op_index,
                    "access": classify_mem_access(ins, op_index) if kind == "memory" else "immediate",
                    "instruction": insn_json(ins),
                    "loadedRegister": loaded_reg,
                    "nearestStride0x4cSetup": nearest_stride_setup(insns, i),
                    "contextBefore": before,
                    "contextAfter": after,
                    "loadedRegisterFlowUntilOverwrite": flow,
                }
            )

    classifier_reads = [
        x
        for x in xrefs
        if x["label"] == "runtime_zone_classifier_base"
        and x["kind"] == "memory"
        and x["access"] == "read"
    ]
    classifier_writes = [
        x
        for x in xrefs
        if x["label"] == "runtime_zone_classifier_base"
        and x["kind"] == "memory"
        and x["access"] != "read"
    ]

    out = {
        "format": "t6-current-client-runtime-zone-table-xref-probe-v1",
        "authority": "SHA-classified current Plutonium client only",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": sha256,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "knownGeometry": {
            "runtimeZoneTableBase": f"0x{TABLE_BASE:08x}",
            "classifierFieldBase": f"0x{CLASSIFIER_BASE:08x}",
            "classifierOffset": 0x40,
            "recordStride": STRIDE,
            "zoneIndexGlobal": f"0x{ZONE_INDEX_GLOBAL:08x}",
        },
        "xrefs": xrefs,
        "summary": {
            "xrefCount": len(xrefs),
            "classifierReadCount": len(classifier_reads),
            "classifierWriteOrRmwCount": len(classifier_writes),
            "classifierReadAddresses": [x["instruction"]["address"] for x in classifier_reads],
            "classifierWriteAddresses": [x["instruction"]["address"] for x in classifier_writes],
        },
        "status": "exact_current_client_runtime_zone_table_xrefs_only_no_source_symbol_or_precedence_promoted",
        "proofBoundary": (
            "The table geometry and classifier storage are prior exact current-client evidence. "
            "This probe adds exact decoded executable xrefs and local register flow for the same "
            "SHA-classified client. A classifier read, mask, comparison, call adjacency, or similarity "
            "to dedicated-server code does not by itself identify DB_GetZonePriority/DB_OverrideAsset, "
            "establish historical-retail behavior, or select any Technique winner."
        ),
    }

    payload = (json.dumps(out, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(
        json.dumps(
            {
                "proofBytes": len(payload),
                "proofSha256": hashlib.sha256(payload).hexdigest(),
                **out["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
