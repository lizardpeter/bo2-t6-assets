#!/usr/bin/env python3
"""Join exact SEAL6 role-complete materials to source-closed lit shader semantics.

The output explicitly distinguishes native Material inputs from inputs referenced
by the ordinary-lit executable.  It never drops a native slot: unreferenced
slots remain preserved for other TechniqueSet passes.  Exact Material constants
come only from native OAT Material JSON and must be invariant across physical
copies.  Shader-family selection comes only from the exact TechniqueSet and the
SHA-locked semantics manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-seal6-blender-shader-plan-v1"
ROLE_FORMAT = "t6-seal6-blender-role-plan-v1"
CONFLICT_FORMAT = "t6-seal6-native-material-conflict-report-v1"
SEMANTICS_FORMAT = "t6-retail-seal6-lit-semantics-v1"

TARGETS = {
    "mc/mtl_c_usa_milcas_mcknight_head_camo": "mc_sw4_3d_char_skin_hero_9949fq1j",
    "mc/mtl_c_usa_mp_seal6_smg_arms": "mc_sw4_3d_char_skin_j92387z3",
    "mc/mtl_gen_eye_cornea": "mc_sw4_3d_char_eye_cornea_2eww29wu",
    "mc/mtl_gen_eye_iris_green": "mc_sw4_3d_char_skin_j92387z3",
    "mc/mtl_c_gen_insidemouth": "mc_sw4_3d_char_skin_j92387z3",
}
EXPECTED_NATIVE_SLOTS = 20
EXPECTED_LIT_TEXTURE_SLOTS = 15
EXPECTED_PRESERVED_NONLIT_SLOTS = 5
EXPECTED_CONSTANTS = 22
EXPECTED_ARGUMENT_BINDINGS = 37


class Seal6BlenderShaderPlanError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _literal_constant_rows(material: dict[str, Any]) -> list[dict[str, Any]]:
    copies = material.get("copies")
    if not isinstance(copies, list) or not copies:
        raise Seal6BlenderShaderPlanError(f"{material.get('material')}: no native Material copies")
    rows = copies[0].get("nativeMaterialRecord", {}).get("constants")
    if not isinstance(rows, list):
        raise Seal6BlenderShaderPlanError(f"{material.get('material')}: native Material has no constants[]")
    for copy in copies[1:]:
        other = copy.get("nativeMaterialRecord", {}).get("constants")
        if other != rows:
            raise Seal6BlenderShaderPlanError(
                f"{material.get('material')}: native Material constants differ across physical copies"
            )
    out = []
    seen = set()
    for row in rows:
        name = str(row.get("name") or "")
        literal = row.get("literal")
        if not name or name in seen:
            raise Seal6BlenderShaderPlanError(f"{material.get('material')}: invalid/duplicate constant {name!r}")
        if not isinstance(literal, list) or len(literal) != 4:
            raise Seal6BlenderShaderPlanError(f"{material.get('material')}: constant {name!r} is not float4")
        seen.add(name)
        out.append({"name": name, "literal": [float(v) for v in literal]})
    return out


def _semantic_families(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if doc.get("format") != SEMANTICS_FORMAT:
        raise Seal6BlenderShaderPlanError(f"unsupported semantics {doc.get('format')!r}")
    if doc.get("summary", {}).get("exactMaterialArgumentAbiClosed") is not True:
        raise Seal6BlenderShaderPlanError("shader semantics does not close the exact Material argument ABI")
    if doc.get("summary", {}).get("completeRetailPixelOutputInBlender") is not False:
        raise Seal6BlenderShaderPlanError("v1 expects Blender global runtime inputs to remain explicitly incomplete")
    rows = doc.get("families")
    if not isinstance(rows, list):
        raise Seal6BlenderShaderPlanError("semantics has no families[]")
    out = {}
    for row in rows:
        name = str(row.get("techniqueSet") or "")
        if not name or name in out:
            raise Seal6BlenderShaderPlanError(f"invalid/duplicate shader family {name!r}")
        out[name] = row
    if set(out) != set(TARGETS.values()):
        raise Seal6BlenderShaderPlanError(f"unexpected semantics TechniqueSet set: {sorted(out)}")
    return out


def _role_materials(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if doc.get("format") != ROLE_FORMAT:
        raise Seal6BlenderShaderPlanError(f"unsupported role plan {doc.get('format')!r}")
    summary = doc.get("summary") or {}
    if int(summary.get("nativeTextureSlots", -1)) != EXPECTED_NATIVE_SLOTS:
        raise Seal6BlenderShaderPlanError("role plan does not contain exactly twenty native texture slots")
    if summary.get("allNativeTextureSlotsRepresented") is not True:
        raise Seal6BlenderShaderPlanError("role plan does not preserve all native texture slots")
    rows = doc.get("materials")
    if not isinstance(rows, list):
        raise Seal6BlenderShaderPlanError("role plan has no materials[]")
    out = {str(row.get("material") or ""): row for row in rows}
    if set(out) != set(TARGETS):
        raise Seal6BlenderShaderPlanError(f"role plan Material set drift: {sorted(out)}")
    return out


def _conflict_materials(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if doc.get("format") != CONFLICT_FORMAT:
        raise Seal6BlenderShaderPlanError(f"unsupported native Material report {doc.get('format')!r}")
    rows = doc.get("materials")
    if not isinstance(rows, list):
        raise Seal6BlenderShaderPlanError("native Material report has no materials[]")
    out = {str(row.get("material") or ""): row for row in rows}
    if set(TARGETS) - set(out):
        raise Seal6BlenderShaderPlanError(f"native Material report missing targets: {sorted(set(TARGETS)-set(out))}")
    return out


def _family_ops(semantics: dict[str, Any], family: dict[str, Any]) -> dict[str, Any]:
    family_id = str(family.get("id") or "")
    if family_id in {"seal6-char-skin-hero-lit-v1", "seal6-char-skin-standard-lit-v1"}:
        shared = semantics.get("sharedSkinSemantics")
        if not isinstance(shared, dict):
            raise Seal6BlenderShaderPlanError("skin family has no sharedSkinSemantics")
        return {
            "familyId": family_id,
            "familyLocal": {"normal": family.get("normal")},
            "sharedSkin": shared,
        }
    if family_id == "seal6-char-eye-cornea-lit-v1":
        return {
            "familyId": family_id,
            "fillDirectionVertexTransport": family.get("fillDirectionVertexTransport"),
            "surfaceNormal": family.get("surfaceNormal"),
            "highlightHelper": family.get("highlightHelper"),
            "alpha": family.get("alpha"),
            "rgb": family.get("rgb"),
        }
    raise Seal6BlenderShaderPlanError(f"unsupported exact SEAL6 shader family {family_id!r}")


def build(role: dict[str, Any], conflict: dict[str, Any], semantics: dict[str, Any]) -> dict[str, Any]:
    role_rows = _role_materials(role)
    native_rows = _conflict_materials(conflict)
    families = _semantic_families(semantics)

    output = []
    lit_slot_count = 0
    preserved_nonlit_count = 0
    constant_count = 0
    argument_binding_count = 0

    for material, expected_techset in TARGETS.items():
        rmat = role_rows[material]
        nmat = native_rows[material]
        techset = str(rmat.get("techniqueSet") or "")
        if techset != expected_techset:
            raise Seal6BlenderShaderPlanError(f"{material}: TechniqueSet {techset!r} != expected {expected_techset!r}")
        if nmat.get("techniqueSetIdenticalAcrossCopies") is not True:
            raise Seal6BlenderShaderPlanError(f"{material}: TechniqueSet is not invariant across physical Material copies")
        copy_techsets = {str(c.get("techniqueSet") or "") for c in nmat.get("copies", [])}
        if copy_techsets != {techset}:
            raise Seal6BlenderShaderPlanError(f"{material}: native TechniqueSet copies do not match role plan")

        family = families[techset]
        pixel_args = list(family.get("materialArguments") or [])
        vertex_args = list(family.get("vertexMaterialArguments") or [])
        if len(pixel_args) != len(set(pixel_args)) or len(vertex_args) != len(set(vertex_args)):
            raise Seal6BlenderShaderPlanError(f"{material}: duplicate exact shader arguments")
        if set(pixel_args) & set(vertex_args):
            raise Seal6BlenderShaderPlanError(f"{material}: same Material argument appears in both stages")
        stage_by_arg = {name: "pixel" for name in pixel_args}
        stage_by_arg.update({name: "vertex" for name in vertex_args})

        slots = rmat.get("nativeSlots")
        if not isinstance(slots, list):
            raise Seal6BlenderShaderPlanError(f"{material}: no role-plan nativeSlots[]")
        seen_slot_arguments = set()
        out_slots = []
        for slot in slots:
            native_name = slot.get("nativeName")
            argument = str(native_name) if native_name is not None else ""
            referenced = bool(argument and argument in stage_by_arg)
            if referenced:
                if argument in seen_slot_arguments:
                    raise Seal6BlenderShaderPlanError(f"{material}: shader argument {argument!r} maps to multiple native slots")
                seen_slot_arguments.add(argument)
                lit_slot_count += 1
            else:
                preserved_nonlit_count += 1
            out_slots.append({
                "slotIndex": int(slot["slotIndex"]),
                "semantic": slot.get("semantic"),
                "nativeName": native_name,
                "image": slot.get("image"),
                "exactRetailPayload": slot.get("exactRetailPayload"),
                "ordinaryLitBinding": {
                    "referenced": referenced,
                    "shaderArgument": argument if referenced else None,
                    "stage": stage_by_arg.get(argument) if referenced else None,
                    "status": (
                        "referenced-by-exact-ordinary-lit-executable"
                        if referenced
                        else "preserved-native-slot-not-referenced-by-exact-ordinary-lit-executable"
                    ),
                },
            })

        constants = _literal_constant_rows(nmat)
        constant_count += len(constants)
        constant_names = {row["name"] for row in constants}
        out_constants = []
        for row in constants:
            name = row["name"]
            if name not in stage_by_arg:
                raise Seal6BlenderShaderPlanError(
                    f"{material}: native constant {name!r} is not consumed by the exact ordinary-lit VS/PS ABI"
                )
            out_constants.append({
                **row,
                "ordinaryLitBinding": {
                    "referenced": True,
                    "shaderArgument": name,
                    "stage": stage_by_arg[name],
                    "status": "referenced-by-exact-ordinary-lit-executable",
                },
            })

        required = set(stage_by_arg)
        provided = seen_slot_arguments | constant_names
        missing = required - provided
        extra_named = provided - required
        if missing or extra_named:
            raise Seal6BlenderShaderPlanError(
                f"{material}: exact lit argument join mismatch missing={sorted(missing)} extra={sorted(extra_named)}"
            )
        argument_binding_count += len(required)

        output.append({
            "material": material,
            "techniqueSet": techset,
            "shaderFamilyId": family["id"],
            "shaderIdentity": {
                "vertexDxbcSha256": family["vertexDxbcSha256"],
                "pixelDxbcSha256": family["pixelDxbcSha256"],
            },
            "activeRetailClientWholeMaterialOwnerResolved": bool(nmat.get("activeRetailClientOwnerResolved")),
            "physicalMaterialCopyCount": int(nmat.get("physicalCopyCount", len(nmat.get("copies", [])))),
            "constantsInvariantAcrossPhysicalCopies": True,
            "ordinaryLitArguments": {
                "pixel": pixel_args,
                "vertex": vertex_args,
                "allRequiredArgumentsClosed": True,
            },
            "nativeTextureSlots": out_slots,
            "nativeConstants": out_constants,
            "exactLitEquations": _family_ops(semantics, family),
            "blenderLowering": {
                "exactMaterialInputsClosed": True,
                "exactOrdinaryLitEquationsClosed": True,
                "materialLocalNodeLoweringPermitted": True,
                "globalRuntimeLightingInputsBound": False,
                "completeRetailPixelOutput": False,
                "authoringPreviewMayRemainAsFallbackView": True,
            },
        })

    if lit_slot_count != EXPECTED_LIT_TEXTURE_SLOTS:
        raise Seal6BlenderShaderPlanError(f"ordinary-lit referenced texture slots {lit_slot_count} != 15")
    if preserved_nonlit_count != EXPECTED_PRESERVED_NONLIT_SLOTS:
        raise Seal6BlenderShaderPlanError(f"preserved non-lit texture slots {preserved_nonlit_count} != 5")
    if constant_count != EXPECTED_CONSTANTS:
        raise Seal6BlenderShaderPlanError(f"native Material constants {constant_count} != 22")
    if argument_binding_count != EXPECTED_ARGUMENT_BINDINGS:
        raise Seal6BlenderShaderPlanError(f"exact shader argument bindings {argument_binding_count} != 37")

    return {
        "format": FORMAT,
        "summary": {
            "targetMaterials": len(output),
            "nativeTextureSlotsPreserved": EXPECTED_NATIVE_SLOTS,
            "ordinaryLitReferencedTextureSlots": lit_slot_count,
            "preservedNativeTextureSlotsNotReferencedByOrdinaryLit": preserved_nonlit_count,
            "nativeMaterialConstants": constant_count,
            "exactVsPsMaterialArgumentBindings": argument_binding_count,
            "allOrdinaryLitMaterialArgumentsClosed": True,
            "exactOrdinaryLitEquationsClosed": True,
            "headOrdinaryLitExecutableIndependentOfUnresolvedWholeMaterialOwner": True,
            "globalRuntimeLightingInputsBoundInBlender": False,
            "completeRetailPixelOutputInBlender": False,
        },
        "materials": output,
        "globalRuntimeDependencies": semantics.get("backendPolicy", {}).get(
            "globalResourcesStillRequiredForCompleteRetailOutput", []
        ),
        "forbiddenFallbacks": semantics.get("backendPolicy", {}).get("forbiddenFallbacks", []),
        "proofBoundary": (
            "Native texture slots and constants come only from exact OAT Material records; texture payload identity comes from the role-complete exact retail plan; shader usage and equations come only from the SHA-locked SEAL6 semantics manifest. A native slot absent from the ordinary-lit Material argument ABI is preserved but not connected into that pass. No mask/rim/camo/specular/roughness meaning is inferred from filenames or slot proximity. Complete Blender retail pixel output remains false until the required T6 runtime lighting/probe/fog/HDR inputs are provided or exactly baked."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role-plan", type=Path, required=True)
    ap.add_argument("--native-conflicts", type=Path, required=True)
    ap.add_argument("--semantics", type=Path, default=Path("manifests/render/T6_RETAIL_SEAL6_LIT_SEMANTICS_V1.json"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = build(_load(args.role_plan), _load(args.native_conflicts), _load(args.semantics))
    result["inputs"] = {
        "rolePlanSha256": _sha(args.role_plan),
        "nativeConflictReportSha256": _sha(args.native_conflicts),
        "semanticsSha256": _sha(args.semantics),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
