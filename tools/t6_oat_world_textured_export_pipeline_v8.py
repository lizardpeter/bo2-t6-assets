#!/usr/bin/env python3
"""Production T6 world export pipeline v8: executable render-state contracts.

V8 promotes v7 and automatically compiles the retained OAT-decoded T6 material
state into:

1. renderer-neutral `t6-material-render-state-contract-v1`;
2. retail-grounded `t6-material-wgpu-state-v2` pipeline descriptors.

The wgpu state is tied to the retained retail D3D11 executable proof. Fixed
polygon-offset modes are exact and shadowmap bias is parameterized by T6's live
DVAR values (retail defaults 8192 / 2.0).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v7 as v7
from t6_material_render_state_contract_v1 import compile_manifest as compile_state_contract
from t6_material_wgpu_state_v2 import (
    DEFAULT_SHADOWMAP_BIAS,
    DEFAULT_SHADOWMAP_SCALE,
    compile_contract as compile_wgpu_state,
)


class OatTexturedPipelineV8Error(RuntimeError):
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


def _promote_file(path_value: str, destination: Path) -> dict:
    source = Path(path_value)
    if not source.is_file():
        raise OatTexturedPipelineV8Error(f"v7 staging output missing during v8 promotion: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return _file_record(destination)


def run_oat_textured_pipeline(
    *,
    shadowmap_bias: int = DEFAULT_SHADOWMAP_BIAS,
    shadowmap_scale: float = DEFAULT_SHADOWMAP_SCALE,
    **kwargs,
) -> dict:
    result = v7.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v7":
        raise OatTexturedPipelineV8Error(
            f"unexpected v7 base manifest {result.get('format')!r}"
        )

    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV8Error("v7 result lacks outputs")

    material_record = outputs.get("oatMaterialManifest")
    if not isinstance(material_record, dict):
        raise OatTexturedPipelineV8Error("v7 result lacks OAT material manifest")
    material_path = Path(str(material_record.get("path") or ""))
    if not material_path.is_file():
        raise OatTexturedPipelineV8Error(f"OAT material manifest missing: {material_path}")
    material_doc = json.loads(material_path.read_text(encoding="utf-8"))
    if material_doc.get("source", {}).get("producer") != "t6_oat_material_manifest_v4.py":
        raise OatTexturedPipelineV8Error("v8 requires render-state-aware material manifest v4")

    contract1 = compile_state_contract(copy.deepcopy(material_doc))
    contract2 = compile_state_contract(copy.deepcopy(material_doc))
    contract_payload = _json_bytes(contract1)
    if _json_bytes(contract2) != contract_payload:
        raise OatTexturedPipelineV8Error(
            "renderer-neutral T6 state contract regeneration was not byte-identical"
        )
    contract_path = output_dir / f"{map_name}.material_render_state_contract_v1.json"
    contract_path.write_bytes(contract_payload)
    outputs["t6MaterialRenderStateContract"] = _file_record(contract_path, contract_payload)

    wgpu1 = compile_wgpu_state(
        copy.deepcopy(contract1),
        shadowmap_bias=shadowmap_bias,
        shadowmap_scale=shadowmap_scale,
    )
    wgpu2 = compile_wgpu_state(
        copy.deepcopy(contract1),
        shadowmap_bias=shadowmap_bias,
        shadowmap_scale=shadowmap_scale,
    )
    wgpu_payload = _json_bytes(wgpu1)
    if _json_bytes(wgpu2) != wgpu_payload:
        raise OatTexturedPipelineV8Error(
            "retail-grounded wgpu state regeneration was not byte-identical"
        )
    if not wgpu1.get("stats", {}).get("allPipelineDescriptorsExact"):
        raise OatTexturedPipelineV8Error("wgpu state compiler did not close every pipeline descriptor")
    wgpu_path = output_dir / f"{map_name}.material_wgpu_state_v2.json"
    wgpu_path.write_bytes(wgpu_payload)
    outputs["t6MaterialWgpuState"] = _file_record(wgpu_path, wgpu_payload)

    glb_record = outputs.get("oatPortableTexturedGlb")
    if not isinstance(glb_record, dict):
        raise OatTexturedPipelineV8Error("v7 result lacks final GLB")
    outputs["oatPortableTexturedGlb"] = _promote_file(
        str(glb_record["path"]),
        output_dir / f"{map_name}.world_oat_portable_textured_v8.glb",
    )
    if "oatPortableTexturedGltf" in outputs:
        gltf_record = outputs["oatPortableTexturedGltf"]
        outputs["oatPortableTexturedGltf"] = _promote_file(
            str(gltf_record["path"]),
            output_dir / f"{map_name}.world_oat_portable_textured_v8.gltf",
        )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    result["format"] = "t6-oat-world-textured-export-pipeline-manifest-v8"
    validation = result.setdefault("validation", {})
    validation.update(
        {
            "t6RenderStateContractRegenerationByteIdentical": True,
            "t6WgpuStateRegenerationByteIdentical": True,
            "t6WgpuAllPipelineDescriptorsExact": True,
            "t6WgpuRetailD3d11Proof": wgpu1["retailD3d11Proof"],
        }
    )
    stats = result.setdefault("stats", {})
    stats["t6RenderStateContract"] = contract1.get("stats", {})
    stats["t6WgpuState"] = wgpu1.get("stats", {})
    policies = result.setdefault("policies", {})
    policies["t6ExecutableRenderState"] = (
        "exact OAT-decoded T6 material state -> renderer-neutral contract -> retail-D3D11-grounded "
        "wgpu descriptor; generic glTF state is not used as a substitute"
    )
    policies["shadowmapPolygonOffset"] = (
        "DepthBias=-sm_polygonOffsetBias and SlopeScaledDepthBias=-sm_polygonOffsetScale; "
        f"this run uses bias={int(shadowmap_bias)}, scale={float(shadowmap_scale)}"
    )

    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v8.json"
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
    parser.add_argument(
        "--asset-pointer-base", type=lambda value: int(value, 0), required=True
    )
    parser.add_argument("--oat-material-root", type=Path, required=True)
    parser.add_argument("--dds-root", type=Path, required=True)
    parser.add_argument("--format-registry", type=Path, required=True)
    parser.add_argument("--lightmap-catalog", type=Path)
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
    args = parser.parse_args()

    manifest = run_oat_textured_pipeline(
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
        dds_root=args.dds_root,
        output_dir=args.out_dir,
        format_registry_path=args.format_registry,
        lightmap_catalog_path=args.lightmap_catalog,
        write_gltf=args.write_gltf,
        shadowmap_bias=args.sm_polygon_offset_bias,
        shadowmap_scale=args.sm_polygon_offset_scale,
        allow_unresolved_world_materials=args.allow_unresolved_world_materials,
        allow_missing_oat_materials=args.allow_missing_oat_materials,
        allow_missing_dds=args.allow_missing_dds,
        allow_missing_preview_textures=args.allow_missing_preview_textures,
        allow_missing_dependency_textures=args.allow_missing_dependency_textures,
        allow_missing_lightmap_dds=args.allow_missing_lightmap_dds,
    )
    print(
        json.dumps(
            {
                "map": manifest["map"],
                "manifest": manifest["manifest"],
                "worldVertexFormatGate": manifest["stats"]["worldVertexFormatGate"],
                "materialRenderState": manifest["stats"]["materialRenderState"],
                "t6RenderStateContract": manifest["stats"]["t6RenderStateContract"],
                "t6WgpuState": manifest["stats"]["t6WgpuState"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
