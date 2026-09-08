#!/usr/bin/env python3
"""Build the exact role-complete Blender input plan for all 12 SEAL6 LOD0 Materials.

Inputs are three independently closed layers:

1. the 12-Material native OAT census (physical Material JSON, ordered textures);
2. the exact LOD0 character binding plan (serialized surface->Material identity and
   MaterialTextureDef image resolution);
3. the exact retail IPAK materialization manifest.

Every LOD0 native slot is joined by exact Material identity + slot index + image.
The binding semantic must equal the native OAT semantic except for one explicitly
source-closed shared alias: cornea slot 2 is native semantic ``colorMap`` with
native argument name ``radiantDiffuseMap`` and binding semanticName
``radiantDiffuseMap``.  That slot is admitted only with
``exact-shared-radiant-alias-proof`` and image ``sw_radiant_default``; it is
preserved as a non-streamed built-in/shared resource and is never fabricated as a
PNG.

No shader equation is inferred here.  The historical baseColor/normal selection
is retained only as authoring-preview metadata so exact shader backends can be
layered on the complete native input graph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-seal6-lod0-blender-role-plan-v2"
CENSUS_FORMAT = "t6-seal6-native-material-conflict-report-v1"
BINDING_FORMAT = "t6-character-material-binding-plan-v1"
MATERIALIZATION_FORMAT = "t6-ipak-iwi-materialization-v3"
EXPECTED_MATERIALS = 12
EXPECTED_NATIVE_SLOTS = 41
EXPECTED_STREAMED_SLOTS = 40
EXPECTED_SHARED_ALIASES = 1
EXPECTED_UNIQUE_STREAMED_IMAGES = 39
EXPECTED_UNIQUE_NATIVE_IMAGES = 40
CLOTH_TECHSET = "mc_sw4_3d_char_cloth_4z8fq5wu"

EXPECTED_COUNTS = {
    "mc/mtl_c_gen_insidemouth": 4,
    "mc/mtl_gen_eye_cornea": 3,
    "mc/mtl_c_usa_mp_seal6_smg_arms": 4,
    "mc/mtl_c_usa_mp_seal6_shoes_1": 3,
    "mc/mtl_c_usa_mp_seal6_gear": 3,
    "mc/mtl_c_usa_mp_seal6_vest_1": 3,
    "mc/mtl_c_usa_mp_seal6_pants_1": 3,
    "mc/mtl_gen_eye_iris_green": 4,
    "mc/mtl_c_usa_mp_seal6_gloves_2": 3,
    "mc/mtl_c_usa_mp_seal6_smg_gear": 3,
    "mc/mtl_c_gen_mp_datapad": 3,
    "mc/mtl_c_usa_milcas_mcknight_head_camo": 5,
}

EXPECTED_TECHSETS = {
    "mc/mtl_c_gen_insidemouth": "mc_sw4_3d_char_skin_j92387z3",
    "mc/mtl_gen_eye_cornea": "mc_sw4_3d_char_eye_cornea_2eww29wu",
    "mc/mtl_c_usa_mp_seal6_smg_arms": "mc_sw4_3d_char_skin_j92387z3",
    "mc/mtl_c_usa_mp_seal6_shoes_1": CLOTH_TECHSET,
    "mc/mtl_c_usa_mp_seal6_gear": CLOTH_TECHSET,
    "mc/mtl_c_usa_mp_seal6_vest_1": CLOTH_TECHSET,
    "mc/mtl_c_usa_mp_seal6_pants_1": CLOTH_TECHSET,
    "mc/mtl_gen_eye_iris_green": "mc_sw4_3d_char_skin_j92387z3",
    "mc/mtl_c_usa_mp_seal6_gloves_2": CLOTH_TECHSET,
    "mc/mtl_c_usa_mp_seal6_smg_gear": CLOTH_TECHSET,
    "mc/mtl_c_gen_mp_datapad": CLOTH_TECHSET,
    "mc/mtl_c_usa_milcas_mcknight_head_camo": "mc_sw4_3d_char_skin_hero_9949fq1j",
}


class Lod0RolePlanError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _norm_material(value: Any) -> str:
    text = str(value or "")
    return text[1:] if text.startswith(",") else text


def _lod0_material_set(binding: dict[str, Any]) -> set[str]:
    if binding.get("format") != BINDING_FORMAT:
        raise Lod0RolePlanError(f"unsupported binding format {binding.get('format')!r}")
    summary = binding.get("summary") or {}
    if int(summary.get("lod", -1)) != 0 or int(summary.get("lodSurfaces", -1)) != 14:
        raise Lod0RolePlanError("binding plan is not exact SEAL6 LOD0/14-surface plan")
    if int(summary.get("lodUniqueMaterials", -1)) != EXPECTED_MATERIALS:
        raise Lod0RolePlanError("binding plan does not close 12 LOD0 unique Materials")
    if summary.get("nativeIdentityClosure") is not True:
        raise Lod0RolePlanError("binding plan native identity closure is false")
    rows = binding.get("surfaceBindings")
    if not isinstance(rows, list) or len(rows) != 14:
        raise Lod0RolePlanError("binding plan lacks 14 surfaceBindings")
    indices = [int(row.get("surfaceIndex", -1)) for row in rows]
    if indices != list(range(14)):
        raise Lod0RolePlanError(f"LOD0 surface order drift: {indices}")
    names = {_norm_material(row.get("material")) for row in rows}
    if names != set(EXPECTED_COUNTS):
        raise Lod0RolePlanError(f"LOD0 Material set drift: {sorted(names)}")
    return names


def _binding_materials(binding: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for row in binding.get("materials", []):
        name = _norm_material(row.get("material"))
        if not name or name in out:
            raise Lod0RolePlanError(f"invalid/duplicate binding Material {name!r}")
        out[name] = row
    if not set(EXPECTED_COUNTS).issubset(out):
        raise Lod0RolePlanError("binding materials[] misses one or more LOD0 targets")
    return out


def _native_materials(census: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if census.get("format") != CENSUS_FORMAT:
        raise Lod0RolePlanError(f"unsupported census format {census.get('format')!r}")
    summary = census.get("summary") or {}
    if int(summary.get("targetCount", -1)) != EXPECTED_MATERIALS:
        raise Lod0RolePlanError("native census targetCount is not 12")
    if int(summary.get("textureRoleInvariantTargetCount", -1)) != EXPECTED_MATERIALS:
        raise Lod0RolePlanError("not all 12 native texture tables are invariant")
    out = {}
    for row in census.get("materials", []):
        name = str(row.get("material") or "")
        if not name or name in out:
            raise Lod0RolePlanError(f"invalid/duplicate census Material {name!r}")
        out[name] = row
    if set(out) != set(EXPECTED_COUNTS):
        raise Lod0RolePlanError(f"native census Material set drift: {sorted(out)}")
    return out


def _materialized(materialized: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if materialized.get("format") != MATERIALIZATION_FORMAT:
        raise Lod0RolePlanError(f"unsupported materialization format {materialized.get('format')!r}")
    summary = materialized.get("summary") or {}
    if int(summary.get("requested", -1)) != 42 or int(summary.get("materialized", -1)) != 42 or int(summary.get("unresolved", -1)) != 0:
        raise Lod0RolePlanError("retail texture materialization is not exact 42/42 closure")
    repos = summary.get("repositories") or {}
    if repos.get("base.ipak") != 40 or repos.get("mp.ipak") != 2:
        raise Lod0RolePlanError("retail texture repository split drift")
    out = {}
    for row in materialized.get("textures", []):
        name = str(row.get("image") or "")
        if not name or name in out:
            raise Lod0RolePlanError(f"invalid/duplicate materialized image {name!r}")
        if row.get("exactKeyValidated") is not True or row.get("crc29Validated") is not True:
            raise Lod0RolePlanError(f"{name}: streamed payload lacks exact-key/CRC29 proof")
        out[name] = row
    return out


def _native_texture_rows(material: str, row: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    if row.get("techniqueSetIdenticalAcrossCopies") is not True:
        raise Lod0RolePlanError(f"{material}: TechniqueSet differs across physical copies")
    if row.get("textureRecordsStructurallyIdenticalAcrossCopies") is not True:
        raise Lod0RolePlanError(f"{material}: texture table differs across physical copies")
    copies = row.get("copies")
    if not isinstance(copies, list) or not copies:
        raise Lod0RolePlanError(f"{material}: no physical native Material copy")
    techsets = {str(copy.get("techniqueSet") or "") for copy in copies}
    if techsets != {EXPECTED_TECHSETS[material]}:
        raise Lod0RolePlanError(f"{material}: TechniqueSet identity drift {techsets}")
    first = copies[0].get("textureRoleRows")
    if not isinstance(first, list) or len(first) != EXPECTED_COUNTS[material]:
        raise Lod0RolePlanError(f"{material}: native texture count drift")
    for copy in copies[1:]:
        if copy.get("textureRoleRows") != first:
            raise Lod0RolePlanError(f"{material}: invariant flag disagrees with native role rows")
    return EXPECTED_TECHSETS[material], first


def _binding_slots(material: str, row: dict[str, Any], native_count: int) -> dict[int, dict[str, Any]]:
    slots = row.get("slots")
    if not isinstance(slots, list) or len(slots) != native_count:
        raise Lod0RolePlanError(f"{material}: binding slot count drift")
    out = {int(slot.get("index", -1)): slot for slot in slots}
    if set(out) != set(range(native_count)) or len(out) != native_count:
        raise Lod0RolePlanError(f"{material}: binding slot index set drift")
    return out


def _preview(row: dict[str, Any], native_rows: list[dict[str, Any]]) -> dict[str, Any]:
    preview = row.get("gltfVisualization")
    if not isinstance(preview, dict):
        raise Lod0RolePlanError("binding Material lacks historical glTF visualization")
    out = {
        "policy": "historical exact identity selection retained only as authoring preview; not native shader truth",
        "shaderApproximation": bool(preview.get("shaderApproximation")),
    }
    for key in ("baseColor", "normal"):
        src = preview.get(key)
        if not isinstance(src, dict):
            raise Lod0RolePlanError(f"historical preview lacks {key}")
        index = int(src.get("slotIndex", -1))
        if index < 0 or index >= len(native_rows):
            raise Lod0RolePlanError(f"historical preview {key} slot outside native table")
        if str(src.get("image") or "") != str(native_rows[index].get("image") or ""):
            raise Lod0RolePlanError(f"historical preview {key} image does not join native slot")
        out[key] = {"slotIndex": index, "image": src.get("image")}
    return out


def build(census: dict[str, Any], binding: dict[str, Any], materialized: dict[str, Any]) -> dict[str, Any]:
    targets = _lod0_material_set(binding)
    bind = _binding_materials(binding)
    native = _native_materials(census)
    payloads = _materialized(materialized)

    rows = []
    native_slots = streamed_slots = shared_aliases = 0
    streamed_images: set[str] = set()
    native_images: set[str] = set()

    ordered_targets = []
    for surface in binding["surfaceBindings"]:
        name = _norm_material(surface.get("material"))
        if name not in ordered_targets:
            ordered_targets.append(name)
    if len(ordered_targets) != EXPECTED_MATERIALS or set(ordered_targets) != targets:
        raise Lod0RolePlanError("cannot derive exact first-surface LOD0 Material order")

    for material in ordered_targets:
        nrow = native[material]
        techset, nslots = _native_texture_rows(material, nrow)
        bslots = _binding_slots(material, bind[material], len(nslots))
        out_slots = []
        for index, nslot in enumerate(nslots):
            bslot = bslots[index]
            nimage = str(nslot.get("image") or "")
            bimage = str(bslot.get("image") or "")
            if not nimage or nimage != bimage:
                raise Lod0RolePlanError(
                    f"{material} slot {index}: native/binding image mismatch {nimage!r} != {bimage!r}"
                )
            native_semantic = str(nslot.get("semantic") or "")
            native_name = nslot.get("name")
            binding_semantic = str(bslot.get("semanticName") or "")
            evidence = str(bslot.get("identityEvidence") or "")

            resource: dict[str, Any]
            semantic_join: str
            payload = payloads.get(nimage)
            if payload is not None:
                if binding_semantic != native_semantic:
                    raise Lod0RolePlanError(
                        f"{material} slot {index}: streamed binding semantic {binding_semantic!r} != native {native_semantic!r}"
                    )
                if evidence != "exact-resolved-MaterialTextureDef-use-v4":
                    raise Lod0RolePlanError(
                        f"{material} slot {index}: streamed image lacks exact MaterialTextureDef-use-v4 evidence"
                    )
                resource = {
                    "kind": "exact-streamed-retail-payload",
                    "repository": payload.get("repository"),
                    "nameHash": payload.get("nameHash"),
                    "dataHash": payload.get("dataHash"),
                    "iwiSha256": payload.get("iwiSha256"),
                    "pngSha256": payload.get("pngSha256"),
                    "pngFile": payload.get("pngFile"),
                    "exactKeyValidated": True,
                    "crc29Validated": True,
                }
                semantic_join = "binding-semantic-equals-native-semantic"
                streamed_slots += 1
                streamed_images.add(nimage)
            else:
                if not (
                    material == "mc/mtl_gen_eye_cornea"
                    and index == 2
                    and nimage == "sw_radiant_default"
                    and native_semantic == "colorMap"
                    and native_name == "radiantDiffuseMap"
                    and binding_semantic == "radiantDiffuseMap"
                    and evidence == "exact-shared-radiant-alias-proof"
                ):
                    raise Lod0RolePlanError(
                        f"{material} slot {index}: unmaterialized resource is not the exact shared radiant alias"
                    )
                resource = {
                    "kind": "exact-shared-built-in-alias",
                    "image": "sw_radiant_default",
                    "identityEvidence": "exact-shared-radiant-alias-proof",
                    "streamedPayloadRequired": False,
                    "fabricatedPng": False,
                }
                semantic_join = "binding-semantic-equals-native-argument-name-for-exact-shared-alias"
                shared_aliases += 1

            native_slots += 1
            native_images.add(nimage)
            out_slots.append({
                "slotIndex": index,
                "nativeSemantic": native_semantic,
                "nativeName": native_name,
                "image": nimage,
                "bindingSemantic": binding_semantic,
                "identityEvidence": evidence,
                "semanticJoin": semantic_join,
                "nativeRecord": nslot.get("nativeRecord"),
                "resource": resource,
            })

        rows.append({
            "material": material,
            "techniqueSet": techset,
            "shaderFamilyClass": "cloth" if techset == CLOTH_TECHSET else "character-specialized",
            "physicalMaterialCopyCount": int(nrow.get("physicalCopyCount", len(nrow.get("copies", [])))),
            "activeRetailClientWholeMaterialOwnerResolved": bool(nrow.get("activeRetailClientOwnerResolved")),
            "textureRoleInvariantAcrossPhysicalCopies": True,
            "nativeSlotCount": len(out_slots),
            "nativeSlots": out_slots,
            "authoringPreview": _preview(bind[material], nslots),
            "shaderLowering": {
                "nativeInputsComplete": True,
                "ordinaryLitMathAttachedBySeparateExactShaderPlan": False,
                "completeRetailPixelOutput": False,
            },
        })

    if native_slots != EXPECTED_NATIVE_SLOTS:
        raise Lod0RolePlanError(f"native slot count {native_slots} != {EXPECTED_NATIVE_SLOTS}")
    if streamed_slots != EXPECTED_STREAMED_SLOTS:
        raise Lod0RolePlanError(f"streamed slot count {streamed_slots} != {EXPECTED_STREAMED_SLOTS}")
    if shared_aliases != EXPECTED_SHARED_ALIASES:
        raise Lod0RolePlanError(f"shared alias count {shared_aliases} != {EXPECTED_SHARED_ALIASES}")
    if len(streamed_images) != EXPECTED_UNIQUE_STREAMED_IMAGES:
        raise Lod0RolePlanError(
            f"unique streamed image count {len(streamed_images)} != {EXPECTED_UNIQUE_STREAMED_IMAGES}"
        )
    if len(native_images) != EXPECTED_UNIQUE_NATIVE_IMAGES:
        raise Lod0RolePlanError(
            f"unique native image count {len(native_images)} != {EXPECTED_UNIQUE_NATIVE_IMAGES}"
        )

    cloth = [row for row in rows if row["techniqueSet"] == CLOTH_TECHSET]
    if len(cloth) != 7 or any(row["nativeSlotCount"] != 3 for row in cloth):
        raise Lod0RolePlanError("cloth Material population is not exact 7x3")

    return {
        "format": FORMAT,
        "summary": {
            "lod": 0,
            "surfaces": 14,
            "targetMaterials": len(rows),
            "nativeTextureSlots": native_slots,
            "streamedNativeTextureSlots": streamed_slots,
            "sharedBuiltInAliasSlots": shared_aliases,
            "uniqueStreamedRetailImages": len(streamed_images),
            "uniqueNativeImagesIncludingSharedAlias": len(native_images),
            "clothMaterials": len(cloth),
            "allNativeTextureSlotsRepresented": True,
            "allStreamedPayloadsExactKeyAndCrcValidated": True,
            "sharedRadiantAliasPreservedWithoutFabrication": True,
            "completeRetailPixelOutput": False,
        },
        "materials": rows,
        "proofBoundary": (
            "The exact LOD0 Material set is derived from the 14 serialized surfaceBindings, then joined to the independent 12-Material OAT census. Every native texture slot is preserved in OAT order and cross-checked against the exact binding image at the same slot index. Streamed resources require exact MaterialTextureDef-use-v4 evidence plus exact-key/CRC29 materialization. The sole non-streamed resource is cornea sw_radiant_default, admitted only by exact-shared-radiant-alias-proof and preserved without a fabricated payload. Historical glTF visualization selections remain authoring metadata only. No shader equations, PBR parameters, or runtime global values are inferred here."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--native-census", type=Path, required=True)
    ap.add_argument("--binding-plan", type=Path, required=True)
    ap.add_argument("--materialized-manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = build(_load(args.native_census), _load(args.binding_plan), _load(args.materialized_manifest))
    out["inputs"] = {
        "nativeCensusSha256": _sha(args.native_census),
        "bindingPlanSha256": _sha(args.binding_plan),
        "materializedManifestSha256": _sha(args.materialized_manifest),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
