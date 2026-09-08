#!/usr/bin/env python3
"""Build the exact runtime-global ABI contract for SEAL6 ordinary-lit shaders.

Inputs are the previously validated SEAL6 DXBC->SPIR-V/RDEF artifact and the
committed exact shader semantics.  Material-owned texture/constants are removed
using the exact family Material argument lists.  Everything else actually read
by the VS/PS becomes a required runtime-global input.

This is an ABI contract, not a source of values.  It does not invent lighting,
camera, fog, reflection, SH, HDR, world-matrix or per-object data.  A Blender or
engine provider can satisfy this contract with exact live values or an exact
bake; until then complete retail pixel output remains false.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-seal6-runtime-global-contract-v1"
IR_FORMAT = "t6-seal6-exact-lit-shader-ir-v1"
ABI_FORMAT = "t6-seal6-lit-shader-abi-manifest-v1"
SEMANTICS_FORMAT = "t6-retail-seal6-lit-semantics-v1"

PROGRAMS = {
    "skin_vs": "b1bacc64d083fb8b2a60ab28e346e14bb6f0dd9cbf21930480f7dc647f42dabe.vs",
    "hero_ps": "dbad6541db6ffa00308d732ab2c07777dca960465ebcc9710823ab68b16c78ec.ps",
    "standard_ps": "785e8ef0f0936016ce9dd18f67cdcad1c15bdbed58c174e93049df3f46b79b98.ps",
    "cornea_vs": "db872ac90083aea7bd1cc0c53a3edd6f5c9bab2ece1a6616d86876169bb72cf5.vs",
    "cornea_ps": "6d4913fd080a783f1c08e78124884c491725c5e69dfe93846bc27a2a78ada298.ps",
}
FAMILY_PROGRAMS = {
    "seal6-char-skin-hero-lit-v1": ("skin_vs", "hero_ps"),
    "seal6-char-skin-standard-lit-v1": ("skin_vs", "standard_ps"),
    "seal6-char-eye-cornea-lit-v1": ("cornea_vs", "cornea_ps"),
}

EXPECTED_CONSTANTS = {
    "skin_vs": {
        ("b0", "fogColor"), ("b0", "fogConsts"), ("b0", "fogConsts2"),
        ("b0", "sunFogDir"), ("b0", "sunFogColor"), ("b0", "sunFog"),
        ("b0", "viewProjectionMatrix"),
        ("b3", "worldMatrix"), ("b3", "gridLightingCoordsAndVis"),
        ("b3", "gridLightingSH0"), ("b3", "gridLightingSH1"), ("b3", "gridLightingSH2"),
        ("b3", "reflectionLightingSH0"), ("b3", "reflectionLightingSH1"), ("b3", "reflectionLightingSH2"),
    },
    "hero_ps": {
        ("b0", "sunPosition"), ("b0", "sunDiffuse"), ("b0", "hdrControl0"),
        ("b0", "lightingLookupScale"),
        ("b0", "heroLightingR"), ("b0", "heroLightingG"), ("b0", "heroLightingB"),
        ("b1", "scriptVector0"),
    },
    "standard_ps": {
        ("b0", "sunPosition"), ("b0", "sunDiffuse"), ("b0", "hdrControl0"),
        ("b0", "lightingLookupScale"),
        ("b0", "heroLightingR"), ("b0", "heroLightingG"), ("b0", "heroLightingB"),
        ("b1", "scriptVector0"),
    },
    "cornea_vs": {
        ("b0", "fogColor"), ("b0", "fogConsts"), ("b0", "fogConsts2"),
        ("b0", "sunFogDir"), ("b0", "sunFogColor"), ("b0", "sunFog"),
        ("b0", "viewProjectionMatrix"), ("b0", "inverseViewMatrix"),
        ("b3", "worldMatrix"), ("b3", "gridLightingCoordsAndVis"),
        ("b3", "gridLightingSH0"), ("b3", "gridLightingSH1"), ("b3", "gridLightingSH2"),
        ("b3", "reflectionLightingSH0"), ("b3", "reflectionLightingSH1"), ("b3", "reflectionLightingSH2"),
    },
    "cornea_ps": {
        ("b0", "sunPosition"), ("b0", "sunDiffuse"), ("b0", "hdrControl0"),
        ("b0", "lightingLookupScale"),
    },
}
EXPECTED_TEXTURES = {
    "skin_vs": set(),
    "hero_ps": {("t13", "modelLightingSampler", "texture3d"), ("t15", "reflectionProbeSampler", "texturecube")},
    "standard_ps": {("t13", "modelLightingSampler", "texture3d"), ("t15", "reflectionProbeSampler", "texturecube")},
    "cornea_vs": set(),
    "cornea_ps": {("t13", "modelLightingSampler", "texture3d")},
}
EXPECTED_SAMPLERS = {
    "skin_vs": set(),
    "hero_ps": {("s13", "modelLightingSampler"), ("s15", "reflectionProbeSampler")},
    "standard_ps": {("s13", "modelLightingSampler"), ("s15", "reflectionProbeSampler")},
    "cornea_vs": set(),
    "cornea_ps": {("s13", "modelLightingSampler")},
}

# Exact semantic role classification.  This does not add inputs; it labels only
# names already proven live by RDEF+translated instruction use.
ROLES = {
    "fogColor": "fog",
    "fogConsts": "fog",
    "fogConsts2": "fog",
    "sunFogDir": "fog",
    "sunFogColor": "fog",
    "sunFog": "fog",
    "viewProjectionMatrix": "camera-transform",
    "inverseViewMatrix": "camera-transform",
    "worldMatrix": "object-transform",
    "gridLightingCoordsAndVis": "model-lighting-grid",
    "gridLightingSH0": "lighting-sh",
    "gridLightingSH1": "lighting-sh",
    "gridLightingSH2": "lighting-sh",
    "reflectionLightingSH0": "reflection-lighting-sh",
    "reflectionLightingSH1": "reflection-lighting-sh",
    "reflectionLightingSH2": "reflection-lighting-sh",
    "sunPosition": "sun-lighting",
    "sunDiffuse": "sun-lighting",
    "hdrControl0": "hdr-output",
    "lightingLookupScale": "model-lighting-grid",
    "heroLightingR": "hero-lighting-transform",
    "heroLightingG": "hero-lighting-transform",
    "heroLightingB": "hero-lighting-transform",
    "scriptVector0": "per-object-character-control",
    "modelLightingSampler": "model-lighting-volume",
    "reflectionProbeSampler": "reflection-probe",
}


class Seal6GlobalContractError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _material_args(semantics: dict[str, Any]) -> dict[str, set[str]]:
    out = {}
    for row in semantics.get("families", []):
        fid = str(row.get("id") or "")
        if fid not in FAMILY_PROGRAMS:
            continue
        out[fid] = set(str(x) for x in row.get("materialArguments", [])) | set(
            str(x) for x in row.get("vertexMaterialArguments", [])
        )
    if set(out) != set(FAMILY_PROGRAMS):
        raise Seal6GlobalContractError(f"semantic family set drift: {sorted(out)}")
    return out


def _program_rows(ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {str(row.get("stem") or ""): row for row in ir.get("programs", [])}
    expected = set(PROGRAMS.values())
    if set(rows) != expected:
        raise Seal6GlobalContractError(f"IR program set drift: {sorted(rows)}")
    return rows


def _rdef(path: Path) -> dict[str, Any]:
    d = _load(path)
    if d.get("format") != "t6-dxbc-rdef-abi-v1":
        raise Seal6GlobalContractError(f"unexpected RDEF format in {path}")
    return d


def _constant_rows(rdef: dict[str, Any], material_names: set[str]) -> list[dict[str, Any]]:
    used = rdef.get("translatedSpirv", {}).get("usedConstants", [])
    if not isinstance(used, list):
        raise Seal6GlobalContractError("RDEF lacks translated usedConstants[]")
    unique = {}
    for row in used:
        name = str(row.get("variable") or "")
        if not name or name in material_names:
            continue
        key = (str(row.get("register") or ""), name)
        unique.setdefault(key, {
            "kind": "constant",
            "name": name,
            "constantBuffer": row.get("constantBuffer"),
            "register": row.get("register"),
            "variableStartOffset": row.get("variableStartOffset"),
            "variableSize": row.get("variableSize"),
            "usedVec4Slots": [],
            "role": ROLES.get(name),
        })
        unique[key]["usedVec4Slots"].append(int(row["vec4Slot"]))
    result = []
    for key in sorted(unique):
        item = unique[key]
        item["usedVec4Slots"] = sorted(set(item["usedVec4Slots"]))
        if not item["role"]:
            raise Seal6GlobalContractError(f"unclassified runtime constant {item['name']!r}")
        result.append(item)
    return result


def _resource_rows(rdef: dict[str, Any], material_names: set[str]) -> tuple[list[dict], list[dict]]:
    textures, samplers = [], []
    for row in rdef.get("resources", []):
        name = str(row.get("name") or "")
        if not name or name in material_names or row.get("resourceType") == "cbuffer":
            continue
        typ = row.get("resourceType")
        if typ == "texture":
            item = {
                "kind": "texture",
                "name": name,
                "register": row.get("register"),
                "dimension": row.get("dimension"),
                "role": ROLES.get(name),
            }
            textures.append(item)
        elif typ == "sampler":
            item = {
                "kind": "sampler",
                "name": name,
                "register": row.get("register"),
                "role": ROLES.get(name),
            }
            samplers.append(item)
        else:
            raise Seal6GlobalContractError(f"unhandled runtime resource {name!r} type={typ!r}")
    for item in textures + samplers:
        if not item["role"]:
            raise Seal6GlobalContractError(f"unclassified runtime resource {item['name']!r}")
    return sorted(textures, key=lambda x: (x["register"], x["name"])), sorted(samplers, key=lambda x: (x["register"], x["name"]))


def build(ir: dict[str, Any], abi: dict[str, Any], semantics: dict[str, Any], rdef_dir: Path) -> dict[str, Any]:
    if ir.get("format") != IR_FORMAT:
        raise Seal6GlobalContractError(f"unexpected IR format {ir.get('format')!r}")
    if abi.get("format") != ABI_FORMAT:
        raise Seal6GlobalContractError(f"unexpected ABI format {abi.get('format')!r}")
    if semantics.get("format") != SEMANTICS_FORMAT:
        raise Seal6GlobalContractError(f"unexpected semantics format {semantics.get('format')!r}")
    if abi.get("summary", {}).get("allMaterialArgumentsClosedToRdef") is not True:
        raise Seal6GlobalContractError("Material argument ABI is not closed")
    if semantics.get("summary", {}).get("exactMaterialArgumentAbiClosed") is not True:
        raise Seal6GlobalContractError("semantic manifest does not retain exact Material ABI closure")

    _program_rows(ir)
    material_by_family = _material_args(semantics)
    # A program shared by multiple families must see the union of their exact
    # material arguments when classifying RDEF names.  This matters for skin VS.
    material_by_program: dict[str, set[str]] = {key: set() for key in PROGRAMS}
    for family, (vs_key, ps_key) in FAMILY_PROGRAMS.items():
        material_by_program[vs_key] |= material_by_family[family]
        material_by_program[ps_key] |= material_by_family[family]

    programs = []
    for key, stem in PROGRAMS.items():
        path = rdef_dir / f"{stem}.json"
        if not path.is_file():
            raise Seal6GlobalContractError(f"missing exact RDEF {path}")
        d = _rdef(path)
        constants = _constant_rows(d, material_by_program[key])
        textures, samplers = _resource_rows(d, material_by_program[key])
        const_sig = {(x["register"], x["name"]) for x in constants}
        tex_sig = {(x["register"], x["name"], x["dimension"]) for x in textures}
        sampler_sig = {(x["register"], x["name"]) for x in samplers}
        if const_sig != EXPECTED_CONSTANTS[key]:
            raise Seal6GlobalContractError(f"{key}: runtime constant ABI drift: {sorted(const_sig)}")
        if tex_sig != EXPECTED_TEXTURES[key]:
            raise Seal6GlobalContractError(f"{key}: runtime texture ABI drift: {sorted(tex_sig)}")
        if sampler_sig != EXPECTED_SAMPLERS[key]:
            raise Seal6GlobalContractError(f"{key}: runtime sampler ABI drift: {sorted(sampler_sig)}")
        programs.append({
            "programKey": key,
            "stem": stem,
            "stage": "vertex" if stem.endswith(".vs") else "pixel",
            "dxbcSha256": d.get("source", {}).get("sha256"),
            "runtimeConstants": constants,
            "runtimeTextures": textures,
            "runtimeSamplers": samplers,
            "materialArgumentsExcludedFromRuntimeContract": sorted(material_by_program[key]),
        })

    by_key = {row["programKey"]: row for row in programs}
    families = []
    for family_id, (vs_key, ps_key) in FAMILY_PROGRAMS.items():
        required = []
        seen = set()
        for stage_row in (by_key[vs_key], by_key[ps_key]):
            for group in ("runtimeConstants", "runtimeTextures", "runtimeSamplers"):
                for item in stage_row[group]:
                    sig = (item["kind"], item["name"], item.get("register"))
                    if sig in seen:
                        continue
                    seen.add(sig)
                    required.append({**item, "stages": [stage_row["stage"]]})
        # Merge same name/register used in both stages, if any.
        merged = {}
        for item in required:
            sig = (item["kind"], item["name"], item.get("register"))
            if sig not in merged:
                merged[sig] = item
            else:
                merged[sig]["stages"] = sorted(set(merged[sig]["stages"] + item["stages"]))
        families.append({
            "shaderFamilyId": family_id,
            "vertexProgramKey": vs_key,
            "pixelProgramKey": ps_key,
            "requiredRuntimeGlobals": [merged[k] for k in sorted(merged)],
            "runtimeValuesBound": False,
            "exactBakeAccepted": True,
            "completeRetailPixelOutput": False,
        })

    unique_constant_names = sorted({x["name"] for p in programs for x in p["runtimeConstants"]})
    unique_texture_names = sorted({x["name"] for p in programs for x in p["runtimeTextures"]})
    unique_sampler_names = sorted({x["name"] for p in programs for x in p["runtimeSamplers"]})
    return {
        "format": FORMAT,
        "summary": {
            "exactPrograms": 5,
            "shaderFamilies": 3,
            "uniqueRuntimeConstantVariables": len(unique_constant_names),
            "uniqueRuntimeTextures": len(unique_texture_names),
            "uniqueRuntimeSamplers": len(unique_sampler_names),
            "runtimeValuesBound": False,
            "exactBakeAccepted": True,
            "completeRetailPixelOutputInBlender": False,
        },
        "uniqueRuntimeConstantNames": unique_constant_names,
        "uniqueRuntimeTextureNames": unique_texture_names,
        "uniqueRuntimeSamplerNames": unique_sampler_names,
        "programs": programs,
        "families": families,
        "providerPolicy": {
            "accepted": [
                "exact live T6-equivalent runtime value/resource provider",
                "exact source-derived bake preserving the shader-visible value/resource at the evaluated sample",
            ],
            "forbidden": [
                "invent default lighting constants",
                "replace modelLightingSampler with generic Blender ambient light",
                "replace reflectionProbeSampler with generic Principled environment reflection",
                "invent SH coefficients",
                "invent fog or HDR values",
                "treat Blender camera/world matrices as T6-equivalent without a coordinate/matrix proof",
            ],
        },
        "proofBoundary": (
            "Runtime-global membership comes only from exact live RDEF resources and translated used-constant slots "
            "after removing exact Material-owned arguments. Register, cbuffer, texture dimension and stage ownership "
            "are preserved. This contract does not provide runtime values and therefore does not close final retail output."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ir-manifest", type=Path, required=True)
    ap.add_argument("--abi-manifest", type=Path, required=True)
    ap.add_argument("--semantics", type=Path, default=Path("manifests/render/T6_RETAIL_SEAL6_LIT_SEMANTICS_V1.json"))
    ap.add_argument("--rdef-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    ir, abi, semantics = _load(args.ir_manifest), _load(args.abi_manifest), _load(args.semantics)
    result = build(ir, abi, semantics, args.rdef_dir)
    result["inputs"] = {
        "irManifestSha256": _sha(args.ir_manifest),
        "abiManifestSha256": _sha(args.abi_manifest),
        "semanticsSha256": _sha(args.semantics),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
