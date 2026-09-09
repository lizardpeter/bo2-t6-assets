#!/usr/bin/env python3
"""Census the exact Nuketown GfxWorld layered-Material texture transform.

Fail-closed scope:
- selection comes only from T6_NUKETOWN_EXACT_LAYERED_MATERIAL_UNIVERSE_V1;
- standalone-known component rows bind to generated rows only by the exact
  layer-suffixed texture name observed in retail OAT dumps;
- every known row must bind exactly once and preserve its component-relative
  order inside the generated table;
- all field changes other than the layer name rewrite are reported, not hidden;
- target tables are promoted only when every occurrence leaves an exact,
  disjoint residual row set and all occurrences of the same target agree.

This proves serialized Material texture-table reconstruction. It does not prove
TechniqueSet/shader blend math.
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


EXPECTED_TARGETS = {
    "wpc/asphalt_road_dark_dec",
    "wpc/decal_concrete_clean_line",
    "wpc/decal_damage_asphalt_crack01",
    "wpc/decal_grunge_glue",
    "wpc/decal_grunge_mold01",
    "wpc/decal_signage_const_marking01",
    "wpc/decal_signage_const_marking02",
}
NAME_RE = re.compile(r"^\*(?P<tokens>[^()]+)\((?P<components>[^()]*)\)$")


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    raw = path.read_bytes()
    return json.loads(raw), raw


def parse_compound(name: str) -> tuple[list[str], list[str], str]:
    m = NAME_RE.fullmatch(name)
    if not m:
        raise ProofError(f"invalid compound identity {name!r}")
    tokens = m.group("tokens").split("_")
    components = m.group("components").split(":")
    if not 1 <= len(tokens) <= 4 or len(tokens) != len(components):
        raise ProofError(f"invalid layer/component count in {name!r}")
    storage = "generated/_" + m.group("tokens")
    return tokens, components, storage


def load_textures(path: Path) -> tuple[dict, list[dict], str, int]:
    doc, raw = load_json(path)
    rows = doc.get("textures")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ProofError(f"{path}: textures is not an object list")
    return doc, rows, sha256_bytes(raw), len(raw)


def expected_generated_name(source_name: str, layer_index: int) -> str:
    return source_name if layer_index == 0 else f"{source_name}{layer_index}"


def inverse_generated_name(generated_name: str, layer_index: int) -> str:
    if layer_index == 0:
        return generated_name
    suffix = str(layer_index)
    if not generated_name.endswith(suffix):
        raise ProofError(f"generated texture name {generated_name!r} lacks layer suffix {suffix!r}")
    return generated_name[: -len(suffix)]


def build_census(material_root: Path, universe_path: Path) -> dict:
    universe, universe_raw = load_json(universe_path)
    if universe.get("format") != "t6-nuketown-exact-layered-material-universe-v1":
        raise ProofError(f"unsupported universe format {universe.get('format')!r}")
    names = universe.get("layeredMaterials")
    if not isinstance(names, list) or len(names) != 120 or len(set(names)) != 120:
        raise ProofError("exact layered universe must contain 120 unique identities")
    summary = universe.get("summary", {})
    if summary != {"layeredMaterialCount": 120, "referencedComponentCount": 83, "worldMaterialCount": 327}:
        raise ProofError(f"unexpected exact-universe summary {summary!r}")

    parsed = []
    referenced = set()
    storage_ids = set()
    for name in names:
        tokens, components, storage = parse_compound(name)
        if storage in storage_ids:
            raise ProofError(f"duplicate storage identity {storage}")
        storage_ids.add(storage)
        referenced.update(components)
        parsed.append((name, tokens, components, storage))
    if len(referenced) != 83:
        raise ProofError(f"exact universe resolved {len(referenced)} components, expected 83")

    component_cache: dict[str, tuple[dict, list[dict], str, int] | None] = {}

    def component(identity: str):
        if identity not in component_cache:
            path = material_root / f"{identity}.json"
            component_cache[identity] = load_textures(path) if path.is_file() else None
        return component_cache[identity]

    missing = {identity for identity in referenced if component(identity) is None}
    if missing != EXPECTED_TARGETS:
        raise ProofError(
            f"standalone-missing component set changed: got={sorted(missing)!r} expected={sorted(EXPECTED_TARGETS)!r}"
        )

    difference_key_hist = Counter()
    field_differences = []
    name_binding_failures = []
    relative_order_failures = []
    generated_reports = []
    known_component_occurrences = 0
    known_texture_occurrences = 0
    exact_after_name_rewrite = 0
    target_occurrence_rows: dict[str, list[dict]] = defaultdict(list)
    target_occurrence_count = Counter()
    all_known_count = 0
    all_known_fully_accounted = 0

    for full_name, tokens, components, storage in parsed:
        generated_path = material_root / f"{storage}.json"
        if not generated_path.is_file():
            raise ProofError(f"missing exact generated Material JSON {storage}")
        _, generated_rows, generated_sha, generated_bytes = load_textures(generated_path)
        by_name: dict[str, list[tuple[int, dict]]] = defaultdict(list)
        for index, row in enumerate(generated_rows):
            name = row.get("name")
            if not isinstance(name, str) or not name:
                raise ProofError(f"{storage}: generated row {index} lacks a resolved texture name")
            by_name[name].append((index, row))

        consumed: set[int] = set()
        known_binding_indices: dict[int, list[int]] = defaultdict(list)
        local_binding_failures = []
        local_order_failures = []
        unknown_layers = []

        for layer_index, identity in enumerate(components):
            source = component(identity)
            if source is None:
                unknown_layers.append((layer_index, identity))
                target_occurrence_count[identity] += 1
                continue
            known_component_occurrences += 1
            _, source_rows, _, _ = source
            known_texture_occurrences += len(source_rows)
            bound_indices = []
            for source_index, source_row in enumerate(source_rows):
                source_name = source_row.get("name")
                if not isinstance(source_name, str) or not source_name:
                    raise ProofError(f"{identity}: source row {source_index} lacks a resolved texture name")
                generated_name = expected_generated_name(source_name, layer_index)
                matches = by_name.get(generated_name, [])
                if len(matches) != 1:
                    local_binding_failures.append(
                        {
                            "component": identity,
                            "layerIndex": layer_index,
                            "sourceTextureIndex": source_index,
                            "sourceName": source_name,
                            "expectedGeneratedName": generated_name,
                            "matchCount": len(matches),
                        }
                    )
                    continue
                generated_index, actual = matches[0]
                if generated_index in consumed:
                    local_binding_failures.append(
                        {
                            "component": identity,
                            "layerIndex": layer_index,
                            "sourceTextureIndex": source_index,
                            "expectedGeneratedName": generated_name,
                            "duplicateGeneratedIndex": generated_index,
                        }
                    )
                    continue
                consumed.add(generated_index)
                bound_indices.append(generated_index)
                expected = dict(source_row)
                expected["name"] = generated_name
                if canonical(expected) == canonical(actual):
                    exact_after_name_rewrite += 1
                else:
                    keys = sorted(set(expected) | set(actual))
                    diff_keys = [key for key in keys if expected.get(key) != actual.get(key)]
                    difference_key_hist.update(diff_keys)
                    field_differences.append(
                        {
                            "generatedMaterial": full_name,
                            "storageIdentity": storage,
                            "component": identity,
                            "layerIndex": layer_index,
                            "sourceTextureIndex": source_index,
                            "generatedTextureIndex": generated_index,
                            "differingKeys": diff_keys,
                            "source": source_row,
                            "expectedAfterNameRewrite": expected,
                            "actual": actual,
                        }
                    )
            known_binding_indices[layer_index] = bound_indices
            if bound_indices != sorted(bound_indices):
                local_order_failures.append(
                    {
                        "component": identity,
                        "layerIndex": layer_index,
                        "generatedIndicesInSourceOrder": bound_indices,
                    }
                )

        if local_binding_failures:
            name_binding_failures.append({"material": full_name, "failures": local_binding_failures})
        if local_order_failures:
            relative_order_failures.append({"material": full_name, "failures": local_order_failures})

        residual = [(index, row) for index, row in enumerate(generated_rows) if index not in consumed]
        if not unknown_layers:
            all_known_count += 1
            if not local_binding_failures and not local_order_failures and not residual:
                all_known_fully_accounted += 1
        else:
            assigned: set[int] = set()
            for layer_index, identity in unknown_layers:
                suffix = str(layer_index)
                candidates = [
                    (index, row)
                    for index, row in residual
                    if layer_index == 0 or str(row.get("name", "")).endswith(suffix)
                ]
                if not candidates:
                    raise ProofError(f"{full_name}: target {identity} layer {layer_index} has no residual rows")
                overlap = assigned.intersection(index for index, _ in candidates)
                if overlap:
                    raise ProofError(f"{full_name}: target residual overlap at {sorted(overlap)}")
                assigned.update(index for index, _ in candidates)
                recovered_rows = []
                for index, row in candidates:
                    recovered = dict(row)
                    recovered["name"] = inverse_generated_name(str(row["name"]), layer_index)
                    recovered_rows.append(recovered)
                target_occurrence_rows[identity].append(
                    {
                        "generatedMaterial": full_name,
                        "storageIdentity": storage,
                        "layerIndex": layer_index,
                        "token": tokens[layer_index],
                        "generatedIndices": [index for index, _ in candidates],
                        "recoveredRows": recovered_rows,
                        "recoveredCanonicalSha256": sha256_bytes(canonical(recovered_rows)),
                    }
                )
            residual_indices = {index for index, _ in residual}
            if assigned != residual_indices:
                raise ProofError(
                    f"{full_name}: target residual accounting mismatch assigned={sorted(assigned)} residual={sorted(residual_indices)}"
                )

        generated_reports.append(
            {
                "material": full_name,
                "storageIdentity": storage,
                "rawBytes": generated_bytes,
                "rawSha256": generated_sha,
                "textureCount": len(generated_rows),
                "knownConsumedTextureCount": len(consumed),
                "targetLayerCount": len(unknown_layers),
                "residualTextureCount": len(residual),
            }
        )

    if name_binding_failures:
        raise ProofError(f"{len(name_binding_failures)} generated Materials have exact-name binding failures")
    if relative_order_failures:
        raise ProofError(f"{len(relative_order_failures)} generated Materials violate component-relative texture order")
    if all_known_fully_accounted != all_known_count:
        raise ProofError(
            f"all-known generated accounting incomplete: {all_known_fully_accounted}/{all_known_count}"
        )

    expected_occurrences = {
        "wpc/asphalt_road_dark_dec": 1,
        "wpc/decal_concrete_clean_line": 7,
        "wpc/decal_damage_asphalt_crack01": 1,
        "wpc/decal_grunge_glue": 2,
        "wpc/decal_grunge_mold01": 2,
        "wpc/decal_signage_const_marking01": 1,
        "wpc/decal_signage_const_marking02": 1,
    }
    if dict(sorted(target_occurrence_count.items())) != expected_occurrences:
        raise ProofError(f"target occurrence census changed: {dict(target_occurrence_count)!r}")

    recovered_targets = {}
    for identity in sorted(EXPECTED_TARGETS):
        occurrences = target_occurrence_rows[identity]
        signatures = {entry["recoveredCanonicalSha256"] for entry in occurrences}
        if len(signatures) != 1:
            raise ProofError(f"{identity}: {len(signatures)} recovered texture-table variants across occurrences")
        rows = occurrences[0]["recoveredRows"]
        recovered_targets[identity] = {
            "textureCount": len(rows),
            "canonicalSha256": next(iter(signatures)),
            "textures": rows,
            "occurrenceCount": len(occurrences),
            "occurrences": occurrences,
            "orderBoundary": (
                "row order is source-closed for this fixture by the all-known component-relative-order census; "
                "the target occurrence retains generated-index relative order after layer extraction"
            ),
        }

    return {
        "format": "t6-nuketown-layered-texture-transform-census-v2",
        "authority": {
            "materialUniverse": str(universe_path),
            "materialUniverseSha256": sha256_bytes(universe_raw),
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
            "exactAfterNameRewriteCount": exact_after_name_rewrite,
            "nonNameFieldDifferenceCount": len(field_differences),
            "nameBindingFailureCount": len(name_binding_failures),
            "relativeOrderFailureCount": len(relative_order_failures),
            "allKnownGeneratedMaterialCount": all_known_count,
            "allKnownFullyAccountedCount": all_known_fully_accounted,
            "targetBearingGeneratedMaterialCount": sum(1 for row in generated_reports if row["targetLayerCount"]),
            "targetOccurrenceCount": sum(target_occurrence_count.values()),
            "recoveredTargetCount": len(recovered_targets),
        },
        "differenceKeyHistogram": dict(sorted(difference_key_hist.items())),
        "fieldDifferences": field_differences,
        "targetOccurrenceHistogram": dict(sorted(target_occurrence_count.items())),
        "recoveredTargets": recovered_targets,
        "generatedMaterials": generated_reports,
        "proofBoundary": (
            "Exact serialized texture-table transform and seven-target recovery only. "
            "TechniqueSet selection, shader blend/compositor math, constants, state bits, and complete Material reconstruction remain separate gates."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_root", type=Path)
    parser.add_argument("universe_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    doc = build_census(args.material_root, args.universe_json)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.output_json.write_text(payload, encoding="utf-8")
    print("GREEN T6 NUKETOWN LAYERED TEXTURE TRANSFORM CENSUS V2")
    print(json.dumps(doc["summary"], sort_keys=True))
    print("DIFFERENCE_KEYS", json.dumps(doc["differenceKeyHistogram"], sort_keys=True))
    for identity, target in doc["recoveredTargets"].items():
        print("TARGET", identity, "textures", target["textureCount"], "occurrences", target["occurrenceCount"], "sha", target["canonicalSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
