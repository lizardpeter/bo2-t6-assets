#!/usr/bin/env python3
"""Production T6 world export pipeline v7: registry gate + exact render states.

v7 keeps the v6 world-format production preflight and v5 nullable-lightmap
contract, while promoting material generation from v3 to v4 so every final map
manifest/GLB dependency graph retains the exact OAT-decoded T6 GPU state table:
alpha test, separate RGB/alpha blending, culling, depth, write masks, polygon
offset, stencil, sort key, constants, and stateBitsEntry routing.

Unsupported state is metadata for a T6-aware Blender/wgpu adapter; it is never
approximated into generic core glTF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v5 as v5
import t6_oat_world_textured_export_pipeline_v6 as v6
from t6_oat_material_manifest_v4 import build_manifest as build_material_manifest_v4


class OatTexturedPipelineV7Error(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _file_record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha256(payload)}


def _promote_file(path_value: str, destination: Path) -> dict:
    source = Path(path_value)
    if not source.is_file():
        raise OatTexturedPipelineV7Error(f"v6 staging output missing during v7 promotion: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return _file_record(destination)


def run_oat_textured_pipeline(**kwargs) -> dict:
    # v5 and v6 share the imported v4 pipeline module object. Patching only the
    # material builder preserves all older versioned orchestration while making
    # the production call consume v4 render-state-aware manifests.
    old_builder = v5.v4.build_manifest
    try:
        v5.v4.build_manifest = build_material_manifest_v4
        result = v6.run_oat_textured_pipeline(**kwargs)
    finally:
        v5.v4.build_manifest = old_builder

    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v6":
        raise OatTexturedPipelineV7Error(f"unexpected v6 base manifest {result.get('format')!r}")

    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV7Error("v6 result lacks outputs")

    glb = outputs.get("oatPortableTexturedGlb")
    if not isinstance(glb, dict):
        raise OatTexturedPipelineV7Error("v6 result lacks final GLB")
    outputs["oatPortableTexturedGlb"] = _promote_file(
        str(glb["path"]), output_dir / f"{map_name}.world_oat_portable_textured_v7.glb"
    )
    if "oatPortableTexturedGltf" in outputs:
        gltf = outputs["oatPortableTexturedGltf"]
        outputs["oatPortableTexturedGltf"] = _promote_file(
            str(gltf["path"]), output_dir / f"{map_name}.world_oat_portable_textured_v7.gltf"
        )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    material_manifest_record = outputs.get("oatMaterialManifest")
    if not isinstance(material_manifest_record, dict):
        raise OatTexturedPipelineV7Error("v6 result lacks OAT material manifest")
    material_manifest_path = Path(str(material_manifest_record["path"]))
    material_doc = json.loads(material_manifest_path.read_text(encoding="utf-8"))
    producer = material_doc.get("source", {}).get("producer")
    if producer != "t6_oat_material_manifest_v4.py":
        raise OatTexturedPipelineV7Error(f"material state promotion failed; producer={producer!r}")
    mstats = material_doc.get("stats", {})
    required_stats = (
        "renderStateMaterialCount", "uniqueDecodedStateSignatureCount",
        "alphaTestMaterialCount", "blendMaterialCount", "stencilMaterialCount",
        "polygonOffsetMaterialCount",
    )
    missing = [key for key in required_stats if key not in mstats]
    if missing:
        raise OatTexturedPipelineV7Error(f"material v4 render-state stats missing: {missing}")

    result["format"] = "t6-oat-world-textured-export-pipeline-manifest-v7"
    validation = result.setdefault("validation", {})
    validation.update({
        "exactT6MaterialRenderStateArchived": True,
        "materialManifestProducer": producer,
        "materialRenderStateMaterialCount": int(mstats["renderStateMaterialCount"]),
        "materialUniqueDecodedStateSignatureCount": int(mstats["uniqueDecodedStateSignatureCount"]),
    })
    result.setdefault("stats", {})["materialRenderState"] = {
        key: mstats[key] for key in required_stats
    }
    result.setdefault("policies", {})["materialRenderState"] = (
        "exact OAT-decoded T6 stateBits/stateBitsEntry/constants/sortKey retained; "
        "unsupported alpha/blend/depth/cull/stencil/polygon-offset behavior is not approximated into core glTF"
    )

    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v7.json"
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
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--write-gltf", action="store_true")
    parser.add_argument("--allow-unresolved-world-materials", action="store_true")
    parser.add_argument("--allow-missing-oat-materials", action="store_true")
    parser.add_argument("--allow-missing-dds", action="store_true")
    parser.add_argument("--allow-missing-preview-textures", action="store_true")
    parser.add_argument("--allow-missing-dependency-textures", action="store_true")
    parser.add_argument("--allow-missing-lightmap-dds", action="store_true")
    args = parser.parse_args()
    manifest = run_oat_textured_pipeline(
        map_name=args.map_name, surfaces_path=args.surfaces, vd0_path=args.vd0,
        vd1_path=args.vd1, indices_path=args.indices, materials_path=args.materials,
        catalog_path=args.catalog, prefix_path=args.prefix,
        asset_pointer_array_virtual_base=args.asset_pointer_base,
        oat_material_root=args.oat_material_root, dds_root=args.dds_root,
        output_dir=args.out_dir, format_registry_path=args.format_registry,
        lightmap_catalog_path=args.lightmap_catalog, write_gltf=args.write_gltf,
        allow_unresolved_world_materials=args.allow_unresolved_world_materials,
        allow_missing_oat_materials=args.allow_missing_oat_materials,
        allow_missing_dds=args.allow_missing_dds,
        allow_missing_preview_textures=args.allow_missing_preview_textures,
        allow_missing_dependency_textures=args.allow_missing_dependency_textures,
        allow_missing_lightmap_dds=args.allow_missing_lightmap_dds,
    )
    print(json.dumps({
        "map": manifest["map"], "manifest": manifest["manifest"],
        "validation": manifest["validation"],
        "worldVertexFormatGate": manifest["stats"]["worldVertexFormatGate"],
        "materialRenderState": manifest["stats"]["materialRenderState"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
