#!/usr/bin/env python3
"""Production T6 world export pipeline v16: exact layered-normal basis attachment.

v16 preserves v15's dual-proof normal-transform ownership and optionally consumes
`t6-generated-layered-normal-vs-basis-probe-v2`.  When supplied, every embedded
canonical generated recipe with secondary normals receives a compact exact basis
attachment after strict canonical VS/PS identity and v15 transform-binding checks.

The postpass is regenerated twice from the untouched v15 GLB and must be byte
identical.  Normal-map sample XY decode remains a separate proof boundary and is
not invented here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v15 as v15
from t6_generated_layered_normal_basis_attach_v1 import (
    FORMAT as BASIS_ATTACHMENT_FORMAT,
    attach_gltf as attach_normal_basis,
)
from t6_glb_parse_v1 import parse_glb
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v16"


class OatTexturedPipelineV16Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _path(record, label: str) -> Path:
    if not isinstance(record, dict):
        raise OatTexturedPipelineV16Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV16Error(f"{label} does not exist: {path}")
    return path


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _postpass(base_glb: bytes, proof: dict) -> tuple[dict, bytes, dict]:
    document, raw = parse_glb(base_glb)
    stats = attach_normal_basis(document, proof)
    return document, raw, stats


def run_oat_textured_pipeline(
    *,
    generated_normal_basis_proof_path: Path | None = None,
    **kwargs,
) -> dict:
    result = v15.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v15":
        raise OatTexturedPipelineV16Error(
            f"unexpected v15 base manifest {result.get('format')!r}"
        )

    map_name = str(kwargs["map_name"])
    output_dir = Path(kwargs["output_dir"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV16Error("v15 result lacks outputs")
    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v15 portable GLB")
    base_glb = old_glb.read_bytes()
    old_gltf_record = outputs.get("oatPortableTexturedGltf")

    proof_record = None
    basis_stats = None
    deterministic = None

    if generated_normal_basis_proof_path is not None:
        proof_raw = generated_normal_basis_proof_path.read_bytes()
        try:
            proof = json.loads(proof_raw.decode("utf-8"))
        except Exception as exc:
            raise OatTexturedPipelineV16Error(
                f"cannot parse generated normal basis proof: {exc}"
            ) from exc
        proof_record = _record(generated_normal_basis_proof_path, proof_raw)

        doc1, raw1, stats1 = _postpass(base_glb, proof)
        doc2, raw2, stats2 = _postpass(base_glb, proof)
        glb1 = glb_bytes(doc1, raw1)
        glb2 = glb_bytes(doc2, raw2)
        if raw1 != raw2 or glb1 != glb2 or stats1 != stats2:
            raise OatTexturedPipelineV16Error(
                "v16 layered-normal basis postpass regeneration was not byte-identical"
            )
        if not bool(stats1.get("allSecondaryNormalMaterialsAttached")):
            raise OatTexturedPipelineV16Error(
                "v16 did not attach an exact basis to every secondary-normal material"
            )
        basis_stats = stats1
        deterministic = True

        new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v16.glb"
        new_glb.write_bytes(glb1)
        if old_glb != new_glb and old_glb.is_file():
            old_glb.unlink()
        outputs["oatPortableTexturedGlb"] = _record(new_glb, glb1)

        if isinstance(old_gltf_record, dict):
            old_gltf = _path(old_gltf_record, "v15 portable glTF")
            text1 = gltf_bytes(doc1, raw1)
            text2 = gltf_bytes(doc2, raw2)
            if text1 != text2:
                raise OatTexturedPipelineV16Error(
                    "v16 layered-normal basis glTF regeneration was not byte-identical"
                )
            new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v16.gltf"
            new_gltf.write_bytes(text1)
            if old_gltf != new_gltf and old_gltf.is_file():
                old_gltf.unlink()
            outputs["oatPortableTexturedGltf"] = _record(new_gltf, text1)
    else:
        new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v16.glb"
        old_glb.replace(new_glb)
        outputs["oatPortableTexturedGlb"] = _record(new_glb)
        if isinstance(old_gltf_record, dict):
            old_gltf = _path(old_gltf_record, "v15 portable glTF")
            new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v16.gltf"
            old_gltf.replace(new_gltf)
            outputs["oatPortableTexturedGltf"] = _record(new_gltf)

    result.setdefault("inputs", {})["generatedNormalBasisProof"] = proof_record
    result.setdefault("stats", {})["generatedNormalBasisAttachment"] = basis_stats
    result.setdefault("validation", {}).update({
        "v16GeneratedNormalBasisProofAttached": basis_stats is not None,
        "v16GeneratedNormalBasisAttachmentFormat": BASIS_ATTACHMENT_FORMAT if basis_stats is not None else None,
        "v16GeneratedNormalBasisPostpassByteIdentical": deterministic,
        "v16SecondaryNormalMaterialCount": None if basis_stats is None else int(basis_stats["secondaryNormalMaterialCount"]),
        "v16AttachedNormalBasisCount": None if basis_stats is None else int(basis_stats["attachedBasisCount"]),
        "v16AllSecondaryNormalMaterialsBasisExact": None if basis_stats is None else bool(basis_stats["allSecondaryNormalMaterialsAttached"]),
    })
    result.setdefault("policies", {})["v16GeneratedLayeredNormalBasis"] = (
        "optional exact v2 paired-VS basis proof; embedded recipe VS/PS SHA and v15 dual-proof transform ownership must agree; "
        "basis is never inferred from TechniqueSet names and normal-map sample decode remains separate"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()
    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v16.json"
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
        "generatedNormalBasisAttachment": result.get("stats", {}).get("generatedNormalBasisAttachment"),
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
