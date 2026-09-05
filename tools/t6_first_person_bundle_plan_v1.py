#!/usr/bin/env python3
"""Resolve a T6 first-person benchmark against retained retail evidence.

The planner joins three independently checkable things:
  benchmark spec -> exact XModel target probes -> exact/normalized XAnim records.

It never promotes external discovery references.  A model is retail-resolved only
when a t6-xmodel-target-probe-v1 input contains status=exact_inline_xmodel for the
exact name.  An animation is retail-resolved only when it occurs in an explicitly
supplied XAnim JSON artifact (raw proof output or normalized XAnim sidecar).

This is intentionally a closure planner rather than an exporter.  Its output is
a machine-readable list of what can be exported now and what exact dependency is
still missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_inputs(paths: Iterable[Path]) -> list[Path]:
    out = []
    for path in paths:
        if path.is_dir():
            out.extend(sorted(p for p in path.rglob("*.json") if p.is_file()))
        else:
            out.append(path)
    seen = set()
    unique = []
    for path in out:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def collect_named_records(value: Any, source: Path, out: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str) and name:
            out.append({"name": name, "record": value, "source": str(source)})
        for child in value.values():
            collect_named_records(child, source, out)
    elif isinstance(value, list):
        for child in value:
            collect_named_records(child, source, out)


def load_model_probes(paths: list[Path]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    sources = []
    for path in paths:
        doc = read_json(path)
        if doc.get("format") != "t6-xmodel-target-probe-v1":
            raise ValueError(f"{path}: not t6-xmodel-target-probe-v1")
        source = doc.get("source", {})
        sources.append({
            "path": str(path),
            "sha256": sha256(path),
            "retailStreamSha256": source.get("sha256"),
            "retailStreamBytes": source.get("bytes"),
        })
        for row in doc.get("targets", []):
            if row.get("status") != "exact_inline_xmodel":
                continue
            name = row.get("name")
            if not isinstance(name, str):
                continue
            evidence = dict(row)
            evidence["probePath"] = str(path)
            evidence["retailStreamSha256"] = source.get("sha256")
            by_name.setdefault(name, []).append(evidence)
    return by_name, sources


def load_xanims(paths: list[Path]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    sources = []
    for path in json_inputs(paths):
        try:
            doc = read_json(path)
        except Exception:
            continue
        records: list[dict[str, Any]] = []
        if isinstance(doc, dict) and doc.get("format") == "t6-xanim-normalized-v1" and isinstance(doc.get("name"), str):
            records.append({"name": doc["name"], "record": doc, "source": str(path)})
        else:
            collect_named_records(doc, path, records)
        useful = [r for r in records if r["name"].startswith("viewmodel_") or str(r["record"].get("format", "")).startswith("t6-xanim")]
        if not useful:
            continue
        sources.append({"path": str(path), "sha256": sha256(path), "namedRecordCount": len(useful)})
        for item in useful:
            evidence = {
                "source": item["source"],
                "sourceSha256": sha256(path),
                "format": item["record"].get("format"),
                "rawStructOffset": item["record"].get("raw_struct_offset", item["record"].get("rawStructOffset")),
                "numframes": item["record"].get("numframes", item["record"].get("numFrames")),
                "framerate": item["record"].get("framerate", item["record"].get("frameRate")),
                "serializedSha256": item["record"].get("serialized_sha256", item["record"].get("serializedSha256")),
                "normalized": item["record"].get("format") == "t6-xanim-normalized-v1",
            }
            by_name.setdefault(item["name"], []).append(evidence)
    return by_name, sources


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--xmodel-probe", type=Path, action="append", default=[])
    ap.add_argument("--xanim-json", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    spec = read_json(args.spec)
    if spec.get("format") != "t6-first-person-benchmark-spec-v1":
        raise ValueError("unsupported benchmark spec")
    model_evidence, model_sources = load_model_probes(args.xmodel_probe)
    xanim_evidence, xanim_sources = load_xanims(args.xanim_json)

    model_rows = []
    for target in spec.get("models", []):
        name = target["name"]
        hits = model_evidence.get(name, [])
        model_rows.append({
            "role": target.get("role"),
            "name": name,
            "required": bool(target.get("required", True)),
            "expectedClass": target.get("expectedClass"),
            "status": "retail-resolved" if hits else "unresolved",
            "retailEvidenceCount": len(hits),
            "retailEvidence": hits,
            "requiresSourcePrecedenceSelection": len({h.get("retailStreamSha256") for h in hits}) > 1,
        })

    anim_spec = spec.get("animations", {})
    prefix = str(anim_spec.get("familyPrefix", ""))
    family_names = sorted(name for name in xanim_evidence if name.startswith(prefix))
    expected_family_count = int(anim_spec.get("retailExpectedFamilyCount", 0))
    core_rows = []
    for name in anim_spec.get("requiredCore", []):
        hits = xanim_evidence.get(name, [])
        core_rows.append({
            "name": name,
            "status": "retail-resolved" if hits else "unresolved",
            "evidenceCount": len(hits),
            "hasNormalizedXAnim": any(h.get("normalized") for h in hits),
            "evidence": hits,
        })

    unresolved_models = [r["name"] for r in model_rows if r["required"] and r["status"] != "retail-resolved"]
    unresolved_core = [r["name"] for r in core_rows if r["status"] != "retail-resolved"]
    family_count_ok = len(family_names) >= expected_family_count if expected_family_count else True
    normalized_core = [r["name"] for r in core_rows if r["hasNormalizedXAnim"]]
    duplicate_layer_models = [r["name"] for r in model_rows if r["requiresSourcePrecedenceSelection"]]

    identity_gate = not unresolved_models and not unresolved_core and family_count_ok
    normalized_animation_gate = len(normalized_core) == len(core_rows) and bool(core_rows)
    ready_for_bundle_export = identity_gate and normalized_animation_gate and not duplicate_layer_models

    next_actions = []
    if unresolved_models:
        next_actions.append({"action": "probe-retail-xmodels", "identities": unresolved_models})
    if duplicate_layer_models:
        next_actions.append({"action": "resolve-base-patch-precedence", "identities": duplicate_layer_models})
    if unresolved_core:
        next_actions.append({"action": "retain-or-normalize-required-xanims", "identities": unresolved_core})
    if not family_count_ok:
        next_actions.append({"action": "recover-complete-animation-family", "prefix": prefix, "observed": len(family_names), "expectedAtLeast": expected_family_count})
    missing_normalized = [r["name"] for r in core_rows if r["status"] == "retail-resolved" and not r["hasNormalizedXAnim"]]
    if missing_normalized:
        next_actions.append({"action": "normalize-retail-xanims", "identities": missing_normalized})
    if identity_gate:
        next_actions.append({"action": "run-character-bundle-export", "note": "export model/skeleton/material sidecars and v7 animations; dependency gates remain separate"})

    out = {
        "format": "t6-first-person-bundle-plan-v1",
        "benchmark": {"id": spec.get("id"), "title": spec.get("title"), "specPath": str(args.spec), "specSha256": sha256(args.spec)},
        "rules": {
            "externalDiscoveryEvidenceNeverCountsAsRetailResolution": True,
            "exactModelIdentityRequired": True,
            "exactAnimationIdentityRequired": True,
            "patchLayerDuplicatesRemainExplicit": True,
            "normalizedXAnimRequiredBeforeBundleAnimationExport": True,
        },
        "sources": {"xmodelProbes": model_sources, "xanimArtifacts": xanim_sources},
        "models": model_rows,
        "animations": {
            "familyPrefix": prefix,
            "expectedFamilyCount": expected_family_count,
            "observedFamilyCount": len(family_names),
            "familyCountSatisfied": family_count_ok,
            "observedFamilyNames": family_names,
            "requiredCore": core_rows,
        },
        "candidateDependencies": spec.get("dependencyCandidates", {}),
        "closureGates": spec.get("closureGates", []),
        "summary": {
            "requiredModels": sum(r["required"] for r in model_rows),
            "resolvedRequiredModels": sum(r["required"] and r["status"] == "retail-resolved" for r in model_rows),
            "unresolvedRequiredModels": unresolved_models,
            "requiredCoreAnimations": len(core_rows),
            "resolvedCoreAnimations": sum(r["status"] == "retail-resolved" for r in core_rows),
            "normalizedCoreAnimations": len(normalized_core),
            "unresolvedCoreAnimations": unresolved_core,
            "familyCountSatisfied": family_count_ok,
            "retailIdentityGate": identity_gate,
            "normalizedAnimationGate": normalized_animation_gate,
            "readyForBundleExport": ready_for_bundle_export,
        },
        "nextActions": next_actions,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0 if ready_for_bundle_export else 2


if __name__ == "__main__":
    raise SystemExit(main())
