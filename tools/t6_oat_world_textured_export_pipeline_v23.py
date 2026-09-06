#!/usr/bin/env python3
"""Production T6 world export pipeline v23: per-surface lightmap preview shells.

v23 preserves v22 and, when derived lightmap previews are present, specializes
preview material shells by exact (retail material, lightmapIndex, lightmap UV
set).  This is JSON-only: the entire v22 BIN remains byte-identical.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v22 as v22
from t6_glb_parse_v1 import parse_glb
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_lightmap_material_specialize_v1 import (
    FORMAT as SPECIALIZATION_FORMAT,
    specialize,
)
from t6_world_lightmap_preview_embed_v1 import ROOT_KEY as PREVIEW_ROOT

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v23"


class OatTexturedPipelineV23Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _path(record, label: str) -> Path:
    if not isinstance(record, dict):
        raise OatTexturedPipelineV23Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV23Error(f"{label} does not exist: {path}")
    return path


def run_oat_textured_pipeline(**kwargs) -> dict:
    result = v22.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v22":
        raise OatTexturedPipelineV23Error(
            f"unexpected v22 base manifest {result.get('format')!r}"
        )
    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs", {})
    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v22 portable GLB")
    base_glb = old_glb.read_bytes()
    source_doc, source_raw = parse_glb(base_glb)
    source_copy = bytes(source_raw)
    has_previews = isinstance(
        source_doc.get("extras", {}).get("T6", {}).get(PREVIEW_ROOT), dict
    )

    specialization_stats = None
    if has_previews:
        try:
            doc1, raw1, stats1 = specialize(source_doc, source_raw)
            doc2, raw2, stats2 = specialize(*parse_glb(base_glb))
        except Exception as exc:
            raise OatTexturedPipelineV23Error(
                f"per-surface lightmap preview specialization failed: {exc}"
            ) from exc
        glb1 = glb_bytes(doc1, raw1)
        glb2 = glb_bytes(doc2, raw2)
        if raw1 != source_copy or raw2 != source_copy:
            raise OatTexturedPipelineV23Error("v23 changed v22 BIN bytes")
        if stats1 != stats2 or glb1 != glb2:
            raise OatTexturedPipelineV23Error(
                "v23 lightmap material specialization regeneration was not byte-identical"
            )
        specialization_stats = stats1
    else:
        doc1, raw1, glb1 = source_doc, source_raw, base_glb

    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v23.glb"
    new_glb.write_bytes(glb1)
    if old_glb != new_glb and old_glb.is_file():
        old_glb.unlink()
    outputs["oatPortableTexturedGlb"] = _record(new_glb, glb1)

    old_gltf_record = outputs.get("oatPortableTexturedGltf")
    gltf_deterministic = None
    if isinstance(old_gltf_record, dict):
        old_gltf = _path(old_gltf_record, "v22 portable glTF")
        text1 = gltf_bytes(doc1, raw1)
        if has_previews:
            doc_check, raw_check, _ = specialize(*parse_glb(base_glb))
            text2 = gltf_bytes(doc_check, raw_check)
            if text1 != text2:
                raise OatTexturedPipelineV23Error(
                    "v23 specialized glTF regeneration was not byte-identical"
                )
            gltf_deterministic = True
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v23.gltf"
        new_gltf.write_bytes(text1)
        if old_gltf != new_gltf and old_gltf.is_file():
            old_gltf.unlink()
        outputs["oatPortableTexturedGltf"] = _record(new_gltf, text1)

    result.setdefault("stats", {})["lightmapMaterialSpecialization"] = specialization_stats
    result.setdefault("validation", {}).update({
        "v23LightmapPreviewPresent": has_previews,
        "v23MaterialSpecializationFormat": SPECIALIZATION_FORMAT if has_previews else None,
        "v23BinByteIdenticalToV22": True,
        "v23SpecializedMaterialCount": None if specialization_stats is None else int(specialization_stats["specializedMaterialCount"]),
        "v23RedirectedLightmappedPrimitiveCount": None if specialization_stats is None else int(specialization_stats["redirectedLightmappedPrimitiveCount"]),
        "v23MissingPresentPreviewRoleUseCount": None if specialization_stats is None else int(specialization_stats["missingPresentPreviewRoleUseCount"]),
        "v23GlbRegenerationByteIdentical": True,
        "v23GltfRegenerationByteIdentical": gltf_deterministic,
    })
    result.setdefault("policies", {})["v23LightmapMaterialOwnership"] = (
        "preview-only material variants follow exact GfxSurface.lightmapIndex and lightmap TEXCOORD ownership; "
        "canonical retail material/recipe identity and all BIN bytes remain unchanged"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        p = Path(str(old_manifest.get("path") or ""))
        if p.is_file():
            p.unlink()
    result["format"] = FORMAT
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v23.json"
    manifest_path.write_bytes(payload)
    result["manifest"] = _record(manifest_path, payload)
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--map", dest="map_name", required=True)
    p.add_argument("--surfaces", type=Path, required=True); p.add_argument("--vd0", type=Path, required=True)
    p.add_argument("--vd1", type=Path, required=True); p.add_argument("--indices", type=Path, required=True)
    p.add_argument("--materials", type=Path, required=True); p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--prefix", type=Path, required=True); p.add_argument("--asset-pointer-base", type=lambda v:int(v,0), required=True)
    p.add_argument("--oat-material-root", type=Path, required=True); p.add_argument("--oat-shader-root", type=Path)
    p.add_argument("--dds-root", type=Path, required=True); p.add_argument("--format-registry", type=Path, required=True)
    p.add_argument("--lightmap-catalog", type=Path); p.add_argument("--reflection-probe-catalog", type=Path)
    p.add_argument("--generated-shader-recipes", type=Path); p.add_argument("--generated-shader-expanded-world", type=Path)
    p.add_argument("--generated-normal-basis-proof", type=Path); p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--write-gltf", action="store_true")
    p.add_argument("--sm-polygon-offset-bias", type=int, default=DEFAULT_SHADOWMAP_BIAS)
    p.add_argument("--sm-polygon-offset-scale", type=float, default=DEFAULT_SHADOWMAP_SCALE)
    for flag in ("unresolved-world-materials","missing-oat-materials","missing-dds","missing-preview-textures","missing-dependency-textures","missing-lightmap-dds","missing-reflection-probe-dds"):
        p.add_argument("--allow-" + flag, action="store_true")
    a=p.parse_args()
    result=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds)
    print(json.dumps({"format":result["format"],"glb":result["outputs"]["oatPortableTexturedGlb"],"specialization":result["stats"]["lightmapMaterialSpecialization"],"manifest":result["manifest"]},indent=2,sort_keys=True));return 0

if __name__=="__main__": raise SystemExit(main())
