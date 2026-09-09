#!/usr/bin/env python3
"""Census exact residual texture-row sets for Nuketown missing layered components.

Diagnostic only: this proves row membership/fields after exact known-row
subtraction. It intentionally does not promote multi-row source order.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from t6_nuketown_layered_texture_transform_census_v3 import (
    TARGETS, EXPECTED_OCCURRENCES, ProofError, canonical, generated_name,
    load_json, load_rows, parse_compound, sha256, source_name,
)


def row_set_signature(rows: list[dict]) -> str:
    return sha256(canonical(sorted(rows, key=lambda r: canonical(r))))


def build(material_root: Path, universe_path: Path) -> dict:
    universe, universe_raw = load_json(universe_path)
    if universe.get("format") != "t6-nuketown-exact-layered-material-universe-v1":
        raise ProofError("unexpected exact layered universe format")
    layered = universe.get("layeredMaterials")
    if not isinstance(layered, list) or len(layered) != 120 or len(set(layered)) != 120:
        raise ProofError("expected 120 unique layered Materials")

    parsed = []
    referenced = set()
    for identity in layered:
        tokens, components, storage = parse_compound(identity)
        parsed.append((identity, tokens, components, storage))
        referenced.update(components)
    if len(referenced) != 83:
        raise ProofError(f"referenced component census changed: {len(referenced)}")

    cache = {}
    for identity in sorted(referenced):
        path = material_root / f"{identity}.json"
        cache[identity] = load_rows(path) if path.is_file() else None
    missing = {k for k, v in cache.items() if v is None}
    if missing != TARGETS:
        raise ProofError(f"standalone-missing set changed: {sorted(missing)!r}")

    counts = Counter()
    occurrences = defaultdict(list)
    known_rows_checked = 0
    target_bearing = 0
    multi_missing_materials = 0

    for identity, tokens, components, storage in parsed:
        generated_path = material_root / f"{storage}.json"
        if not generated_path.is_file():
            raise ProofError(f"missing generated Material {storage}")
        generated_rows, generated_sha, generated_bytes = load_rows(generated_path)
        by_name = defaultdict(list)
        for gi, row in enumerate(generated_rows):
            name = row.get("name")
            if not isinstance(name, str) or not name:
                raise ProofError(f"{identity}: generated row {gi} lacks exact name")
            by_name[name].append((gi, row))

        consumed = set()
        unknown = []
        for layer, component in enumerate(components):
            source = cache[component]
            if source is None:
                unknown.append((layer, component))
                counts[component] += 1
                continue
            for si, src in enumerate(source[0]):
                src_name = src.get("name")
                if not isinstance(src_name, str) or not src_name:
                    raise ProofError(f"{component}: source row {si} lacks exact name")
                expected_name = generated_name(src_name, layer)
                matches = by_name.get(expected_name, [])
                if len(matches) != 1:
                    raise ProofError(f"{identity}: exact known row {expected_name!r} match count {len(matches)}")
                gi, actual = matches[0]
                if gi in consumed:
                    raise ProofError(f"{identity}: generated row {gi} consumed twice")
                expected = dict(src)
                expected["name"] = expected_name
                if canonical(expected) != canonical(actual):
                    raise ProofError(f"{identity}: non-name change in known row {expected_name!r}")
                consumed.add(gi)
                known_rows_checked += 1

        residual = [(gi, row) for gi, row in enumerate(generated_rows) if gi not in consumed]
        if not unknown:
            if residual:
                raise ProofError(f"{identity}: all-known Material has {len(residual)} residual rows")
            continue

        target_bearing += 1
        if len(unknown) > 1:
            multi_missing_materials += 1
        if not residual:
            raise ProofError(f"{identity}: missing-layer Material has no residual rows")

        groups = []
        if len(unknown) == 1:
            groups.append((unknown[0][0], unknown[0][1], residual))
        else:
            if any(layer == 0 for layer, _ in unknown):
                raise ProofError(f"{identity}: multi-missing fixture contains layer 0; suffix partition is ambiguous")
            assigned = set()
            for layer, component in unknown:
                suffix = str(layer)
                candidates = [
                    (gi, row) for gi, row in residual
                    if isinstance(row.get("name"), str) and row["name"].endswith(suffix)
                ]
                if not candidates:
                    raise ProofError(f"{identity}: missing layer {layer} has no suffix-matched residual rows")
                overlap = assigned.intersection(gi for gi, _ in candidates)
                if overlap:
                    raise ProofError(f"{identity}: suffix partition overlap {sorted(overlap)}")
                assigned.update(gi for gi, _ in candidates)
                groups.append((layer, component, candidates))
            if assigned != {gi for gi, _ in residual}:
                raise ProofError(f"{identity}: suffix partition does not cover all residual rows")

        for layer, component, candidates in groups:
            recovered = []
            for gi, row in candidates:
                name = row.get("name")
                if not isinstance(name, str):
                    raise ProofError(f"{identity}: residual row {gi} lacks string name")
                restored = dict(row)
                restored["name"] = source_name(name, layer)
                recovered.append(restored)
            occurrences[component].append({
                "generatedMaterial": identity,
                "storageIdentity": storage,
                "generatedMaterialSha256": generated_sha,
                "generatedMaterialBytes": generated_bytes,
                "layerIndex": layer,
                "token": tokens[layer],
                "generatedIndices": [gi for gi, _ in candidates],
                "recoveredRowsInGeneratedOrder": recovered,
                "recoveredGeneratedOrderSha256": sha256(canonical(recovered)),
                "recoveredRowSetSha256": row_set_signature(recovered),
                "semanticSequenceInGeneratedOrder": [r.get("semantic") for r in recovered],
                "nameSequenceInGeneratedOrder": [r.get("name") for r in recovered],
            })

    if dict(sorted(counts.items())) != EXPECTED_OCCURRENCES:
        raise ProofError(f"target occurrence census changed: {dict(sorted(counts.items()))!r}")

    targets = {}
    for component in sorted(TARGETS):
        rows = occurrences[component]
        if len(rows) != EXPECTED_OCCURRENCES[component]:
            raise ProofError(f"{component}: occurrence count mismatch")
        set_sigs = {r["recoveredRowSetSha256"] for r in rows}
        if len(set_sigs) != 1:
            raise ProofError(f"{component}: exact recovered row membership/fields disagree across occurrences")
        counts_here = {len(r["recoveredRowsInGeneratedOrder"]) for r in rows}
        if len(counts_here) != 1:
            raise ProofError(f"{component}: recovered texture count disagrees across occurrences")
        texture_count = next(iter(counts_here))
        targets[component] = {
            "textureCount": texture_count,
            "rowSetSha256": next(iter(set_sigs)),
            "occurrenceCount": len(rows),
            "occurrences": rows,
            "sourceOrderStatus": "closed-singleton" if texture_count == 1 else "OPEN-multi-row-order",
        }

    return {
        "format": "t6-nuketown-missing-layer-residual-probe-v1",
        "authority": {
            "materialUniverseSha256": sha256(universe_raw),
            "fastFile": universe["authority"]["fastFile"],
            "fastFileSha256": universe["authority"]["fastFileSha256"],
            "oatCommit": "9dca965366541504b71fa8cfb7ac049cb9b717e1",
        },
        "summary": {
            "exactLayeredMaterialCount": len(parsed),
            "referencedComponentCount": len(referenced),
            "knownRowExactMatchCount": known_rows_checked,
            "targetBearingGeneratedMaterialCount": target_bearing,
            "multiMissingGeneratedMaterialCount": multi_missing_materials,
            "targetLayerOccurrenceCount": sum(counts.values()),
            "targetCount": len(targets),
            "singletonTargetCount": sum(t["textureCount"] == 1 for t in targets.values()),
            "multiRowTargetCount": sum(t["textureCount"] > 1 for t in targets.values()),
        },
        "targetOccurrenceHistogram": dict(sorted(counts.items())),
        "targets": targets,
        "proofBoundary": (
            "Diagnostic row-set closure only. Exact known rows are subtracted by unique layer-renamed name with all fields unchanged. "
            "Multi-row target source order remains explicitly open; generated row order is retained only as evidence."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("material_root", type=Path)
    ap.add_argument("universe_json", type=Path)
    ap.add_argument("output_json", type=Path)
    args = ap.parse_args()
    doc = build(args.material_root, args.universe_json)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.output_json.write_text(payload, encoding="utf-8")
    print("RESIDUAL PROBE", json.dumps(doc["summary"], sort_keys=True))
    for name, target in doc["targets"].items():
        first = target["occurrences"][0]
        print("TARGET", name, "textures", target["textureCount"], "status", target["sourceOrderStatus"], "semantics", first["semanticSequenceInGeneratedOrder"], "names", first["nameSequenceInGeneratedOrder"])
    print("output_sha256=" + sha256(payload.encode()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
