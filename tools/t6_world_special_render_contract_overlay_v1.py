#!/usr/bin/env python3
"""Attach exact T6 special-render replay metadata to an existing world glTF.

This overlay deliberately does not translate T6 shaders into core glTF PBR.
It deep-copies the input document and modifies only ``extras.T6``. Geometry,
core Material fields, embedded textures/images/samplers and buffer payloads are
left untouched.

The replay contract is joined only through the exact ``extras.T6.sourceMaterial``
identity emitted by ``t6_world_gltf_export_v1.py``. A glTF display name alone is
not sufficient provenance.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-special-render-replay-contract-v1"
MAP = "mp_nuketown_2020"
RAW_MATERIAL = "wpc/glass_clear_wall_opaque_white"
OVERLAY_FORMAT = "t6-world-special-render-contract-overlay-v1"


class RenderContractOverlayError(RuntimeError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _contract_core(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "rawnormal": contract.get("rawnormal"),
        "unlitAndEmissiveSpecialMaterials": contract.get("unlitAndEmissiveSpecialMaterials"),
        "shadowcasters": contract.get("shadowcasters"),
    }


def _validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("format") != FORMAT or contract.get("map") != MAP:
        raise RenderContractOverlayError("render replay contract identity changed")
    expected = str(contract.get("contractDigestSha256") or "")
    actual = _digest(_contract_core(contract))
    if len(expected) != 64 or actual != expected:
        raise RenderContractOverlayError(f"render replay contract digest {actual} != {expected}")

    special = contract.get("unlitAndEmissiveSpecialMaterials")
    shadows = contract.get("shadowcasters")
    raw = contract.get("rawnormal")
    if not isinstance(special, list) or not isinstance(shadows, list) or not isinstance(raw, dict):
        raise RenderContractOverlayError("render replay contract sections malformed")
    names = [str(row.get("material") or "") for row in special if isinstance(row, dict)]
    if len(names) != len(set(names)) or any(not name for name in names):
        raise RenderContractOverlayError("special Material identities are empty/duplicated")
    if str(raw.get("material") or "") != RAW_MATERIAL:
        raise RenderContractOverlayError("raw-normal Material identity changed")
    shadow_names = [str(row.get("material") or "") for row in shadows if isinstance(row, dict)]
    if len(shadow_names) != len(set(shadow_names)) or any(not name for name in shadow_names):
        raise RenderContractOverlayError("shadowcaster Material identities are empty/duplicated")


def _contract_material_index(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}

    def row(name: str) -> dict[str, Any]:
        if not name:
            raise RenderContractOverlayError("empty contract Material identity")
        return out.setdefault(name, {"material": name})

    for special in contract["unlitAndEmissiveSpecialMaterials"]:
        if not isinstance(special, dict):
            raise RenderContractOverlayError("malformed unlit/emissive contract row")
        name = str(special.get("material") or "")
        row(name)["unlitAndEmissive"] = copy.deepcopy(special)

    raw = contract["rawnormal"]
    row(str(raw["material"]))["rawnormal"] = copy.deepcopy(raw)

    for shadow in contract["shadowcasters"]:
        if not isinstance(shadow, dict):
            raise RenderContractOverlayError("malformed shadow contract row")
        name = str(shadow.get("material") or "")
        row(name)["shadowcaster"] = copy.deepcopy(shadow)
    return out


def _source_material(material: dict[str, Any]) -> str | None:
    extras = material.get("extras")
    if not isinstance(extras, dict):
        return None
    t6 = extras.get("T6")
    if not isinstance(t6, dict):
        return None
    value = t6.get("sourceMaterial")
    if not isinstance(value, str) or not value:
        return None
    return value


def _runtime_requirements(entry: dict[str, Any]) -> set[str]:
    req: set[str] = set()
    raw = entry.get("rawnormal")
    if isinstance(raw, dict):
        for shader in raw.get("pixelShaders", []):
            if not isinstance(shader, dict):
                continue
            for tex in shader.get("runtimeTextureBindings", []):
                req.add("texture:" + json.dumps(tex, sort_keys=True, separators=(",", ":")))
            for var in shader.get("runtimeConstantVariables", []):
                req.add("constant:" + json.dumps(var, sort_keys=True, separators=(",", ":")))
    special = entry.get("unlitAndEmissive")
    if isinstance(special, dict):
        for program in special.get("programs", []):
            if not isinstance(program, dict):
                continue
            for leaf in program.get("runtimeConstantLeaves", []):
                req.add("constant-leaf:" + json.dumps(leaf, sort_keys=True, separators=(",", ":")))
    return req


def apply_special_render_contract(
    gltf: dict[str, Any],
    contract: dict[str, Any],
    *,
    require_all_contract_materials: bool = False,
) -> dict[str, Any]:
    """Return a deep-copied glTF with exact contract metadata under extras.T6."""
    _validate_contract(contract)
    if not isinstance(gltf, dict):
        raise RenderContractOverlayError("glTF document must be an object")
    materials = gltf.get("materials")
    if not isinstance(materials, list):
        raise RenderContractOverlayError("glTF materials array missing")

    out = copy.deepcopy(gltf)
    contract_by_material = _contract_material_index(contract)

    source_to_index: dict[str, int] = {}
    for i, material in enumerate(out["materials"]):
        if not isinstance(material, dict):
            raise RenderContractOverlayError(f"glTF material {i} is not an object")
        source = _source_material(material)
        if source is None:
            continue
        if source in source_to_index:
            raise RenderContractOverlayError(
                f"duplicate exact glTF sourceMaterial {source!r} at {source_to_index[source]} and {i}"
            )
        source_to_index[source] = i

    matched: list[str] = []
    raw_count = 0
    shadow_count = 0
    runtime_requirements: set[str] = set()
    for source, entry in sorted(contract_by_material.items()):
        index = source_to_index.get(source)
        if index is None:
            continue
        material = out["materials"][index]
        t6 = material.setdefault("extras", {}).setdefault("T6", {})
        if "renderReplayContract" in t6:
            raise RenderContractOverlayError(f"{source}: renderReplayContract already present")
        t6["renderReplayContract"] = {
            "format": OVERLAY_FORMAT,
            "contractDigestSha256": contract["contractDigestSha256"],
            "sourceMaterial": source,
            "exactT6ShaderReplayMetadata": copy.deepcopy(entry),
            "coreGltfMaterialPolicy": (
                "Existing core glTF/PBR fields are an evidence-scoped portable preview only; "
                "they are not the exact T6 multipass shader. This overlay does not modify them."
            ),
        }
        matched.append(source)
        raw_count += int("rawnormal" in entry)
        shadow_count += int("shadowcaster" in entry)
        runtime_requirements |= _runtime_requirements(entry)

    unmatched = sorted(set(contract_by_material) - set(matched))
    if require_all_contract_materials and unmatched:
        raise RenderContractOverlayError(f"contract Materials absent from glTF: {unmatched}")

    t6_root = out.setdefault("extras", {}).setdefault("T6", {})
    if "renderReplayContractOverlay" in t6_root:
        raise RenderContractOverlayError("top-level renderReplayContractOverlay already present")
    t6_root["renderReplayContractOverlay"] = {
        "format": OVERLAY_FORMAT,
        "map": MAP,
        "contractDigestSha256": contract["contractDigestSha256"],
        "policy": {
            "join": "exact extras.T6.sourceMaterial only",
            "coreMaterialMutation": "none",
            "exactReplay": "requires the attached shader/DAG identities plus all listed runtime inputs",
            "portablePreview": "existing glTF/PBR may remain, but is explicitly non-exact",
        },
        "stats": {
            "exactContractSpecialMaterialCount": len(contract_by_material),
            "exactContractMatchedMaterialCount": len(matched),
            "exactContractRawnormalCount": raw_count,
            "exactContractShadowcasterCount": shadow_count,
            "portablePreviewOnlyMaterialCount": len(out["materials"]) - len(matched),
            "exactRuntimeInputRequirementCount": len(runtime_requirements),
        },
        "matchedContractMaterials": matched,
        "unmatchedContractMaterials": unmatched,
    }

    # Strong non-mutation check: remove only the fields this overlay owns and
    # demand the rest of every Material equal the caller's input exactly.
    for i, (before, after) in enumerate(zip(materials, out["materials"])):
        probe = copy.deepcopy(after)
        extras = probe.get("extras")
        if isinstance(extras, dict):
            t6 = extras.get("T6")
            if isinstance(t6, dict):
                t6.pop("renderReplayContract", None)
        if probe != before:
            raise RenderContractOverlayError(f"core/pre-existing glTF Material {i} was mutated")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("gltf_json", type=Path)
    ap.add_argument("contract_json", type=Path)
    ap.add_argument("output_json", type=Path)
    ap.add_argument("--require-all-contract-materials", action="store_true")
    a = ap.parse_args()
    gltf = json.loads(a.gltf_json.read_text(encoding="utf-8"))
    contract = json.loads(a.contract_json.read_text(encoding="utf-8"))
    out = apply_special_render_contract(
        gltf,
        contract,
        require_all_contract_materials=a.require_all_contract_materials,
    )
    a.output_json.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["extras"]["T6"]["renderReplayContractOverlay"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
