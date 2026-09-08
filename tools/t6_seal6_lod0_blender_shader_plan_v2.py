#!/usr/bin/env python3
"""Join all 12 exact SEAL6 LOD0 Material inputs to ordinary-lit shader semantics.

This extends the five-material character shader plan with the independently
closed seven-material cloth family. Inputs remain fail-closed:

* exact 12-Material OAT census;
* exact 12-Material/41-slot Blender role plan v2;
* SHA-locked hero/standard/cornea semantics manifest;
* SHA-locked cloth semantics manifest.

Every native slot remains represented. A slot is marked ordinary-lit only when
its literal OAT argument name appears in the exact shader ABI. Native constants
come only from invariant physical OAT Material copies. No filename, slot-order,
or visual inference is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-seal6-lod0-blender-shader-plan-v2"
ROLE_FORMAT = "t6-seal6-lod0-blender-role-plan-v2"
CENSUS_FORMAT = "t6-seal6-native-material-conflict-report-v1"
CHAR_SEMANTICS_FORMAT = "t6-retail-seal6-lit-semantics-v1"
CLOTH_SEMANTICS_FORMAT = "t6-retail-seal6-cloth-lit-semantics-v1"
CLOTH_TECHSET = "mc_sw4_3d_char_cloth_4z8fq5wu"

EXPECTED_MATERIALS = 12
EXPECTED_NATIVE_SLOTS = 41
EXPECTED_LIT_SLOTS = 36
EXPECTED_PRESERVED_NONLIT = 5
EXPECTED_CONSTANTS = 22
EXPECTED_ARGUMENT_BINDINGS = 58


class Lod0ShaderPlanError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _role_materials(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if doc.get("format") != ROLE_FORMAT:
        raise Lod0ShaderPlanError(f"unsupported role plan {doc.get('format')!r}")
    s = doc.get("summary") or {}
    expected = {
        "targetMaterials": EXPECTED_MATERIALS,
        "nativeTextureSlots": EXPECTED_NATIVE_SLOTS,
        "streamedNativeTextureSlots": 40,
        "sharedBuiltInAliasSlots": 1,
        "clothMaterials": 7,
    }
    for key, value in expected.items():
        if int(s.get(key, -1)) != value:
            raise Lod0ShaderPlanError(f"role-plan {key}={s.get(key)!r} != {value}")
    if s.get("allNativeTextureSlotsRepresented") is not True:
        raise Lod0ShaderPlanError("role plan does not preserve every native slot")
    if s.get("allStreamedPayloadsExactKeyAndCrcValidated") is not True:
        raise Lod0ShaderPlanError("role plan lacks exact streamed payload closure")
    if s.get("sharedRadiantAliasPreservedWithoutFabrication") is not True:
        raise Lod0ShaderPlanError("role plan does not preserve the exact shared radiant alias")
    rows = doc.get("materials")
    if not isinstance(rows, list) or len(rows) != EXPECTED_MATERIALS:
        raise Lod0ShaderPlanError("role plan materials[] is not exact 12 rows")
    names = [str(r.get("material") or "") for r in rows]
    if len(set(names)) != EXPECTED_MATERIALS or any(not n for n in names):
        raise Lod0ShaderPlanError("role plan Material identities are empty/duplicated")
    return rows


def _native_materials(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if doc.get("format") != CENSUS_FORMAT:
        raise Lod0ShaderPlanError(f"unsupported census {doc.get('format')!r}")
    s = doc.get("summary") or {}
    if int(s.get("targetCount", -1)) != EXPECTED_MATERIALS:
        raise Lod0ShaderPlanError("native census targetCount is not 12")
    if int(s.get("textureRoleInvariantTargetCount", -1)) != EXPECTED_MATERIALS:
        raise Lod0ShaderPlanError("not all native role tables are invariant")
    rows = {str(r.get("material") or ""): r for r in doc.get("materials", [])}
    if len(rows) != EXPECTED_MATERIALS:
        raise Lod0ShaderPlanError("native census Material set is not exact 12")
    return rows


def _char_families(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if doc.get("format") != CHAR_SEMANTICS_FORMAT:
        raise Lod0ShaderPlanError(f"unsupported character semantics {doc.get('format')!r}")
    s = doc.get("summary") or {}
    if s.get("exactMaterialArgumentAbiClosed") is not True or s.get("completeRetailPixelOutputInBlender") is not False:
        raise Lod0ShaderPlanError("character semantics proof boundary drift")
    rows = doc.get("families")
    if not isinstance(rows, list) or len(rows) != 3:
        raise Lod0ShaderPlanError("character semantics must contain three exact families")
    out = {str(r.get("techniqueSet") or ""): r for r in rows}
    if len(out) != 3:
        raise Lod0ShaderPlanError("character TechniqueSet identities duplicate")
    return out


def _cloth_family(doc: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    if doc.get("format") != CLOTH_SEMANTICS_FORMAT:
        raise Lod0ShaderPlanError(f"unsupported cloth semantics {doc.get('format')!r}")
    s = doc.get("summary") or {}
    if s.get("exactMaterialArgumentAbiClosed") is not True or s.get("exactOrdinaryLitEquationsClosed") is not True:
        raise Lod0ShaderPlanError("cloth semantics is not exact")
    if s.get("completeRetailPixelOutputInBlender") is not False:
        raise Lod0ShaderPlanError("cloth runtime globals must remain unbound")
    family = doc.get("family")
    if not isinstance(family, dict) or family.get("techniqueSet") != CLOTH_TECHSET:
        raise Lod0ShaderPlanError("cloth family TechniqueSet drift")
    mats = doc.get("materials")
    if not isinstance(mats, list) or len(mats) != 7:
        raise Lod0ShaderPlanError("cloth semantics does not cover seven Materials")
    names = {str(r.get("material") or "") for r in mats}
    if len(names) != 7:
        raise Lod0ShaderPlanError("cloth Material identities duplicate/empty")
    return family, names


def _constant_rows(material: str, native: dict[str, Any]) -> list[dict[str, Any]]:
    copies = native.get("copies")
    if not isinstance(copies, list) or not copies:
        raise Lod0ShaderPlanError(f"{material}: no physical Material copies")
    rows = copies[0].get("nativeMaterialRecord", {}).get("constants")
    if not isinstance(rows, list):
        raise Lod0ShaderPlanError(f"{material}: native constants[] missing")
    for copy in copies[1:]:
        if copy.get("nativeMaterialRecord", {}).get("constants") != rows:
            raise Lod0ShaderPlanError(f"{material}: constants differ across physical copies")
    out = []
    seen = set()
    for row in rows:
        name = str(row.get("name") or "")
        literal = row.get("literal")
        if not name or name in seen or not isinstance(literal, list) or len(literal) != 4:
            raise Lod0ShaderPlanError(f"{material}: malformed/duplicate constant {name!r}")
        seen.add(name)
        out.append({"name": name, "literal": [float(x) for x in literal]})
    return out


def _family_ops(character_doc: dict[str, Any], family: dict[str, Any]) -> dict[str, Any]:
    family_id = str(family.get("id") or "")
    if family_id in {"seal6-char-skin-hero-lit-v1", "seal6-char-skin-standard-lit-v1"}:
        shared = character_doc.get("sharedSkinSemantics")
        if not isinstance(shared, dict):
            raise Lod0ShaderPlanError("skin family lacks sharedSkinSemantics")
        return {"familyId": family_id, "familyLocal": {"normal": family.get("normal")}, "sharedSkin": shared}
    if family_id == "seal6-char-eye-cornea-lit-v1":
        return {
            "familyId": family_id,
            "fillDirectionVertexTransport": family.get("fillDirectionVertexTransport"),
            "surfaceNormal": family.get("surfaceNormal"),
            "highlightHelper": family.get("highlightHelper"),
            "alpha": family.get("alpha"),
            "rgb": family.get("rgb"),
        }
    raise Lod0ShaderPlanError(f"unsupported character family {family_id!r}")


def build(role: dict[str, Any], census: dict[str, Any], char_sem: dict[str, Any], cloth_sem: dict[str, Any]) -> dict[str, Any]:
    role_rows = _role_materials(role)
    native = _native_materials(census)
    char_families = _char_families(char_sem)
    cloth_family, cloth_materials = _cloth_family(cloth_sem)

    role_names = {str(r["material"]) for r in role_rows}
    if set(native) != role_names:
        raise Lod0ShaderPlanError("role/census Material set mismatch")
    if not cloth_materials < role_names:
        raise Lod0ShaderPlanError("cloth semantics Material set is not a seven-row subset of LOD0")

    out_rows = []
    lit_slots = preserved = constants_total = bindings_total = 0
    for rmat in role_rows:
        material = str(rmat["material"])
        nmat = native[material]
        techset = str(rmat.get("techniqueSet") or "")
        copies = nmat.get("copies") or []
        copy_techsets = {str(c.get("techniqueSet") or "") for c in copies}
        if nmat.get("techniqueSetIdenticalAcrossCopies") is not True or copy_techsets != {techset}:
            raise Lod0ShaderPlanError(f"{material}: native/role TechniqueSet closure drift")

        is_cloth = material in cloth_materials
        if is_cloth:
            if techset != CLOTH_TECHSET:
                raise Lod0ShaderPlanError(f"{material}: cloth Material has wrong TechniqueSet")
            family = cloth_family
            pixel_args = list(family.get("materialArguments") or [])
            vertex_args: list[str] = []
            exact_ops = {"familyId": family.get("id"), "cloth": family}
            family_source = "t6-retail-seal6-cloth-lit-semantics-v1"
        else:
            family = char_families.get(techset)
            if family is None:
                raise Lod0ShaderPlanError(f"{material}: no exact character family for TechniqueSet {techset!r}")
            pixel_args = list(family.get("materialArguments") or [])
            vertex_args = list(family.get("vertexMaterialArguments") or [])
            exact_ops = _family_ops(char_sem, family)
            family_source = "t6-retail-seal6-lit-semantics-v1"

        if len(pixel_args) != len(set(pixel_args)) or len(vertex_args) != len(set(vertex_args)):
            raise Lod0ShaderPlanError(f"{material}: duplicate exact shader ABI argument")
        if set(pixel_args) & set(vertex_args):
            raise Lod0ShaderPlanError(f"{material}: ABI argument appears in both stages")
        stage = {str(x): "pixel" for x in pixel_args}
        stage.update({str(x): "vertex" for x in vertex_args})

        slots = rmat.get("nativeSlots")
        if not isinstance(slots, list):
            raise Lod0ShaderPlanError(f"{material}: missing nativeSlots[]")
        provided_texture_args = set()
        out_slots = []
        for slot in slots:
            native_name = slot.get("nativeName")
            arg = str(native_name) if native_name is not None else ""
            referenced = bool(arg and arg in stage)
            if referenced:
                if arg in provided_texture_args:
                    raise Lod0ShaderPlanError(f"{material}: argument {arg!r} maps to multiple texture slots")
                provided_texture_args.add(arg)
                lit_slots += 1
            else:
                preserved += 1
            out_slots.append({
                **slot,
                "ordinaryLitBinding": {
                    "referenced": referenced,
                    "shaderArgument": arg if referenced else None,
                    "stage": stage.get(arg) if referenced else None,
                    "status": "referenced-by-exact-ordinary-lit-executable" if referenced else "preserved-native-slot-not-referenced-by-exact-ordinary-lit-executable",
                },
            })

        constants = _constant_rows(material, nmat)
        constants_total += len(constants)
        provided_constants = set()
        out_constants = []
        for row in constants:
            name = row["name"]
            if name not in stage:
                raise Lod0ShaderPlanError(f"{material}: native constant {name!r} absent from exact lit ABI")
            provided_constants.add(name)
            out_constants.append({
                **row,
                "ordinaryLitBinding": {
                    "referenced": True,
                    "shaderArgument": name,
                    "stage": stage[name],
                    "status": "referenced-by-exact-ordinary-lit-executable",
                },
            })

        required = set(stage)
        provided = provided_texture_args | provided_constants
        if provided != required:
            raise Lod0ShaderPlanError(
                f"{material}: exact ABI join mismatch missing={sorted(required-provided)} extra={sorted(provided-required)}"
            )
        bindings_total += len(required)

        out_rows.append({
            "material": material,
            "techniqueSet": techset,
            "shaderFamilyId": family.get("id"),
            "shaderFamilySource": family_source,
            "shaderIdentity": {
                "vertexDxbcSha256": family.get("vertexDxbcSha256"),
                "pixelDxbcSha256": family.get("pixelDxbcSha256"),
            },
            "activeRetailClientWholeMaterialOwnerResolved": bool(nmat.get("activeRetailClientOwnerResolved")),
            "physicalMaterialCopyCount": int(nmat.get("physicalCopyCount", len(copies))),
            "constantsInvariantAcrossPhysicalCopies": True,
            "ordinaryLitArguments": {"pixel": pixel_args, "vertex": vertex_args, "allRequiredArgumentsClosed": True},
            "nativeTextureSlots": out_slots,
            "nativeConstants": out_constants,
            "exactLitEquations": exact_ops,
            "pipelineState": family.get("pipelineState") if is_cloth else None,
            "blenderLowering": {
                "exactMaterialInputsClosed": True,
                "exactOrdinaryLitEquationsClosed": True,
                "materialLocalNodeLoweringPermitted": True,
                "globalRuntimeLightingInputsBound": False,
                "completeRetailPixelOutput": False,
            },
        })

    if lit_slots != EXPECTED_LIT_SLOTS:
        raise Lod0ShaderPlanError(f"ordinary-lit referenced slots {lit_slots} != {EXPECTED_LIT_SLOTS}")
    if preserved != EXPECTED_PRESERVED_NONLIT:
        raise Lod0ShaderPlanError(f"preserved non-lit slots {preserved} != {EXPECTED_PRESERVED_NONLIT}")
    if constants_total != EXPECTED_CONSTANTS:
        raise Lod0ShaderPlanError(f"native constants {constants_total} != {EXPECTED_CONSTANTS}")
    if bindings_total != EXPECTED_ARGUMENT_BINDINGS:
        raise Lod0ShaderPlanError(f"exact argument bindings {bindings_total} != {EXPECTED_ARGUMENT_BINDINGS}")

    return {
        "format": FORMAT,
        "summary": {
            "targetMaterials": EXPECTED_MATERIALS,
            "nativeTextureSlotsPreserved": EXPECTED_NATIVE_SLOTS,
            "ordinaryLitReferencedTextureSlots": lit_slots,
            "preservedNativeTextureSlotsNotReferencedByOrdinaryLit": preserved,
            "nativeMaterialConstants": constants_total,
            "exactVsPsMaterialArgumentBindings": bindings_total,
            "clothMaterials": 7,
            "characterSpecializedMaterials": 5,
            "allOrdinaryLitMaterialArgumentsClosed": True,
            "exactOrdinaryLitEquationsClosed": True,
            "headOrdinaryLitExecutableIndependentOfUnresolvedWholeMaterialOwner": True,
            "globalRuntimeLightingInputsBoundInBlender": False,
            "completeRetailPixelOutputInBlender": False,
        },
        "materials": out_rows,
        "runtimeBoundary": {
            "character": char_sem.get("backendPolicy", {}).get("globalResourcesStillRequiredForCompleteRetailOutput", []),
            "cloth": cloth_sem.get("runtimeAbi"),
        },
        "proofBoundary": (
            "All 12 LOD0 native texture slots/constants are joined only by exact OAT identity to SHA-locked ordinary-lit family ABIs. The seven cloth Materials use the separately closed cloth DXBC semantics with literal unit controls, not inferred defaults. Native slots absent from the ordinary-lit ABI remain preserved and unconnected. Runtime model-lighting/probe/SH/sun/fog/HDR values remain external, so complete retail pixel output is explicitly false."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role-plan", type=Path, required=True)
    ap.add_argument("--native-census", type=Path, required=True)
    ap.add_argument("--character-semantics", type=Path, default=Path("manifests/render/T6_RETAIL_SEAL6_LIT_SEMANTICS_V1.json"))
    ap.add_argument("--cloth-semantics", type=Path, default=Path("manifests/render/T6_RETAIL_SEAL6_CLOTH_LIT_SEMANTICS_V1.json"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = build(_load(a.role_plan), _load(a.native_census), _load(a.character_semantics), _load(a.cloth_semantics))
    out["inputs"] = {
        "rolePlanSha256": _sha(a.role_plan),
        "nativeCensusSha256": _sha(a.native_census),
        "characterSemanticsSha256": _sha(a.character_semantics),
        "clothSemanticsSha256": _sha(a.cloth_semantics),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
