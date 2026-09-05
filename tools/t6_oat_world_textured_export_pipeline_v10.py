#!/usr/bin/env python3
"""Production T6 world export pipeline v10: recover Nuketown shader recipes.

v10 preserves the complete v9 production path and adds one exact orchestration
mode for mp_nuketown_2020: rebuild the previously uncommitted 120-row generated
shader recipe manifest directly from the retained expanded retail world and a
normal OAT T6 dump before v9 attaches those recipes to the portable GLB.

Manual ``--generated-shader-recipes`` remains supported and mutually exclusive
with automatic recovery.  Automatic recovery is deliberately Nuketown-specific
until equivalent retained-world gates are defined for other maps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v1 as recipe_recovery
import t6_oat_world_textured_export_pipeline_v9 as v9
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE


FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v10"


class OatTexturedPipelineV10Error(RuntimeError):
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
        raise OatTexturedPipelineV10Error(f"missing {label} file record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV10Error(f"{label} file does not exist: {path}")
    return path


def _recover_recipe_manifest(
    *,
    map_name: str,
    expanded_world: Path,
    oat_shader_root: Path,
    output_dir: Path,
) -> tuple[Path, dict, bytes]:
    if map_name != recipe_recovery.MAP:
        raise OatTexturedPipelineV10Error(
            "automatic generated-shader recovery v1 is source-gated to "
            f"{recipe_recovery.MAP!r}, got {map_name!r}"
        )
    doc1 = recipe_recovery.recover(
        expanded_world=expanded_world,
        oat_root=oat_shader_root,
        strict_nuketown=True,
    )
    doc2 = recipe_recovery.recover(
        expanded_world=expanded_world,
        oat_root=oat_shader_root,
        strict_nuketown=True,
    )
    payload1 = _json_bytes(doc1)
    payload2 = _json_bytes(doc2)
    if doc2 != doc1 or payload2 != payload1:
        raise OatTexturedPipelineV10Error(
            "Nuketown generated-shader recovery was not deterministic"
        )
    path = output_dir / f"{map_name}.generated_shader_recipes_v1.json"
    path.write_bytes(payload1)
    return path, doc1, payload1


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
    auto_requested = (
        generated_shader_expanded_world_path is not None or oat_shader_root is not None
    )
    if generated_shader_recipe_manifest_path is not None and auto_requested:
        raise OatTexturedPipelineV10Error(
            "manual generated-shader manifest and automatic recovery are mutually exclusive"
        )
    if (generated_shader_expanded_world_path is None) != (oat_shader_root is None):
        raise OatTexturedPipelineV10Error(
            "automatic recovery requires both generated_shader_expanded_world_path and oat_shader_root"
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    recovery_doc = None
    recovery_payload = None
    recovery_path = None
    recipe_path = generated_shader_recipe_manifest_path
    if auto_requested:
        recovery_path, recovery_doc, recovery_payload = _recover_recipe_manifest(
            map_name=map_name,
            expanded_world=Path(generated_shader_expanded_world_path),
            oat_shader_root=Path(oat_shader_root),
            output_dir=output_dir,
        )
        recipe_path = recovery_path

    result = v9.run_oat_textured_pipeline(
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
        generated_shader_recipe_manifest_path=recipe_path,
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
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v9":
        raise OatTexturedPipelineV10Error(
            f"unexpected v9 base manifest {result.get('format')!r}"
        )

    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV10Error("v9 result lacks outputs")

    # The content is already final after v9. Rename only the production artifact
    # generation so the filename cannot misrepresent the manifest contract.
    glb_old = _record_path(outputs.get("oatPortableTexturedGlb"), "v9 portable textured GLB")
    glb_new = output_dir / f"{map_name}.world_oat_portable_textured_v10.glb"
    glb_old.replace(glb_new)
    outputs["oatPortableTexturedGlb"] = _file_record(glb_new)

    gltf_record = outputs.get("oatPortableTexturedGltf")
    if isinstance(gltf_record, dict):
        gltf_old = _record_path(gltf_record, "v9 portable textured glTF")
        gltf_new = output_dir / f"{map_name}.world_oat_portable_textured_v10.gltf"
        gltf_old.replace(gltf_new)
        outputs["oatPortableTexturedGltf"] = _file_record(gltf_new)

    inputs = result.setdefault("inputs", {})
    inputs["generatedShaderRecipeRecoveryExpandedWorld"] = (
        None
        if generated_shader_expanded_world_path is None
        else _file_record(Path(generated_shader_expanded_world_path))
    )
    inputs["generatedShaderRecipeRecoveryOatRoot"] = (
        None if oat_shader_root is None else str(Path(oat_shader_root))
    )
    if recovery_path is not None and recovery_payload is not None:
        inputs["generatedShaderRecipeManifest"] = _file_record(
            recovery_path, recovery_payload
        )

    stats = result.setdefault("stats", {})
    stats["generatedShaderRecipeRecovery"] = (
        None if recovery_doc is None else recovery_doc["recovery"]
    )

    validation = result.setdefault("validation", {})
    validation.update({
        "v10AutomaticGeneratedShaderRecipeRecovery": recovery_doc is not None,
        "v10RecoveredRecipeManifestDeterministic": recovery_doc is not None,
        "v10RecoveredGeneratedMaterialCount": (
            None if recovery_doc is None else recovery_doc["recovery"]["generatedMaterialCount"]
        ),
        "v10RecoveredUniqueTechniqueSetCount": (
            None if recovery_doc is None else recovery_doc["recovery"]["uniqueTechniqueSetCount"]
        ),
        "v10RecoveredUniqueSlot4PixelShaderCount": (
            None
            if recovery_doc is None
            else recovery_doc["recovery"]["uniqueSlot4PixelShaderCount"]
        ),
        "v10RecoveredCrossTechniqueSetShaderReuseCount": (
            None
            if recovery_doc is None
            else recovery_doc["recovery"]["crossTechniqueSetShaderReuseCount"]
        ),
    })

    policies = result.setdefault("policies", {})
    policies["v10GeneratedShaderRecipeRecovery"] = (
        "For mp_nuketown_2020, optional automatic recovery binds each retail generated "
        "Material::techniqueSet pointer to its exact TechniqueSet, resolves zero-based T6 "
        "technique slot 4 ('lit') through OAT .techset/.tech assets, hashes the verbatim "
        "DX11 shader_bin payload, and requires retained 120 material / 34 TechniqueSet / "
        "34 unique shader / 95,7,17,1 world-format invariants. No compound material name "
        "is used to infer TechniqueSet or pixel-shader identity."
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v10.json"
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
        "map": map_name if (map_name := manifest.get("map")) else args.map_name,
        "glb": manifest["outputs"]["oatPortableTexturedGlb"],
        "generatedShaderRecipeRecovery": manifest["stats"].get("generatedShaderRecipeRecovery"),
        "manifest": manifest["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
