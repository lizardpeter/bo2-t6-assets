#!/usr/bin/env python3
"""Production T6 world export pipeline v20: vertex-stage binormal attribute.

v20 preserves v19's complete generated normal recipe state and zero-copy N/T/w
aliases, then appends one exact renderer-facing binormal vector per serialized
world vertex group used by generated primitives:

    B_vertex = cross(N_vertex, T_vertex) * TANGENT.w

This preserves the paired retail vertex-shader stage and subsequent interpolation
instead of recomputing a cross from interpolated N/T in a fragment shader.  The
entire v19 logical BIN payload must remain an exact prefix of v20; only derived
binormal VEC3 data (plus alignment padding if required) may be appended.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v19 as v19
from t6_glb_parse_v1 import parse_glb
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
from t6_world_generated_normal_basis_attributes_v2 import (
    FORMAT as BASIS_V2_FORMAT,
    apply_contract,
)
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v20"


class OatTexturedPipelineV20Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _path(record, label: str) -> Path:
    if not isinstance(record, dict):
        raise OatTexturedPipelineV20Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV20Error(f"{label} does not exist: {path}")
    return path


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _postpass(base_glb: bytes) -> tuple[dict, bytes, dict, bytes]:
    document, source_raw = parse_glb(base_glb)
    source_copy = bytes(source_raw)
    document, raw, stats = apply_contract(document, source_raw)
    if raw[:len(source_copy)] != source_copy:
        raise OatTexturedPipelineV20Error("v20 changed bytes inside the v19 BIN prefix")
    return document, raw, stats, source_copy


def run_oat_textured_pipeline(**kwargs) -> dict:
    result = v19.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v19":
        raise OatTexturedPipelineV20Error(
            f"unexpected v19 base manifest {result.get('format')!r}"
        )

    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV20Error("v19 result lacks outputs")
    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v19 portable GLB")
    base_glb = old_glb.read_bytes()

    doc1, raw1, stats1, source1 = _postpass(base_glb)
    doc2, raw2, stats2, source2 = _postpass(base_glb)
    glb1 = glb_bytes(doc1, raw1)
    glb2 = glb_bytes(doc2, raw2)
    if source1 != source2 or raw1 != raw2 or stats1 != stats2 or glb1 != glb2:
        raise OatTexturedPipelineV20Error(
            "v20 vertex-binormal postpass regeneration was not byte-identical"
        )
    if raw1[:len(source1)] != source1:
        raise OatTexturedPipelineV20Error("v20 final BIN does not preserve v19 as exact prefix")
    expected_growth = int(stats1["appendedBinBytes"])
    if len(raw1) - len(source1) != expected_growth:
        raise OatTexturedPipelineV20Error(
            f"v20 BIN growth {len(raw1)-len(source1)} != contract {expected_growth}"
        )

    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v20.glb"
    new_glb.write_bytes(glb1)
    if old_glb != new_glb and old_glb.is_file():
        old_glb.unlink()
    outputs["oatPortableTexturedGlb"] = _record(new_glb, glb1)

    old_gltf_record = outputs.get("oatPortableTexturedGltf")
    gltf_deterministic = None
    if isinstance(old_gltf_record, dict):
        old_gltf = _path(old_gltf_record, "v19 portable glTF")
        text1 = gltf_bytes(doc1, raw1)
        text2 = gltf_bytes(doc2, raw2)
        if text1 != text2:
            raise OatTexturedPipelineV20Error(
                "v20 vertex-binormal glTF regeneration was not byte-identical"
            )
        gltf_deterministic = True
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v20.gltf"
        new_gltf.write_bytes(text1)
        if old_gltf != new_gltf and old_gltf.is_file():
            old_gltf.unlink()
        outputs["oatPortableTexturedGltf"] = _record(new_gltf, text1)

    result.setdefault("stats", {})["generatedNormalBasisAttributesV2"] = stats1
    result.setdefault("validation", {}).update({
        "v20GeneratedNormalBasisV2Attached": True,
        "v20GeneratedNormalBasisV2Format": BASIS_V2_FORMAT,
        "v20V19BinExactPrefix": True,
        "v20V19BinBytes": len(source1),
        "v20FinalBinBytes": len(raw1),
        "v20AppendedBinBytes": expected_growth,
        "v20DerivedBinormalVertexCount": int(stats1["derivedBinormalVertexCount"]),
        "v20DerivedBinormalAccessorCount": int(stats1["derivedBinormalAccessorCount"]),
        "v20GlbRegenerationByteIdentical": True,
        "v20GltfRegenerationByteIdentical": gltf_deterministic,
    })
    result.setdefault("policies", {})["v20GeneratedWorldBinormal"] = (
        "derive cross(N,T)*TANGENT.w once per exported vertex and interpolate as its own custom attribute; "
        "v19 BIN is immutable prefix; do not recompute cross after interpolation"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        path = Path(str(old_manifest.get("path") or ""))
        if path.is_file():
            path.unlink()
    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v20.json"
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
        "basisV2": result["stats"]["generatedNormalBasisAttributesV2"],
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
