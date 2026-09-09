#!/usr/bin/env python3
"""Close Nuketown layered texture rows without assuming component row order.

The retail corpus disproves stable component-relative ordering for six known
layer-1 tables. This verifier therefore binds every standalone-known row only by
its exact layer-renamed texture name, requires every non-name field to match
exactly, accounts for every generated row, and promotes a missing component only
when a target-bearing generated Material contains exactly one missing layer and
all exact occurrences recover the same singleton row.

It deliberately does not infer a universal generated texture-array sort rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


class ProofError(RuntimeError):
    pass


TARGETS = {
    "wpc/asphalt_road_dark_dec",
    "wpc/decal_concrete_clean_line",
    "wpc/decal_damage_asphalt_crack01",
    "wpc/decal_grunge_glue",
    "wpc/decal_grunge_mold01",
    "wpc/decal_signage_const_marking01",
    "wpc/decal_signage_const_marking02",
}
EXPECTED_OCCURRENCES = {
    "wpc/asphalt_road_dark_dec": 1,
    "wpc/decal_concrete_clean_line": 7,
    "wpc/decal_damage_asphalt_crack01": 1,
    "wpc/decal_grunge_glue": 2,
    "wpc/decal_grunge_mold01": 2,
    "wpc/decal_signage_const_marking01": 1,
    "wpc/decal_signage_const_marking02": 1,
}
EXPECTED_ORDER_ANOMALIES = {
    ("*169n_82n(wpc/intro_sewer_grate_02_dec:wpc/com_decal_puddle01)", "wpc/com_decal_puddle01", 1, (4, 1, 3)),
    ("*326n_368n(wpc/nt_2020_wall_sm_yellow_lt:wpc/nt_2020_floor_kitchen_02)", "wpc/nt_2020_floor_kitchen_02", 1, (5, 2, 4)),
    ("*45n_82n(wpc/al_muntaha_concrete:wpc/com_decal_puddle01)", "wpc/com_decal_puddle01", 1, (4, 1, 3)),
    ("*65n_82n(wpc/concrete_sidewalk_tile:wpc/com_decal_puddle01)", "wpc/com_decal_puddle01", 1, (4, 1, 3)),
    ("*66n_177(wpc/us_art_wall_vinylsiding_white:wpc/glass_clear_mp)", "wpc/glass_clear_mp", 1, (4, 1, 3)),
    ("*99_108n(wpc/ug_vista_road_01:wpc/grass_fairway_blend)", "wpc/grass_fairway_blend", 1, (4, 1, 3)),
}
NAME_RE = re.compile(r"^\*(?P<tokens>[^()]+)\((?P<components>[^()]*)\)$")


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    raw = path.read_bytes()
    return json.loads(raw), raw


def load_rows(path: Path):
    doc, raw = load_json(path)
    rows = doc.get("textures")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ProofError(f"{path}: invalid textures table")
    return rows, sha256(raw), len(raw)


def parse_compound(identity: str):
    m = NAME_RE.fullmatch(identity)
    if not m:
        raise ProofError(f"invalid layered Material identity {identity!r}")
    tokens = m.group("tokens").split("_")
    components = m.group("components").split(":")
    if not 1 <= len(tokens) <= 4 or len(tokens) != len(components):
        raise ProofError(f"layer/component count mismatch {identity!r}")
    return tokens, components, "generated/_" + m.group("tokens")


def generated_name(source_name: str, layer: int) -> str:
    return source_name if layer == 0 else f"{source_name}{layer}"


def source_name(generated: str, layer: int) -> str:
    if layer == 0:
        return generated
    suffix = str(layer)
    if not generated.endswith(suffix):
        raise ProofError(f"generated name {generated!r} lacks exact layer suffix {suffix!r}")
    result = generated[:-len(suffix)]
    if not result:
        raise ProofError(f"generated name {generated!r} becomes empty after layer suffix removal")
    return result


def build(material_root: Path, universe_path: Path) -> dict:
    universe, universe_raw = load_json(universe_path)
    if universe.get("format") != "t6-nuketown-exact-layered-material-universe-v1":
        raise ProofError("unexpected exact layered universe format")
    if universe.get("summary") != {
        "layeredMaterialCount": 120,
        "referencedComponentCount": 83,
        "worldMaterialCount": 327,
    }:
        raise ProofError(f"unexpected universe summary {universe.get('summary')!r}")
    layered = universe.get("layeredMaterials")
    if not isinstance(layered, list) or len(layered) != 120 or len(set(layered)) != 120:
        raise ProofError("expected exactly 120 unique layered Materials")

    parsed = []
    referenced = set()
    storages = set()
    for identity in layered:
        tokens, components, storage = parse_compound(identity)
        if storage in storages:
            raise ProofError(f"duplicate generated storage identity {storage}")
        storages.add(storage)
        referenced.update(components)
        parsed.append((identity, tokens, components, storage))
    if len(referenced) != 83:
        raise ProofError(f"referenced component census changed: {len(referenced)}")

    cache = {}
    for identity in sorted(referenced):
        p = material_root / f"{identity}.json"
        cache[identity] = load_rows(p) if p.is_file() else None
    missing = {identity for identity, value in cache.items() if value is None}
    if missing != TARGETS:
        raise ProofError(f"standalone-missing set changed: {sorted(missing)!r}")

    known_component_occurrences = 0
    known_texture_occurrences = 0
    exact_field_matches = 0
    target_counts = Counter()
    target_occurrences = defaultdict(list)
    order_anomalies = set()
    generated_reports = []
    all_known_count = 0
    target_bearing_count = 0

    for identity, tokens, components, storage in parsed:
        path = material_root / f"{storage}.json"
        if not path.is_file():
            raise ProofError(f"missing generated Material {storage}")
        rows, raw_sha, raw_bytes = load_rows(path)
        by_name = defaultdict(list)
        for gi, row in enumerate(rows):
            name = row.get("name")
            if not isinstance(name, str) or not name:
                raise ProofError(f"{identity}: generated row {gi} has no exact name")
            by_name[name].append((gi, row))

        consumed = set()
        unknown = []
        for layer, component in enumerate(components):
            source = cache[component]
            if source is None:
                unknown.append((layer, component))
                target_counts[component] += 1
                continue
            known_component_occurrences += 1
            source_rows = source[0]
            known_texture_occurrences += len(source_rows)
            bound = []
            for si, src in enumerate(source_rows):
                name = src.get("name")
                if not isinstance(name, str) or not name:
                    raise ProofError(f"{component}: source row {si} has no exact name")
                expected_name = generated_name(name, layer)
                matches = by_name.get(expected_name, [])
                if len(matches) != 1:
                    raise ProofError(
                        f"{identity}: {component} row {si} expected one {expected_name!r}, got {len(matches)}"
                    )
                gi, actual = matches[0]
                if gi in consumed:
                    raise ProofError(f"{identity}: generated row {gi} consumed twice")
                consumed.add(gi)
                bound.append(gi)
                expected = dict(src)
                expected["name"] = expected_name
                if canonical(expected) != canonical(actual):
                    keys = sorted(set(expected) | set(actual))
                    differing = [k for k in keys if expected.get(k) != actual.get(k)]
                    raise ProofError(
                        f"{identity}: non-name field mismatch for {component} row {si}: {differing!r}"
                    )
                exact_field_matches += 1
            if bound != sorted(bound):
                order_anomalies.add((identity, component, layer, tuple(bound)))

        residual = [(gi, row) for gi, row in enumerate(rows) if gi not in consumed]
        if not unknown:
            all_known_count += 1
            if residual:
                raise ProofError(f"{identity}: all-known Material leaves {len(residual)} unaccounted rows")
        else:
            target_bearing_count += 1
            if len(unknown) != 1:
                raise ProofError(f"{identity}: target-bearing Material has {len(unknown)} missing layers, expected 1")
            layer, component = unknown[0]
            if not residual:
                raise ProofError(f"{identity}: target {component} leaves no residual rows")
            recovered = []
            indices = []
            for gi, row in residual:
                generated = row.get("name")
                if not isinstance(generated, str) or not generated:
                    raise ProofError(f"{identity}: target residual {gi} lacks exact name")
                restored = dict(row)
                restored["name"] = source_name(generated, layer)
                recovered.append(restored)
                indices.append(gi)
            sig = sha256(canonical(recovered))
            target_occurrences[component].append({
                "generatedMaterial": identity,
                "storageIdentity": storage,
                "layerIndex": layer,
                "token": tokens[layer],
                "generatedIndices": indices,
                "recoveredRows": recovered,
                "recoveredCanonicalSha256": sig,
            })

        generated_reports.append({
            "material": identity,
            "storageIdentity": storage,
            "rawBytes": raw_bytes,
            "rawSha256": raw_sha,
            "textureCount": len(rows),
            "knownConsumedTextureCount": len(consumed),
            "missingLayerCount": len(unknown),
            "residualTextureCount": len(residual),
        })

    if order_anomalies != EXPECTED_ORDER_ANOMALIES:
        got = sorted((a, b, c, list(d)) for a, b, c, d in order_anomalies)
        exp = sorted((a, b, c, list(d)) for a, b, c, d in EXPECTED_ORDER_ANOMALIES)
        raise ProofError(f"relative-order anomaly census changed: got={got!r} expected={exp!r}")
    if dict(sorted(target_counts.items())) != EXPECTED_OCCURRENCES:
        raise ProofError(f"target occurrence census changed: {dict(sorted(target_counts.items()))!r}")

    recovered_targets = {}
    for component in sorted(TARGETS):
        occurrences = target_occurrences[component]
        if len(occurrences) != EXPECTED_OCCURRENCES[component]:
            raise ProofError(f"{component}: occurrence count mismatch")
        signatures = {o["recoveredCanonicalSha256"] for o in occurrences}
        if len(signatures) != 1:
            raise ProofError(f"{component}: recovered rows disagree across exact occurrences")
        recovered = occurrences[0]["recoveredRows"]
        if len(recovered) != 1:
            raise ProofError(
                f"{component}: recovered table has {len(recovered)} rows; singleton-only promotion refuses ordering inference"
            )
        recovered_targets[component] = {
            "textureCount": 1,
            "canonicalSha256": next(iter(signatures)),
            "textures": recovered,
            "occurrenceCount": len(occurrences),
            "occurrences": occurrences,
            "orderBoundary": "Singleton table: source row ordering is not an unresolved degree of freedom.",
        }

    return {
        "format": "t6-nuketown-layered-texture-transform-census-v3",
        "authority": {
            "materialUniverse": str(universe_path),
            "materialUniverseSha256": sha256(universe_raw),
            "fastFile": universe["authority"]["fastFile"],
            "fastFileSha256": universe["authority"]["fastFileSha256"],
            "oatCommit": "9dca965366541504b71fa8cfb7ac049cb9b717e1",
        },
        "summary": {
            "exactLayeredMaterialCount": len(parsed),
            "referencedComponentCount": len(referenced),
            "standaloneKnownComponentCount": len(referenced - missing),
            "standaloneMissingComponentCount": len(missing),
            "knownComponentOccurrenceCount": known_component_occurrences,
            "knownTextureOccurrenceCount": known_texture_occurrences,
            "exactKnownRowMatchCount": exact_field_matches,
            "relativeOrderAnomalyCount": len(order_anomalies),
            "allKnownGeneratedMaterialCount": all_known_count,
            "targetBearingGeneratedMaterialCount": target_bearing_count,
            "targetOccurrenceCount": sum(target_counts.values()),
            "recoveredSingletonTargetCount": len(recovered_targets),
        },
        "relativeOrderAnomalies": [
            {
                "generatedMaterial": a,
                "component": b,
                "layerIndex": c,
                "generatedIndicesInSourceOrder": list(d),
            }
            for a, b, c, d in sorted(order_anomalies)
        ],
        "targetOccurrenceHistogram": dict(sorted(target_counts.items())),
        "recoveredTargets": recovered_targets,
        "generatedMaterials": generated_reports,
        "proofBoundary": (
            "This closes only the seven missing serialized texture tables as singleton residuals in the exact Nuketown layered-Material universe. "
            "It does not infer a universal generated texture-array order and does not close complete standalone Material objects, TechniqueSet selection, shader blend/compositor math, constants, or state bits."
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
    print("GREEN LAYERED TEXTURE TRANSFORM CENSUS V3", json.dumps(doc["summary"], sort_keys=True))
    for identity, target in doc["recoveredTargets"].items():
        row = target["textures"][0]
        print("TARGET", identity, "occurrences", target["occurrenceCount"], "row", json.dumps(row, sort_keys=True))
    print("output_sha256=" + sha256(payload.encode()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
