#!/usr/bin/env python3
"""Locate exact target T6 XModels across an expanded retail XFile corpus.

Runs the strict t6_xmodel_target_probe_v1 rules against every supplied stream and
aggregates exact ownership by source hash.  This is designed for characters and
weapons whose dependencies cross `common`, faction, map, Zombies/SP and patch
zones.

No winning source is selected merely because a model appears more than once.
Multi-source identities are explicitly marked `requiresPrecedenceResolution`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_nonmap_corpus_census_v1 import collect_inputs
from t6_xmodel_target_probe_v1 import load_module, load_targets, probe_name


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--glob", default="*.expanded")
    ap.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--raw-parser", type=Path, required=True)
    ap.add_argument("--targets", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    streams = collect_inputs(args.inputs, args.glob, args.recursive)
    if not streams:
        raise ValueError("no expanded XFiles matched")
    targets = load_targets(args.targets)
    rawmod = load_module(args.raw_parser)

    source_rows = []
    by_name = {t["name"]: [] for t in targets}
    for stream in streams:
        data = stream.read_bytes()
        front = rawmod.parse_front(data)
        blocks = [int(x["bytes"]) for x in front["block_sizes"]]
        digest = hashlib.sha256(data).hexdigest()
        rows = [probe_name(data, t, rawmod, blocks) for t in targets]
        source_rows.append({
            "path": str(stream),
            "bytes": len(data),
            "sha256": digest,
            "assetCount": front.get("asset_count"),
            "results": rows,
        })
        for row in rows:
            if row["status"] == "exact_inline_xmodel":
                by_name[row["name"]].append({
                    "sourcePath": str(stream),
                    "sourceSha256": digest,
                    "rawStructOffset": row["rawStructOffset"],
                    "fixedRecordSha256": row["fixedRecordSha256"],
                    "fixedPlusNameSha256": row["fixedPlusNameSha256"],
                    "numBones": row["numBones"],
                    "numRootBones": row["numRootBones"],
                    "numSurfs": row["numSurfs"],
                    "numLods": row["numLods"],
                })

    target_rows = []
    for target in targets:
        hits = by_name[target["name"]]
        source_hashes = sorted({h["sourceSha256"] for h in hits})
        target_rows.append({
            "role": target.get("role"),
            "name": target["name"],
            "required": bool(target.get("required", True)),
            "expectedClass": target.get("expectedClass"),
            "status": "retail-resolved" if hits else "unresolved",
            "exactSourceCount": len(source_hashes),
            "requiresPrecedenceResolution": len(source_hashes) > 1,
            "exactSources": hits,
        })

    required = [r for r in target_rows if r["required"]]
    unresolved = [r["name"] for r in required if r["status"] != "retail-resolved"]
    duplicates = [r["name"] for r in required if r["requiresPrecedenceResolution"]]
    out = {
        "format": "t6-xmodel-target-corpus-probe-v1",
        "authority": "direct expanded retail T6 XFile bytes",
        "targetSpec": {"path": str(args.targets), "sha256": sha256(args.targets)},
        "rawParser": {"path": str(args.raw_parser), "sha256": sha256(args.raw_parser)},
        "rules": {
            "perStreamValidation": "t6-xmodel-target-probe-v1",
            "exactIdentityRequired": True,
            "packedOrReusedNamesAreNotGuessed": True,
            "multipleExactSourcesDoNotImplicitlyChooseWinner": True,
        },
        "summary": {
            "streamsScanned": len(streams),
            "targets": len(target_rows),
            "requiredTargets": len(required),
            "resolvedRequiredTargets": len(required) - len(unresolved),
            "unresolvedRequiredTargets": unresolved,
            "requiredTargetsWithMultipleSources": duplicates,
            "allRequiredFoundSomewhere": not unresolved,
        },
        "targets": target_rows,
        "sources": source_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0 if not unresolved else 2


if __name__ == "__main__":
    raise SystemExit(main())
