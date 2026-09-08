#!/usr/bin/env python3
"""Compile exact SEAL6 native texture slots into a role-complete Blender plan.

This adapter is the bridge from the native OAT closure to Blender. It does not
solve unknown shader math. It guarantees that every closed native texture slot
for head, arms, cornea, iris and mouth is represented explicitly and joins those
slots to the already-exact character binding plan and materialized retail image
payloads.

The historical two-texture glTF selection is retained only as an explicitly
marked authoring preview. Every additional native source remains present as a
first-class node input so later exact shader lowering can consume it without
rebuilding or guessing the dependency graph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-seal6-blender-role-plan-v1"
CONFLICT_FORMAT = "t6-seal6-native-material-conflict-report-v1"
BINDING_FORMAT = "t6-character-material-binding-plan-v1"
MATERIALIZATION_FORMATS = {"t6-ipak-iwi-materialization-v1", "t6-ipak-iwi-materialization-v3"}

TARGETS = {
    "mc/mtl_c_usa_milcas_mcknight_head_camo": 5,
    "mc/mtl_c_usa_mp_seal6_smg_arms": 4,
    "mc/mtl_gen_eye_cornea": 3,
    "mc/mtl_gen_eye_iris_green": 4,
    "mc/mtl_c_gen_insidemouth": 4,
}


class BlenderRolePlanError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _norm_material(value: str) -> str:
    return value[1:] if value.startswith(",") else value


def _copy_texture_rows(material: dict[str, Any]) -> list[dict[str, Any]]:
    copies = material.get("copies")
    if not isinstance(copies, list) or not copies:
        raise BlenderRolePlanError(f"{material.get('material')}: no physical Material copies")
    if material.get("textureRecordsStructurallyIdenticalAcrossCopies") is not True:
        raise BlenderRolePlanError(f"{material.get('material')}: native texture array differs across physical copies")
    first = copies[0].get("textureRoleRows")
    if not isinstance(first, list):
        raise BlenderRolePlanError(f"{material.get('material')}: first copy has no textureRoleRows")
    for copy in copies[1:]:
        if copy.get("textureRoleRows") != first:
            raise BlenderRolePlanError(f"{material.get('material')}: texture-role invariant flag does not match rows")
    return first


def _binding_materials(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if doc.get("format") != BINDING_FORMAT:
        raise BlenderRolePlanError(f"unsupported binding plan {doc.get('format')!r}")
    rows = doc.get("materials")
    if not isinstance(rows, list):
        raise BlenderRolePlanError("binding plan has no materials[]")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = _norm_material(str(row.get("material") or ""))
        if not name or name in out:
            raise BlenderRolePlanError(f"invalid/duplicate binding-plan Material {name!r}")
        out[name] = row
    return out


def _materialized_images(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if doc.get("format") not in MATERIALIZATION_FORMATS:
        raise BlenderRolePlanError(f"unsupported materialization manifest {doc.get('format')!r}")
    out: dict[str, dict[str, Any]] = {}
    for row in doc.get("textures", []):
        name = str(row.get("image") or "")
        if not name or name in out:
            raise BlenderRolePlanError(f"invalid/duplicate materialized image {name!r}")
        if row.get("exactKeyValidated") is not True or row.get("crc29Validated") is not True:
            raise BlenderRolePlanError(f"{name}: image payload lacks exact-key/CRC29 closure")
        out[name] = row
    return out


def _join_binding_slots(material: str, native: list[dict[str, Any]], binding: dict[str, Any]) -> None:
    slots = binding.get("slots")
    if not isinstance(slots, list):
        raise BlenderRolePlanError(f"{material}: binding plan has no slots[]")
    by_index = {int(row.get("index")): row for row in slots}
    if len(by_index) != len(slots):
        raise BlenderRolePlanError(f"{material}: duplicate binding slot index")
    expected = set(range(len(native)))
    if set(by_index) != expected:
        raise BlenderRolePlanError(
            f"{material}: binding slot indices {sorted(by_index)} do not match native {sorted(expected)}"
        )
    for index, nrow in enumerate(native):
        brow = by_index[index]
        if str(brow.get("image") or "") != str(nrow.get("image") or ""):
            raise BlenderRolePlanError(
                f"{material} slot {index}: binding image {brow.get('image')!r} != native {nrow.get('image')!r}"
            )
        if str(brow.get("semanticName") or "") != str(nrow.get("semantic") or ""):
            raise BlenderRolePlanError(
                f"{material} slot {index}: binding semantic {brow.get('semanticName')!r} != native {nrow.get('semantic')!r}"
            )


def _preview_indices(material: str, native: list[dict[str, Any]], binding: dict[str, Any]) -> tuple[int, int]:
    preview = binding.get("gltfVisualization")
    if not isinstance(preview, dict):
        raise BlenderRolePlanError(f"{material}: binding plan has no gltfVisualization")
    color = preview.get("baseColor")
    normal = preview.get("normal")
    if not isinstance(color, dict) or not isinstance(normal, dict):
        raise BlenderRolePlanError(f"{material}: preview baseColor/normal pair incomplete")
    cidx = int(color.get("slotIndex"))
    nidx = int(normal.get("slotIndex"))
    if not (0 <= cidx < len(native)) or not (0 <= nidx < len(native)):
        raise BlenderRolePlanError(f"{material}: preview slot outside native texture table")
    if native[cidx].get("image") != color.get("image") or native[nidx].get("image") != normal.get("image"):
        raise BlenderRolePlanError(f"{material}: preview selection does not join exact native slot identities")
    return cidx, nidx


def build(conflict: dict[str, Any], binding: dict[str, Any], materialized: dict[str, Any]) -> dict[str, Any]:
    if conflict.get("format") != CONFLICT_FORMAT:
        raise BlenderRolePlanError(f"unsupported native conflict report {conflict.get('format')!r}")
    conflict_rows = {str(row.get("material") or ""): row for row in conflict.get("materials", [])}
    if set(TARGETS) - set(conflict_rows):
        raise BlenderRolePlanError(f"native report missing targets: {sorted(set(TARGETS)-set(conflict_rows))}")
    bind = _binding_materials(binding)
    images = _materialized_images(materialized)

    result_rows = []
    unique_images: set[str] = set()
    for material, expected_count in TARGETS.items():
        native_mat = conflict_rows[material]
        if native_mat.get("techniqueSetIdenticalAcrossCopies") is not True:
            raise BlenderRolePlanError(f"{material}: TechniqueSet differs across physical copies")
        native = _copy_texture_rows(native_mat)
        if len(native) != expected_count:
            raise BlenderRolePlanError(f"{material}: native texture count {len(native)} != {expected_count}")
        bmat = bind.get(material)
        if bmat is None:
            raise BlenderRolePlanError(f"{material}: absent from exact character binding plan")
        _join_binding_slots(material, native, bmat)
        cidx, nidx = _preview_indices(material, native, bmat)

        slots = []
        for index, row in enumerate(native):
            image = str(row.get("image") or "")
            if not image:
                raise BlenderRolePlanError(f"{material} slot {index}: empty image")
            payload = images.get(image)
            if payload is None:
                raise BlenderRolePlanError(f"{material} slot {index}: exact image {image!r} is not materialized")
            unique_images.add(image)
            preview_use = []
            if index == cidx:
                preview_use.append("legacy-authoring-base-color")
            if index == nidx:
                preview_use.append("legacy-authoring-normal")
            slots.append({
                "slotIndex": index,
                "semantic": row.get("semantic"),
                "nativeName": row.get("name"),
                "image": image,
                "nativeRecord": row.get("nativeRecord"),
                "nodeName": f"T6_SLOT_{index:02d}_{row.get('semantic') or 'unknown'}",
                "sampling": "Non-Color/native-shader-data",
                "previewUse": preview_use,
                "exactRetailPayload": {
                    "repository": payload.get("repository"),
                    "nameHash": payload.get("nameHash"),
                    "dataHash": payload.get("dataHash"),
                    "iwiSha256": payload.get("iwiSha256"),
                    "pngSha256": payload.get("pngSha256"),
                    "pngFile": payload.get("pngFile"),
                    "crc29Validated": payload.get("crc29Validated"),
                    "exactKeyValidated": payload.get("exactKeyValidated"),
                },
            })

        result_rows.append({
            "material": material,
            "physicalMaterialCopyCount": native_mat.get("physicalCopyCount"),
            "activeRetailClientOwnerResolved": native_mat.get("activeRetailClientOwnerResolved"),
            "wholeMaterialByteIdenticalAcrossCopies": native_mat.get("byteIdenticalAcrossCopies"),
            "techniqueSet": native_mat["copies"][0].get("techniqueSet"),
            "textureRoleInvariantAcrossPhysicalCopies": True,
            "nativeSlotCount": len(slots),
            "nativeSlots": slots,
            "authoringPreview": {
                "policy": "retain historical exact identity selection only; shader math remains explicitly approximate until exact family lowering is solved",
                "baseColorSlotIndex": cidx,
                "normalSlotIndex": nidx,
                "shaderApproximation": True,
            },
            "shaderLowering": {
                "status": "native-inputs-complete-shader-math-not-yet-promoted",
                "completeNativeInputGraph": True,
                "completeRetailPixelOutput": False,
                "forbidden": [
                    "drop unconnected native slots",
                    "infer mask/camo/detail-normal math from filenames",
                    "map specular/gloss to Principled roughness/metallic without exact shader evidence",
                    "treat the authoring preview pair as the native T6 material definition",
                ],
            },
        })

    return {
        "format": FORMAT,
        "summary": {
            "targetMaterials": len(result_rows),
            "nativeTextureSlots": sum(row["nativeSlotCount"] for row in result_rows),
            "uniqueExactRetailImages": len(unique_images),
            "allNativeTextureSlotsRepresented": True,
            "allExactRetailPayloadsValidated": True,
            "completeRetailPixelOutput": False,
        },
        "materials": result_rows,
        "proofBoundary": (
            "All native texture slots are inherited only from the exact OAT role-invariance report and are cross-joined by exact slot index/image/semantic to the character binding plan and exact-key/CRC29-validated retail payload manifest. The existing baseColor+normal selection survives only as an explicitly approximate authoring preview. No additional shader arithmetic, mask meaning, channel swizzle, normal-detail composition, Fresnel term, PBR parameter, or retail-client duplicate winner is inferred here."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--native-conflicts", type=Path, required=True)
    ap.add_argument("--binding-plan", type=Path, required=True)
    ap.add_argument("--materialized-manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    conflict, binding, materialized = _load(a.native_conflicts), _load(a.binding_plan), _load(a.materialized_manifest)
    result = build(conflict, binding, materialized)
    result["inputs"] = {
        "nativeConflictsSha256": _sha(a.native_conflicts),
        "bindingPlanSha256": _sha(a.binding_plan),
        "materializedManifestSha256": _sha(a.materialized_manifest),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
