#!/usr/bin/env python3
"""Resolve a T6 first-person benchmark against retained retail evidence.

The planner joins independently checkable evidence:
  benchmark spec
    -> exact raw XModel target probes
    -> provenance-pinned OAT T6 XModel descriptors/classification
    -> exact/normalized XAnim records.

External discovery references in the benchmark never count as retail proof.
Direct raw probes and OAT catalogs only count when tied to retained retail source
hashes.  `viewhands` classification is accepted from pinned OAT because that
classification is derived from native XModel structure, not filename heuristics.
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
            evidence.update({
                "evidenceKind": "direct-raw-xmodel",
                "probePath": str(path),
                "retailStreamSha256": source.get("sha256"),
            })
            by_name.setdefault(name, []).append(evidence)
    return by_name, sources


def load_oat_xmodels(paths: list[Path]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    sources = []
    for path in paths:
        doc = read_json(path)
        if doc.get("format") != "t6-oat-xmodel-catalog-v1":
            raise ValueError(f"{path}: not t6-oat-xmodel-catalog-v1")
        source = doc.get("source", {})
        source_sha = source.get("retailSourceSha256")
        if not isinstance(source_sha, str) or len(source_sha) != 64:
            raise ValueError(f"{path}: OAT catalog lacks pinned retail source SHA-256")
        sources.append({
            "path": str(path),
            "sha256": sha256(path),
            "zoneName": source.get("zoneName"),
            "retailSourceSha256": source_sha,
            "oatCommit": doc.get("producer", {}).get("commit"),
        })
        for row in doc.get("models", []):
            name = row.get("name")
            if not isinstance(name, str):
                continue
            evidence = dict(row)
            evidence.update({
                "evidenceKind": "pinned-oat-xmodel",
                "catalogPath": str(path),
                "retailStreamSha256": source_sha,
                "zoneName": source.get("zoneName"),
            })
            by_name.setdefault(name, []).append(evidence)
    return by_name, sources


def merge_evidence(*sources: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        for name, rows in source.items():
            out.setdefault(name, []).extend(rows)
    return out


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
        source_hash = sha256(path)
        sources.append({"path": str(path), "sha256": source_hash, "namedRecordCount": len(useful)})
        for item in useful:
            evidence = {
                "source": item["source"],
                "sourceSha256": source_hash,
                "format": item["record"].get("format"),
                "rawStructOffset": item["record"].get("raw_struct_offset", item["record"].get("rawStructOffset")),
                "numframes": item["record"].get("numframes", item["record"].get("numFrames")),
                "framerate": item["record"].get("framerate", item["record"].get("frameRate")),
                "serializedSha256": item["record"].get("serialized_sha256", item["record"].get("serializedSha256")),
                "normalized": item["record"].get("format") == "t6-xanim-normalized-v1",
            }
            by_name.setdefault(item["name"], []).append(evidence)
    return by_name, sources


EXPECTED_OAT_TYPES = {
    "viewhands": {"viewhands"},
    "human-third-person": {"animated"},
}


def class_validation(expected_class: str | None, hits: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = EXPECTED_OAT_TYPES.get(expected_class or "")
    oat_types = sorted({h.get("type") for h in hits if h.get("evidenceKind") == "pinned-oat-xmodel" and h.get("type")})
    if allowed is None:
        return {"required": False, "status": "not-required", "oatTypes": oat_types}
    if not oat_types:
        return {"required": True, "status": "unvalidated", "allowedOatTypes": sorted(allowed), "oatTypes": []}
    ok = all(t in allowed for t in oat_types)
    return {"required": True, "status": "validated" if ok else "contradiction", "allowedOatTypes": sorted(allowed), "oatTypes": oat_types}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--xmodel-probe", type=Path, action="append", default=[])
    ap.add_argument("--oat-xmodel-catalog", type=Path, action="append", default=[])
    ap.add_argument("--xanim-json", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    spec = read_json(args.spec)
    if spec.get("format") != "t6-first-person-benchmark-spec-v1":
        raise ValueError("unsupported benchmark spec")
    raw_models, raw_model_sources = load_model_probes(args.xmodel_probe)
    oat_models, oat_model_sources = load_oat_xmodels(args.oat_xmodel_catalog)
    model_evidence = merge_evidence(raw_models, oat_models)
    xanim_evidence, xanim_sources = load_xanims(args.xanim_json)

    model_rows = []
    for target in spec.get("models", []):
        name = target["name"]
        hits = model_evidence.get(name, [])
        expected_class = target.get("expectedClass")
        class_check = class_validation(expected_class, hits)
        raw_hit = any(h.get("evidenceKind") == "direct-raw-xmodel" for h in hits)
        oat_hit = any(h.get("evidenceKind") == "pinned-oat-xmodel" for h in hits)
        source_hashes = {h.get("retailStreamSha256") for h in hits if h.get("retailStreamSha256")}
        model_rows.append({
            "role": target.get("role"),
            "name": name,
            "required": bool(target.get("required", True)),
            "expectedClass": expected_class,
            "status": "retail-resolved" if hits else "unresolved",
            "directRawEvidence": raw_hit,
            "oatEvidence": oat_hit,
            "crossValidatedRawAndOat": raw_hit and oat_hit,
            "classValidation": class_check,
            "retailEvidenceCount": len(hits),
            "retailEvidence": hits,
            "requiresSourcePrecedenceSelection": len(source_hashes) > 1,
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
    class_unvalidated = [r["name"] for r in model_rows if r["required"] and r["classValidation"]["status"] == "unvalidated"]
    class_contradictions = [r["name"] for r in model_rows if r["required"] and r["classValidation"]["status"] == "contradiction"]

    identity_gate = not unresolved_models and not unresolved_core and family_count_ok
    model_class_gate = not class_unvalidated and not class_contradictions
    normalized_animation_gate = len(normalized_core) == len(core_rows) and bool(core_rows)
    ready_for_bundle_export = identity_gate and model_class_gate and normalized_animation_gate and not duplicate_layer_models

    next_actions = []
    if unresolved_models:
        next_actions.append({"action": "probe-or-dump-retail-xmodels", "identities": unresolved_models})
    if class_unvalidated:
        next_actions.append({"action": "run-pinned-oat-xmodel-catalog-for-structural-classification", "identities": class_unvalidated})
    if class_contradictions:
        next_actions.append({"action": "investigate-model-classification-contradiction", "identities": class_contradictions})
    if duplicate_layer_models:
        next_actions.append({"action": "resolve-base-patch-precedence", "identities": duplicate_layer_models})
    if unresolved_core:
        next_actions.append({"action": "retain-or-normalize-required-xanims", "identities": unresolved_core})
    if not family_count_ok:
        next_actions.append({"action": "recover-complete-animation-family", "prefix": prefix, "observed": len(family_names), "expectedAtLeast": expected_family_count})
    missing_normalized = [r["name"] for r in core_rows if r["status"] == "retail-resolved" and not r["hasNormalizedXAnim"]]
    if missing_normalized:
        next_actions.append({"action": "normalize-retail-xanims", "identities": missing_normalized})
    if identity_gate and model_class_gate:
        next_actions.append({"action": "run-character-bundle-export", "note": "export model/skeleton/material sidecars and v7 animations; dependency gates remain separate"})

    out = {
        "format": "t6-first-person-bundle-plan-v1",
        "benchmark": {"id": spec.get("id"), "title": spec.get("title"), "specPath": str(args.spec), "specSha256": sha256(args.spec)},
        "rules": {
            "externalDiscoveryEvidenceNeverCountsAsRetailResolution": True,
            "exactModelIdentityRequired": True,
            "exactAnimationIdentityRequired": True,
            "oatCatalogRequiresPinnedRetailSourceHash": True,
            "viewhandsClassificationUsesNativeOatStructuralRule": True,
            "patchLayerDuplicatesRemainExplicit": True,
            "normalizedXAnimRequiredBeforeBundleAnimationExport": True,
        },
        "sources": {
            "rawXmodelProbes": raw_model_sources,
            "oatXmodelCatalogs": oat_model_sources,
            "xanimArtifacts": xanim_sources,
        },
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
            "classUnvalidatedModels": class_unvalidated,
            "classContradictions": class_contradictions,
            "requiredCoreAnimations": len(core_rows),
            "resolvedCoreAnimations": sum(r["status"] == "retail-resolved" for r in core_rows),
            "normalizedCoreAnimations": len(normalized_core),
            "unresolvedCoreAnimations": unresolved_core,
            "familyCountSatisfied": family_count_ok,
            "retailIdentityGate": identity_gate,
            "modelClassGate": model_class_gate,
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
