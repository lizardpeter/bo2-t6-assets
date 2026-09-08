#!/usr/bin/env python3
"""Normalize the three exact SEAL6 ordinary-lit shader families.

This is intentionally a SHA-locked semantic adapter, not a pattern recognizer.
It accepts only the exact validated IR/ABI produced by the pinned SEAL6 shader
closure and only the exact SPIRV-Cross GLSL hashes below.  The emitted equations
are direct finite-value normalization of those translated instruction streams.
No generic PBR interpretation, filename inference, or runtime duplicate winner
is introduced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

FORMAT = "t6-retail-seal6-lit-semantics-v1"
IR_FORMAT = "t6-seal6-exact-lit-shader-ir-v1"
ABI_FORMAT = "t6-seal6-lit-shader-abi-manifest-v1"

RUN = 34179663551
ARTIFACT = 10038442629
ARTIFACT_DIGEST = "sha256:1cb9304d7b4471e215a5fe3d4b6ee211c074914e7512ed1b62878c3bcc153976"
SOURCE_NATIVE_RUN = 34178602640
SOURCE_NATIVE_ARTIFACT = 10038097215

SHADERS = {
    "skin_vs": {
        "stem": "b1bacc64d083fb8b2a60ab28e346e14bb6f0dd9cbf21930480f7dc647f42dabe.vs",
        "dxbc": "b1bacc64d083fb8b2a60ab28e346e14bb6f0dd9cbf21930480f7dc647f42dabe",
        "glsl": "196464c7600a52c60d99c6da515d4a84020c29000992ab68f96a6b73d5f90613",
    },
    "hero_ps": {
        "stem": "dbad6541db6ffa00308d732ab2c07777dca960465ebcc9710823ab68b16c78ec.ps",
        "dxbc": "dbad6541db6ffa00308d732ab2c07777dca960465ebcc9710823ab68b16c78ec",
        "glsl": "b17cfb08bf81972c607a1847264ece9a31db8fcc832a70e71885b5a2436ecfbc",
    },
    "standard_ps": {
        "stem": "785e8ef0f0936016ce9dd18f67cdcad1c15bdbed58c174e93049df3f46b79b98.ps",
        "dxbc": "785e8ef0f0936016ce9dd18f67cdcad1c15bdbed58c174e93049df3f46b79b98",
        "glsl": "94ca4f31a5ccf0ee2acb6f416afe41c7b5e6ba60f1227d0d8c4ee1663a744168",
    },
    "cornea_vs": {
        "stem": "db872ac90083aea7bd1cc0c53a3edd6f5c9bab2ece1a6616d86876169bb72cf5.vs",
        "dxbc": "db872ac90083aea7bd1cc0c53a3edd6f5c9bab2ece1a6616d86876169bb72cf5",
        "glsl": "bc4c4c40a186c84f51f97d220980d93e5c0810b250bde119c23eb96a12b60d58",
    },
    "cornea_ps": {
        "stem": "6d4913fd080a783f1c08e78124884c491725c5e69dfe93846bc27a2a78ada298.ps",
        "dxbc": "6d4913fd080a783f1c08e78124884c491725c5e69dfe93846bc27a2a78ada298",
        "glsl": "546f5a793bf64861e98e20a9e7e1fe3b862bef58782f1e450325ac7d3b0a8b82",
    },
}

FAMILIES = {
    "mc_sw4_3d_char_skin_hero_9949fq1j": (SHADERS["skin_vs"]["dxbc"], SHADERS["hero_ps"]["dxbc"]),
    "mc_sw4_3d_char_skin_j92387z3": (SHADERS["skin_vs"]["dxbc"], SHADERS["standard_ps"]["dxbc"]),
    "mc_sw4_3d_char_eye_cornea_2eww29wu": (SHADERS["cornea_vs"]["dxbc"], SHADERS["cornea_ps"]["dxbc"]),
}

EXPECTED_ARGUMENTS = {
    "mc_sw4_3d_char_skin_hero_9949fq1j": [
        "SpecularAndGloss", "Normal_Map", "Normal_Detail_Map", "Diffuse_Map",
        "Reflection_Amount", "Normal_Detail_Scale", "Specular_Amount", "Diffuse_Normal_Height",
    ],
    "mc_sw4_3d_char_skin_j92387z3": [
        "SpecularAndGloss", "Normal_Map", "Diffuse_Map",
        "Reflection_Amount", "Diffuse_Normal_Height_Facing", "Specular_Amount",
    ],
    "mc_sw4_3d_char_eye_cornea_2eww29wu": [
        "Mask", "Surface_Normal_Map", "Hightlight_1_Size", "Highlight_1_Sharpness",
        "Highlight_1_Brightness", "Highlight_2_Size", "Highlight_2_Sharpness",
        "Highlight_2_Brightness", "OverallBrightness",
    ],
}

# Exact translated operations used as a fail-closed guard against accidentally
# normalizing a different compiler output under the same friendly family label.
REQUIRED_FRAGMENTS = {
    "hero_ps": [
        "v5 * cb2_0._m0[5u].yy",
        "texture(sampler2D(t1, s1)",
        "fma(r3.xy, vec2(4.01574802398681640625), r2.xy)",
        "r2.xy * cb2_0._m0[5u].ww",
        "texture(sampler2D(t3, s3)",
        "cb1_0._m0[23u].x",
        "textureLod(samplerCube(t15, s15)",
        "dot(r0, cb0_0._m0[114u])",
        "sqrt(r0.xyz)",
    ],
    "standard_ps": [
        "texture(sampler2D(t0, s1)",
        "r4.xy * cb2_0._m0[5u].zz",
        "texture(sampler2D(t2, s2)",
        "cb1_0._m0[23u].x",
        "textureLod(samplerCube(t15, s15)",
        "v2.xyz * v2.xyz",
        "dot(r0, cb0_0._m0[114u])",
        "sqrt(r0.xyz)",
    ],
    "cornea_vs": [
        "dot(cb2_0._m0[5u].xyz, cb0_0._m0[40u].xyz)",
        "o7 = -r0",
        "dot(cb2_0._m0[7u].xyz, cb0_0._m0[40u].xyz)",
        "o8 = -r0",
    ],
    "cornea_ps": [
        "fma(r3.xy, vec2(4.01574802398681640625), vec2(-2.01574802398681640625))",
        "fma(r0.x, 0.180000007152557373046875, 0.7200000286102294921875)",
        "r0.y += 0.20000000298023223876953125",
        "r1.x * 5.0",
        "r0.x + (-0.0500000007450580596923828125)",
        "texture(sampler2D(t1, s1)",
        "o0.w = sqrt(r0.x)",
        "cb2_0._m0[8u].z * cb2_0._m0[8u].z",
        "sqrt(r0.xyz)",
    ],
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def saturate(x: float) -> float:
    return min(max(x, 0.0), 1.0)


def smooth01(x: float) -> float:
    t = saturate(x)
    return t * t * (3.0 - 2.0 * t)


def cornea_sharp_window(power_term: float, sharpness: float) -> float:
    """Finite-value normalization of the exact 0.72 +/- 0.18*(1-sharpness) window."""
    a = 1.0 - sharpness
    lo = 0.72 - 0.18 * a
    hi = 0.72 + 0.18 * a
    return smooth01((power_term - lo) * (1.0 / (hi - lo)))


def cornea_side_gate(ndot_neg_fill: float) -> float:
    return smooth01((ndot_neg_fill + 0.2) * 5.0)


def _read_glsl(glsl_dir: Path, key: str) -> str:
    spec = SHADERS[key]
    path = glsl_dir / f"{spec['stem']}.glsl"
    if not path.is_file():
        raise ValueError(f"missing exact translated GLSL {path}")
    data = path.read_bytes()
    actual = sha256(data)
    if actual != spec["glsl"]:
        raise ValueError(f"GLSL SHA mismatch for {path.name}: {actual} != {spec['glsl']}")
    text = data.decode("utf-8")
    for fragment in REQUIRED_FRAGMENTS.get(key, []):
        if fragment not in text:
            raise ValueError(f"{path.name}: required translated operation missing: {fragment!r}")
    return text


def _validate_ir(ir: dict[str, Any]) -> None:
    if ir.get("format") != IR_FORMAT:
        raise ValueError(f"unexpected IR format {ir.get('format')!r}")
    src = ir.get("sourceArtifact", {})
    if src.get("id") != SOURCE_NATIVE_ARTIFACT:
        raise ValueError("IR source native artifact id drift")
    rows = {row["stem"]: row for row in ir.get("programs", [])}
    if set(rows) != {s["stem"] for s in SHADERS.values()}:
        raise ValueError(f"unexpected exact IR program set: {sorted(rows)}")
    for spec in SHADERS.values():
        row = rows[spec["stem"]]
        if row["dxbc"]["sha256"] != spec["dxbc"] or row["glsl"]["sha256"] != spec["glsl"]:
            raise ValueError(f"IR identity drift for {spec['stem']}")


def _validate_abi(abi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if abi.get("format") != ABI_FORMAT:
        raise ValueError(f"unexpected ABI format {abi.get('format')!r}")
    if not abi.get("summary", {}).get("allMaterialArgumentsClosedToRdef"):
        raise ValueError("ABI does not close all Material arguments")
    families = {row["techniqueSet"]: row for row in abi.get("families", [])}
    if set(families) != set(FAMILIES):
        raise ValueError(f"ABI TechniqueSet set drift: {sorted(families)}")
    for name, (vs, ps) in FAMILIES.items():
        row = families[name]
        if (row["vertexShaderSha256"], row["pixelShaderSha256"]) != (vs, ps):
            raise ValueError(f"ABI executable pair drift for {name}")
        args = list(row.get("pixelMaterialArguments", []))
        if args != EXPECTED_ARGUMENTS[name]:
            raise ValueError(f"ABI pixel Material argument drift for {name}: {args}")
        if name == "mc_sw4_3d_char_eye_cornea_2eww29wu":
            resources = {b["argument"]: b for b in row["pixelArgumentBindings"]}
            if "SpecularAndGloss" in resources or "Reflection_Amount" in resources:
                raise ValueError("cornea unexpectedly acquired generic skin specular/reflection inputs")
    return families


def build(ir: dict[str, Any], abi: dict[str, Any], glsl_dir: Path) -> dict[str, Any]:
    _validate_ir(ir)
    families = _validate_abi(abi)
    for key in ("skin_vs", "hero_ps", "standard_ps", "cornea_vs", "cornea_ps"):
        _read_glsl(glsl_dir, key)

    skin_common = {
        "viewAndSun": {
            "V": "normalize(worldPosition)",
            "L": "sunPosition.xyz",
            "H": "normalize(L - V)",
        },
        "tangentBasis": {
            "Nbase": "normalize(decoded/transformed T6 vertex normal)",
            "T": "decoded/transformed T6 tangent",
            "B": "tangentHandedness * cross(Nbase, T)",
            "normalXYDecode": "sample.rg * 4.01574802398681640625 - 2.01574802398681640625",
        },
        "directSpecular": {
            "NH": "saturate(dot(Nspec,H))",
            "HL": "saturate(dot(H,L))",
            "NL": "saturate(dot(Nspec,L))",
            "P": "exp2(13.0 * SpecularAndGloss.a)",
            "shape": "exp2(log2(NH) * P) * (0.125 * P + 0.25)",
            "denominator": "1.0099999904632568359375 + saturate(SpecularAndGloss.a + 0.545000016689300537109375) * (HL*HL - 1.0)",
            "lobe": "shape * NL / denominator",
            "characterFactor": "1.0 - saturate(scriptVector0.x)",
            "C": "characterFactor * SpecularAndGloss.rgb",
            "base": "C*C + (1.0 - C*C) * exp2(-10.0 * HL)",
            "rgb": "base * lobe * Specular_Amount * (gridLightingCoordsAndVis.w * sunDiffuse.rgb)",
        },
        "reflection": {
            "R": "V - 2.0*Nspec*dot(Nspec,V)",
            "g": "exp2(-9.27999973297119140625 * saturate(dot(Nspec,-V)))",
            "lod": "4.0 - 4.0 * SpecularAndGloss.a",
            "probeRgb": "sampleCubeLod(reflectionProbeSampler,R,lod).rgb / (sample.a + 9.9999999747524270787835121154785e-7)",
            "p0": "1.0416667461395263671875 * SpecularAndGloss.a",
            "p1": "0.4749999940395355224609375 * SpecularAndGloss.a",
            "p2": "0.01822919957339763641357421875 * SpecularAndGloss.a - 0.015625",
            "p3": "0.25 * SpecularAndGloss.a + 0.75",
            "q": "p0 * min(g,p1) + p2",
            "F": "saturate((C*C) * (p3-q) + q)",
            "rgb": "probeRgb * F * (vertexColor.a * Reflection_Amount) * reflectionLightingRatio",
        },
        "diffuse": {
            "encoded": "Diffuse_Map.rgb * (vertexColor.rgb * vertexColor.rgb)",
            "linearLike": "encoded * encoded",
            "lookupAxisMax": "m = max(abs(Ndiff.x),abs(Ndiff.y),abs(Ndiff.z))",
            "lookupUVW": "Ndiff * lightingLookupScale.xyz / m + gridLightingCoordsAndVis.xyz",
            "modelLighting": "sample3D(modelLightingSampler,lookupUVW).rgb^2",
            "lighting": "32.0 * vertexColor.a * modelLighting + saturate(dot(L,Ndiff)) * (gridLightingCoordsAndVis.w * sunDiffuse.rgb)",
            "rgb": "linearLike * lighting",
            "note": "The vertex-color RGB is explicitly squared before multiplication by Diffuse_Map and the product is then squared again; do not collapse this to (Diffuse*vertexColor)^2.",
        },
        "heroTransformFogOutput": {
            "preHero": "directSpecular.rgb + reflection.rgb + diffuse.rgb",
            "heroRgb": "vec3(dot(vec4(preHero,1),heroLightingR), dot(vec4(preHero,1),heroLightingG), dot(vec4(preHero,1),heroLightingB))",
            "foggedRgb": "fogColor + fogVisibility * (heroRgb - fogColor)",
            "outRgb": "sqrt(foggedRgb * hdrControl0.x)",
            "outAlpha": "1.0",
        },
    }

    hero = families["mc_sw4_3d_char_skin_hero_9949fq1j"]
    standard = families["mc_sw4_3d_char_skin_j92387z3"]
    cornea = families["mc_sw4_3d_char_eye_cornea_2eww29wu"]

    return {
        "format": FORMAT,
        "proofBoundary": (
            "Direct finite-value semantic normalization of the five exact SHA-pinned SEAL6 ordinary-lit DXBC programs after vkd3d DXBC->SPIR-V translation, spirv-val validation, SPIRV-Cross pretty-printing, and RDEF argument closure. Family membership is exact VS+PS SHA only. No metallic/roughness/PBR substitution, filename-based role inference, or retail-client duplicate-precedence claim is made."
        ),
        "proof": {
            "shaderIrRun": RUN,
            "shaderIrArtifactId": ARTIFACT,
            "shaderIrArtifactDigest": ARTIFACT_DIGEST,
            "sourceNativeShaderRun": SOURCE_NATIVE_RUN,
            "sourceNativeShaderArtifactId": SOURCE_NATIVE_ARTIFACT,
            "glslSha256": {key: spec["glsl"] for key, spec in SHADERS.items()},
        },
        "summary": {
            "families": 3,
            "uniqueVertexPrograms": 2,
            "uniquePixelPrograms": 3,
            "exactMaterialArgumentAbiClosed": True,
            "heroExecutablePairIndependentOfUnresolvedMaterialOwner": True,
            "completeRetailPixelOutputInBlender": False,
        },
        "sharedSkinSemantics": skin_common,
        "families": [
            {
                "id": "seal6-char-skin-hero-lit-v1",
                "techniqueSet": hero["techniqueSet"],
                "vertexDxbcSha256": hero["vertexShaderSha256"],
                "pixelDxbcSha256": hero["pixelShaderSha256"],
                "materialArguments": hero["pixelMaterialArguments"],
                "normal": {
                    "baseXY": "Normal_Map.rg * 4.01574802398681640625 - 2.01574802398681640625",
                    "detailUV": "UV0 * Normal_Detail_Scale",
                    "combinedXY": "baseXY + (Normal_Detail_Map(detailUV).rg * 4.01574802398681640625 - 2.01574802398681640625)",
                    "Nspec": "normalize(Nbase + combinedXY.x*T + combinedXY.y*B)",
                    "Ndiff": "normalize(Nbase + (combinedXY*Diffuse_Normal_Height).x*T + (combinedXY*Diffuse_Normal_Height).y*B)",
                },
                "inheritsExactSharedSkinSemantics": True,
                "activeRetailClientWholeMaterialOwnerResolved": False,
                "ordinaryLitExecutablePairInvariantAcrossPhysicalHeadParents": True,
            },
            {
                "id": "seal6-char-skin-standard-lit-v1",
                "techniqueSet": standard["techniqueSet"],
                "vertexDxbcSha256": standard["vertexShaderSha256"],
                "pixelDxbcSha256": standard["pixelShaderSha256"],
                "materialArguments": standard["pixelMaterialArguments"],
                "normal": {
                    "normalXY": "Normal_Map.rg * 4.01574802398681640625 - 2.01574802398681640625",
                    "Nspec": "normalize(Nbase + normalXY.x*T + normalXY.y*B)",
                    "Ndiff": "normalize(Nbase + (normalXY*Diffuse_Normal_Height_Facing).x*T + (normalXY*Diffuse_Normal_Height_Facing).y*B)",
                },
                "inheritsExactSharedSkinSemantics": True,
            },
            {
                "id": "seal6-char-eye-cornea-lit-v1",
                "techniqueSet": cornea["techniqueSet"],
                "vertexDxbcSha256": cornea["vertexShaderSha256"],
                "pixelDxbcSha256": cornea["pixelShaderSha256"],
                "materialArguments": cornea["pixelMaterialArguments"],
                "fillDirectionVertexTransport": {
                    "F1": "-normalize(mat3(inverseViewMatrix) * Fill_Direction)",
                    "F2": "-normalize(mat3(inverseViewMatrix) * Fill_Direction2)",
                    "note": "This is the exact translated row-dot operation using inverseViewMatrix rows 40..42; F1/F2 denote the emitted negative normalized varyings."
                },
                "surfaceNormal": {
                    "normalXY": "Surface_Normal_Map.rg * 4.01574802398681640625 - 2.01574802398681640625",
                    "Nsurface": "normalize(Nbase + normalXY.x*T + normalXY.y*B)",
                },
                "highlightHelper": {
                    "Vcamera": "normalize(-worldPosition)",
                    "H": "normalize(Vcamera - F)",
                    "powerTerm": "exp2(log2(saturate(dot(Nsurface,H))) / max(Size,9.9999997473787516355514526367188e-6))",
                    "a": "1.0 - Sharpness",
                    "lower": "0.7200000286102294921875 - 0.180000007152557373046875*a",
                    "upper": "0.7200000286102294921875 + 0.180000007152557373046875*a",
                    "windowT": "saturate((powerTerm-lower) * (1.0/(upper-lower)))",
                    "window": "windowT*windowT*(3.0-2.0*windowT)",
                    "sideT": "saturate((dot(Nsurface,-F)+0.20000000298023223876953125)*5.0)",
                    "side": "sideT*sideT*(3.0-2.0*sideT)",
                    "lobe": "window * side * Brightness",
                },
                "alpha": {
                    "lobe1": "highlightHelper(F1,Hightlight_1_Size,Highlight_1_Sharpness,Highlight_1_Brightness)",
                    "lobe2": "highlightHelper(F2,Highlight_2_Size,Highlight_2_Sharpness,Highlight_2_Brightness)",
                    "gate": "Mask.r * saturate(lobe1 + lobe2 - 0.0500000007450580596923828125)",
                    "outAlpha": "sqrt(gate)",
                },
                "rgb": {
                    "lightingNormal": "Nbase (the decoded/transformed vertex normal; Surface_Normal_Map perturbs highlight alpha only in this PS)",
                    "lookupAxisMax": "m = max(abs(Nbase.x),abs(Nbase.y),abs(Nbase.z))",
                    "lookupUVW": "Nbase * lightingLookupScale.xyz / m + gridLightingCoordsAndVis.xyz",
                    "modelLighting": "32.0 * sample3D(modelLightingSampler,lookupUVW).rgb^2",
                    "sunLighting": "saturate(dot(sunPosition.xyz,Nbase)) * (gridLightingCoordsAndVis.w * sunDiffuse.rgb)",
                    "brightness": "OverallBrightness * OverallBrightness",
                    "litRgb": "brightness * (modelLighting + sunLighting)",
                    "foggedRgb": "fogColor + fogVisibility*(litRgb-fogColor)",
                    "outRgb": "sqrt(foggedRgb * hdrControl0.x)",
                },
                "forbiddenInferences": ["specular texture", "reflection probe", "generic cornea roughness/IOR", "Principled alpha formula substitution"],
            },
        ],
        "backendPolicy": {
            "familySelection": "exact VS+PS DXBC SHA pair only",
            "materialLocalExactNodesNowPossible": True,
            "globalResourcesStillRequiredForCompleteRetailOutput": [
                "modelLightingSampler texture3D", "gridLightingCoordsAndVis", "grid/reflection lighting SH", "sunPosition/sunDiffuse", "heroLightingR/G/B", "fog outputs/constants", "hdrControl0.x", "reflectionProbeSampler for skin"
            ],
            "forbiddenFallbacks": [
                "invent metallic", "invent roughness", "map SpecularAndGloss to Principled parameters without an exact proof", "drop Normal_Detail_Map", "drop cornea Mask/highlight arithmetic", "replace explicit RGB square/sqrt operations with ordinary sRGB transfer", "select a head runtime Material winner from patch/faction naming"
            ],
            "completeRetailPixelOutputInBlender": False,
        },
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ir-manifest", type=Path, required=True)
    p.add_argument("--abi-manifest", type=Path, required=True)
    p.add_argument("--glsl-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    ir = json.loads(a.ir_manifest.read_text(encoding="utf-8"))
    abi = json.loads(a.abi_manifest.read_text(encoding="utf-8"))
    out = build(ir, abi, a.glsl_dir)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
