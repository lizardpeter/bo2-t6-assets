#!/usr/bin/env python3
"""T6 OAT material manifest v4: exact render-state archival + compatibility census.

v3 closes exact GfxImage identity/disk mapping. v4 additionally retains the
already-decoded T6 Material GPU state contract exposed by pinned OpenAssetTools:

- sortKey;
- stateBits[] (blend, alpha-test, cull, depth, polygon offset, stencil, writes);
- stateBitsEntry[] technique-state routing;
- constants[];
- existing T6 material info and texture/sampler metadata.

No renderer behavior is guessed. Generic glTF compatibility is reported only
for properties that are uniformly representable across all *referenced* state
entries. Arbitrary T6 blend/depth/stencil/polygon-offset behavior remains exact
metadata for a Treyarch-aware Blender/wgpu adapter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_oat_material_manifest_v3 import (
    OatMaterialManifestError,
    build_manifest as build_manifest_v3,
)


PRODUCER = "t6_oat_material_manifest_v4.py"
RENDER_STATE_FIELDS = (
    "srcBlendRgb",
    "dstBlendRgb",
    "blendOpRgb",
    "alphaTest",
    "cullFace",
    "srcBlendAlpha",
    "dstBlendAlpha",
    "blendOpAlpha",
    "colorWriteRgb",
    "colorWriteAlpha",
    "polymodeLine",
    "depthWrite",
    "depthTest",
    "polygonOffset",
    "stencilFront",
    "stencilBack",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load_oat_materials(material_root: Path) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for path in sorted(material_root.rglob("*.json")):
        raw = path.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise OatMaterialManifestError(f"invalid JSON {path}: {exc}") from exc
        if doc.get("_game") != "t6" or doc.get("_type") != "material":
            continue
        identity = path.relative_to(material_root).with_suffix("").as_posix()
        if identity in indexed:
            raise OatMaterialManifestError(f"duplicate OAT material identity {identity!r}")
        indexed[identity] = {"path": path, "raw": raw, "doc": doc}
    return indexed


def _validate_state(state: dict, *, material: str, index: int) -> dict:
    if not isinstance(state, dict):
        raise OatMaterialManifestError(
            f"{material!r}: stateBits[{index}] must be an object"
        )
    missing = [key for key in RENDER_STATE_FIELDS if key not in state]
    if missing:
        raise OatMaterialManifestError(
            f"{material!r}: stateBits[{index}] missing fields {missing}"
        )
    normalized = {key: state.get(key) for key in RENDER_STATE_FIELDS}
    return normalized


def _state_archive(identity: str, source: dict) -> dict:
    doc = source["doc"]
    states_raw = doc.get("stateBits")
    routing_raw = doc.get("stateBitsEntry")
    constants = doc.get("constants", [])
    if not isinstance(states_raw, list):
        raise OatMaterialManifestError(f"{identity!r}: stateBits must be a list")
    if not isinstance(routing_raw, list):
        raise OatMaterialManifestError(f"{identity!r}: stateBitsEntry must be a list")
    if not isinstance(constants, list):
        raise OatMaterialManifestError(f"{identity!r}: constants must be a list")

    states = [
        _validate_state(state, material=identity, index=index)
        for index, state in enumerate(states_raw)
    ]
    routing: list[int] = []
    referenced: set[int] = set()
    for slot, raw_index in enumerate(routing_raw):
        if isinstance(raw_index, bool):
            raise OatMaterialManifestError(
                f"{identity!r}: stateBitsEntry[{slot}] is boolean"
            )
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise OatMaterialManifestError(
                f"{identity!r}: stateBitsEntry[{slot}] is not integer-like"
            ) from exc
        if index < -1 or index >= len(states):
            raise OatMaterialManifestError(
                f"{identity!r}: stateBitsEntry[{slot}]={index} outside -1..{len(states)-1}"
            )
        routing.append(index)
        if index >= 0:
            referenced.add(index)

    # Some data may contain an unreferenced state table entry. Preserve it, but
    # compatibility is determined only from states reachable through routing.
    reachable_states = [states[index] for index in sorted(referenced)]
    signatures = sorted({_canonical(state) for state in states})
    reachable_signatures = sorted({_canonical(state) for state in reachable_states})

    cull_faces = sorted({str(state["cullFace"]) for state in reachable_states})
    alpha_tests = sorted({str(state["alphaTest"]) for state in reachable_states})
    depth_tests = sorted({str(state["depthTest"]) for state in reachable_states})
    polygon_offsets = sorted({str(state["polygonOffset"]) for state in reachable_states})
    blend_tuples = sorted(
        {
            (
                str(state["srcBlendRgb"]), str(state["dstBlendRgb"]),
                str(state["blendOpRgb"]), str(state["srcBlendAlpha"]),
                str(state["dstBlendAlpha"]), str(state["blendOpAlpha"]),
            )
            for state in reachable_states
        }
    )
    stencil_used = any(
        state.get("stencilFront") is not None or state.get("stencilBack") is not None
        for state in reachable_states
    )
    polygon_offset_used = any(value != "offset0" for value in polygon_offsets)
    alpha_test_used = any(value != "disabled" for value in alpha_tests)
    blend_used = any(
        rgb_op != "disabled" or alpha_op != "disabled"
        for _, _, rgb_op, _, _, alpha_op in blend_tuples
    )
    depth_write_values = sorted({bool(state["depthWrite"]) for state in reachable_states})
    color_write_rgb_values = sorted({bool(state["colorWriteRgb"]) for state in reachable_states})
    color_write_alpha_values = sorted({bool(state["colorWriteAlpha"]) for state in reachable_states})
    polymode_values = sorted({bool(state["polymodeLine"]) for state in reachable_states})

    gltf_double_sided = None
    if cull_faces == ["none"]:
        gltf_double_sided = True
    elif cull_faces == ["back"]:
        gltf_double_sided = False

    gltf_alpha_mode = None
    if reachable_states and not alpha_test_used and not blend_used:
        gltf_alpha_mode = "OPAQUE"

    blockers: list[str] = []
    if not reachable_states:
        blockers.append("no-stateBitsEntry-route")
    if gltf_double_sided is None and reachable_states:
        blockers.append("cull-state-not-uniformly-core-gltf-representable")
    if gltf_alpha_mode is None and reachable_states:
        blockers.append("alpha-test-or-blend-requires-t6-aware-render-state")
    if len(depth_tests) != 1 or depth_tests not in (["less_equal"], ["less"], ["disabled"], ["always"]):
        blockers.append("depth-test-varies-or-requires-explicit-render-state")
    elif reachable_states:
        # Core glTF does not normatively expose depth compare/write controls.
        blockers.append("depth-test-write-not-core-gltf-state")
    if len(depth_write_values) > 1:
        blockers.append("depth-write-varies-by-technique-state")
    if polygon_offset_used:
        blockers.append("polygon-offset-not-core-gltf")
    if stencil_used:
        blockers.append("stencil-not-core-gltf")
    if polymode_values == [True] or len(polymode_values) > 1:
        blockers.append("line-polygon-mode-not-core-gltf")
    if color_write_rgb_values not in ([True], []):
        blockers.append("rgb-write-mask-not-core-gltf")
    if color_write_alpha_values not in ([True], []):
        blockers.append("alpha-write-mask-not-core-gltf")

    return {
        "sourceFile": source["path"].name,
        "sourceSha256": _sha256(source["raw"]),
        "sortKey": doc.get("sortKey"),
        "stateFlags": doc.get("stateFlags"),
        "gameFlags": doc.get("gameFlags"),
        "surfaceFlags": doc.get("surfaceFlags"),
        "surfaceTypeBits": doc.get("surfaceTypeBits"),
        "layeredSurfaceTypes": doc.get("layeredSurfaceTypes"),
        "contents": doc.get("contents"),
        "cameraRegion": doc.get("cameraRegion"),
        "constants": constants,
        "stateBits": states,
        "stateBitsEntry": routing,
        "referencedStateIndices": sorted(referenced),
        "stateCount": len(states),
        "referencedStateCount": len(referenced),
        "uniqueStateSignatureCount": len(signatures),
        "reachableStateSignatureCount": len(reachable_signatures),
        "features": {
            "cullFaces": cull_faces,
            "alphaTests": alpha_tests,
            "alphaTestUsed": alpha_test_used,
            "blendTuples": [list(value) for value in blend_tuples],
            "blendUsed": blend_used,
            "depthTests": depth_tests,
            "depthWriteValues": depth_write_values,
            "polygonOffsets": polygon_offsets,
            "polygonOffsetUsed": polygon_offset_used,
            "stencilUsed": stencil_used,
            "polymodeLineValues": polymode_values,
            "colorWriteRgbValues": color_write_rgb_values,
            "colorWriteAlphaValues": color_write_alpha_values,
        },
        "coreGltfCompatibility": {
            "doubleSided": gltf_double_sided,
            "alphaMode": gltf_alpha_mode,
            "fullyRepresentable": len(blockers) == 0,
            "blockers": blockers,
        },
    }


def _source_identity(source_record: dict | None) -> str | None:
    if not isinstance(source_record, dict):
        return None
    file_name = str(source_record.get("file") or "")
    if not file_name:
        return None
    return Path(file_name).with_suffix("").as_posix()


def build_manifest(
    *,
    material_root: Path,
    catalog_doc: dict,
    source_texture_extension: str,
    allow_missing_materials: bool = False,
) -> dict:
    doc = build_manifest_v3(
        material_root=material_root,
        catalog_doc=catalog_doc,
        source_texture_extension=source_texture_extension,
        allow_missing_materials=allow_missing_materials,
    )
    indexed = _load_oat_materials(material_root)
    archive_cache: dict[str, dict] = {}

    def archive_for(identity: str) -> dict:
        if identity not in archive_cache:
            source = indexed.get(identity)
            if source is None:
                raise OatMaterialManifestError(
                    f"render-state source material missing from OAT root: {identity!r}"
                )
            archive_cache[identity] = _state_archive(identity, source)
        return archive_cache[identity]

    material_state_count = 0
    component_state_count = 0
    exact_core_count = 0
    alpha_test_count = 0
    blend_count = 0
    stencil_count = 0
    polygon_offset_count = 0
    unique_state_signatures: set[str] = set()

    for material in doc.get("materials", []):
        identity = _source_identity(material.get("sourceOatMaterial"))
        if identity is not None:
            archive = archive_for(identity)
            material["renderState"] = archive
            material_state_count += 1
            exact_core_count += int(archive["coreGltfCompatibility"]["fullyRepresentable"])
            alpha_test_count += int(archive["features"]["alphaTestUsed"])
            blend_count += int(archive["features"]["blendUsed"])
            stencil_count += int(archive["features"]["stencilUsed"])
            polygon_offset_count += int(archive["features"]["polygonOffsetUsed"])
            unique_state_signatures.update(
                _canonical(state) for state in archive["stateBits"]
            )
        else:
            material["renderState"] = None

        for layer in material.get("layers", []):
            layer_identity = _source_identity(layer.get("sourceOatMaterial"))
            if layer_identity is None:
                continue
            archive = archive_for(layer_identity)
            layer["renderState"] = archive
            component_state_count += 1
            unique_state_signatures.update(
                _canonical(state) for state in archive["stateBits"]
            )

    source = doc.setdefault("source", {})
    source["producer"] = PRODUCER
    source["renderStateReference"] = {
        "repository": "Laupetin/OpenAssetTools",
        "commit": "7d027e8f89118196713e955b0e11f8404149c54d",
        "schema": "material.v1.json",
        "policy": "archive OAT-decoded T6 stateBits/stateBitsEntry without reinterpretation",
    }
    policy = doc.setdefault("policy", {})
    policy["renderState"] = (
        "retain exact OAT-decoded T6 stateBits/stateBitsEntry/constants/sortKey; "
        "do not approximate unsupported depth/blend/stencil/polygon-offset state into core glTF"
    )
    policy["coreGltfRenderState"] = (
        "report only uniform directly representable properties; T6-aware adapter remains authoritative"
    )
    stats = doc.setdefault("stats", {})
    stats.update(
        {
            "renderStateMaterialCount": material_state_count,
            "renderStateComponentLayerCount": component_state_count,
            "uniqueDecodedStateSignatureCount": len(unique_state_signatures),
            "coreGltfFullyRepresentableMaterialCount": exact_core_count,
            "alphaTestMaterialCount": alpha_test_count,
            "blendMaterialCount": blend_count,
            "stencilMaterialCount": stencil_count,
            "polygonOffsetMaterialCount": polygon_offset_count,
        }
    )
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_root", type=Path)
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--source-texture-extension", required=True)
    parser.add_argument("--allow-missing-materials", action="store_true")
    args = parser.parse_args()
    catalog_doc = json.loads(args.catalog_json.read_text(encoding="utf-8"))
    doc = build_manifest(
        material_root=args.material_root,
        catalog_doc=catalog_doc,
        source_texture_extension=args.source_texture_extension,
        allow_missing_materials=args.allow_missing_materials,
    )
    args.output_json.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.output_json), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
