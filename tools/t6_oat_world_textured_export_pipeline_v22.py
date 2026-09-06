#!/usr/bin/env python3
"""Production T6 world export pipeline v22: derived lightmap preview images.

v22 preserves v21 and, when its canonical nullable lightmap DDS archive exists,
appends deterministic PNG authoring previews derived from the exact embedded DDS
payloads.  The v21 BIN must remain an exact prefix.  DDS remains authoritative;
no material/lightmap shader binding is created here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v21 as v21
from t6_glb_parse_v1 import parse_glb
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_lightmap_preview_embed_v1 import (
    FORMAT as LIGHTMAP_PREVIEW_FORMAT,
    embed_lightmap_previews,
)

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v22"


class OatTexturedPipelineV22Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _path(record, label: str) -> Path:
    if not isinstance(record, dict):
        raise OatTexturedPipelineV22Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV22Error(f"{label} does not exist: {path}")
    return path


def run_oat_textured_pipeline(**kwargs) -> dict:
    result = v21.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v21":
        raise OatTexturedPipelineV22Error(
            f"unexpected v21 base manifest {result.get('format')!r}"
        )
    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs", {})
    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v21 portable GLB")
    base_glb = old_glb.read_bytes()
    source_doc, source_raw = parse_glb(base_glb)
    source_copy = bytes(source_raw)
    has_archive = isinstance(
        source_doc.get("extras", {}).get("T6", {}).get("lightmapArchive"), dict
    )

    preview_stats = None
    if has_archive:
        try:
            doc1, raw1, stats1 = embed_lightmap_previews(source_doc, source_raw)
            doc2, raw2, stats2 = embed_lightmap_previews(*parse_glb(base_glb))
        except Exception as exc:
            raise OatTexturedPipelineV22Error(
                f"derived exact-lightmap preview staging failed: {exc}"
            ) from exc
        glb1 = glb_bytes(doc1, raw1)
        glb2 = glb_bytes(doc2, raw2)
        if raw1[:len(source_copy)] != source_copy or raw2[:len(source_copy)] != source_copy:
            raise OatTexturedPipelineV22Error("v22 changed bytes inside v21 BIN prefix")
        if raw1 != raw2 or stats1 != stats2 or glb1 != glb2:
            raise OatTexturedPipelineV22Error(
                "v22 lightmap preview regeneration was not byte-identical"
            )
        preview_stats = stats1
    else:
        doc1, raw1 = source_doc, source_raw
        glb1 = base_glb

    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v22.glb"
    new_glb.write_bytes(glb1)
    if old_glb != new_glb and old_glb.is_file():
        old_glb.unlink()
    outputs["oatPortableTexturedGlb"] = _record(new_glb, glb1)

    old_gltf_record = outputs.get("oatPortableTexturedGltf")
    gltf_deterministic = None
    if isinstance(old_gltf_record, dict):
        old_gltf = _path(old_gltf_record, "v21 portable glTF")
        text1 = gltf_bytes(doc1, raw1)
        if has_archive:
            doc_check, raw_check, _ = embed_lightmap_previews(*parse_glb(base_glb))
            text2 = gltf_bytes(doc_check, raw_check)
            if text1 != text2:
                raise OatTexturedPipelineV22Error(
                    "v22 lightmap preview glTF regeneration was not byte-identical"
                )
            gltf_deterministic = True
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v22.gltf"
        new_gltf.write_bytes(text1)
        if old_gltf != new_gltf and old_gltf.is_file():
            old_gltf.unlink()
        outputs["oatPortableTexturedGltf"] = _record(new_gltf, text1)

    result.setdefault("stats", {})["lightmapPreviewArchive"] = preview_stats
    result.setdefault("validation", {}).update({
        "v22CanonicalLightmapArchivePresent": has_archive,
        "v22LightmapPreviewFormat": LIGHTMAP_PREVIEW_FORMAT if has_archive else None,
        "v22V21BinExactPrefix": True if has_archive else None,
        "v22SourceBinBytes": len(source_copy),
        "v22FinalBinBytes": len(raw1),
        "v22AppendedPreviewBytes": None if preview_stats is None else int(preview_stats["appendedPreviewBytes"]),
        "v22UniquePreviewImageCount": None if preview_stats is None else int(preview_stats["uniquePreviewImageCount"]),
        "v22GlbRegenerationByteIdentical": True,
        "v22GltfRegenerationByteIdentical": gltf_deterministic,
    })
    result.setdefault("policies", {})["v22LightmapPreview"] = (
        "canonical raw DDS lightmap archive remains authoritative; derived RGBA PNG is preview/data only; "
        "no material binding or lightmap composition is inferred"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        p = Path(str(old_manifest.get("path") or ""))
        if p.is_file():
            p.unlink()
    result["format"] = FORMAT
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v22.json"
    manifest_path.write_bytes(payload)
    result["manifest"] = _record(manifest_path, payload)
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--map", dest="map_name", required=True)
    p.add_argument("--surfaces", type=Path, required=True)
    p.add_argument("--vd0", type=Path, required=True)
    p.add_argument("--vd1", type=Path, required=True)
    p.add_argument("--indices", type=Path, required=True)
    p.add_argument("--materials", type=Path, required=True)
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--prefix", type=Path, required=True)
    p.add_argument("--asset-pointer-base", type=lambda value: int(value, 0), required=True)
    p.add_argument("--oat-material-root", type=Path, required=True)
    p.add_argument("--oat-shader-root", type=Path)
    p.add_argument("--dds-root", type=Path, required=True)
    p.add_argument("--format-registry", type=Path, required=True)
    p.add_argument("--lightmap-catalog", type=Path)
    p.add_argument("--reflection-probe-catalog", type=Path)
    p.add_argument("--generated-shader-recipes", type=Path)
    p.add_argument("--generated-shader-expanded-world", type=Path)
    p.add_argument("--generated-normal-basis-proof", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--write-gltf", action="store_true")
    p.add_argument("--sm-polygon-offset-bias", type=int, default=DEFAULT_SHADOWMAP_BIAS)
    p.add_argument("--sm-polygon-offset-scale", type=float, default=DEFAULT_SHADOWMAP_SCALE)
    for flag in (
        "unresolved-world-materials", "missing-oat-materials", "missing-dds",
        "missing-preview-textures", "missing-dependency-textures", "missing-lightmap-dds",
        "missing-reflection-probe-dds",
    ):
        p.add_argument("--allow-" + flag, action="store_true")
    a = p.parse_args()
    result = run_oat_textured_pipeline(
        map_name=a.map_name, surfaces_path=a.surfaces, vd0_path=a.vd0, vd1_path=a.vd1,
        indices_path=a.indices, materials_path=a.materials, catalog_path=a.catalog,
        prefix_path=a.prefix, asset_pointer_array_virtual_base=a.asset_pointer_base,
        oat_material_root=a.oat_material_root, oat_shader_root=a.oat_shader_root,
        dds_root=a.dds_root, output_dir=a.out_dir, format_registry_path=a.format_registry,
        lightmap_catalog_path=a.lightmap_catalog, reflection_probe_catalog_path=a.reflection_probe_catalog,
        generated_shader_recipe_manifest_path=a.generated_shader_recipes,
        generated_shader_expanded_world_path=a.generated_shader_expanded_world,
        generated_normal_basis_proof_path=a.generated_normal_basis_proof, write_gltf=a.write_gltf,
        shadowmap_bias=a.sm_polygon_offset_bias, shadowmap_scale=a.sm_polygon_offset_scale,
        allow_unresolved_world_materials=a.allow_unresolved_world_materials,
        allow_missing_oat_materials=a.allow_missing_oat_materials, allow_missing_dds=a.allow_missing_dds,
        allow_missing_preview_textures=a.allow_missing_preview_textures,
        allow_missing_dependency_textures=a.allow_missing_dependency_textures,
        allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,
        allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds,
    )
    print(json.dumps({"format": result["format"], "glb": result["outputs"]["oatPortableTexturedGlb"],
                      "lightmapPreview": result["stats"]["lightmapPreviewArchive"],
                      "manifest": result["manifest"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
