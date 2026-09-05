#!/usr/bin/env python3
"""Production T6 world export pipeline v9: shader recipes + reflection resources.

v9 preserves the complete production v8 path (retail vertex-format registry
preflight, exact OAT material/image/lightmap data, render-state contract, and
retail-grounded wgpu pipeline state), then applies a deterministic final GLB
post-pass for two additional independently proven contracts:

1. optional canonical generated-world shader recipes at
   `material.extras.T6.generatedShaderRecipeV1`, joined by exact material name;
2. optional exact reflection-probe resource ownership:
     GfxSurface.reflectionProbeIndex
       -> GfxWorld.draw.reflectionProbes[index]
       -> nullable reflectionImage GfxImage
       -> verbatim OAT DDS payload archived in an untyped GLB bufferView.

Reflection DDS containers are not flattened into 2D textures. Their faces,
mips, and native DDS pixel-format metadata remain in the original bytes. Probe
shader equations remain separate in `t6_reflection_probe_semantics_v1.py`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v8 as v8
from t6_generated_shader_recipe_contract_v1 import attach_recipes
from t6_glb_parse_v1 import parse_glb
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_reflection_probe_glb_embed_v1 import (
    ARCHIVE_FORMAT as REFLECTION_ARCHIVE_FORMAT,
    embed_reflection_probe_dds,
)
from t6_world_reflection_probe_manifest_v2 import (
    FORMAT as REFLECTION_MANIFEST_FORMAT,
    build_manifest as build_reflection_probe_manifest,
)


FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v9"


class OatTexturedPipelineV9Error(RuntimeError):
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
        raise OatTexturedPipelineV9Error(f"missing {label} file record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV9Error(f"{label} file does not exist: {path}")
    return path


def _normalized_world(result: dict) -> dict:
    inputs = result.get("inputs")
    if not isinstance(inputs, dict):
        raise OatTexturedPipelineV9Error("v8 result lacks inputs")
    base_manifest_path = _record_path(
        inputs.get("baseWorldPipelineManifest"), "base world pipeline manifest"
    )
    base = json.loads(base_manifest_path.read_text(encoding="utf-8"))
    outputs = base.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV9Error("base world pipeline manifest lacks outputs")
    normalized_path = _record_path(outputs.get("normalizedWorld"), "normalized world")
    world = json.loads(normalized_path.read_text(encoding="utf-8"))
    if world.get("format") != "t6-world-mesh-normalized-v1":
        raise OatTexturedPipelineV9Error(
            f"unexpected normalized world format {world.get('format')!r}"
        )
    return world


def _postprocess_once(
    base_glb: bytes,
    *,
    shader_recipe_manifest: dict | None,
    reflection_manifest: dict | None,
    dds_root: Path,
    allow_missing_reflection_probe_dds: bool,
) -> tuple[dict, bytes, dict | None, dict | None]:
    document, raw = parse_glb(base_glb)

    recipe_stats = None
    if shader_recipe_manifest is not None:
        recipe_stats = attach_recipes(
            document,
            shader_recipe_manifest,
            require_all_generated_materials=True,
            reject_unused_recipes=True,
        )

    reflection_stats = None
    if reflection_manifest is not None:
        document, raw = embed_reflection_probe_dds(
            document,
            raw,
            reflection_manifest,
            dds_root=dds_root,
            allow_missing=allow_missing_reflection_probe_dds,
        )
        reflection_stats = document["extras"]["T6"]["reflectionProbeArchive"]["stats"]

    return document, raw, recipe_stats, reflection_stats


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
    result = v8.run_oat_textured_pipeline(
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
        write_gltf=write_gltf,
        shadowmap_bias=shadowmap_bias,
        shadowmap_scale=shadowmap_scale,
        allow_unresolved_world_materials=allow_unresolved_world_materials,
        allow_missing_oat_materials=allow_missing_oat_materials,
        allow_missing_dds=allow_missing_dds,
        allow_missing_preview_textures=allow_missing_preview_textures,
        allow_missing_dependency_textures=allow_missing_dependency_textures,
        allow_missing_lightmap_dds=allow_missing_lightmap_dds,
    )
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v8":
        raise OatTexturedPipelineV9Error(
            f"unexpected v8 base manifest {result.get('format')!r}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV9Error("v8 result lacks outputs")

    reflection_manifest = None
    reflection_catalog_input = None
    if reflection_probe_catalog_path is not None:
        world = _normalized_world(result)
        catalog_raw = reflection_probe_catalog_path.read_bytes()
        catalog_doc = json.loads(catalog_raw.decode("utf-8"))
        reflection_manifest = build_reflection_probe_manifest(
            world,
            catalog_doc,
            source_texture_extension=".dds",
        )
        reflection_payload = _json_bytes(reflection_manifest)
        reflection_path = (
            output_dir / f"{map_name}.world_reflection_probe_manifest_v2.json"
        )
        reflection_path.write_bytes(reflection_payload)
        outputs["worldReflectionProbeManifest"] = _file_record(
            reflection_path, reflection_payload
        )
        reflection_catalog_input = _file_record(
            reflection_probe_catalog_path, catalog_raw
        )

    shader_recipe_manifest = None
    shader_recipe_input = None
    if generated_shader_recipe_manifest_path is not None:
        recipe_raw = generated_shader_recipe_manifest_path.read_bytes()
        shader_recipe_manifest = json.loads(recipe_raw.decode("utf-8"))
        shader_recipe_input = _file_record(
            generated_shader_recipe_manifest_path, recipe_raw
        )

    base_glb_path = _record_path(
        outputs.get("oatPortableTexturedGlb"), "v8 portable textured GLB"
    )
    base_glb = base_glb_path.read_bytes()

    document1, raw1, recipe_stats1, reflection_stats1 = _postprocess_once(
        base_glb,
        shader_recipe_manifest=shader_recipe_manifest,
        reflection_manifest=reflection_manifest,
        dds_root=dds_root,
        allow_missing_reflection_probe_dds=allow_missing_reflection_probe_dds,
    )
    glb1 = glb_bytes(document1, raw1)

    document2, raw2, recipe_stats2, reflection_stats2 = _postprocess_once(
        base_glb,
        shader_recipe_manifest=shader_recipe_manifest,
        reflection_manifest=reflection_manifest,
        dds_root=dds_root,
        allow_missing_reflection_probe_dds=allow_missing_reflection_probe_dds,
    )
    glb2 = glb_bytes(document2, raw2)
    if raw2 != raw1 or glb2 != glb1:
        raise OatTexturedPipelineV9Error(
            "v9 shader/reflection GLB post-pass regeneration was not byte-identical"
        )
    if recipe_stats2 != recipe_stats1 or reflection_stats2 != reflection_stats1:
        raise OatTexturedPipelineV9Error(
            "v9 shader/reflection semantic stats changed across regeneration"
        )

    final_glb_path = output_dir / f"{map_name}.world_oat_portable_textured_v9.glb"
    final_glb_path.write_bytes(glb1)
    if base_glb_path != final_glb_path and base_glb_path.is_file():
        base_glb_path.unlink()
    outputs["oatPortableTexturedGlb"] = _file_record(final_glb_path, glb1)

    gltf_deterministic = None
    if write_gltf:
        gltf1 = gltf_bytes(document1, raw1)
        gltf2 = gltf_bytes(document2, raw2)
        if gltf2 != gltf1:
            raise OatTexturedPipelineV9Error(
                "v9 shader/reflection glTF post-pass regeneration was not byte-identical"
            )
        gltf_deterministic = True
        prior = outputs.get("oatPortableTexturedGltf")
        if isinstance(prior, dict):
            prior_path = _record_path(prior, "v8 portable textured glTF")
            if prior_path.is_file():
                prior_path.unlink()
        final_gltf_path = output_dir / f"{map_name}.world_oat_portable_textured_v9.gltf"
        final_gltf_path.write_bytes(gltf1)
        outputs["oatPortableTexturedGltf"] = _file_record(final_gltf_path, gltf1)

    inputs = result.setdefault("inputs", {})
    inputs["reflectionProbeCatalog"] = reflection_catalog_input
    inputs["generatedShaderRecipeManifest"] = shader_recipe_input

    stats = result.setdefault("stats", {})
    stats["generatedShaderRecipes"] = recipe_stats1
    stats["reflectionProbes"] = (
        None if reflection_manifest is None else reflection_manifest["stats"]
    )
    stats["reflectionProbeArchive"] = reflection_stats1

    validation = result.setdefault("validation", {})
    validation.update(
        {
            "canonicalGeneratedShaderRecipesAttached": recipe_stats1 is not None,
            "generatedShaderRecipeContract": (
                "material.extras.T6.generatedShaderRecipeV1"
                if recipe_stats1 is not None
                else None
            ),
            "generatedShaderRecipeAttachedCount": (
                None if recipe_stats1 is None else recipe_stats1["attachedRecipeCount"]
            ),
            "reflectionProbeCatalogJoined": reflection_manifest is not None,
            "reflectionProbeManifestFormat": (
                REFLECTION_MANIFEST_FORMAT if reflection_manifest is not None else None
            ),
            "reflectionProbeArchiveFormat": (
                REFLECTION_ARCHIVE_FORMAT if reflection_manifest is not None else None
            ),
            "reflectionProbeRawDdsArchiveEmbedded": reflection_stats1 is not None,
            "v9PostpassGlbRegenerationByteIdentical": True,
            "v9PostpassGltfRegenerationByteIdentical": gltf_deterministic,
        }
    )
    if reflection_manifest is not None and reflection_stats1 is not None:
        validation.update(
            {
                "reflectionProbeCount": reflection_manifest["stats"]["reflectionProbeCount"],
                "referencedReflectionProbeCount": reflection_manifest["stats"][
                    "referencedReflectionProbeCount"
                ],
                "reflectionProbePresentImageCount": reflection_manifest["stats"][
                    "presentReflectionImageProbeCount"
                ],
                "reflectionProbeAbsentImageCount": reflection_manifest["stats"][
                    "absentReflectionImageProbeCount"
                ],
                "reflectionProbeUniqueGfxImageCount": reflection_stats1[
                    "uniquePresentGfxImageCount"
                ],
                "reflectionProbeEmbeddedGfxImageCount": reflection_stats1[
                    "embeddedGfxImageCount"
                ],
                "reflectionProbeMissingGfxImageCount": reflection_stats1[
                    "missingGfxImageCount"
                ],
                "reflectionProbeAccountedGfxImageCount": reflection_stats1[
                    "accountedGfxImageCount"
                ],
            }
        )

    policies = result.setdefault("policies", {})
    policies["generatedShaderRecipes"] = (
        "optional canonical source-backed generated shader recipe manifest; exact material-name "
        "join; every generated '*' material and every supplied recipe must account exactly; no "
        "TechniqueSet or shader-archetype inference from compound material names"
    )
    policies["reflectionProbes"] = (
        "optional exact GfxSurface.reflectionProbeIndex -> dense GfxWorld.draw.reflectionProbes[] "
        "join preserving origin, SH, nullable reflectionImage, volume planes and mipLodBias; "
        "present reflection DDS bytes archived verbatim; no sentinel, nearest-probe search, "
        "cubemap flattening, face extraction, PBR environment binding or fallback image"
    )
    policies["reflectionRendererContract"] = (
        "coordinate/decode/mip and family-specific weighting remain in "
        "t6_reflection_probe_semantics_v1.py; resource archival does not widen shader proof"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v9.json"
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
    parser.add_argument("--dds-root", type=Path, required=True)
    parser.add_argument("--format-registry", type=Path, required=True)
    parser.add_argument("--lightmap-catalog", type=Path)
    parser.add_argument("--reflection-probe-catalog", type=Path)
    parser.add_argument("--generated-shader-recipes", type=Path)
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
        dds_root=args.dds_root,
        output_dir=args.out_dir,
        format_registry_path=args.format_registry,
        lightmap_catalog_path=args.lightmap_catalog,
        reflection_probe_catalog_path=args.reflection_probe_catalog,
        generated_shader_recipe_manifest_path=args.generated_shader_recipes,
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
    print(
        json.dumps(
            {
                "map": manifest["map"],
                "manifest": manifest["manifest"],
                "worldVertexFormatGate": manifest["stats"]["worldVertexFormatGate"],
                "t6WgpuState": manifest["stats"]["t6WgpuState"],
                "generatedShaderRecipes": manifest["stats"]["generatedShaderRecipes"],
                "reflectionProbes": manifest["stats"]["reflectionProbes"],
                "reflectionProbeArchive": manifest["stats"]["reflectionProbeArchive"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
