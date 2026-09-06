#!/usr/bin/env python3
"""Production T6 world export pipeline v24: generated final-output DAG sidecar.

v24 preserves the complete v23 GLB/glTF byte content.  When both an exact
canonical generated-shader recipe manifest and an OAT shader dump root are
available, it additionally emits a deterministic forensic sidecar containing
the v3 full slot-4 pixel-shader output DAGs.

The sidecar is proof data only.  It is not embedded into materials and does not
change final shading.  For Nuketown the strict 120/34/34/zero-reuse/world-format
identity gates are mandatory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_generated_slot4_final_output_symbolic_v3 as final_output
import t6_oat_world_textured_export_pipeline_v23 as v23
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v24"


class OatTexturedPipelineV24Error(RuntimeError):
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
        raise OatTexturedPipelineV24Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV24Error(f"{label} does not exist: {path}")
    return path


def _recipe_path(result: dict, kwargs: dict) -> Path | None:
    inputs = result.get("inputs")
    if isinstance(inputs, dict):
        record = inputs.get("generatedShaderRecipeManifest")
        if isinstance(record, dict) and record.get("path"):
            path = Path(str(record["path"]))
            if not path.is_file():
                raise OatTexturedPipelineV24Error(
                    f"recorded generated shader recipe manifest does not exist: {path}"
                )
            return path
    manual = kwargs.get("generated_shader_recipe_manifest_path")
    if manual is not None:
        path = Path(manual)
        if not path.is_file():
            raise OatTexturedPipelineV24Error(
                f"generated shader recipe manifest does not exist: {path}"
            )
        return path
    return None


def run_oat_textured_pipeline(**kwargs) -> dict:
    result = v23.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != v23.FORMAT:
        raise OatTexturedPipelineV24Error(
            f"unexpected v23 base manifest {result.get('format')!r}"
        )

    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV24Error("v23 result lacks outputs")

    # v24 is a sidecar-only promotion. Rename the inherited visual artifact so
    # its generation matches the production manifest version, but do not parse,
    # rewrite, or otherwise mutate its bytes.
    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v23 portable GLB")
    glb_bytes = old_glb.read_bytes()
    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v24.glb"
    new_glb.write_bytes(glb_bytes)
    if old_glb != new_glb and old_glb.is_file():
        old_glb.unlink()
    outputs["oatPortableTexturedGlb"] = _record(new_glb, glb_bytes)

    old_gltf_record = outputs.get("oatPortableTexturedGltf")
    if isinstance(old_gltf_record, dict):
        old_gltf = _path(old_gltf_record, "v23 portable glTF")
        gltf_bytes = old_gltf.read_bytes()
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v24.gltf"
        new_gltf.write_bytes(gltf_bytes)
        if old_gltf != new_gltf and old_gltf.is_file():
            old_gltf.unlink()
        outputs["oatPortableTexturedGltf"] = _record(new_gltf, gltf_bytes)

    recipes = _recipe_path(result, kwargs)
    oat_shader_root = kwargs.get("oat_shader_root")
    requested = recipes is not None or oat_shader_root is not None
    if (recipes is None) != (oat_shader_root is None):
        raise OatTexturedPipelineV24Error(
            "v24 final-output proof requires both canonical generated recipes and oat_shader_root"
        )

    final_doc = None
    final_payload = None
    final_path = None
    if recipes is not None:
        recipe_doc = json.loads(recipes.read_text(encoding="utf-8"))
        strict = map_name == final_output.MAP
        try:
            doc1 = final_output.build(
                recipe_doc,
                oat_root=Path(oat_shader_root),
                strict_nuketown=strict,
            )
            doc2 = final_output.build(
                recipe_doc,
                oat_root=Path(oat_shader_root),
                strict_nuketown=strict,
            )
        except Exception as exc:
            raise OatTexturedPipelineV24Error(
                f"generated slot-4 final-output symbolic proof failed: {exc}"
            ) from exc
        payload1 = _json_bytes(doc1)
        payload2 = _json_bytes(doc2)
        if doc1 != doc2 or payload1 != payload2:
            raise OatTexturedPipelineV24Error(
                "generated final-output symbolic sidecar regeneration was not byte-identical"
            )
        final_doc = doc1
        final_payload = payload1
        final_path = output_dir / f"{map_name}.generated_slot4_final_output_symbolic_v3.json"
        final_path.write_bytes(final_payload)
        outputs["generatedSlot4FinalOutputSymbolic"] = _record(final_path, final_payload)

    result.setdefault("stats", {})["generatedSlot4FinalOutputSymbolic"] = (
        None if final_doc is None else final_doc["summary"]
    )
    result.setdefault("validation", {}).update({
        "v24FinalOutputSymbolicRequested": requested,
        "v24FinalOutputSymbolicGenerated": final_doc is not None,
        "v24FinalOutputSymbolicFormat": None if final_doc is None else final_doc["format"],
        "v24FinalOutputSymbolicDeterministic": None if final_doc is None else True,
        "v24FinalOutputCanonicalIdentityMismatchCount": (
            None if final_doc is None else int(final_doc["summary"]["canonicalShaderIdentityMismatchCount"])
        ),
        "v24FinalOutputUniquePixelShaderCount": (
            None if final_doc is None else int(final_doc["summary"]["uniquePixelShaderCount"])
        ),
        "v24VisualGlbByteIdenticalToV23": True,
        "v24VisualGltfByteIdenticalToV23": True if isinstance(old_gltf_record, dict) else None,
    })
    result.setdefault("policies", {})["v24GeneratedFinalOutputProof"] = (
        "full slot-4 o0 expression DAG is emitted as a deterministic proof sidecar only when exact canonical recipes "
        "and OAT shader bytes are both available; visual GLB/glTF bytes are inherited unchanged; no physical final "
        "lighting equation is assigned by this stage"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    result["format"] = FORMAT
    manifest_payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v24.json"
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
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
