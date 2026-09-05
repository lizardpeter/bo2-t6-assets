#!/usr/bin/env python3
"""Production T6 world export pipeline v14: exact Nuketown normal transforms.

v14 preserves the complete v13/v12 portable artifact. In automatic Nuketown
recipe recovery only, it upgrades recovery v5 to v6 so every canonical generated
recipe carries the map-proven secondary-normal ownership contract:

    layer -> direct
or
    layer -> transform2x2 -> _T6_NORMAL_TRANSFORM_0 / _1

No normal-map channel decode is invented here. The authoritative v12+ logical
normal-transform attributes, paired VS/PS identities, height DAGs, textures,
lightmaps, reflection data and render state remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v6 as recipe_recovery_v6
import t6_oat_world_textured_export_pipeline_v13 as v13
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE


FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v14"


class OatTexturedPipelineV14Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _path(record, label: str) -> Path:
    if not isinstance(record, dict):
        raise OatTexturedPipelineV14Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV14Error(f"{label} does not exist: {path}")
    return path


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def run_oat_textured_pipeline(**kwargs) -> dict:
    old_recovery = v13.recipe_recovery_v5
    v13.recipe_recovery_v5 = recipe_recovery_v6
    try:
        result = v13.run_oat_textured_pipeline(**kwargs)
    finally:
        v13.recipe_recovery_v5 = old_recovery

    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v13":
        raise OatTexturedPipelineV14Error(
            f"unexpected v13 base manifest {result.get('format')!r}"
        )
    recovery = result.get("stats", {}).get("generatedShaderRecipeRecovery")
    automatic = isinstance(recovery, dict)
    if automatic:
        if recovery.get("format") != recipe_recovery_v6.FORMAT:
            raise OatTexturedPipelineV14Error(
                f"automatic recipe recovery did not reach v6: {recovery.get('format')!r}"
            )
        if not bool(recovery.get("normalTransformBindingCoverageComplete")):
            raise OatTexturedPipelineV14Error(
                "automatic recovery did not close Nuketown normal transform ownership"
            )
        generated = int(recovery.get("generatedMaterialCount", -1))
        bound = int(recovery.get("normalTransformBoundMaterialCount", -2))
        if generated < 0 or bound != generated:
            raise OatTexturedPipelineV14Error(
                f"normal transform binding material count {bound} != generated recipe count {generated}"
            )

    map_name = str(kwargs["map_name"])
    output_dir = Path(kwargs["output_dir"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV14Error("v13 result lacks outputs")

    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v13 portable GLB")
    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v14.glb"
    old_glb.replace(new_glb)
    outputs["oatPortableTexturedGlb"] = _record(new_glb)

    old_gltf_record = outputs.get("oatPortableTexturedGltf")
    if isinstance(old_gltf_record, dict):
        old_gltf = _path(old_gltf_record, "v13 portable glTF")
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v14.gltf"
        old_gltf.replace(new_gltf)
        outputs["oatPortableTexturedGltf"] = _record(new_gltf)

    validation = result.setdefault("validation", {})
    validation.update({
        "v14AutomaticRecipeRecoveryUsesV6": automatic,
        "v14NormalTransformBindingCoverageComplete": (
            None if not automatic else bool(recovery["normalTransformBindingCoverageComplete"])
        ),
        "v14NormalTransformBoundMaterialCount": (
            None if not automatic else int(recovery["normalTransformBoundMaterialCount"])
        ),
        "v14SecondaryNormalMaterialCount": (
            None if not automatic else int(recovery["secondaryNormalMaterialCount"])
        ),
        "v14SecondaryNormalLayerCount": (
            None if not automatic else int(recovery["secondaryNormalLayerCount"])
        ),
        "v14DirectSecondaryNormalLayerCount": (
            None if not automatic else int(recovery["directSecondaryNormalLayerCount"])
        ),
        "v14TransformedSecondaryNormalLayerCount": (
            None if not automatic else int(recovery["transformedSecondaryNormalLayerCount"])
        ),
    })
    result.setdefault("policies", {})["v14GeneratedNormalTransformBinding"] = (
        "automatic Nuketown recipes bind secondary normal-bearing component order to direct or exact "
        "v12+ logical _T6_NORMAL_TRANSFORM_0/_1 attributes using the retained n-marker/world-normalCount "
        "proof; no layerIndex-1 shortcut and no normal-map channel decode assumption"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        path = Path(str(old_manifest.get("path") or ""))
        if path.is_file():
            path.unlink()

    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v14.json"
    manifest_path.write_bytes(payload)
    result["manifest"] = _record(manifest_path, payload)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="map_name", required=True)
    parser.add_argument("--surfaces", type=Path, required=True)
    parser.add_argument("--vd0", type=Path, required=True)
    parser.add_argument("--vd1", type=Path, required=True)
    parser.add_argument("--indices", type=Path, required=True)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--asset-pointer-base", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--oat-material-root", type=Path, required=True)
    parser.add_argument("--oat-shader-root", type=Path)
    parser.add_argument("--dds-root", type=Path, required=True)
    parser.add_argument("--format-registry", type=Path, required=True)
    parser.add_argument("--lightmap-catalog", type=Path)
    parser.add_argument("--reflection-probe-catalog", type=Path)
    parser.add_argument("--generated-shader-recipes", type=Path)
    parser.add_argument("--generated-shader-expanded-world", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--write-gltf", action="store_true")
    parser.add_argument("--sm-polygon-offset-bias", type=int, default=DEFAULT_SHADOWMAP_BIAS)
    parser.add_argument("--sm-polygon-offset-scale", type=float, default=DEFAULT_SHADOWMAP_SCALE)
    parser.add_argument("--allow-unresolved-world-materials", action="store_true")
    parser.add_argument("--allow-missing-oat-materials", action="store_true")
    parser.add_argument("--allow-missing-dds", action="store_true")
    parser.add_argument("--allow-missing-preview-textures", action="store_true")
    parser.add_argument("--allow-missing-dependency-textures", action="store_true")
    parser.add_argument("--allow-missing-lightmap-dds", action="store_true")
    parser.add_argument("--allow-missing-reflection-probe-dds", action="store_true")
    args = parser.parse_args()
    result = run_oat_textured_pipeline(
        map_name=args.map_name,
        surfaces_path=args.surfaces,
        vd0_path=args.vd0,
        vd1_path=args.vd1,
        indices_path=args.indices,
        materials_path=args.materials,
        catalog_path=args.catalog,
        prefix_path=args.prefix,
        asset_pointer_array_virtual_base=args.asset_pointer_base,
        oat_material_root=args.oat_material_root,
        oat_shader_root=args.oat_shader_root,
        dds_root=args.dds_root,
        output_dir=args.out_dir,
        format_registry_path=args.format_registry,
        lightmap_catalog_path=args.lightmap_catalog,
        reflection_probe_catalog_path=args.reflection_probe_catalog,
        generated_shader_recipe_manifest_path=args.generated_shader_recipes,
        generated_shader_expanded_world_path=args.generated_shader_expanded_world,
        write_gltf=args.write_gltf,
        shadowmap_bias=args.sm_polygon_offset_bias,
        shadowmap_scale=args.sm_polygon_offset_scale,
        allow_unresolved_world_materials=args.allow_unresolved_world_materials,
        allow_missing_oat_materials=args.allow_missing_oat_materials,
        allow_missing_dds=args.allow_missing_dds,
        allow_missing_preview_textures=args.allow_missing_preview_textures,
        allow_missing_dependency_textures=args.allow_missing_dependency_textures,
        allow_missing_lightmap_dds=args.allow_missing_lightmap_dds,
        allow_missing_reflection_probe_dds=args.allow_missing_reflection_probe_dds,
    )
    print(json.dumps({
        "format": result["format"],
        "map": result.get("map", args.map_name),
        "glb": result["outputs"]["oatPortableTexturedGlb"],
        "generatedShaderRecipeRecovery": result.get("stats", {}).get("generatedShaderRecipeRecovery"),
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
