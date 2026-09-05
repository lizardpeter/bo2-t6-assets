#!/usr/bin/env python3
"""Production T6 world export pipeline v19: exact normal basis vertex attributes.

v19 preserves v18's complete generated normal recipe state and performs one
renderer-facing zero-copy GLB postpass.  For generated primitives it exposes the
already exact standard NORMAL/TANGENT bytes as custom T6 attributes, including
TANGENT.w handedness, so Blender/Tour do not need to recompute a tangent basis.

The BIN chunk must remain byte-identical.  The postpass is regenerated twice
from untouched v18 bytes and the final GLB/glTF must be deterministic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v18 as v18
from t6_glb_parse_v1 import parse_glb
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
from t6_world_generated_normal_basis_attributes_v1 import (
    FORMAT as BASIS_ATTRIBUTE_FORMAT,
    apply_contract,
)
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v19"


class OatTexturedPipelineV19Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _path(record, label: str) -> Path:
    if not isinstance(record, dict):
        raise OatTexturedPipelineV19Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV19Error(f"{label} does not exist: {path}")
    return path


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _postpass(base_glb: bytes) -> tuple[dict, bytes, dict]:
    document, raw = parse_glb(base_glb)
    original_raw = raw
    document, raw, stats = apply_contract(document, raw)
    if raw != original_raw:
        raise OatTexturedPipelineV19Error("v19 normal-basis attribute postpass changed BIN bytes")
    return document, raw, stats


def run_oat_textured_pipeline(**kwargs) -> dict:
    result = v18.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v18":
        raise OatTexturedPipelineV19Error(
            f"unexpected v18 base manifest {result.get('format')!r}"
        )

    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV19Error("v18 result lacks outputs")
    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v18 portable GLB")
    base_glb = old_glb.read_bytes()
    base_doc, base_raw = parse_glb(base_glb)
    base_raw_sha = _sha(base_raw)

    doc1, raw1, stats1 = _postpass(base_glb)
    doc2, raw2, stats2 = _postpass(base_glb)
    glb1 = glb_bytes(doc1, raw1)
    glb2 = glb_bytes(doc2, raw2)
    if raw1 != raw2 or raw1 != base_raw:
        raise OatTexturedPipelineV19Error("v19 BIN payload is not byte-identical to v18")
    if stats1 != stats2 or glb1 != glb2:
        raise OatTexturedPipelineV19Error(
            "v19 normal-basis attribute GLB regeneration was not byte-identical"
        )
    if _sha(raw1) != base_raw_sha or not bool(stats1.get("binByteIdentical")):
        raise OatTexturedPipelineV19Error("v19 normal-basis contract did not prove BIN identity")

    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v19.glb"
    new_glb.write_bytes(glb1)
    if old_glb != new_glb and old_glb.is_file():
        old_glb.unlink()
    outputs["oatPortableTexturedGlb"] = _record(new_glb, glb1)

    old_gltf_record = outputs.get("oatPortableTexturedGltf")
    gltf_deterministic = None
    if isinstance(old_gltf_record, dict):
        old_gltf = _path(old_gltf_record, "v18 portable glTF")
        text1 = gltf_bytes(doc1, raw1)
        text2 = gltf_bytes(doc2, raw2)
        if text1 != text2:
            raise OatTexturedPipelineV19Error(
                "v19 normal-basis attribute glTF regeneration was not byte-identical"
            )
        gltf_deterministic = True
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v19.gltf"
        new_gltf.write_bytes(text1)
        if old_gltf != new_gltf and old_gltf.is_file():
            old_gltf.unlink()
        outputs["oatPortableTexturedGltf"] = _record(new_gltf, text1)

    result.setdefault("stats", {})["generatedNormalBasisAttributes"] = stats1
    result.setdefault("validation", {}).update({
        "v19GeneratedNormalBasisAttributesAttached": True,
        "v19GeneratedNormalBasisAttributeFormat": BASIS_ATTRIBUTE_FORMAT,
        "v19GeneratedNormalBasisBinByteIdentical": True,
        "v19GeneratedNormalBasisBinSha256": base_raw_sha,
        "v19GeneratedNormalBasisGlbRegenerationByteIdentical": True,
        "v19GeneratedNormalBasisGltfRegenerationByteIdentical": gltf_deterministic,
        "v19GeneratedPrimitiveCount": int(stats1["generatedPrimitiveCount"]),
        "v19UniqueTangentSourceAccessorCount": int(stats1["uniqueTangentSourceAccessorCount"]),
    })
    result.setdefault("policies", {})["v19GeneratedNormalBasisAttributes"] = (
        "generated primitives expose exact existing NORMAL and TANGENT.xyz/w bytes through custom T6 attributes; "
        "no renderer tangent recomputation and no BIN payload mutation"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        path = Path(str(old_manifest.get("path") or ""))
        if path.is_file():
            path.unlink()
    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v19.json"
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
        map_name=a.map_name,
        surfaces_path=a.surfaces,
        vd0_path=a.vd0,
        vd1_path=a.vd1,
        indices_path=a.indices,
        materials_path=a.materials,
        catalog_path=a.catalog,
        prefix_path=a.prefix,
        asset_pointer_array_virtual_base=a.asset_pointer_base,
        oat_material_root=a.oat_material_root,
        oat_shader_root=a.oat_shader_root,
        dds_root=a.dds_root,
        output_dir=a.out_dir,
        format_registry_path=a.format_registry,
        lightmap_catalog_path=a.lightmap_catalog,
        reflection_probe_catalog_path=a.reflection_probe_catalog,
        generated_shader_recipe_manifest_path=a.generated_shader_recipes,
        generated_shader_expanded_world_path=a.generated_shader_expanded_world,
        generated_normal_basis_proof_path=a.generated_normal_basis_proof,
        write_gltf=a.write_gltf,
        shadowmap_bias=a.sm_polygon_offset_bias,
        shadowmap_scale=a.sm_polygon_offset_scale,
        allow_unresolved_world_materials=a.allow_unresolved_world_materials,
        allow_missing_oat_materials=a.allow_missing_oat_materials,
        allow_missing_dds=a.allow_missing_dds,
        allow_missing_preview_textures=a.allow_missing_preview_textures,
        allow_missing_dependency_textures=a.allow_missing_dependency_textures,
        allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,
        allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds,
    )
    print(json.dumps({
        "format": result["format"],
        "glb": result["outputs"]["oatPortableTexturedGlb"],
        "basisAttributes": result["stats"]["generatedNormalBasisAttributes"],
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
