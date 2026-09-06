#!/usr/bin/env python3
"""Validate canonical per-asset T6 extraction proof manifests.

The purpose of this format is to keep discovery, extraction, decoding and
semantic proof separate.  A file existing on disk is not evidence that an asset
is semantically closed.  Ambiguous/unresolved dependencies fail closed, and a
claim at a later lifecycle stage requires evidence for every earlier stage.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FORMAT = "t6-asset-proof-manifest-v1"
LIFECYCLE = [
    "discovered",
    "uniquely_resolved",
    "raw_extracted",
    "decoded",
    "dependency_closed",
    "exported",
    "semantically_validated",
    "packaged_audited",
]
DEPENDENCY_STATUSES = {"resolved", "unresolved", "ambiguous", "not-applicable"}
VALIDATION_STATUSES = {"pass", "fail", "pending"}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class AssetProofError(RuntimeError):
    pass


def _text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssetProofError(f"{label} must be non-empty text")
    return value


def _evidence_list(value, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and x.strip() for x in value):
        raise AssetProofError(f"{label} must be a non-empty string list")
    return value


def _sha(value, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise AssetProofError(f"{label} must be a 64-hex SHA-256")
    return value.lower()


def validate(document: dict) -> dict:
    if not isinstance(document, dict):
        raise AssetProofError("asset proof must be an object")
    if document.get("format") != FORMAT:
        raise AssetProofError(f"unexpected asset proof format {document.get('format')!r}")

    asset = document.get("asset")
    if not isinstance(asset, dict):
        raise AssetProofError("asset must be an object")
    asset_id = _text(asset.get("id"), "asset.id")
    asset_type = _text(asset.get("type"), "asset.type")
    _text(asset.get("name"), "asset.name")

    stage = document.get("lifecycleStage")
    if stage not in LIFECYCLE:
        raise AssetProofError(f"invalid lifecycleStage {stage!r}")
    stage_index = LIFECYCLE.index(stage)

    stages = document.get("stages")
    if not isinstance(stages, dict):
        raise AssetProofError("stages must be an object")
    for required_stage in LIFECYCLE[: stage_index + 1]:
        row = stages.get(required_stage)
        if not isinstance(row, dict):
            raise AssetProofError(f"claimed lifecycle requires stages.{required_stage}")
        if row.get("status") != "pass":
            raise AssetProofError(f"stages.{required_stage}.status must be pass")
        _evidence_list(row.get("evidence"), f"stages.{required_stage}.evidence")
    for future_stage in LIFECYCLE[stage_index + 1 :]:
        row = stages.get(future_stage)
        if isinstance(row, dict) and row.get("status") == "pass":
            raise AssetProofError(
                f"stages.{future_stage} cannot pass while lifecycleStage is only {stage}"
            )

    sources = document.get("sources")
    if not isinstance(sources, list) or not sources:
        raise AssetProofError("sources must be a non-empty list")
    source_ids: set[str] = set()
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            raise AssetProofError(f"sources[{i}] is not an object")
        sid = _text(source.get("id"), f"sources[{i}].id")
        if sid in source_ids:
            raise AssetProofError(f"duplicate source id {sid!r}")
        source_ids.add(sid)
        _text(source.get("kind"), f"sources[{i}].kind")
        sha = source.get("sha256")
        evidence_ref = source.get("evidenceRef")
        if sha is None and not evidence_ref:
            raise AssetProofError(f"sources[{i}] requires sha256 or evidenceRef")
        if sha is not None:
            _sha(sha, f"sources[{i}].sha256")
        if evidence_ref is not None:
            _text(evidence_ref, f"sources[{i}].evidenceRef")

    dependencies = document.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise AssetProofError("dependencies must be a list")
    dependency_counts = {"resolved": 0, "unresolved": 0, "ambiguous": 0, "not-applicable": 0}
    dep_ids: set[str] = set()
    for i, dep in enumerate(dependencies):
        if not isinstance(dep, dict):
            raise AssetProofError(f"dependencies[{i}] is not an object")
        dep_id = _text(dep.get("id"), f"dependencies[{i}].id")
        if dep_id in dep_ids:
            raise AssetProofError(f"duplicate dependency id {dep_id!r}")
        dep_ids.add(dep_id)
        status = dep.get("status")
        if status not in DEPENDENCY_STATUSES:
            raise AssetProofError(f"dependency {dep_id!r} has invalid status {status!r}")
        dependency_counts[status] += 1
        _text(dep.get("type"), f"dependency {dep_id!r} type")
        if status in {"resolved", "not-applicable"}:
            _evidence_list(dep.get("evidence"), f"dependency {dep_id!r} evidence")

    if stage_index >= LIFECYCLE.index("dependency_closed"):
        bad = dependency_counts["unresolved"] + dependency_counts["ambiguous"]
        if bad:
            raise AssetProofError(
                f"dependency_closed claim contains {bad} unresolved/ambiguous dependencies"
            )

    outputs = document.get("outputs", [])
    if not isinstance(outputs, list):
        raise AssetProofError("outputs must be a list")
    if stage_index >= LIFECYCLE.index("exported") and not outputs:
        raise AssetProofError("exported-or-later lifecycle requires outputs[]")
    for i, output in enumerate(outputs):
        if not isinstance(output, dict):
            raise AssetProofError(f"outputs[{i}] is not an object")
        _text(output.get("kind"), f"outputs[{i}].kind")
        if output.get("sha256") is not None:
            _sha(output["sha256"], f"outputs[{i}].sha256")
        if output.get("bytes") is not None and (not isinstance(output["bytes"], int) or output["bytes"] < 0):
            raise AssetProofError(f"outputs[{i}].bytes must be a non-negative integer")
        if not output.get("path") and not output.get("sha256") and not output.get("evidenceRef"):
            raise AssetProofError(f"outputs[{i}] requires path, sha256, or evidenceRef")

    validations = document.get("validations", [])
    if not isinstance(validations, list):
        raise AssetProofError("validations must be a list")
    pass_count = 0
    fail_count = 0
    pending_count = 0
    validation_ids: set[str] = set()
    for i, check in enumerate(validations):
        if not isinstance(check, dict):
            raise AssetProofError(f"validations[{i}] is not an object")
        cid = _text(check.get("id"), f"validations[{i}].id")
        if cid in validation_ids:
            raise AssetProofError(f"duplicate validation id {cid!r}")
        validation_ids.add(cid)
        status = check.get("status")
        if status not in VALIDATION_STATUSES:
            raise AssetProofError(f"validation {cid!r} has invalid status {status!r}")
        if status == "pass":
            pass_count += 1
            _evidence_list(check.get("evidence"), f"validation {cid!r} evidence")
        elif status == "fail":
            fail_count += 1
        else:
            pending_count += 1

    if stage_index >= LIFECYCLE.index("semantically_validated"):
        if fail_count or pending_count:
            raise AssetProofError("semantically_validated claim cannot contain failed/pending validations")
        if pass_count == 0:
            raise AssetProofError("semantically_validated claim requires at least one passed validation")

    exact_claim = document.get("exactClaim", False)
    if not isinstance(exact_claim, bool):
        raise AssetProofError("exactClaim must be boolean")
    if exact_claim and stage_index < LIFECYCLE.index("semantically_validated"):
        raise AssetProofError("exactClaim requires semantically_validated lifecycle")
    if exact_claim and (dependency_counts["unresolved"] or dependency_counts["ambiguous"] or fail_count or pending_count):
        raise AssetProofError("exactClaim requires zero unresolved/ambiguous dependencies and zero failed/pending validations")

    _text(document.get("proofBoundary"), "proofBoundary")
    return {
        "format": "t6-asset-proof-summary-v1",
        "assetId": asset_id,
        "assetType": asset_type,
        "lifecycleStage": stage,
        "lifecycleOrdinal": stage_index,
        "exactClaim": exact_claim,
        "sourceCount": len(sources),
        "dependencyCounts": dependency_counts,
        "outputCount": len(outputs),
        "validationCounts": {"pass": pass_count, "fail": fail_count, "pending": pending_count},
        "failClosed": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    doc = json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    summary = validate(doc)
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
