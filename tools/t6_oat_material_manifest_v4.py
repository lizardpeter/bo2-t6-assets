#!/usr/bin/env python3
"""T6 OAT material manifest v4: exact render-state archival + compatibility census.

v3 closes exact GfxImage identity/disk mapping. v4 additionally retains the
already-decoded T6 Material GPU state contract exposed by pinned OpenAssetTools:
sortKey, stateBits[], stateBitsEntry[], constants[], material info, and sampler
metadata. Unsupported GPU state is never approximated into core glTF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_oat_material_manifest_v3 import OatMaterialManifestError, build_manifest as build_manifest_v3

PRODUCER = "t6_oat_material_manifest_v4.py"
REQUIRED_STATE_FIELDS = (
    "srcBlendRgb", "dstBlendRgb", "blendOpRgb", "alphaTest", "cullFace",
    "srcBlendAlpha", "dstBlendAlpha", "blendOpAlpha", "colorWriteRgb",
    "colorWriteAlpha", "polymodeLine", "depthWrite", "depthTest", "polygonOffset",
)
OPTIONAL_STATE_FIELDS = ("stencilFront", "stencilBack")


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
        raise OatMaterialManifestError(f"{material!r}: stateBits[{index}] must be an object")
    missing = [key for key in REQUIRED_STATE_FIELDS if key not in state]
    if missing:
        raise OatMaterialManifestError(f"{material!r}: stateBits[{index}] missing fields {missing}")
    normalized = {key: state[key] for key in REQUIRED_STATE_FIELDS}
    for key in OPTIONAL_STATE_FIELDS:
        normalized[key] = state.get(key)
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

    states = [_validate_state(state, material=identity, index=i) for i, state in enumerate(states_raw)]
    routing: list[int] = []
    referenced: set[int] = set()
    for slot, raw_index in enumerate(routing_raw):
        if isinstance(raw_index, bool):
            raise OatMaterialManifestError(f"{identity!r}: stateBitsEntry[{slot}] is boolean")
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise OatMaterialManifestError(f"{identity!r}: stateBitsEntry[{slot}] is not integer-like") from exc
        if index < -1 or index >= len(states):
            raise OatMaterialManifestError(
                f"{identity!r}: stateBitsEntry[{slot}]={index} outside -1..{len(states)-1}"
            )
        routing.append(index)
        if index >= 0:
            referenced.add(index)

    reachable = [states[index] for index in sorted(referenced)]
    cull_faces = sorted({str(s["cullFace"]) for s in reachable})
    alpha_tests = sorted({str(s["alphaTest"]) for s in reachable})
    depth_tests = sorted({str(s["depthTest"]) for s in reachable})
    polygon_offsets = sorted({str(s["polygonOffset"]) for s in reachable})
    blend_tuples = sorted({
        (str(s["srcBlendRgb"]), str(s["dstBlendRgb"]), str(s["blendOpRgb"]),
         str(s["srcBlendAlpha"]), str(s["dstBlendAlpha"]), str(s["blendOpAlpha"]))
        for s in reachable
    })
    alpha_test_used = any(value != "disabled" for value in alpha_tests)
    blend_used = any(rgb_op != "disabled" or alpha_op != "disabled" for _, _, rgb_op, _, _, alpha_op in blend_tuples)
    stencil_used = any(s.get("stencilFront") is not None or s.get("stencilBack") is not None for s in reachable)
    polygon_offset_used = any(value != "offset0" for value in polygon_offsets)
    depth_write_values = sorted({bool(s["depthWrite"]) for s in reachable})
    color_write_rgb_values = sorted({bool(s["colorWriteRgb"]) for s in reachable})
    color_write_alpha_values = sorted({bool(s["colorWriteAlpha"]) for s in reachable})
    polymode_values = sorted({bool(s["polymodeLine"]) for s in reachable})

    gltf_double_sided = True if cull_faces == ["none"] else False if cull_faces == ["back"] else None
    gltf_alpha_mode = "OPAQUE" if reachable and not alpha_test_used and not blend_used else None
    blockers: list[str] = []
    if not reachable:
        blockers.append("no-stateBitsEntry-route")
    if reachable and gltf_double_sided is None:
        blockers.append("cull-state-not-uniformly-core-gltf-representable")
    if reachable and gltf_alpha_mode is None:
        blockers.append("alpha-test-or-blend-requires-t6-aware-render-state")
    if reachable:
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
        "uniqueStateSignatureCount": len({_canonical(s) for s in states}),
        "reachableStateSignatureCount": len({_canonical(s) for s in reachable}),
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
    return Path(file_name).with_suffix("").as_posix() if file_name else None


def build_manifest(*, material_root: Path, catalog_doc: dict, source_texture_extension: str, allow_missing_materials: bool = False) -> dict:
    doc = build_manifest_v3(
        material_root=material_root,
        catalog_doc=catalog_doc,
        source_texture_extension=source_texture_extension,
        allow_missing_materials=allow_missing_materials,
    )
    indexed = _load_oat_materials(material_root)
    cache: dict[str, dict] = {}

    def archive_for(identity: str) -> dict:
        if identity not in cache:
            source = indexed.get(identity)
            if source is None:
                raise OatMaterialManifestError(f"render-state source missing: {identity!r}")
            cache[identity] = _state_archive(identity, source)
        return cache[identity]

    material_state_count = component_state_count = exact_core_count = 0
    alpha_test_count = blend_count = stencil_count = polygon_offset_count = 0
    unique_signatures: set[str] = set()
    for material in doc.get("materials", []):
        identity = _source_identity(material.get("sourceOatMaterial"))
        material["renderState"] = archive_for(identity) if identity is not None else None
        if material["renderState"] is not None:
            state = material["renderState"]
            material_state_count += 1
            exact_core_count += int(state["coreGltfCompatibility"]["fullyRepresentable"])
            alpha_test_count += int(state["features"]["alphaTestUsed"])
            blend_count += int(state["features"]["blendUsed"])
            stencil_count += int(state["features"]["stencilUsed"])
            polygon_offset_count += int(state["features"]["polygonOffsetUsed"])
            unique_signatures.update(_canonical(x) for x in state["stateBits"])
        for layer in material.get("layers", []):
            layer_identity = _source_identity(layer.get("sourceOatMaterial"))
            if layer_identity is None:
                continue
            layer_state = archive_for(layer_identity)
            layer["renderState"] = layer_state
            component_state_count += 1
            unique_signatures.update(_canonical(x) for x in layer_state["stateBits"])

    doc.setdefault("source", {}).update({
        "producer": PRODUCER,
        "renderStateReference": {
            "repository": "Laupetin/OpenAssetTools",
            "commit": "7d027e8f89118196713e955b0e11f8404149c54d",
            "schema": "material.v1.json",
            "policy": "archive OAT-decoded T6 stateBits/stateBitsEntry without reinterpretation",
        },
    })
    doc.setdefault("policy", {}).update({
        "renderState": (
            "retain exact OAT-decoded T6 stateBits/stateBitsEntry/constants/sortKey; "
            "do not approximate unsupported depth/blend/stencil/polygon-offset state into core glTF"
        ),
        "coreGltfRenderState": "report only uniform directly representable properties; T6-aware adapter remains authoritative",
    })
    doc.setdefault("stats", {}).update({
        "renderStateMaterialCount": material_state_count,
        "renderStateComponentLayerCount": component_state_count,
        "uniqueDecodedStateSignatureCount": len(unique_signatures),
        "coreGltfFullyRepresentableMaterialCount": exact_core_count,
        "alphaTestMaterialCount": alpha_test_count,
        "blendMaterialCount": blend_count,
        "stencilMaterialCount": stencil_count,
        "polygonOffsetMaterialCount": polygon_offset_count,
    })
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
    args.output_json.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.output_json), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
