#!/usr/bin/env python3
"""Comparative-only CFG/caller/data-flow probe for selected T6 current-client targets.

The target addresses come from the exact current-client zone-xref probe. This
script does not infer historical-retail function identity or Technique winners.
It records decoded control-flow, direct-call edges, and local register/memory
provenance around exact stored-zone-mask instructions in the SHA-classified
current client.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, deque
from pathlib import Path

from capstone import (
    Cs,
    CS_ARCH_X86,
    CS_GRP_CALL,
    CS_GRP_JUMP,
    CS_GRP_RET,
    CS_MODE_32,
)
from capstone.x86_const import X86_INS_JMP, X86_OP_IMM, X86_OP_MEM, X86_OP_REG


EXPECTED_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS = {
    "mask_005225f0": 0x005225F0,
    "mask_006ad580": 0x006AD580,
    "mask_005fb2f0": 0x005FB2F0,
    "mask_00682340": 0x00682340,
    "shared_00424f00": 0x00424F00,
    "shared_004c0830": 0x004C0830,
}
MASKS = {0x3FFFFFFF, 0x17FFFFFF}
MAX_CFG_INSNS = 4096
MAX_LOCAL_SPAN = 0x10000
MAX_BLOCK_INSNS = 512
TRACE_BACK = 32
TRACE_FORWARD = 32


class ProbeError(RuntimeError):
    pass


def parse_pe(raw: bytes):
    if raw[:2] != b"MZ":
        raise ProbeError("not MZ")
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    if raw[pe : pe + 4] != b"PE\0\0":
        raise ProbeError("not PE")
    coff = pe + 4
    machine, nsec, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", raw, coff)
    if machine != 0x14C:
        raise ProbeError(f"not i386: 0x{machine:04x}")
    opt = coff + 20
    if struct.unpack_from("<H", raw, opt)[0] != 0x10B:
        raise ProbeError("not PE32")
    image_base = struct.unpack_from("<I", raw, opt + 28)[0]
    sec_off = opt + opt_size
    sections = []
    for i in range(nsec):
        o = sec_off + i * 40
        name = raw[o : o + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        virtual_size, rva, raw_size, raw_off = struct.unpack_from("<IIII", raw, o + 8)
        characteristics = struct.unpack_from("<I", raw, o + 36)[0]
        sections.append(
            {
                "name": name,
                "va": image_base + rva,
                "virtualSize": virtual_size,
                "rawSize": raw_size,
                "rawOffset": raw_off,
                "executable": bool(characteristics & 0x20000000),
            }
        )
    return image_base, sections


def section_for_va(sections, va: int):
    for sec in sections:
        if sec["va"] <= va < sec["va"] + sec["rawSize"]:
            return sec
    return None


def va_to_offset(sections, va: int):
    sec = section_for_va(sections, va)
    if sec is None:
        return None
    return sec["rawOffset"] + (va - sec["va"])


def is_executable_va(sections, va: int) -> bool:
    sec = section_for_va(sections, va)
    return bool(sec and sec["executable"])


def make_md(*, detail=True):
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = detail
    return md


def decode_one(raw: bytes, sections, va: int):
    off = va_to_offset(sections, va)
    if off is None or not is_executable_va(sections, va):
        return None
    sec = section_for_va(sections, va)
    end = min(off + 15, sec["rawOffset"] + sec["rawSize"])
    insns = list(make_md().disasm(raw[off:end], va, count=1))
    return insns[0] if insns else None


def reg_name(insn, reg_id: int):
    return insn.reg_name(reg_id) if reg_id else None


def operand_json(insn, op):
    if op.type == X86_OP_REG:
        return {"type": "reg", "reg": reg_name(insn, op.reg)}
    if op.type == X86_OP_IMM:
        return {"type": "imm", "value": int(op.imm) & 0xFFFFFFFF, "hex": f"0x{int(op.imm) & 0xFFFFFFFF:08x}"}
    if op.type == X86_OP_MEM:
        mem = op.mem
        return {
            "type": "mem",
            "segment": reg_name(insn, mem.segment),
            "base": reg_name(insn, mem.base),
            "index": reg_name(insn, mem.index),
            "scale": int(mem.scale),
            "disp": int(mem.disp),
            "dispHex": f"0x{int(mem.disp) & 0xFFFFFFFF:08x}",
        }
    return {"type": f"other:{op.type}"}


def insn_json(insn):
    try:
        reads, writes = insn.regs_access()
    except Exception:
        reads, writes = (), ()
    return {
        "address": f"0x{insn.address:08x}",
        "size": insn.size,
        "bytes": insn.bytes.hex(),
        "mnemonic": insn.mnemonic,
        "opStr": insn.op_str,
        "operands": [operand_json(insn, op) for op in getattr(insn, "operands", ())],
        "regsRead": [reg_name(insn, r) for r in reads],
        "regsWrite": [reg_name(insn, r) for r in writes],
    }


def direct_target(insn):
    if not getattr(insn, "operands", None):
        return None
    op = insn.operands[0]
    return (int(op.imm) & 0xFFFFFFFF) if op.type == X86_OP_IMM else None


def build_cfg(raw: bytes, sections, start: int):
    queue = deque([start])
    block_starts = {start}
    decoded = {}
    blocks = {}
    direct_calls = []
    branch_edges = []
    external_jumps = []
    ret_sites = []
    truncated = False

    while queue and len(decoded) < MAX_CFG_INSNS:
        block = queue.popleft()
        if block in blocks:
            continue
        va = block
        block_rows = []
        seen_in_block = set()
        for _ in range(MAX_BLOCK_INSNS):
            if va in seen_in_block:
                break
            seen_in_block.add(va)
            if va in decoded and va != block:
                branch_edges.append({"from": f"0x{block_rows[-1]['addressInt']:08x}" if block_rows else f"0x{block:08x}", "to": f"0x{va:08x}", "kind": "joins_decoded"})
                break
            insn = decode_one(raw, sections, va)
            if insn is None:
                break
            decoded[va] = insn
            j = insn_json(insn)
            j["addressInt"] = va
            block_rows.append(j)
            if insn.group(CS_GRP_CALL):
                target = direct_target(insn)
                direct_calls.append(
                    {
                        "site": f"0x{va:08x}",
                        "target": None if target is None else f"0x{target:08x}",
                        "direct": target is not None,
                        "targetExecutable": bool(target is not None and is_executable_va(sections, target)),
                    }
                )
            if insn.group(CS_GRP_RET):
                ret_sites.append(f"0x{va:08x}")
                break
            if insn.group(CS_GRP_JUMP):
                target = direct_target(insn)
                is_unconditional = insn.id == X86_INS_JMP
                if target is not None and is_executable_va(sections, target):
                    if abs(target - start) <= MAX_LOCAL_SPAN:
                        branch_edges.append({"from": f"0x{va:08x}", "to": f"0x{target:08x}", "kind": "jmp" if is_unconditional else "jcc"})
                        if target not in block_starts:
                            block_starts.add(target)
                            queue.append(target)
                    else:
                        external_jumps.append({"site": f"0x{va:08x}", "target": f"0x{target:08x}", "kind": "direct_jump_outside_local_span"})
                elif target is not None:
                    external_jumps.append({"site": f"0x{va:08x}", "target": f"0x{target:08x}", "kind": "direct_jump_nonexec"})
                else:
                    external_jumps.append({"site": f"0x{va:08x}", "target": None, "kind": "indirect_jump"})
                if is_unconditional:
                    break
                fall = va + insn.size
                branch_edges.append({"from": f"0x{va:08x}", "to": f"0x{fall:08x}", "kind": "fallthrough"})
                if fall not in block_starts:
                    block_starts.add(fall)
                    queue.append(fall)
                break
            va += insn.size
            if abs(va - start) > MAX_LOCAL_SPAN:
                external_jumps.append({"site": f"0x{insn.address:08x}", "target": f"0x{va:08x}", "kind": "linear_fallthrough_outside_local_span"})
                break
        else:
            truncated = True
        blocks[block] = block_rows

    if queue or len(decoded) >= MAX_CFG_INSNS:
        truncated = True

    # Strip private integer helper before serialization.
    clean_blocks = []
    for block, rows in sorted(blocks.items()):
        clean = []
        for item in rows:
            item = dict(item)
            item.pop("addressInt", None)
            clean.append(item)
        clean_blocks.append({"start": f"0x{block:08x}", "instructions": clean})

    addresses = sorted(decoded)
    return {
        "start": f"0x{start:08x}",
        "instructionCount": len(decoded),
        "basicBlockCount": len(blocks),
        "minDecodedVa": None if not addresses else f"0x{addresses[0]:08x}",
        "maxDecodedVa": None if not addresses else f"0x{addresses[-1]:08x}",
        "retSites": ret_sites,
        "directCalls": direct_calls,
        "branchEdges": branch_edges,
        "externalOrIndirectJumps": external_jumps,
        "truncated": truncated,
        "locallyClosedCfg": bool(ret_sites) and not truncated and not external_jumps,
        "blocks": clean_blocks,
    }, blocks


def global_inbound_calls(raw: bytes, sections, wanted: set[int]):
    inbound = {x: [] for x in wanted}
    md = make_md()
    md.skipdata = True
    for sec in sections:
        if not sec["executable"]:
            continue
        blob = raw[sec["rawOffset"] : sec["rawOffset"] + sec["rawSize"]]
        for insn in md.disasm(blob, sec["va"]):
            if not insn.group(CS_GRP_CALL):
                continue
            target = direct_target(insn)
            if target in inbound:
                inbound[target].append(insn_json(insn))
    return inbound


def block_insns(blocks):
    out = {}
    md = make_md()
    # Rehydrate only the fields necessary for local trace from serialized block rows
    # is undesirable; instead this function is unused and kept out intentionally.
    return out


def mask_immediates(insn):
    found = set()
    for op in getattr(insn, "operands", ()):
        if op.type == X86_OP_IMM:
            value = int(op.imm) & 0xFFFFFFFF
            if value in MASKS:
                found.add(value)
    return sorted(found)


def trace_masks(raw: bytes, sections, cfg_blocks):
    results = []
    for block_start, serialized_rows in cfg_blocks.items():
        # Decode the exact block again so register-access metadata is native Capstone data.
        insns = []
        va = block_start
        for _ in range(len(serialized_rows)):
            insn = decode_one(raw, sections, va)
            if insn is None:
                break
            insns.append(insn)
            va += insn.size
        for idx, insn in enumerate(insns):
            masks = mask_immediates(insn)
            if not masks:
                continue
            dest_reg = None
            if getattr(insn, "operands", None) and insn.operands[0].type == X86_OP_REG:
                dest_reg = insn.operands[0].reg

            origin = None
            origin_index = None
            if dest_reg:
                for j in range(idx - 1, max(-1, idx - TRACE_BACK - 1), -1):
                    prev = insns[j]
                    try:
                        _, writes = prev.regs_access()
                    except Exception:
                        writes = ()
                    if dest_reg in writes:
                        origin = insn_json(prev)
                        origin_index = j
                        break

            forward_uses = []
            overwritten_at = None
            if dest_reg:
                for j in range(idx + 1, min(len(insns), idx + TRACE_FORWARD + 1)):
                    nxt = insns[j]
                    try:
                        reads, writes = nxt.regs_access()
                    except Exception:
                        reads, writes = (), ()
                    if dest_reg in reads:
                        forward_uses.append(insn_json(nxt))
                    if dest_reg in writes:
                        overwritten_at = insn_json(nxt)
                        break

            results.append(
                {
                    "blockStart": f"0x{block_start:08x}",
                    "maskInstruction": insn_json(insn),
                    "maskValues": [f"0x{x:08x}" for x in masks],
                    "destinationRegister": reg_name(insn, dest_reg) if dest_reg else None,
                    "nearestPriorWriterInBlock": origin,
                    "nearestPriorWriterDistanceInstructions": None if origin_index is None else idx - origin_index,
                    "forwardUsesBeforeOverwrite": forward_uses,
                    "firstOverwriteAfterMask": overwritten_at,
                    "contextBefore": [insn_json(x) for x in insns[max(0, idx - 12) : idx]],
                    "contextAfter": [insn_json(x) for x in insns[idx + 1 : min(len(insns), idx + 13)]],
                }
            )
    return results


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

    image_base, sections = parse_pe(raw)
    missing = [f"0x{x:08x}" for x in TARGETS.values() if not is_executable_va(sections, x)]
    if missing:
        raise SystemExit(f"target addresses not executable in classified client: {missing}")

    inbound = global_inbound_calls(raw, sections, set(TARGETS.values()))
    target_docs = []
    summary = {}
    for name, va in TARGETS.items():
        cfg, blocks = build_cfg(raw, sections, va)
        masks = trace_masks(raw, sections, blocks)
        doc = {
            "name": name,
            "address": f"0x{va:08x}",
            "globalInboundDirectCalls": inbound[va],
            "cfg": cfg,
            "maskDataflow": masks,
        }
        target_docs.append(doc)
        outbound = Counter(
            x["target"]
            for x in cfg["directCalls"]
            if x["direct"] and x["target"] is not None
        )
        summary[name] = {
            "address": f"0x{va:08x}",
            "globalInboundDirectCallCount": len(inbound[va]),
            "cfgInstructionCount": cfg["instructionCount"],
            "basicBlockCount": cfg["basicBlockCount"],
            "retCount": len(cfg["retSites"]),
            "externalOrIndirectJumpCount": len(cfg["externalOrIndirectJumps"]),
            "truncated": cfg["truncated"],
            "locallyClosedCfg": cfg["locallyClosedCfg"],
            "maskSiteCount": len(masks),
            "topOutboundDirectCallTargets": [
                {"target": target, "count": count}
                for target, count in outbound.most_common(12)
            ],
        }

    # Exact direct relationships among the six selected candidates.
    selected = {f"0x{x:08x}": name for name, x in TARGETS.items()}
    selected_edges = []
    for doc in target_docs:
        for edge in doc["cfg"]["directCalls"]:
            if edge["target"] in selected:
                selected_edges.append(
                    {
                        "fromCandidate": doc["name"],
                        "site": edge["site"],
                        "toCandidate": selected[edge["target"]],
                        "target": edge["target"],
                    }
                )

    output = {
        "format": "t6-current-client-candidate-cfg-dataflow-probe-v1",
        "authority": "current Plutonium CDN object only; comparative discovery, not historical-retail authority",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": sha256,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "targets": target_docs,
        "selectedCandidateDirectCallEdges": selected_edges,
        "summary": summary,
        "status": "comparative_cfg_dataflow_only_no_function_identity_or_winner_promoted",
        "proofBoundary": (
            "Decoded current-client call/branch/register/memory evidence is exact for the SHA-classified current client only. "
            "A direct call target, local CFG, mask, memory operand, recurrence, or resemblance to server/OpenBO2 code does not "
            "establish historical-retail DB function identity, precedence, or any Technique winner. CFG traversal is explicitly "
            "bounded; locallyClosedCfg is only a statement about this bounded traversal, not a source-level function proof."
        ),
    }
    payload = (json.dumps(output, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({"proofBytes": len(payload), "proofSha256": hashlib.sha256(payload).hexdigest(), "summary": summary, "selectedCandidateDirectCallEdges": selected_edges}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
