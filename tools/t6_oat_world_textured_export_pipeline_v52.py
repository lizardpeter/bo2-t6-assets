#!/usr/bin/env python3
"""Production T6 world export pipeline v52: ordinary special-Material replay.

v52 preserves the complete v51 production artifact and generated-Material replay
sidecar, then closes the complementary ordinary Nuketown special-material tail:
11 exact Materials spanning unlit/emissive, two shadowcasters, and the raw-normal
glass family.

A full ``t6-nuketown-special-render-replay-contract-v1`` must match its durable
seal byte-for-byte. The final post-pass joins only exact
``material.extras.T6.sourceMaterial`` identities and writes replay metadata under
``extras.T6``. Core glTF PBR, geometry, indices, archived DDS payloads, generated
recipes, lightmaps, reflection probes, and the logical GLB BIN payload remain
unchanged.

This is metadata required for exact T6-aware Blender/Rust playback. It does not
pretend generic glTF PBR is the native T6 shader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v51 as v51
from t6_glb_parse_v1 import parse_glb
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_special_render_contract_overlay_v1 import apply_special_render_contract

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v52"
BASE_FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v51"
SEAL_FORMAT = "t6-nuketown-special-render-replay-contract-seal-v1"


class OatTexturedPipelineV52Error(RuntimeError):
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
        raise OatTexturedPipelineV52Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV52Error(f"{label} does not exist: {path}")
    return path


def _load_contract(
    contract_path: Path,
    seal_path: Path,
    map_name: str,
) -> tuple[dict, bytes, dict, bytes]:
    contract_raw = contract_path.read_bytes()
    seal_raw = seal_path.read_bytes()
    try:
        contract = json.loads(contract_raw.decode("utf-8"))
        seal = json.loads(seal_raw.decode("utf-8"))
    except Exception as exc:
        raise OatTexturedPipelineV52Error(f"cannot parse special render contract/seal: {exc}") from exc
    if not isinstance(contract, dict) or not isinstance(seal, dict):
        raise OatTexturedPipelineV52Error("special render contract/seal top level must be objects")
    if seal.get("format") != SEAL_FORMAT or seal.get("map") != map_name:
        raise OatTexturedPipelineV52Error("special render contract seal identity/map mismatch")
    generated = seal.get("generated")
    if not isinstance(generated, dict):
        raise OatTexturedPipelineV52Error("special render contract seal lacks generated section")
    actual_sha = _sha(contract_raw)
    expected_sha = str(generated.get("fileSha256") or "")
    if actual_sha != expected_sha:
        raise OatTexturedPipelineV52Error(
            f"special render contract SHA {actual_sha} != sealed {expected_sha}"
        )
    expected_digest = str(generated.get("contractDigestSha256") or "")
    if str(contract.get("contractDigestSha256") or "") != expected_digest:
        raise OatTexturedPipelineV52Error("special render contract digest disagrees with durable seal")
    if contract.get("map") != map_name:
        raise OatTexturedPipelineV52Error("special render contract map disagrees with export map")
    return contract, contract_raw, seal, seal_raw


def _overlay_once(base_glb: bytes, contract: dict) -> tuple[dict, bytes, bytes]:
    document, raw = parse_glb(base_glb)
    overlaid = apply_special_render_contract(
        document,
        contract,
        require_all_contract_materials=True,
    )
    payload = glb_bytes(overlaid, raw)
    parsed_doc, parsed_raw = parse_glb(payload)
    if parsed_raw != raw:
        raise OatTexturedPipelineV52Error("special replay overlay changed logical GLB BIN payload")
    if parsed_doc != overlaid:
        raise OatTexturedPipelineV52Error("special replay overlay JSON failed exact GLB round-trip")
    return overlaid, raw, payload


def run_oat_textured_pipeline(
    *,
    special_render_contract_path: Path,
    special_render_contract_seal_path: Path,
    **kwargs,
) -> dict:
    map_name = str(kwargs["map_name"])
    output_dir = Path(kwargs["output_dir"])
    contract, contract_raw, seal, seal_raw = _load_contract(
        Path(special_render_contract_path),
        Path(special_render_contract_seal_path),
        map_name,
    )

    result = v51.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != BASE_FORMAT:
        raise OatTexturedPipelineV52Error(
            f"unexpected v51 base manifest {result.get('format')!r}"
        )
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV52Error("v51 result lacks outputs")

    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v51 portable GLB")
    base_glb = old_glb.read_bytes()
    if _sha(base_glb) != str(outputs["oatPortableTexturedGlb"].get("sha256") or ""):
        raise OatTexturedPipelineV52Error("v51 GLB bytes disagree with v51 output record")

    doc1, raw1, glb1 = _overlay_once(base_glb, contract)
    doc2, raw2, glb2 = _overlay_once(base_glb, contract)
    if doc2 != doc1 or raw2 != raw1 or glb2 != glb1:
        raise OatTexturedPipelineV52Error("v52 special replay post-pass was not deterministic")

    overlay = doc1.get("extras", {}).get("T6", {}).get("renderReplayContractOverlay")
    if not isinstance(overlay, dict) or not isinstance(overlay.get("stats"), dict):
        raise OatTexturedPipelineV52Error("v52 special replay overlay metadata missing")
    overlay_stats = overlay["stats"]
    expected = int(overlay_stats.get("exactContractSpecialMaterialCount", -1))
    matched = int(overlay_stats.get("exactContractMatchedMaterialCount", -2))
    if expected != 11 or matched != 11:
        raise OatTexturedPipelineV52Error(
            f"v52 exact special Material population changed: expected={expected} matched={matched}"
        )
    if int(overlay_stats.get("exactContractRawnormalCount", -1)) != 1:
        raise OatTexturedPipelineV52Error("v52 raw-normal exact contract count changed")
    if int(overlay_stats.get("exactContractShadowcasterCount", -1)) != 2:
        raise OatTexturedPipelineV52Error("v52 shadowcaster exact contract count changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v52.glb"
    new_glb.write_bytes(glb1)
    if old_glb != new_glb and old_glb.is_file():
        old_glb.unlink()
    outputs["oatPortableTexturedGlb"] = _record(new_glb, glb1)
    outputs["specialRenderReplayContract"] = _record(Path(special_render_contract_path), contract_raw)
    outputs["specialRenderReplayContractSeal"] = _record(Path(special_render_contract_seal_path), seal_raw)

    had_gltf = isinstance(outputs.get("oatPortableTexturedGltf"), dict)
    gltf_deterministic = None
    if had_gltf:
        old_gltf = _path(outputs["oatPortableTexturedGltf"], "v51 portable glTF")
        text1 = gltf_bytes(doc1, raw1)
        text2 = gltf_bytes(doc2, raw2)
        if text2 != text1:
            raise OatTexturedPipelineV52Error("v52 glTF replay overlay was not byte-identical")
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v52.gltf"
        new_gltf.write_bytes(text1)
        if old_gltf != new_gltf and old_gltf.is_file():
            old_gltf.unlink()
        outputs["oatPortableTexturedGltf"] = _record(new_gltf, text1)
        gltf_deterministic = True

    inputs = result.setdefault("inputs", {})
    inputs["specialRenderReplayContract"] = _record(Path(special_render_contract_path), contract_raw)
    inputs["specialRenderReplayContractSeal"] = _record(Path(special_render_contract_seal_path), seal_raw)

    validation = result.setdefault("validation", {})
    validation.update({
        "v52SpecialRenderContractFileShaMatchedSeal": True,
        "v52SpecialRenderContractDigestMatchedSeal": True,
        "v52SpecialRenderContractAllMaterialsMatched": True,
        "v52SpecialRenderContractMaterialCount": matched,
        "v52SpecialRenderContractRawnormalCount": 1,
        "v52SpecialRenderContractShadowcasterCount": 2,
        "v52LogicalGlbBinByteIdenticalToV51": True,
        "v52LogicalGlbBinSha256": _sha(raw1),
        "v52SpecialReplayPostpassDeterministic": True,
        "v52SpecialReplayGltfDeterministic": gltf_deterministic,
        "v52SpecialRenderContractDigestSha256": contract["contractDigestSha256"],
    })
    stats = result.setdefault("stats", {})
    stats["specialRenderReplayContract"] = overlay_stats
    policies = result.setdefault("policies", {})
    policies["v52OrdinarySpecialMaterialReplay"] = (
        "exact 11-Material Nuketown special replay contract joined only by retained "
        "extras.T6.sourceMaterial; unlit/emissive, raw-normal full PS DAG/static inputs/runtime "
        "requirements and shadowcaster depth state are archived under extras.T6; core glTF PBR "
        "remains preview-only and logical GLB BIN bytes are unchanged"
    )
    policies["v52RuntimeInputBoundary"] = (
        "sun/spot shadows, dynamic-light attenuation, secondary lightmap, reflection probe and "
        "runtime code constants remain external exact inputs; no portable default is promoted as retail truth"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        path = Path(str(old_manifest.get("path") or ""))
        if path.is_file():
            path.unlink()

    result["format"] = FORMAT
    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v52.json"
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
    p.add_argument("--oat-source-root", type=Path)
    p.add_argument("--dds-root", type=Path, required=True)
    p.add_argument("--format-registry", type=Path, required=True)
    p.add_argument("--lightmap-catalog", type=Path)
    p.add_argument("--reflection-probe-catalog", type=Path)
    p.add_argument("--generated-shader-recipes", type=Path)
    p.add_argument("--generated-shader-expanded-world", type=Path)
    p.add_argument("--generated-normal-basis-proof", type=Path)
    p.add_argument("--special-render-contract", type=Path, required=True)
    p.add_argument(
        "--special-render-contract-seal",
        type=Path,
        default=Path("manifests/render/T6_NUKETOWN_SPECIAL_RENDER_REPLAY_CONTRACT_V1.json"),
    )
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
        special_render_contract_path=a.special_render_contract,
        special_render_contract_seal_path=a.special_render_contract_seal,
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
        oat_source_root=a.oat_source_root,
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
        "generatedReplayContract": result["outputs"].get("generatedFinalOutputReplayContract"),
        "specialRenderReplayContract": result["outputs"].get("specialRenderReplayContract"),
        "specialRenderStats": result["stats"].get("specialRenderReplayContract"),
        "manifest": result["manifest"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
