#!/usr/bin/env python3
"""Production T6 world export pipeline v11: complete exact Nuketown vN recipes.

v11 preserves v10/v9 geometry, material, render-state, lightmap and reflection
behavior.  In automatic Nuketown recipe-recovery mode it upgrades the recovery
implementation to v4, so every height-bearing generated recipe carries:

- exact slot-4 shader identity;
- forensic vN scalar DAG;
- per-Material exact retail cbuffer literals;
- exact raw-input -> normalized `_T6_LAYER_WEIGHTS` binding;
- exact sampled shader resource -> OAT material argument -> layer color role.

Manual canonical recipe manifests remain supported exactly as in v10.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v4 as recipe_recovery_v4
import t6_oat_world_textured_export_pipeline_v10 as v10
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE


FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v11"


class OatTexturedPipelineV11Error(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _file_record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(payload),
        "sha256": _sha256(payload),
    }


def _record_path(record, label: str) -> Path:
    if not isinstance(record, dict):
        raise OatTexturedPipelineV11Error(f"missing {label} file record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV11Error(f"{label} file does not exist: {path}")
    return path


def run_oat_textured_pipeline(
    *,
    map_name: str,
    surfaces_path: Path,
    vd0_path: Path,
    vd1_path: Path,
    indices_path: Path,
    materials_path: Path,
    catalog_path: Path,
    prefix_path: Path,
    asset_pointer_array_virtual_base: int,
    oat_material_root: Path,
    dds_root: Path,
    output_dir: Path,
    format_registry_path: Path,
    lightmap_catalog_path: Path | None = None,
    reflection_probe_catalog_path: Path | None = None,
    generated_shader_recipe_manifest_path: Path | None = None,
    generated_shader_expanded_world_path: Path | None = None,
    oat_shader_root: Path | None = None,
    write_gltf: bool = False,
    shadowmap_bias: int = DEFAULT_SHADOWMAP_BIAS,
    shadowmap_scale: float = DEFAULT_SHADOWMAP_SCALE,
    allow_unresolved_world_materials: bool = False,
    allow_missing_oat_materials: bool = False,
    allow_missing_dds: bool = False,
    allow_missing_preview_textures: bool = False,
    allow_missing_dependency_textures: bool = False,
    allow_missing_lightmap_dds: bool = False,
    allow_missing_reflection_probe_dds: bool = False,
) -> dict:
    old_recovery = v10.recipe_recovery
    v10.recipe_recovery = recipe_recovery_v4
    try:
        result = v10.run_oat_textured_pipeline(
            map_name=map_name,
            surfaces_path=surfaces_path,
            vd0_path=vd0_path,
            vd1_path=vd1_path,
            indices_path=indices_path,
            materials_path=materials_path,
            catalog_path=catalog_path,
            prefix_path=prefix_path,
            asset_pointer_array_virtual_base=asset_pointer_array_virtual_base,
            oat_material_root=oat_material_root,
            dds_root=dds_root,
            output_dir=output_dir,
            format_registry_path=format_registry_path,
            lightmap_catalog_path=lightmap_catalog_path,
            reflection_probe_catalog_path=reflection_probe_catalog_path,
            generated_shader_recipe_manifest_path=generated_shader_recipe_manifest_path,
            generated_shader_expanded_world_path=generated_shader_expanded_world_path,
            oat_shader_root=oat_shader_root,
            write_gltf=write_gltf,
            shadowmap_bias=shadowmap_bias,
            shadowmap_scale=shadowmap_scale,
            allow_unresolved_world_materials=allow_unresolved_world_materials,
            allow_missing_oat_materials=allow_missing_oat_materials,
            allow_missing_dds=allow_missing_dds,
            allow_missing_preview_textures=allow_missing_preview_textures,
            allow_missing_dependency_textures=allow_missing_dependency_textures,
            allow_missing_lightmap_dds=allow_missing_lightmap_dds,
            allow_missing_reflection_probe_dds=allow_missing_reflection_probe_dds,
        )
    finally:
        v10.recipe_recovery = old_recovery

    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v10":
        raise OatTexturedPipelineV11Error(
            f"unexpected v10 base manifest {result.get('format')!r}"
        )
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV11Error("v10 result lacks outputs")

    glb_old = _record_path(outputs.get("oatPortableTexturedGlb"), "v10 portable textured GLB")
    glb_new = Path(output_dir) / f"{map_name}.world_oat_portable_textured_v11.glb"
    glb_old.replace(glb_new)
    outputs["oatPortableTexturedGlb"] = _file_record(glb_new)

    gltf_record = outputs.get("oatPortableTexturedGltf")
    if isinstance(gltf_record, dict):
        gltf_old = _record_path(gltf_record, "v10 portable textured glTF")
        gltf_new = Path(output_dir) / f"{map_name}.world_oat_portable_textured_v11.gltf"
        gltf_old.replace(gltf_new)
        outputs["oatPortableTexturedGltf"] = _file_record(gltf_new)

    recovery = result.get("stats", {}).get("generatedShaderRecipeRecovery")
    automatic = isinstance(recovery, dict)
    if automatic and recovery.get("format") != recipe_recovery_v4.FORMAT:
        raise OatTexturedPipelineV11Error(
            f"automatic recipe recovery did not reach v4: {recovery.get('format')!r}"
        )
    validation = result.setdefault("validation", {})
    validation.update({
        "v11AutomaticRecipeRecoveryUsesV4": automatic,
        "v11HeightDagCoverageComplete": (
            None if not automatic else bool(recovery.get("heightDagCoverageComplete"))
        ),
        "v11HeightConstantCoverageComplete": (
            None if not automatic else bool(recovery.get("heightConstantCoverageComplete"))
        ),
        "v11HeightAllLeafCoverageComplete": (
            None if not automatic else bool(recovery.get("heightAllLeafCoverageComplete"))
        ),
        "v11RecoveredHeightLeafBoundMaterialCount": (
            None if not automatic else recovery.get("heightLeafBoundMaterialCount")
        ),
        "v11RecoveredHeightLeafBoundLayerCount": (
            None if not automatic else recovery.get("heightLeafBoundLayerCount")
        ),
    })
    if automatic and not all((
        validation["v11HeightDagCoverageComplete"],
        validation["v11HeightConstantCoverageComplete"],
        validation["v11HeightAllLeafCoverageComplete"],
    )):
        raise OatTexturedPipelineV11Error(
            "automatic Nuketown recipe recovery did not close all vN DAG/constant/leaf coverage gates"
        )

    result.setdefault("policies", {})["v11GeneratedHeightPlaybackContract"] = (
        "automatic Nuketown recipes carry exact shader-specific vN DAGs plus per-Material "
        "retail constants and exact nonconstant leaf bindings; downstream adapters must "
        "execute the serialized DAG rather than substitute a generic height-blend equation"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = Path(output_dir) / f"{map_name}.world_oat_textured_export_manifest_v11.json"
    manifest_path.write_bytes(payload)
    result["manifest"] = _file_record(manifest_path, payload)
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

    manifest = run_oat_textured_pipeline(
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
        "format": manifest["format"],
        "map": manifest.get("map", args.map_name),
        "glb": manifest["outputs"]["oatPortableTexturedGlb"],
        "generatedShaderRecipeRecovery": manifest["stats"].get("generatedShaderRecipeRecovery"),
        "manifest": manifest["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
