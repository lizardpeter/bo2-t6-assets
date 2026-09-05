#!/usr/bin/env python3
"""Fail-closed complete-player gate for T6 character extraction.

This sits above the existing first-person bundle planner.  It prevents a player
benchmark from being called complete merely because viewhands/weapon assets are
ready while the third-person full body is missing or partial.

Accepted evidence is deliberately explicit:
- first-person plan: t6-first-person-bundle-plan-v1
- full-body export: t6-character-bundle-v1 for the exact required XModel
- retail assembly semantics: t6-player-assembly-evidence-v1
- optional third-person animation ownership/compatibility evidence

Missing evidence keeps the corresponding gate open; nothing is inferred from
`_fb`, `viewhands`, or other filename conventions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-complete-player-bundle-gate-v1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def model_row(plan: dict, name: str) -> dict | None:
    for row in plan.get("models", []):
        if row.get("name") == name:
            return row
    return None


def verify_body_bundle(path: Path | None, required_name: str) -> dict:
    if path is None:
        return {"status": "missing", "valid": False}
    doc = read_json(path)
    if doc.get("format") != "t6-character-bundle-v1":
        raise ValueError(f"{path}: not t6-character-bundle-v1")
    identity = doc.get("identity", {})
    names = {identity.get("meshName"), identity.get("skeletonName")}
    names.discard(None)
    valid_identity = names == {required_name}
    summary = doc.get("summary", {})
    outputs = doc.get("outputs", [])
    kinds = {row.get("kind") for row in outputs if isinstance(row, dict)}
    valid_outputs = {"normalized-mesh", "normalized-skeleton", "bind-pose-gltf"}.issubset(kinds)
    return {
        "status": "validated" if valid_identity and valid_outputs else "invalid",
        "valid": valid_identity and valid_outputs,
        "path": str(path),
        "sha256": sha256(path),
        "identity": identity,
        "summary": summary,
        "requiredOutputKindsPresent": valid_outputs,
        "dependencySidecarCount": len(doc.get("dependencySidecars", [])),
    }


def verify_assembly(path: Path | None, requirements: dict) -> dict:
    if path is None:
        return {"status": "missing", "valid": False}
    doc = read_json(path)
    if doc.get("format") != "t6-player-assembly-evidence-v1":
        raise ValueError(f"{path}: not t6-player-assembly-evidence-v1")
    if doc.get("authority") != "retail":
        return {"status": "non-retail-evidence", "valid": False, "path": str(path), "sha256": sha256(path)}
    source_sha = doc.get("source", {}).get("sha256")
    if not isinstance(source_sha, str) or len(source_sha) != 64:
        return {"status": "unhashed-retail-source", "valid": False, "path": str(path), "sha256": sha256(path)}

    expected = requirements.get("semanticCandidate", {}).get("claims", {})
    observed = doc.get("claims", {})
    valid = (
        observed.get("playerModel") == expected.get("playerModel")
        and observed.get("viewModel") == expected.get("viewModel")
        and observed.get("headList") == expected.get("headList")
    )
    return {
        "status": "validated" if valid else "contradiction",
        "valid": valid,
        "path": str(path),
        "sha256": sha256(path),
        "sourceSha256": source_sha,
        "claims": observed,
    }


def verify_third_person_animations(path: Path | None, required_body: str) -> dict:
    if path is None:
        return {"status": "missing", "valid": False}
    doc = read_json(path)
    if doc.get("format") != "t6-third-person-animation-compatibility-v1":
        raise ValueError(f"{path}: not t6-third-person-animation-compatibility-v1")
    source_hashes = doc.get("retailSourceSha256", [])
    if isinstance(source_hashes, str):
        source_hashes = [source_hashes]
    valid_hashes = bool(source_hashes) and all(isinstance(x, str) and len(x) == 64 for x in source_hashes)
    valid = (
        doc.get("bodyModel") == required_body
        and doc.get("allRequiredTracksCompatible") is True
        and doc.get("ownershipResolvedFromRetail") is True
        and valid_hashes
    )
    return {
        "status": "validated" if valid else "invalid",
        "valid": valid,
        "path": str(path),
        "sha256": sha256(path),
        "observedAnimationCount": doc.get("animationCount"),
        "retailSourceSha256": source_hashes,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--requirements", type=Path, required=True)
    ap.add_argument("--first-person-plan", type=Path, required=True)
    ap.add_argument("--full-body-bundle", type=Path)
    ap.add_argument("--assembly-evidence", type=Path)
    ap.add_argument("--third-person-animation-evidence", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    req = read_json(args.requirements)
    if req.get("format") != "t6-complete-player-requirements-v1":
        raise ValueError("unsupported complete-player requirements format")
    plan = read_json(args.first_person_plan)
    if plan.get("format") != "t6-first-person-bundle-plan-v1":
        raise ValueError("unsupported first-person plan format")

    body_name = req["thirdPerson"]["fullBodyModel"]
    hands_name = req["firstPerson"]["viewhandsModel"]
    body_plan = model_row(plan, body_name)
    hands_plan = model_row(plan, hands_name)
    body_identity_gate = bool(body_plan and body_plan.get("status") == "retail-resolved")
    hands_identity_gate = bool(hands_plan and hands_plan.get("status") == "retail-resolved")
    first_person_gate = bool(plan.get("summary", {}).get("readyForBundleExport"))

    body_bundle = verify_body_bundle(args.full_body_bundle, body_name)
    assembly = verify_assembly(args.assembly_evidence, req)
    third_anims = verify_third_person_animations(args.third_person_animation_evidence, body_name)

    body_dependency_gate = bool(
        body_bundle.get("valid")
        and body_bundle.get("dependencySidecarCount", 0) >= 2
    )
    ready = all([
        body_identity_gate,
        hands_identity_gate,
        body_bundle.get("valid", False),
        body_dependency_gate,
        assembly.get("valid", False),
        third_anims.get("valid", False),
        first_person_gate,
    ])

    next_actions = []
    if not body_identity_gate:
        next_actions.append("resolve full-body XModel from retained retail source")
    if not body_bundle.get("valid"):
        next_actions.append("export exact full-body mesh+skeleton bundle")
    if body_bundle.get("valid") and not body_dependency_gate:
        next_actions.append("attach exact full-body material and image dependency sidecars")
    if not assembly.get("valid"):
        next_actions.append("retain retail faction player-assembly semantics: setmodel + setviewmodel + head list")
    if not third_anims.get("valid"):
        next_actions.append("resolve and compatibility-check the retail third-person player animation set")
    if not first_person_gate:
        next_actions.append("finish independent viewhands/weapon first-person bundle gates")

    out = {
        "format": FORMAT,
        "requirements": {
            "path": str(args.requirements),
            "sha256": sha256(args.requirements),
            "id": req.get("id"),
        },
        "firstPersonPlan": {
            "path": str(args.first_person_plan),
            "sha256": sha256(args.first_person_plan),
            "ready": first_person_gate,
        },
        "thirdPerson": {
            "fullBodyModel": body_name,
            "retailIdentityResolved": body_identity_gate,
            "bundle": body_bundle,
            "materialAndImageDependenciesAttached": body_dependency_gate,
            "assemblySemantics": assembly,
            "animationCompatibility": third_anims,
        },
        "firstPerson": {
            "viewhandsModel": hands_name,
            "retailIdentityResolved": hands_identity_gate,
            "bundlePlanReady": first_person_gate,
        },
        "summary": {
            "fullBodyIdentityGate": body_identity_gate,
            "fullBodyBundleGate": body_bundle.get("valid", False),
            "fullBodyDependencyGate": body_dependency_gate,
            "retailAssemblySemanticGate": assembly.get("valid", False),
            "thirdPersonAnimationGate": third_anims.get("valid", False),
            "firstPersonGate": first_person_gate,
            "readyForCompletePlayerBundle": ready,
        },
        "nextActions": next_actions,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
