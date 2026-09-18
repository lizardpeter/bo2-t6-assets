#!/usr/bin/env python3
"""Compact exact evidence from the persisted current-client zone-row sink proof.

This does no new semantic inference. It fail-closes on the expected source
format/client/sink and emits the small byte-derived subset needed for the next
reversal step: entry block, exact 12-byte stride sites, outbound calls, inbound
call sites, and every decoded inbound context containing immediate 0x8000.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FORMAT = "t6-current-client-zone-row-sink-probe-v1"
OUT_FORMAT = "t6-current-client-zone-row-sink-compact-v1"
CLIENT_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
SINK = "0x004174b0"
MAP_FLAG = 0x8000


def imm_values(row: dict) -> list[int]:
    out = []
    for op in row.get("operands") or []:
        if op.get("type") == "imm" and isinstance(op.get("value"), int):
            out.append(op["value"] & 0xFFFFFFFF)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = args.source.read_bytes()
    src_sha = hashlib.sha256(raw).hexdigest()
    doc = json.loads(raw)

    if doc.get("format") != FORMAT:
        raise SystemExit(f"unexpected source format {doc.get('format')!r}")
    if doc.get("client", {}).get("sha256") != CLIENT_SHA256:
        raise SystemExit("unexpected source client SHA-256")
    if doc.get("sink", {}).get("address") != SINK:
        raise SystemExit("unexpected sink address")

    cfg = doc["sink"]["cfg"]
    blocks = cfg.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise SystemExit("source sink CFG has no blocks")

    entry = [x for x in blocks if x.get("start") == SINK]
    if len(entry) != 1:
        raise SystemExit(f"expected exactly one sink entry block, got {len(entry)}")

    stride = doc["sink"].get("exactStride12Evidence")
    if not isinstance(stride, list):
        raise SystemExit("source lacks exactStride12Evidence")

    inbound = doc.get("inboundDirectCalls")
    if not isinstance(inbound, list):
        raise SystemExit("source lacks inboundDirectCalls")

    map_contexts = []
    inbound_sites = []
    for call in inbound:
        site = call.get("call", {}).get("address")
        if not site:
            raise SystemExit("inbound row lacks call address")
        preceding = call.get("precedingInstructions")
        if not isinstance(preceding, list):
            raise SystemExit(f"{site}: missing precedingInstructions")
        inbound_sites.append(
            {
                "callSite": site,
                "section": call.get("section"),
                "precedingInstructionCount": len(preceding),
                "strictMapRowCandidates": call.get("mapFlag8000RowCandidates") or [],
            }
        )
        hits = []
        for i, insn in enumerate(preceding):
            if MAP_FLAG in imm_values(insn):
                hits.append(
                    {
                        "instruction": insn,
                        "contextBefore": preceding[max(0, i - 10):i],
                        "contextAfter": preceding[i + 1:min(len(preceding), i + 11)],
                    }
                )
        if hits:
            map_contexts.append(
                {
                    "callSite": site,
                    "section": call.get("section"),
                    "hits": hits,
                }
            )

    summary = doc.get("summary") or {}
    if summary.get("inboundDirectCallCount") != len(inbound):
        raise SystemExit("inbound count mismatch")
    if summary.get("stride12EvidenceCount") != len(stride):
        raise SystemExit("stride evidence count mismatch")

    out = {
        "format": OUT_FORMAT,
        "source": {
            "path": str(args.source),
            "bytes": len(raw),
            "sha256": src_sha,
            "format": doc["format"],
        },
        "client": doc["client"],
        "sink": SINK,
        "sourceSummary": summary,
        "entryBlock": entry[0],
        "exactStride12Evidence": stride,
        "topOutboundDirectCallTargets": doc["sink"].get("topOutboundDirectCallTargets") or [],
        "inboundCalls": inbound_sites,
        "inboundImmediate8000Contexts": map_contexts,
        "strictMapFlag8000RowCandidates": doc.get("mapFlag8000RowCandidates") or [],
        "proofBoundary": (
            "This file is a lossless selection of fields from the SHA-validated "
            "current-client sink proof. Immediate-0x8000 context is reported only "
            "as decoded operand evidence; it is not promoted to a map row unless "
            "the source strict candidate set already admits it. No source symbol, "
            "historical-retail equivalence, priority rule, or Technique winner is inferred."
        ),
    }
    payload = (json.dumps(out, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({
        "sourceBytes": len(raw),
        "sourceSha256": src_sha,
        "entryInstructionCount": len(entry[0].get("instructions") or []),
        "stride12EvidenceCount": len(stride),
        "inboundDirectCallCount": len(inbound),
        "inboundCallsitesWithImmediate8000": len(map_contexts),
        "strictMapFlag8000RowCandidateCount": len(out["strictMapFlag8000RowCandidates"]),
        "outBytes": len(payload),
        "outSha256": hashlib.sha256(payload).hexdigest(),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
