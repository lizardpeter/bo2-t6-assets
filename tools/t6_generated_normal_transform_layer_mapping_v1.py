#!/usr/bin/env python3
"""Prove which T6 normalTransform stream feeds each generated normal layer.

This closes a renderer integration gap without assuming that transform index N
means generated layer N+1.

For every normal-bearing generated TechniqueSet the proof joins three retained
facts from the same exact slot-4 pass:

1. OAT `.tech` stream routing, e.g.
      vertex.texcoord[5] = code.normalTransform[0];
   proving which VS input semantic receives each source normalTransform stream.
2. Direct paired-VS output ancestry from the existing reflection VS profiler,
   proving which output TEXCOORD components depend on that exact routed input.
3. The already source-closed layered-normal PS recurrence, whose transformed
   normal-pair dot nodes expose the exact PS input-semantic dependencies for each
   normal-bearing generated layer.

A transform->layer relation is promoted only when exactly one routed transform
covers every PS input dependency of that transformed layer and no other routed
normalTransform is a candidate. Direct (non-2x2) normal layers are recorded as
not requiring a transform.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

from t6_generated_shader_recipe_contract_v1 import validate_manifest
from t6_oat_slot_shader_resolver_v2 import resolve_slot_shaders


FORMAT = "t6-generated-normal-transform-layer-mapping-v1"
ROUTE_RE = re.compile(
    r"^\s*vertex\.texcoord\[(\d+)\]\s*=\s*code\.normalTransform\[(\d+)\]\s*;\s*(?://.*)?$"
)
INPUT_DEP_RE = re.compile(r"^TEXCOORD(\d+)\.([xyzw])$")


class NormalTransformLayerMappingError(RuntimeError):
    pass


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise NormalTransformLayerMappingError(f"cannot load verifier {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def parse_normal_transform_routes(technique_text: str) -> dict[int, int]:
    """Return normalTransform index -> VS input TEXCOORD semantic index."""
    out: dict[int, int] = {}
    destinations: dict[int, int] = {}
    for lineno, line in enumerate(technique_text.splitlines(), 1):
        match = ROUTE_RE.match(line)
        if not match:
            continue
        dest_tc = int(match.group(1))
        transform = int(match.group(2))
        if transform not in (0, 1):
            raise NormalTransformLayerMappingError(
                f"line {lineno}: unsupported T6 normalTransform[{transform}]"
            )
        old = out.get(transform)
        if old is not None and old != dest_tc:
            raise NormalTransformLayerMappingError(
                f"normalTransform[{transform}] routes to both TEXCOORD{old} and TEXCOORD{dest_tc}"
            )
        other = destinations.get(dest_tc)
        if other is not None and other != transform:
            raise NormalTransformLayerMappingError(
                f"VS input TEXCOORD{dest_tc} receives normalTransform[{other}] and [{transform}]"
            )
        out[transform] = dest_tc
        destinations[dest_tc] = transform
    return dict(sorted(out.items()))


def _normal_recurring_layers(comp, normal_proof, ps_blob: bytes, technique_set: str) -> list[dict]:
    d = comp.symbolic(ps_blob, *_normal_symbolic_modules(comp))
    rgb = comp.sequence(d, comp.mode_sig(technique_set), "x")
    if not rgb:
        raise NormalTransformLayerMappingError(
            f"{technique_set!r}: no exact RGB compositor sequence"
        )
    weights = rgb[0][1]
    rows = []
    for layer, operation, flags in comp.specs(technique_set):
        if "n" not in flags:
            continue
        current = normal_proof.current_pair(comp, d, layer, weights[layer - 1])
        kinds = {str(d.n[node]["kind"]) for node in current}
        if kinds == {"dot"}:
            deps = sorted({
                dep
                for node in current
                for dep in comp.input_deps(d, node)
            })
            if not deps:
                raise NormalTransformLayerMappingError(
                    f"{technique_set!r} layer {layer}: transformed normal has no input dependencies"
                )
            parsed = []
            for dep in deps:
                match = INPUT_DEP_RE.match(dep)
                if not match:
                    raise NormalTransformLayerMappingError(
                        f"{technique_set!r} layer {layer}: unsupported transform input dependency {dep!r}"
                    )
                parsed.append((int(match.group(1)), match.group(2)))
            rows.append({
                "layerIndex": int(layer),
                "operation": operation,
                "flags": sorted(flags),
                "normalPairKind": "matrix2x2",
                "pixelInputDependencies": deps,
                "pixelTexcoordComponents": [
                    {"texcoord": tc, "component": component}
                    for tc, component in parsed
                ],
            })
        elif kinds == {"add"}:
            rows.append({
                "layerIndex": int(layer),
                "operation": operation,
                "flags": sorted(flags),
                "normalPairKind": "direct",
                "pixelInputDependencies": [],
                "pixelTexcoordComponents": [],
            })
        else:
            raise NormalTransformLayerMappingError(
                f"{technique_set!r} layer {layer}: mixed current normal pair kinds {sorted(kinds)}"
            )
    return rows


# The compositor's symbolic(blob, opcode, operand, inspect) signature is loaded
# lazily and cached here so callers can substitute modules in tests.
_SYMBOLIC_MODULES = None


def _normal_symbolic_modules(comp):
    global _SYMBOLIC_MODULES
    if _SYMBOLIC_MODULES is None:
        import t6_retail_special_shdr_opcode_census_v1 as opcode
        import t6_retail_special_shdr_operand_census_v1 as operand
        import t6_dxbc_inspect_v1 as inspect
        _SYMBOLIC_MODULES = (opcode, operand, inspect)
    return _SYMBOLIC_MODULES


def _vs_transform_output_components(paired, base, vs_blob: bytes, routes: dict[int, int]) -> dict[int, list[str]]:
    """Map normalTransform source index to proven VS output semantic components."""
    routed_inputs = {transform: ("TEXCOORD", input_tc) for transform, input_tc in routes.items()}
    out: dict[int, set[str]] = {transform: set() for transform in routes}
    for output_tc in range(14):
        profile = paired.component_profile(base, vs_blob, output_tc)
        if profile is None:
            continue
        for component_row in profile:
            component = str(component_row.get("component") or "")
            if component not in "xyzw":
                continue
            leaves = {
                tuple(item)
                for item in component_row.get("inputLeaves", [])
                if isinstance(item, (list, tuple)) and len(item) == 2
            }
            for transform, routed_input in routed_inputs.items():
                if routed_input in leaves:
                    out[transform].add(f"TEXCOORD{output_tc}.{component}")
    return {transform: sorted(values) for transform, values in sorted(out.items())}


def _assign_transforms(layer_rows: list[dict], transform_outputs: dict[int, list[str]]) -> list[dict]:
    result = []
    used: dict[int, int] = {}
    for layer in layer_rows:
        row = dict(layer)
        if row["normalPairKind"] == "direct":
            row.update({
                "normalTransformRequired": False,
                "normalTransformIndex": None,
                "candidateTransformIndices": [],
            })
            result.append(row)
            continue
        deps = set(map(str, row["pixelInputDependencies"]))
        candidates = [
            transform
            for transform, outputs in transform_outputs.items()
            if deps and deps.issubset(set(map(str, outputs)))
        ]
        row["normalTransformRequired"] = True
        row["candidateTransformIndices"] = candidates
        if len(candidates) != 1:
            raise NormalTransformLayerMappingError(
                f"generated normal layer {row['layerIndex']} transform candidates {candidates} for deps {sorted(deps)}"
            )
        transform = candidates[0]
        previous = used.get(transform)
        if previous is not None and previous != row["layerIndex"]:
            raise NormalTransformLayerMappingError(
                f"normalTransform[{transform}] maps to generated normal layers {previous} and {row['layerIndex']}"
            )
        used[transform] = row["layerIndex"]
        row["normalTransformIndex"] = transform
        result.append(row)
    return result


def build(
    recipe_manifest: dict,
    *,
    oat_root: Path,
    paired_vs_probe_path: Path,
    base_verifier_path: Path,
    compositor_path: Path,
    normal_proof_path: Path,
) -> dict:
    recipes = validate_manifest(recipe_manifest)
    paired = _load(paired_vs_probe_path, "t6_normal_transform_paired_vs")
    base = _load(base_verifier_path, "t6_normal_transform_vs_base")
    comp = _load(compositor_path, "t6_normal_transform_compositor")
    normal_proof = _load(normal_proof_path, "t6_normal_transform_normal_proof")

    normal_recipes = [
        row for row in recipes.values()
        if any(bool(step.get("hasNormal")) for step in row.get("layerProgram", []))
    ]
    if not normal_recipes:
        raise NormalTransformLayerMappingError("recipe manifest has no normal-bearing generated materials")
    by_techset: dict[str, list[dict]] = {}
    for recipe in normal_recipes:
        by_techset.setdefault(str(recipe["techniqueSet"]), []).append(recipe)

    profiles = []
    mapping_pairs: set[tuple[int, int]] = set()
    transformed_layer_count = direct_layer_count = 0
    for technique_set, owners in sorted(by_techset.items()):
        resolved = resolve_slot_shaders(
            oat_root,
            technique_set,
            slot_index=4,
            require_single_vertex_shader=True,
            require_single_pixel_shader=True,
        )
        vs = resolved["vertexShaders"][0]
        ps = resolved["pixelShaders"][0]
        expected_vs = {str(row.get("vertexShaderArchetype") or "") for row in owners}
        expected_ps = {str(row.get("pixelShaderArchetype") or "") for row in owners}
        if expected_vs != {f"sha256:{vs['sha256']}"}:
            raise NormalTransformLayerMappingError(
                f"{technique_set!r}: paired VS identity disagrees with canonical recipes"
            )
        if expected_ps != {f"sha256:{ps['sha256']}"}:
            raise NormalTransformLayerMappingError(
                f"{technique_set!r}: paired PS identity disagrees with canonical recipes"
            )

        technique_text = (Path(oat_root) / resolved["techniqueFile"]).read_text(
            encoding="utf-8", errors="strict"
        )
        routes = parse_normal_transform_routes(technique_text)
        vs_blob = (Path(oat_root) / vs["relativeFile"]).read_bytes()
        ps_blob = (Path(oat_root) / ps["relativeFile"]).read_bytes()
        if hashlib.sha256(vs_blob).hexdigest() != vs["sha256"]:
            raise NormalTransformLayerMappingError(f"{technique_set!r}: VS bytes changed after resolution")
        if hashlib.sha256(ps_blob).hexdigest() != ps["sha256"]:
            raise NormalTransformLayerMappingError(f"{technique_set!r}: PS bytes changed after resolution")

        transform_outputs = _vs_transform_output_components(paired, base, vs_blob, routes)
        layer_rows = _normal_recurring_layers(comp, normal_proof, ps_blob, technique_set)
        assigned = _assign_transforms(layer_rows, transform_outputs)
        for row in assigned:
            if row["normalTransformRequired"]:
                transformed_layer_count += 1
                mapping_pairs.add((int(row["normalTransformIndex"]), int(row["layerIndex"])))
            else:
                direct_layer_count += 1

        profiles.append({
            "techniqueSet": technique_set,
            "materialOwnerCount": len(owners),
            "vertexShaderSha256": vs["sha256"],
            "pixelShaderSha256": ps["sha256"],
            "techniqueFile": resolved["techniqueFile"],
            "normalTransformRoutes": [
                {
                    "normalTransformIndex": transform,
                    "vertexInputSemantic": f"TEXCOORD{input_tc}",
                }
                for transform, input_tc in sorted(routes.items())
            ],
            "normalTransformVsOutputComponents": {
                str(transform): outputs
                for transform, outputs in sorted(transform_outputs.items())
            },
            "normalLayers": assigned,
        })

    summary = {
        "materialOwnerCount": len(normal_recipes),
        "techniqueSetCount": len(by_techset),
        "transformedNormalLayerOccurrenceCount": transformed_layer_count,
        "directNormalLayerOccurrenceCount": direct_layer_count,
        "observedTransformLayerMappings": [
            {"normalTransformIndex": transform, "layerIndex": layer}
            for transform, layer in sorted(mapping_pairs)
        ],
        "mappingPairCount": len(mapping_pairs),
        "allTransformedLayersUniquelyMapped": True,
        "profilesSha256": _jhash(profiles),
    }
    return {
        "format": FORMAT,
        "producer": "tools/t6_generated_normal_transform_layer_mapping_v1.py",
        "profiles": profiles,
        "summary": summary,
        "proofBoundary": (
            "Exact OAT slot-4 stream routing + direct paired-VS input ancestry + exact transformed normal-layer "
            "PS input dependencies. A normalTransform index is assigned to a generated layer only when it is the "
            "unique routed source whose proven VS output components cover that layer's matrix-dot input deps. "
            "No transform-index-to-layer convention is assumed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", type=Path, required=True)
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument(
        "--paired-vs-probe",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py"),
    )
    parser.add_argument(
        "--base-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py"),
    )
    parser.add_argument(
        "--compositor",
        type=Path,
        default=Path("tools/t6_retail_layered_lmap_compositor_v1.py"),
    )
    parser.add_argument(
        "--normal-proof",
        type=Path,
        default=Path("tools/t6_retail_layered_normal_reconstruction_v1.py"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.recipes.read_text(encoding="utf-8"))
    doc = build(
        manifest,
        oat_root=args.oat_root,
        paired_vs_probe_path=args.paired_vs_probe,
        base_verifier_path=args.base_verifier,
        compositor_path=args.compositor,
        normal_proof_path=args.normal_proof,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
