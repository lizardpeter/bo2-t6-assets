#!/usr/bin/env python3
"""Production T6 world export pipeline v28: strict directional-lightmap anchors.

v28 preserves all v27 visual bytes.  When the exact generated final-output DAG
sidecar exists, it promotes the directional secondary-lightmap equation from a
diagnostic probe to a strict semantic expression-DAG anchor.

Every shader must expose exactly one or two anchors.  The original compiler's
explicit-vs-folded materialization is not inferred because exact SM4 MAD
lowering can erase that distinction in the expression DAG.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_generated_final_output_directional_lightmap_anchor_v2 as directional
import t6_oat_world_textured_export_pipeline_v27 as v27
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v28"


class OatTexturedPipelineV28Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _path(record, label: str) -> Path:
    if not isinstance(record, dict):
        raise OatTexturedPipelineV28Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV28Error(f"{label} does not exist: {path}")
    return path


def run_oat_textured_pipeline(**kwargs) -> dict:
    result = v27.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != v27.FORMAT:
        raise OatTexturedPipelineV28Error(
            f"unexpected v27 base manifest {result.get('format')!r}"
        )
    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV28Error("v27 result lacks outputs")

    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v27 portable GLB")
    glb_payload = old_glb.read_bytes()
    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v28.glb"
    new_glb.write_bytes(glb_payload)
    if old_glb != new_glb and old_glb.is_file():
        old_glb.unlink()
    outputs["oatPortableTexturedGlb"] = _record(new_glb, glb_payload)

    old_gltf_record = outputs.get("oatPortableTexturedGltf")
    if isinstance(old_gltf_record, dict):
        old_gltf = _path(old_gltf_record, "v27 portable glTF")
        gltf_payload = old_gltf.read_bytes()
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v28.gltf"
        new_gltf.write_bytes(gltf_payload)
        if old_gltf != new_gltf and old_gltf.is_file():
            old_gltf.unlink()
        outputs["oatPortableTexturedGltf"] = _record(new_gltf, gltf_payload)

    final_record = outputs.get("generatedSlot4FinalOutputSymbolic")
    anchor_doc = None
    if isinstance(final_record, dict):
        final_path = _path(final_record, "generated final-output symbolic sidecar")
        final_doc = json.loads(final_path.read_text(encoding="utf-8"))
        try:
            doc1 = directional.build(final_doc, strict=True)
            doc2 = directional.build(final_doc, strict=True)
        except Exception as exc:
            raise OatTexturedPipelineV28Error(
                f"strict semantic directional-lightmap anchoring failed: {exc}"
            ) from exc
        payload1 = _json_bytes(doc1)
        payload2 = _json_bytes(doc2)
        if doc1 != doc2 or payload1 != payload2:
            raise OatTexturedPipelineV28Error(
                "semantic directional-lightmap anchor regeneration was not byte-identical"
            )
        anchor_doc = doc1
        path = output_dir / f"{map_name}.generated_final_output_directional_lightmap_anchor_v2.json"
        path.write_bytes(payload1)
        outputs["generatedFinalOutputDirectionalLightmapAnchor"] = _record(path, payload1)

    summary = None if anchor_doc is None else anchor_doc["summary"]
    result.setdefault("stats", {})["generatedFinalOutputDirectionalLightmapAnchor"] = summary
    result.setdefault("validation", {}).update({
        "v28DirectionalLightmapAnchorGenerated": anchor_doc is not None,
        "v28DirectionalLightmapAnchorFormat": None if anchor_doc is None else anchor_doc["format"],
        "v28DirectionalLightmapAnchorDeterministic": None if anchor_doc is None else True,
        "v28DirectionalAnchoredShaderCount": None if summary is None else int(summary["anchoredShaderCount"]),
        "v28DirectionalEquationCount": None if summary is None else int(summary["directionalEquationCount"]),
        "v28DirectionalZeroEquationShaderCount": None if summary is None else int(summary["zeroEquationShaderCount"]),
        "v28DirectionalThreeOrMoreEquationShaderCount": None if summary is None else int(summary["threeOrMoreEquationShaderCount"]),
        "v28VisualGlbByteIdenticalToV27": True,
        "v28VisualGltfByteIdenticalToV27": True if isinstance(old_gltf_record, dict) else None,
    })
    result.setdefault("policies", {})["v28DirectionalLightmapAnchor"] = (
        "strict exact-expression anchor of the retained directional secondary-lightmap equation; one or two equations "
        "required per shader; compiler explicit/folded materialization is not inferred after exact SM4 MAD lowering"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()
    result["format"] = FORMAT
    manifest_payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v28.json"
    manifest_path.write_bytes(manifest_payload)
    result["manifest"] = _record(manifest_path, manifest_payload)
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
    a = p.parse_args()
    result = run_oat_textured_pipeline(
        map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,
        materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,
        asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,
        oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,
        format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,
        reflection_probe_catalog_path=a.reflection_probe_catalog,
        generated_shader_recipe_manifest_path=a.generated_shader_recipes,
        generated_shader_expanded_world_path=a.generated_shader_expanded_world,
        generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,
        shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,
        allow_unresolved_world_materials=a.allow_unresolved_world_materials,
        allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,
        allow_missing_preview_textures=a.allow_missing_preview_textures,
        allow_missing_dependency_textures=a.allow_missing_dependency_textures,
        allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,
        allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds,
    )
    print(json.dumps({
        "format": result["format"],
        "glb": result["outputs"]["oatPortableTexturedGlb"],
        "directionalAnchor": result["outputs"].get("generatedFinalOutputDirectionalLightmapAnchor"),
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
