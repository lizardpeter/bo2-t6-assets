#!/usr/bin/env python3
"""Decode and audit Treyarch layered/generated material names.

T5 engine source in KisakBlack source-closes the name grammar inherited by T6:
- each decimal token is parsed as `bspMaterialIndex` and resolved with
  `R_GetBspMaterial(bspMaterialIndex)`;
- an `n` marker means the referenced layer is expected to have a normal map;
- older BSP variants also accept `x`, which means expected-normal == false;
- at most four component materials are accepted;
- `Material_CreateLayered` sums component texture/constant counts and copies
  each component texture table into the generated material.

T6 compound names additionally retain component material identities inside
parentheses, e.g.:
  *22n_14(wpc/hjk_interior_plastic_tile:wpc/pb_decal_wall_fillet_2_blend)

This tool parses that identity without guessing shader blend/compositor math.
Its optional fixture census cross-checks the grammar against retail GfxWorld
material and vertex-proof records.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from t6_zone_core import MaterialWorldVertexFormat, WORLD_VERTEX_FORMATS


class LayeredMaterialError(RuntimeError):
    pass


_TOKEN_RE = re.compile(r"^(?P<index>[0-9]+)(?P<marker>[nx]?)$")
_NAME_RE = re.compile(r"^\*(?P<tokens>[^()]+)\((?P<components>[^()]*)\)$")


def parse_layered_material_name(name: str) -> dict:
    match = _NAME_RE.fullmatch(name)
    if match is None:
        raise LayeredMaterialError(f"not a supported layered material identity: {name!r}")

    token_texts = match.group("tokens").split("_")
    components = match.group("components").split(":") if match.group("components") else []
    if not 1 <= len(token_texts) <= 4:
        raise LayeredMaterialError(f"{name!r}: layer count {len(token_texts)} outside 1..4")
    if len(token_texts) != len(components):
        raise LayeredMaterialError(
            f"{name!r}: token/component count mismatch {len(token_texts)} != {len(components)}"
        )

    layers: list[dict] = []
    for layer_index, (token_text, component) in enumerate(zip(token_texts, components)):
        token = _TOKEN_RE.fullmatch(token_text)
        if token is None:
            raise LayeredMaterialError(f"{name!r}: invalid layer token {token_text!r}")
        if not component or component.startswith("*"):
            raise LayeredMaterialError(f"{name!r}: invalid component material {component!r}")
        marker = token.group("marker")
        layers.append(
            {
                "layerIndex": layer_index,
                "token": token_text,
                "bspMaterialIndex": int(token.group("index")),
                "marker": marker or None,
                "expectedNormalMap": marker == "n",
                "explicitNoNormalMarker": marker == "x",
                "componentMaterial": component,
            }
        )

    normal_layers = sum(bool(layer["expectedNormalMap"]) for layer in layers)
    return {
        "format": "t6-layered-material-name-v1",
        "material": name,
        "layerCount": len(layers),
        "expectedNormalMapLayerCount": normal_layers,
        "layers": layers,
        "proofBoundary": {
            "numericToken": "source-closed as BSP material index",
            "nMarker": "source-closed as expected Material_HasNormalMap == true",
            "xMarker": "source-closed older-engine explicit expected-normal == false marker",
            "componentNames": "serialized T6 identity text, colon-delimited by layer",
            "blendMath": "not encoded by this name parser; technique-set/shader semantics remain separate",
        },
    }


def _load_surface_mapping(path: Path) -> tuple[list[dict], bytes]:
    raw = path.read_bytes()
    reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
    required = {"materialName", "materialIndex", "textureCount"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise LayeredMaterialError(f"surface mapping missing columns {sorted(missing)}")
    rows = [row for row in reader if row.get("materialName")]
    return rows, raw


def build_fixture_census(surface_mapping_csv: Path, world_vertex_proof_json: Path) -> dict:
    rows, _ = _load_surface_mapping(surface_mapping_csv)
    proof = json.loads(world_vertex_proof_json.read_text(encoding="utf-8"))
    if proof.get("format") != "t6-world-vertex-proof-v1":
        raise LayeredMaterialError(f"unsupported world proof {proof.get('format')!r}")
    if int(proof.get("badGroupCount", 0)) != 0:
        raise LayeredMaterialError("world vertex proof contains bad groups")

    unique_texture_counts: dict[str, set[int]] = defaultdict(set)
    unique_material_indices: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        name = row["materialName"]
        unique_texture_counts[name].add(int(row["textureCount"]))
        unique_material_indices[name].add(int(row["materialIndex"]))
    for name, values in unique_texture_counts.items():
        if len(values) != 1:
            raise LayeredMaterialError(f"material {name!r} has conflicting textureCount {sorted(values)}")
    for name, values in unique_material_indices.items():
        if len(values) != 1:
            raise LayeredMaterialError(f"material {name!r} has conflicting materialIndex {sorted(values)}")

    observed_formats: dict[str, set[int]] = defaultdict(set)
    for group in proof.get("groups", []):
        fmt = int(group["worldVertFormat"])
        for material in group.get("materials", []):
            observed_formats[str(material)].add(fmt)

    compounds = sorted(name for name in unique_texture_counts if name.startswith("*"))
    decoded: list[dict] = []
    token_to_component: dict[str, set[str]] = defaultdict(set)
    component_to_token: dict[str, set[str]] = defaultdict(set)
    layer_histogram = Counter()
    normal_layer_histogram = Counter()
    format_histogram = Counter()
    exact_texture_sum_proofs = 0
    texture_sum_pending = 0
    texture_sum_failures: list[dict] = []
    world_layout_failures: list[dict] = []

    for name in compounds:
        parsed = parse_layered_material_name(name)
        layer_histogram[parsed["layerCount"]] += 1
        normal_layer_histogram[parsed["expectedNormalMapLayerCount"]] += 1
        for layer in parsed["layers"]:
            token_to_component[layer["token"]].add(layer["componentMaterial"])
            component_to_token[layer["componentMaterial"]].add(layer["token"])

        generated_texture_count = next(iter(unique_texture_counts[name]))
        component_counts: list[int | None] = []
        for layer in parsed["layers"]:
            values = unique_texture_counts.get(layer["componentMaterial"])
            component_counts.append(next(iter(values)) if values else None)
        if all(value is not None for value in component_counts):
            component_sum = sum(int(value) for value in component_counts if value is not None)
            if component_sum == generated_texture_count:
                exact_texture_sum_proofs += 1
            else:
                texture_sum_failures.append(
                    {
                        "material": name,
                        "generatedTextureCount": generated_texture_count,
                        "componentTextureCounts": component_counts,
                        "componentTextureCountSum": component_sum,
                    }
                )
        else:
            texture_sum_pending += 1
            component_sum = None

        formats = sorted(observed_formats.get(name, set()))
        layout_checks: list[dict] = []
        for fmt in formats:
            spec = WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(fmt)]
            format_histogram[fmt] += 1
            # Retail-observed T6 relationship. The source-closed meaning of `n`
            # is normal-map presence; the mapping to vertex layout is checked
            # here rather than assumed by the generic name parser.
            expected_normal_count = max(1, parsed["expectedNormalMapLayerCount"])
            check = {
                "worldVertFormat": fmt,
                "formatName": MaterialWorldVertexFormat(fmt).name,
                "uvCount": spec.uv_count,
                "normalCount": spec.normal_count,
                "layerCountMatchesUvCount": parsed["layerCount"] == spec.uv_count,
                "normalMapLayerCountMatchesNormalCount": expected_normal_count == spec.normal_count,
            }
            layout_checks.append(check)
            if not check["layerCountMatchesUvCount"] or not check["normalMapLayerCountMatchesNormalCount"]:
                world_layout_failures.append({"material": name, **check})

        decoded.append(
            {
                **parsed,
                "materialIndex": next(iter(unique_material_indices[name])),
                "generatedTextureCount": generated_texture_count,
                "componentTextureCounts": component_counts,
                "componentTextureCountSum": component_sum,
                "observedWorldVertFormats": formats,
                "worldLayoutChecks": layout_checks,
            }
        )

    ambiguous_tokens = {
        token: sorted(values) for token, values in token_to_component.items() if len(values) != 1
    }
    ambiguous_components = {
        component: sorted(values) for component, values in component_to_token.items() if len(values) != 1
    }
    if texture_sum_failures:
        raise LayeredMaterialError(
            f"{len(texture_sum_failures)} generated texture-count sums disagree with components"
        )
    if world_layout_failures:
        raise LayeredMaterialError(
            f"{len(world_layout_failures)} layered material/world vertex-layout checks failed"
        )

    return {
        "format": "t6-layered-material-fixture-census-v1",
        "map": proof.get("map"),
        "source": {
            "surfaceMapping": surface_mapping_csv.name,
            "worldVertexProof": world_vertex_proof_json.name,
        },
        "stats": {
            "uniqueMaterialCount": len(unique_texture_counts),
            "ordinaryMaterialCount": len(unique_texture_counts) - len(compounds),
            "compoundMaterialCount": len(compounds),
            "layerCountHistogram": {str(k): v for k, v in sorted(layer_histogram.items())},
            "expectedNormalMapLayerCountHistogram": {
                str(k): v for k, v in sorted(normal_layer_histogram.items())
            },
            "observedWorldVertFormatCompoundCounts": {
                str(k): v for k, v in sorted(format_histogram.items())
            },
            "uniqueLayerTokenCount": len(token_to_component),
            "uniqueComponentMaterialCount": len(component_to_token),
            "ambiguousTokenCount": len(ambiguous_tokens),
            "ambiguousComponentCount": len(ambiguous_components),
            "exactGeneratedTextureCountSumProofs": exact_texture_sum_proofs,
            "pendingGeneratedTextureCountSums": texture_sum_pending,
            "generatedTextureCountSumFailures": len(texture_sum_failures),
            "worldLayoutFailures": len(world_layout_failures),
        },
        "retailFindings": {
            "tokenComponentBijection": not ambiguous_tokens and not ambiguous_components,
            "generatedTextureCountEqualsComponentSumWhenAllComponentsStandalone": not texture_sum_failures,
            "layerCountEqualsWorldUvCountForObservedCompounds": not world_layout_failures,
            "normalLayoutRelationship": (
                "for this fixture, world normalCount == max(1, count(layers marked n))"
            ),
        },
        "tokenToComponent": {
            token: next(iter(values)) if len(values) == 1 else sorted(values)
            for token, values in sorted(
                token_to_component.items(),
                key=lambda item: int(item[0].rstrip("nx")),
            )
        },
        "ambiguousTokens": ambiguous_tokens,
        "ambiguousComponents": ambiguous_components,
        "materials": decoded,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse")
    parse_cmd.add_argument("name")

    census_cmd = sub.add_parser("census")
    census_cmd.add_argument("surface_mapping_csv", type=Path)
    census_cmd.add_argument("world_vertex_proof_json", type=Path)
    census_cmd.add_argument("output_json", type=Path)

    args = parser.parse_args()
    if args.command == "parse":
        print(json.dumps(parse_layered_material_name(args.name), indent=2, sort_keys=True))
        return 0

    doc = build_fixture_census(args.surface_mapping_csv, args.world_vertex_proof_json)
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output_json.write_bytes(payload)
    print(json.dumps({"out": str(args.output_json), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
