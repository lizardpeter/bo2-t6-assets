#!/usr/bin/env python3
"""Census source-stored T6 GfxImage metadata for the v4 unresolved image set.

Input metadata must come from the pinned OAT diagnostic logger.  This tool never
computes GfxImage hashes from names and never queries IPAKs.  Every unresolved
v4 image must have at least one native owner record; if multiple physical owners
exist, their runtime identity tuple must agree exactly before promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

FORMAT = "t6-nuketown-native-image-metadata-census-v1"
V4_FORMAT = "t6-nuketown-production-texture-dependency-census-v4"
MARKER = "T6_IMAGE_META_V1|"
ROW_RE = re.compile(
    r"T6_IMAGE_META_V1\|name=(.*?)"
    r"\|hash=(\d+)"
    r"\|streaming=(\d+)"
    r"\|streamedPartCount=(\d+)"
    r"\|part0HashRaw=(\d+)"
    r"\|part0Hash29=(\d+)"
    r"\|width=(\d+)"
    r"\|height=(\d+)"
    r"\|depth=(\d+)"
    r"\|baseSize=(\d+)"
    r"\|loadedSize=(\d+)"
)


class CensusError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise CensusError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise CensusError(f"{path}: top level is not an object")
    return doc, raw


def unresolved_names(v4: dict) -> list[str]:
    if v4.get("format") != V4_FORMAT:
        raise CensusError(f"unexpected v4 format {v4.get('format')!r}")
    summary = v4.get("summary") or {}
    if not (
        int(summary.get("materialUniqueImageCount", -1)) == 423
        and int(summary.get("materialCoveredByKnownExactSourceCount", -1)) == 76
        and int(summary.get("materialMissingFromKnownExactSourceCount", -1)) == 347
    ):
        raise CensusError(f"v4 exact-source population drift: {summary}")
    rows = v4.get("missingProductionImages")
    if not isinstance(rows, list) or len(rows) != 347:
        raise CensusError("v4 missingProductionImages is not the exact 347-row unresolved set")
    names = [str(row.get("image") or "") for row in rows]
    if any(not name for name in names) or len(set(names)) != 347:
        raise CensusError("v4 unresolved image identities are empty or duplicated")
    if "$identitynormalmap" in names:
        raise CensusError("v4 unresolved set incorrectly still contains $identitynormalmap")
    return sorted(names)


def parse_log(label: str, path: Path) -> tuple[list[dict], bytes]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    rows: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if MARKER not in line:
            continue
        match = ROW_RE.search(line)
        if not match:
            raise CensusError(f"{path}:{line_no}: malformed metadata marker: {line!r}")
        name, *nums = match.groups()
        values = [int(x) for x in nums]
        row = {
            "owner": label,
            "name": name,
            "hash": values[0],
            "streaming": values[1],
            "streamedPartCount": values[2],
            "part0HashRaw": values[3],
            "part0Hash29": values[4],
            "width": values[5],
            "height": values[6],
            "depth": values[7],
            "baseSize": values[8],
            "loadedSize": values[9],
            "line": line_no,
        }
        if row["part0Hash29"] != (row["part0HashRaw"] & 0x1FFFFFFF):
            raise CensusError(f"{path}:{line_no}: 29-bit streamed hash mask mismatch")
        if row["streaming"] not in (0, 1):
            raise CensusError(f"{path}:{line_no}: non-boolean streaming field {row['streaming']}")
        if row["streamedPartCount"] == 0 and (row["part0HashRaw"] or row["part0Hash29"]):
            raise CensusError(f"{path}:{line_no}: zero streamedPartCount with nonzero part0 hash")
        rows.append(row)
    if not rows:
        raise CensusError(f"{path}: no {MARKER} rows")
    return rows, raw


def identity_tuple(row: dict) -> tuple[int, ...]:
    return (
        int(row["hash"]),
        int(row["streaming"]),
        int(row["streamedPartCount"]),
        int(row["part0HashRaw"]),
        int(row["part0Hash29"]),
        int(row["width"]),
        int(row["height"]),
        int(row["depth"]),
        int(row["baseSize"]),
        int(row["loadedSize"]),
    )


def build(v4_path: Path, log_specs: list[str]) -> dict:
    v4, v4_raw = load_json(v4_path)
    targets = unresolved_names(v4)
    target_set = set(targets)

    by_name: dict[str, list[dict]] = defaultdict(list)
    inputs = []
    physical_metadata_rows = 0
    for spec in log_specs:
        if "=" not in spec:
            raise CensusError(f"--log must be LABEL=PATH, got {spec!r}")
        label, raw_path = spec.split("=", 1)
        if not label or any(x["label"] == label for x in inputs):
            raise CensusError(f"empty/duplicate log label {label!r}")
        path = Path(raw_path)
        rows, raw = parse_log(label, path)
        inputs.append({"label": label, "path": str(path), "bytes": len(raw), "sha256": sha256(raw), "metadataRowCount": len(rows)})
        physical_metadata_rows += len(rows)
        seen_in_owner: dict[str, tuple[int, ...]] = {}
        for row in rows:
            name = row["name"]
            sig = identity_tuple(row)
            old = seen_in_owner.get(name)
            if old is not None and old != sig:
                raise CensusError(f"{label}: conflicting duplicate native metadata rows for {name!r}")
            seen_in_owner[name] = sig
            if name in target_set:
                by_name[name].append(row)

    missing = sorted(target_set - set(by_name))
    if missing:
        raise CensusError(f"native metadata missing {len(missing)}/347 targets: {missing[:20]!r}")

    output_rows = []
    conflict_count = 0
    for name in targets:
        physical = by_name[name]
        sigs = {identity_tuple(row) for row in physical}
        if len(sigs) != 1:
            conflict_count += 1
            raise CensusError(
                f"native owners disagree for {name!r}: "
                + repr([(row['owner'], identity_tuple(row)) for row in physical])
            )
        canonical = physical[0]
        output_rows.append({
            "image": name,
            "owners": sorted({row["owner"] for row in physical}),
            "physicalOwnerRecordCount": len(physical),
            "hash": canonical["hash"],
            "streaming": bool(canonical["streaming"]),
            "streamedPartCount": canonical["streamedPartCount"],
            "part0HashRaw": canonical["part0HashRaw"],
            "part0Hash29": canonical["part0Hash29"],
            "width": canonical["width"],
            "height": canonical["height"],
            "depth": canonical["depth"],
            "baseSize": canonical["baseSize"],
            "loadedSize": canonical["loadedSize"],
            "sourceAuthority": "native-pinned-oat-loaded-t6-gfximage",
        })

    streaming = [row for row in output_rows if row["streaming"]]
    positive_parts = [row for row in output_rows if row["streamedPartCount"] > 0]
    exact_pair_candidates = [row for row in output_rows if row["streaming"] and row["streamedPartCount"] > 0]
    zero_name_hash = [row for row in output_rows if row["hash"] == 0]
    zero_part_hash = [row for row in exact_pair_candidates if row["part0Hash29"] == 0]
    duplicate_owner = [row for row in output_rows if len(row["owners"]) > 1]

    return {
        "format": FORMAT,
        "map": "mp_nuketown_2020",
        "source": {
            "v4Census": {"path": str(v4_path), "bytes": len(v4_raw), "sha256": sha256(v4_raw)},
            "metadataLogs": inputs,
            "metadataAuthority": "fields read directly from loaded T6::GfxImage before Image conversion",
        },
        "summary": {
            "targetCount": 347,
            "metadataClosedTargetCount": len(output_rows),
            "missingTargetCount": 0,
            "conflictTargetCount": conflict_count,
            "physicalMetadataRowCountAllImages": physical_metadata_rows,
            "targetPhysicalOwnerRecordCount": sum(row["physicalOwnerRecordCount"] for row in output_rows),
            "duplicateOwnerTargetCount": len(duplicate_owner),
            "streamingTargetCount": len(streaming),
            "nonStreamingTargetCount": len(output_rows) - len(streaming),
            "positiveStreamedPartCountTargetCount": len(positive_parts),
            "exactPairCandidateTargetCount": len(exact_pair_candidates),
            "zeroGfxImageHashTargetCount": len(zero_name_hash),
            "zeroPart0Hash29ExactPairCandidateCount": len(zero_part_hash),
            "uniqueExactPairCandidateCount": len({(row['hash'], row['part0Hash29']) for row in exact_pair_candidates}),
            "uniquePart0Hash29CandidateCount": len({row['part0Hash29'] for row in exact_pair_candidates}),
        },
        "rows": output_rows,
        "proofBoundary": (
            "Every promoted field is read directly from a T6 GfxImage loaded by pinned OAT 9dca965 from an exact SHA-pinned FastFile. "
            "No filename hashing, IPAK search, name similarity, dimensions-based substitution, or payload inference occurs in this census."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v4-census", type=Path, required=True)
    ap.add_argument("--log", action="append", default=[], required=True, help="LABEL=PATH")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.v4_census, args.log)
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({"out": str(args.out), "bytes": len(payload), "sha256": sha256(payload), **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
