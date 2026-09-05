#!/usr/bin/env python3
"""Production T6 world export pipeline v13: paired generated vertex shaders.

v13 preserves the complete v12 artifact and authoritative generated-attribute
contract. In automatic Nuketown recipe-recovery mode only, it upgrades the
recipe producer from recovery v4 to v5 so every generated Material also carries
the exact paired slot-4 vertex-shader payload identity from the same OAT pass as
its canonical pixel shader.

No physical VS output role is inferred here. That remains a separate direct
DXBC proof before layered-normal playback is promoted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v5 as recipe_recovery_v5
import t6_oat_world_textured_export_pipeline_v11 as v11
import t6_oat_world_textured_export_pipeline_v12 as v12
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE


FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v13"


class OatTexturedPipelineV13Error(RuntimeError):
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
        raise OatTexturedPipelineV13Error(f"missing {label} file record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV13Error(f"{label} file does not exist: {path}")
    return path


def run_oat_textured_pipeline(**kwargs) -> dict:
    old_recovery = v11.recipe_recovery_v4
    v11.recipe_recovery_v4 = recipe_recovery_v5
    try:
        result = v12.run_oat_textured_pipeline(**kwargs)
    finally:
        v11.recipe_recovery_v4 = old_recovery

    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v12":
        raise OatTexturedPipelineV13Error(
            f"unexpected v12 base manifest {result.get('format')!r}"
        )
    map_name = str(kwargs["map_name"])
    output_dir = Path(kwargs["output_dir"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV13Error("v12 result lacks outputs")

    recovery = result.get("stats", {}).get("generatedShaderRecipeRecovery")
    automatic = isinstance(recovery, dict)
    if automatic:
        if recovery.get("format") != recipe_recovery_v5.FORMAT:
            raise OatTexturedPipelineV13Error(
                f"automatic recipe recovery did not reach v5: {recovery.get('format')!r}"
            )
        if not bool(recovery.get("pairedVertexShaderCoverageComplete")):
            raise OatTexturedPipelineV13Error(
                "automatic recipe recovery did not close paired vertex-shader coverage"
            )
        if int(recovery.get("pairedVertexShaderMaterialCount", -1)) != int(
            recovery.get("generatedMaterialCount", -2)
        ):
            raise OatTexturedPipelineV13Error(
                "paired vertex-shader material count differs from generated recipe population"
            )

    glb_old = _record_path(
        outputs.get("oatPortableTexturedGlb"), "v12 portable textured GLB"
    )
    glb_new = output_dir / f"{map_name}.world_oat_portable_textured_v13.glb"
    glb_old.replace(glb_new)
    outputs["oatPortableTexturedGlb"] = _file_record(glb_new)

    gltf_record = outputs.get("oatPortableTexturedGltf")
    if isinstance(gltf_record, dict):
        gltf_old = _record_path(gltf_record, "v12 portable textured glTF")
        gltf_new = output_dir / f"{map_name}.world_oat_portable_textured_v13.gltf"
        gltf_old.replace(gltf_new)
        outputs["oatPortableTexturedGltf"] = _file_record(gltf_new)

    validation = result.setdefault("validation", {})
    validation.update({
        "v13AutomaticRecipeRecoveryUsesV5": automatic,
        "v13PairedVertexShaderCoverageComplete": (
            None if not automatic else bool(recovery["pairedVertexShaderCoverageComplete"])
        ),
        "v13PairedVertexShaderMaterialCount": (
            None if not automatic else int(recovery["pairedVertexShaderMaterialCount"])
        ),
        "v13PairedVertexShaderTechniqueSetCount": (
            None if not automatic else int(recovery["pairedVertexShaderTechniqueSetCount"])
        ),
        "v13UniquePairedVertexShaderCount": (
            None if not automatic else int(recovery["uniquePairedVertexShaderCount"])
        ),
    })
    result.setdefault("policies", {})["v13PairedGeneratedVertexShaders"] = (
        "automatic Nuketown generated recipes retain exact paired slot-4 OAT vertex-shader "
        "asset/file/SHA from the same pass as the canonical pixel shader; physical output "
        "roles remain unassigned until separate direct-DXBC proof"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v13.json"
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
        "generatedShaderRecipeRecovery": result["stats"].get("generatedShaderRecipeRecovery"),
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
