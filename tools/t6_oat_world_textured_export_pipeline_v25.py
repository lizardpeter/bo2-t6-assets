#!/usr/bin/env python3
"""Production T6 world export pipeline v25: final-output resource ancestry.

v25 preserves v24 visual bytes and, whenever the v24 exact slot-4 final-output
symbolic sidecar exists, independently walks every written o0 lane and emits an
exact RDEF-named texture-resource ancestry sidecar.

No final lighting arithmetic or physical interpretation is assigned here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_generated_final_output_resource_ancestry_v1 as ancestry
import t6_oat_world_textured_export_pipeline_v24 as v24
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v25"


class OatTexturedPipelineV25Error(RuntimeError):
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
        raise OatTexturedPipelineV25Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV25Error(f"{label} does not exist: {path}")
    return path


def run_oat_textured_pipeline(**kwargs) -> dict:
    result = v24.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != v24.FORMAT:
        raise OatTexturedPipelineV25Error(
            f"unexpected v24 base manifest {result.get('format')!r}"
        )
    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV25Error("v24 result lacks outputs")

    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v24 portable GLB")
    glb_payload = old_glb.read_bytes()
    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v25.glb"
    new_glb.write_bytes(glb_payload)
    if old_glb != new_glb and old_glb.is_file():
        old_glb.unlink()
    outputs["oatPortableTexturedGlb"] = _record(new_glb, glb_payload)

    old_gltf_record = outputs.get("oatPortableTexturedGltf")
    if isinstance(old_gltf_record, dict):
        old_gltf = _path(old_gltf_record, "v24 portable glTF")
        gltf_payload = old_gltf.read_bytes()
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v25.gltf"
        new_gltf.write_bytes(gltf_payload)
        if old_gltf != new_gltf and old_gltf.is_file():
            old_gltf.unlink()
        outputs["oatPortableTexturedGltf"] = _record(new_gltf, gltf_payload)

    final_record = outputs.get("generatedSlot4FinalOutputSymbolic")
    ancestry_doc = None
    ancestry_payload = None
    if isinstance(final_record, dict):
        final_path = _path(final_record, "v24 generated final-output symbolic sidecar")
        final_doc = json.loads(final_path.read_text(encoding="utf-8"))
        strict = map_name == ancestry.symbolic_v3.MAP
        try:
            doc1 = ancestry.build(final_doc, strict_nuketown=strict)
            doc2 = ancestry.build(final_doc, strict_nuketown=strict)
        except Exception as exc:
            raise OatTexturedPipelineV25Error(
                f"generated final-output resource ancestry proof failed: {exc}"
            ) from exc
        payload1 = _json_bytes(doc1)
        payload2 = _json_bytes(doc2)
        if doc1 != doc2 or payload1 != payload2:
            raise OatTexturedPipelineV25Error(
                "generated final-output resource ancestry regeneration was not byte-identical"
            )
        ancestry_doc = doc1
        ancestry_payload = payload1
        path = output_dir / f"{map_name}.generated_final_output_resource_ancestry_v1.json"
        path.write_bytes(ancestry_payload)
        outputs["generatedFinalOutputResourceAncestry"] = _record(path, ancestry_payload)

    result.setdefault("stats", {})["generatedFinalOutputResourceAncestry"] = (
        None if ancestry_doc is None else ancestry_doc["summary"]
    )
    result.setdefault("validation", {}).update({
        "v25FinalOutputResourceAncestryGenerated": ancestry_doc is not None,
        "v25FinalOutputResourceAncestryFormat": None if ancestry_doc is None else ancestry_doc["format"],
        "v25FinalOutputResourceAncestryDeterministic": None if ancestry_doc is None else True,
        "v25OutputAncestryMismatchCount": (
            None if ancestry_doc is None else int(ancestry_doc["summary"]["outputAncestryMismatchCount"])
        ),
        "v25UnknownOutputResourceCount": (
            None if ancestry_doc is None else int(ancestry_doc["summary"]["unknownOutputResourceCount"])
        ),
        "v25OutputAncestrySignatureCount": (
            None if ancestry_doc is None else int(ancestry_doc["summary"]["ancestrySignatureCount"])
        ),
        "v25VisualGlbByteIdenticalToV24": True,
        "v25VisualGltfByteIdenticalToV24": True if isinstance(old_gltf_record, dict) else None,
    })
    result.setdefault("policies", {})["v25GeneratedFinalOutputResourceAncestry"] = (
        "independently recompute exact textureSample ancestry from each written o0 lane in the v24 full DAG; "
        "classify only exact known RDEF names; retain unknown names explicitly; do not infer final lighting arithmetic"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()
    result["format"] = FORMAT
    manifest_payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v25.json"
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
        "finalOutput": result["outputs"].get("generatedSlot4FinalOutputSymbolic"),
        "ancestry": result["outputs"].get("generatedFinalOutputResourceAncestry"),
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
