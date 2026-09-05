#!/usr/bin/env python3
"""Production T6 world export pipeline v12: authoritative renderer attributes.

v12 preserves the complete v11 output, then performs one final deterministic
GLB semantic postpass so the production artifact matches the source-closed
renderer contract used by the generated shader/Blender adapters:

    TEXCOORD_0 = material UV0
    TEXCOORD_1 = lightmap UV
    TEXCOORD_2/3/4 = material UV1/2/3
    generated '*' COLOR_0 -> _T6_LAYER_WEIGHTS

Raw stored-order normal-transform accessors are retained as *_RAW and replaced
for rendering by appended logical-order normalized UBYTE4 accessors.

No geometry, index, texture, lightmap, reflection, recipe or render-state source
payload is rewritten. Existing binary bytes remain an exact prefix; only the
logical normal-transform payloads can extend buffer 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v11 as v11
from t6_glb_parse_v1 import parse_glb
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
from t6_world_generated_attribute_contract_v1 import (
    FORMAT as ATTRIBUTE_FORMAT,
    normalize_generated_attributes,
)
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes


FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v12"


class OatTexturedPipelineV12Error(RuntimeError):
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
        raise OatTexturedPipelineV12Error(f"missing {label} file record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV12Error(f"{label} file does not exist: {path}")
    return path


def _normalize_once(base_glb: bytes) -> tuple[dict, bytes, dict]:
    document, raw = parse_glb(base_glb)
    source_raw = bytes(raw)
    document, normalized_raw, stats = normalize_generated_attributes(
        document, source_raw
    )
    if normalized_raw[:len(source_raw)] != source_raw:
        raise OatTexturedPipelineV12Error(
            "generated attribute postpass changed the existing GLB binary prefix"
        )
    return document, normalized_raw, stats


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
    result = v11.run_oat_textured_pipeline(
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
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v11":
        raise OatTexturedPipelineV12Error(
            f"unexpected v11 base manifest {result.get('format')!r}"
        )

    output_dir = Path(output_dir)
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV12Error("v11 result lacks outputs")
    base_path = _record_path(
        outputs.get("oatPortableTexturedGlb"), "v11 portable textured GLB"
    )
    base_glb = base_path.read_bytes()

    doc1, raw1, stats1 = _normalize_once(base_glb)
    doc2, raw2, stats2 = _normalize_once(base_glb)
    glb1 = glb_bytes(doc1, raw1)
    glb2 = glb_bytes(doc2, raw2)
    if doc2 != doc1 or raw2 != raw1 or stats2 != stats1 or glb2 != glb1:
        raise OatTexturedPipelineV12Error(
            "v12 generated-attribute regeneration was not byte-identical"
        )

    root_contract = doc1.get("extras", {}).get("T6", {}).get(
        "generatedAttributeContract"
    )
    if not isinstance(root_contract, dict) or root_contract.get("format") != ATTRIBUTE_FORMAT:
        raise OatTexturedPipelineV12Error(
            "v12 output lacks authoritative generated attribute contract"
        )
    if int(stats1.get("generatedColorRetypeCount", -1)) != int(
        stats1.get("generatedPrimitiveCount", -2)
    ):
        raise OatTexturedPipelineV12Error(
            "v12 did not retype every generated primitive layer control"
        )

    final_glb = output_dir / f"{map_name}.world_oat_portable_textured_v12.glb"
    final_glb.write_bytes(glb1)
    if base_path != final_glb and base_path.is_file():
        base_path.unlink()
    outputs["oatPortableTexturedGlb"] = _file_record(final_glb, glb1)

    gltf_deterministic = None
    if write_gltf:
        payload1 = gltf_bytes(doc1, raw1)
        payload2 = gltf_bytes(doc2, raw2)
        if payload1 != payload2:
            raise OatTexturedPipelineV12Error(
                "v12 normalized glTF regeneration was not byte-identical"
            )
        gltf_deterministic = True
        old_gltf = outputs.get("oatPortableTexturedGltf")
        if isinstance(old_gltf, dict):
            old_path = _record_path(old_gltf, "v11 portable textured glTF")
            if old_path.is_file():
                old_path.unlink()
        final_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v12.gltf"
        final_gltf.write_bytes(payload1)
        outputs["oatPortableTexturedGltf"] = _file_record(final_gltf, payload1)

    validation = result.setdefault("validation", {})
    validation.update({
        "v12GeneratedAttributeContract": ATTRIBUTE_FORMAT,
        "v12GeneratedAttributeRegenerationByteIdentical": True,
        "v12GeneratedAttributeGltfRegenerationByteIdentical": gltf_deterministic,
        "v12ExistingBinaryPrefixPreserved": True,
        "v12GeneratedPrimitiveCount": stats1["generatedPrimitiveCount"],
        "v12GeneratedLayerWeightRetypeCount": stats1["generatedColorRetypeCount"],
        "v12TexcoordNormalizedPrimitiveCount": stats1["texcoordNormalizedPrimitiveCount"],
        "v12LogicalNormalTransformAccessorCount": stats1["logicalNormalTransformAccessorCount"],
        "v12NormalTransformPrimitiveBindingCount": stats1["normalTransformPrimitiveBindingCount"],
    })
    stats = result.setdefault("stats", {})
    stats["generatedAttributeContract"] = stats1
    policies = result.setdefault("policies", {})
    policies["v12GeneratedAttributes"] = (
        "fixed material/lightmap UV semantic contract; generated packed color exposed only as "
        "_T6_LAYER_WEIGHTS; raw normal-transform bytes retained while logical reordered UNORM8 "
        "accessors are appended for renderer use"
    )
    policies["v12BinaryPreservation"] = (
        "all v11 binary bytes remain an exact prefix; only logical normal-transform vertex payloads "
        "may be appended"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v12.json"
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
        "generatedAttributeContract": result["stats"]["generatedAttributeContract"],
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
