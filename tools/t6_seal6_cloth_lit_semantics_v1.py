#!/usr/bin/env python3
"""Normalize the exact SEAL6 cloth ordinary-lit DXBC into reviewed equations.

This is intentionally SHA-locked to one exact vertex/pixel executable pair and
to the exact seven-material native OAT census.  It does not infer equivalence
from TechniqueSet names, Material argument names, or visual similarity.

The cloth VS is byte-identical to the already-solved character skin VS.  The
cloth PS is distinct.  Its translated finite-value program proves that the
normal, direct-specular and reflection scalar controls used by skin are literal
unit multipliers in this cloth program rather than missing Material defaults.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-retail-seal6-cloth-lit-semantics-v1"
IR_FORMAT = "t6-seal6-cloth-lit-shader-ir-v1"
CENSUS_FORMAT = "t6-seal6-native-material-conflict-report-v1"
TECHSET = "mc_sw4_3d_char_cloth_4z8fq5wu"
VS = "b1bacc64d083fb8b2a60ab28e346e14bb6f0dd9cbf21930480f7dc647f42dabe"
PS = "14053d7a2689973c49430b8cbe7a04e4b8c6d352cda47fd64cb600fab4cf7f19"
VS_GLSL = "196464c7600a52c60d99c6da515d4a84020c29000992ab68f96a6b73d5f90613"
PS_GLSL = "9bbc2583f17c8167b7cb7886ed5a7ac7a21df9cc3bc895bda6c29f8bf3db4c4a"
CLOTH_MATERIALS = (
    "mc/mtl_c_usa_mp_seal6_shoes_1",
    "mc/mtl_c_usa_mp_seal6_gear",
    "mc/mtl_c_usa_mp_seal6_vest_1",
    "mc/mtl_c_usa_mp_seal6_pants_1",
    "mc/mtl_c_usa_mp_seal6_gloves_2",
    "mc/mtl_c_usa_mp_seal6_smg_gear",
    "mc/mtl_c_gen_mp_datapad",
)


class ClothSemanticsError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shader(ir: dict[str, Any], stem: str) -> dict[str, Any]:
    rows = [x for x in ir.get("shaders", []) if x.get("stem") == stem]
    if len(rows) != 1:
        raise ClothSemanticsError(f"expected one {stem}, got {len(rows)}")
    return rows[0]


def _resource_pairs(row: dict[str, Any]) -> set[tuple[str, str]]:
    return {(str(x.get("name")), str(x.get("register"))) for x in row.get("resources", [])}


def _used_vars(row: dict[str, Any]) -> set[tuple[str, str, int]]:
    return {
        (str(x.get("constantBuffer")), str(x.get("variable")), int(x.get("vec4Slot")))
        for x in row.get("usedConstants", [])
    }


def _validate_ir(ir: dict[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if ir.get("format") != IR_FORMAT:
        raise ClothSemanticsError(f"unexpected IR format {ir.get('format')!r}")
    ident = ir.get("sourceIdentity") or {}
    if ident.get("format") != "t6-seal6-cloth-lit-binary-identity-v1":
        raise ClothSemanticsError("IR source identity is not the exact cloth binary identity")
    if ident.get("techniqueSet") != TECHSET or ident.get("techniqueSetOwner") != "common_mp":
        raise ClothSemanticsError("cloth TechniqueSet owner drift")
    if ident.get("techniqueSetSha256") != "77be6f0f0acfb5f1e6194c67036801ddf1c70052206a8ef8e1388f9a0bfc6baa":
        raise ClothSemanticsError("cloth TechniqueSet SHA drift")
    if ident.get("litTechnique") != "pimp_technique_sw4_3d_char_cloth_b0d91c7":
        raise ClothSemanticsError("cloth lit technique drift")
    if ident.get("litParsedPassStageIdentitySha256") != "e9ab8d9214d42fe348893a969adc6194fffa4c87dcc35d1c73bf0f213cb92fa8":
        raise ClothSemanticsError("cloth parsed pass/stage identity drift")

    vs = _shader(ir, "cloth_lit_vs")
    ps = _shader(ir, "cloth_lit_ps")
    if vs.get("dxbcSha256") != VS or ps.get("dxbcSha256") != PS:
        raise ClothSemanticsError("cloth DXBC identity drift")
    if vs.get("glslSha256") != VS_GLSL or ps.get("glslSha256") != PS_GLSL:
        raise ClothSemanticsError("cloth translated GLSL identity drift")
    if vs.get("spvSha256") != "50115b7085111df087823ba39785475d32ada6c640daa551e4aa013e686b622b":
        raise ClothSemanticsError("cloth VS SPIR-V drift")
    if ps.get("spvSha256") != "aaaf9b6c3105de1e14392bd8efc9f508ca4a8473b395fec01cc8dd487f5d47b3":
        raise ClothSemanticsError("cloth PS SPIR-V drift")

    vs_glsl = root / "glsl" / "cloth_lit_vs.glsl"
    ps_glsl = root / "glsl" / "cloth_lit_ps.glsl"
    if _sha(vs_glsl) != VS_GLSL or _sha(ps_glsl) != PS_GLSL:
        raise ClothSemanticsError("on-disk translated GLSL does not match IR")
    ps_text = ps_glsl.read_text(encoding="utf-8")

    # Reviewed exact-program anchors for the unit-control conclusions.  These
    # are not broad text heuristics: the whole GLSL file is already SHA-pinned.
    anchors = (
        "vec2 _164 = fma(r4.xy, vec2(4.01574802398681640625), vec2(-2.01574802398681640625));",
        "vec3 _173 = fma(r4.xxx, v4.xyz, r2.xyz);",
        "vec3 _182 = fma(r4.yyy, r3.xyz, r2.xyz);",
        "vec3 _381 = r0.xyz * r4.xyz;",
        "vec3 _507 = r1.xyz * v2.www;",
        "vec3 _515 = fma(r1.xyz, v7, r0.xyz);",
        "vec3 _528 = v2.xyz * v2.xyz;",
        "vec3 _535 = r1.xyz * r3.xyz;",
        "vec3 _542 = r1.xyz * r1.xyz;",
        "vec3 _608 = r2.xyz * vec3(32.0);",
        "vec3 _617 = fma(r0.www, r4.xyz, r2.xyz);",
        "r1.x = dot(r0, cb0_0._m0[114u]);",
        "r1.y = dot(r0, cb0_0._m0[115u]);",
        "r1.z = dot(r0, cb0_0._m0[116u]);",
        "vec3 _674 = sqrt(r0.xyz);",
    )
    missing = [x for x in anchors if x not in ps_text]
    if missing:
        raise ClothSemanticsError(f"SHA-pinned cloth PS lacks reviewed anchors: {missing}")

    expected_ps_resources = {
        ("Normal_Map", "s1"), ("SpecularAndGloss", "s2"), ("Diffuse_Map", "s3"),
        ("modelLightingSampler", "s13"), ("reflectionProbeSampler", "s15"),
        ("Normal_Map", "t0"), ("Diffuse_Map", "t1"), ("SpecularAndGloss", "t2"),
        ("modelLightingSampler", "t13"), ("reflectionProbeSampler", "t15"),
        ("PerSceneConsts", "b0"), ("PerObjectConsts", "b1"),
    }
    if _resource_pairs(ps) != expected_ps_resources:
        raise ClothSemanticsError(f"cloth PS resource ABI drift: {sorted(_resource_pairs(ps))}")
    expected_ps_vars = {
        ("PerSceneConsts", "sunPosition", 18),
        ("PerSceneConsts", "sunDiffuse", 19),
        ("PerSceneConsts", "hdrControl0", 20),
        ("PerSceneConsts", "lightingLookupScale", 56),
        ("PerSceneConsts", "heroLightingR", 114),
        ("PerSceneConsts", "heroLightingG", 115),
        ("PerSceneConsts", "heroLightingB", 116),
        ("PerObjectConsts", "scriptVector0", 23),
    }
    if _used_vars(ps) != expected_ps_vars:
        raise ClothSemanticsError(f"cloth PS runtime constant ABI drift: {sorted(_used_vars(ps))}")
    return vs, ps


def _validate_census(census: dict[str, Any]) -> list[dict[str, Any]]:
    if census.get("format") != CENSUS_FORMAT:
        raise ClothSemanticsError(f"unexpected census format {census.get('format')!r}")
    rows = []
    by_name = {str(x.get("material")): x for x in census.get("materials", [])}
    if set(CLOTH_MATERIALS) - set(by_name):
        raise ClothSemanticsError("census misses one or more cloth Materials")
    exact_state = None
    for name in CLOTH_MATERIALS:
        row = by_name[name]
        if row.get("activeRetailClientOwnerResolved") is not True:
            raise ClothSemanticsError(f"{name}: whole Material owner is not resolved")
        if row.get("textureRecordsStructurallyIdenticalAcrossCopies") is not True:
            raise ClothSemanticsError(f"{name}: texture roles are not invariant")
        copies = row.get("copies") or []
        if len(copies) != 1:
            raise ClothSemanticsError(f"{name}: expected one physical copy, got {len(copies)}")
        record = copies[0].get("nativeMaterialRecord") or {}
        if record.get("techniqueSet") != TECHSET:
            raise ClothSemanticsError(f"{name}: TechniqueSet drift")
        if record.get("constants") != []:
            raise ClothSemanticsError(f"{name}: cloth Material unexpectedly has constants")
        textures = record.get("textures") or []
        signature = [(x.get("semantic"), x.get("name")) for x in textures]
        if signature != [
            ("specularMap", "SpecularAndGloss"),
            ("normalMap", "Normal_Map"),
            ("colorMap", "Diffuse_Map"),
        ]:
            raise ClothSemanticsError(f"{name}: native texture ABI drift {signature}")
        entries = record.get("stateBitsEntry") or []
        states = record.get("stateBits") or []
        if len(entries) <= 4 or int(entries[4]) != 2 or len(states) <= 2:
            raise ClothSemanticsError(f"{name}: ordinary lit stateBits selection drift")
        state = states[2]
        expected = {
            "alphaTest": "disabled", "blendOpAlpha": "disabled", "blendOpRgb": "disabled",
            "colorWriteAlpha": True, "colorWriteRgb": True, "cullFace": "back",
            "depthTest": "less_equal", "depthWrite": True, "dstBlendAlpha": "zero",
            "dstBlendRgb": "zero", "polygonOffset": "offset0", "polymodeLine": False,
            "srcBlendAlpha": "one", "srcBlendRgb": "one",
        }
        if state != expected:
            raise ClothSemanticsError(f"{name}: exact ordinary-lit pipeline state drift")
        if exact_state is None:
            exact_state = state
        elif state != exact_state:
            raise ClothSemanticsError("cloth ordinary-lit pipeline state differs across Materials")
        rows.append({
            "material": name,
            "materialSha256": copies[0]["sha256"],
            "textureCount": len(textures),
            "textureArguments": [x["name"] for x in textures],
            "constants": [],
            "litStateBitsEntry": 2,
        })
    return rows


def build(ir: dict[str, Any], census: dict[str, Any], root: Path) -> dict[str, Any]:
    vs, ps = _validate_ir(ir, root)
    materials = _validate_census(census)
    return {
        "format": FORMAT,
        "family": {
            "id": "seal6-char-cloth-lit-v1",
            "techniqueSet": TECHSET,
            "techniqueSetOwner": "common_mp",
            "vertexDxbcSha256": VS,
            "pixelDxbcSha256": PS,
            "vertexGlslSha256": VS_GLSL,
            "pixelGlslSha256": PS_GLSL,
            "materialArguments": ["SpecularAndGloss", "Normal_Map", "Diffuse_Map"],
            "materialConstants": [],
            "normal": {
                "normalXY": "Normal_Map.rg*4.01574802398681640625-2.01574802398681640625",
                "Nlighting": "normalize(Nbase+normalXY.x*T+normalXY.y*B)",
                "Ndiff": "Nlighting",
                "Nspec": "Nlighting",
                "diffuseNormalHeightMultiplier": 1.0,
                "proof": "The SHA-pinned PS adds decoded normal X*T and Y*B directly before normalize; no Material scalar is read on this path.",
            },
            "unitMaterialControls": {
                "Specular_Amount": 1.0,
                "Reflection_Amount": 1.0,
                "Diffuse_Normal_Height_Facing": 1.0,
                "status": "literal-executable-units-not-missing-defaults",
            },
            "diffuse": {
                "encoded": "Diffuse_Map.rgb*(vertexColor.rgb*vertexColor.rgb)",
                "linearLike": "encoded*encoded",
                "lookupUVW": "Nlighting*lightingLookupScale.xyz/max(abs(Nlighting.x),abs(Nlighting.y),abs(Nlighting.z))+gridLightingCoordsAndVis.xyz",
                "modelLighting": "sample3D(modelLightingSampler,lookupUVW).rgb^2",
                "lighting": "32.0*vertexColor.a*modelLighting+saturate(dot(sunPosition.xyz,Nlighting))*(gridLightingCoordsAndVis.w*sunDiffuse.rgb)",
                "rgb": "linearLike*lighting",
            },
            "directSpecular": {
                "V": "normalize(worldPosition)",
                "L": "sunPosition.xyz",
                "H": "normalize(L-V)",
                "NH": "saturate(dot(Nlighting,H))",
                "HL": "saturate(dot(H,L))",
                "NL": "saturate(dot(L,Nlighting))",
                "P": "exp2(13.0*SpecularAndGloss.a)",
                "shape": "exp2(log2(NH)*P)*(0.125*P+0.25)",
                "denominator": "1.0099999904632568359375+saturate(SpecularAndGloss.a+0.545000016689300537109375)*(HL*HL-1.0)",
                "lobe": "shape*NL/denominator",
                "characterFactor": "1.0-saturate(scriptVector0.x)",
                "C": "characterFactor*SpecularAndGloss.rgb",
                "base": "C*C+(1.0-C*C)*exp2(-10.0*HL)",
                "rgb": "base*lobe*(gridLightingCoordsAndVis.w*sunDiffuse.rgb)",
            },
            "reflection": {
                "R": "V-2.0*Nlighting*dot(Nlighting,V)",
                "g": "exp2(-9.27999973297119140625*saturate(dot(Nlighting,-V)))",
                "lod": "4.0-4.0*SpecularAndGloss.a",
                "p0": "1.0416667461395263671875*SpecularAndGloss.a",
                "p1": "0.4749999940395355224609375*SpecularAndGloss.a",
                "p2": "0.01822919957339763641357421875*SpecularAndGloss.a-0.015625",
                "p3": "0.25*SpecularAndGloss.a+0.75",
                "q": "p0*min(g,p1)+p2",
                "F": "saturate((C*C)*(p3-q)+q)",
                "probeRgb": "sampleCubeLod(reflectionProbeSampler,R,lod).rgb/(sample.a+9.9999999747524270787835121154785e-7)",
                "rgb": "probeRgb*F*vertexColor.a*reflectionLightingRatio",
            },
            "final": {
                "preHero": "directSpecular.rgb+reflection.rgb+diffuse.rgb",
                "heroRgb": "vec3(dot(vec4(preHero,1),heroLightingR),dot(vec4(preHero,1),heroLightingG),dot(vec4(preHero,1),heroLightingB))",
                "foggedRgb": "fogColor+fogVisibility*(heroRgb-fogColor)",
                "outRgb": "sqrt(foggedRgb*hdrControl0.x)",
                "outAlpha": 1.0,
            },
            "pipelineState": {
                "techniqueType": "lit",
                "techniqueTypeIndex": 4,
                "stateBitsIndex": 2,
                "alphaTest": "disabled",
                "blend": "disabled",
                "depthTest": "less_equal",
                "depthWrite": True,
                "cullFace": "back",
                "colorWriteRgb": True,
                "colorWriteAlpha": True,
            },
        },
        "materials": materials,
        "runtimeAbi": {
            "vertexExecutableSameAsSolvedSkinVs": True,
            "pixelConstants": [
                "sunPosition", "sunDiffuse", "hdrControl0", "lightingLookupScale",
                "heroLightingR", "heroLightingG", "heroLightingB", "scriptVector0",
            ],
            "pixelTextures": ["Normal_Map", "Diffuse_Map", "SpecularAndGloss", "modelLightingSampler", "reflectionProbeSampler"],
            "runtimeTextures": ["modelLightingSampler texture3D", "reflectionProbeSampler textureCube"],
            "completeRetailPixelOutputInBlender": False,
        },
        "summary": {
            "materials": 7,
            "nativeTextureSlots": 21,
            "nativeMaterialConstants": 0,
            "uniqueVertexPrograms": 1,
            "uniquePixelPrograms": 1,
            "exactMaterialArgumentAbiClosed": True,
            "exactOrdinaryLitEquationsClosed": True,
            "literalUnitControlsClosed": True,
            "completeRetailPixelOutputInBlender": False,
        },
        "proof": {
            "shaderIrRun": 34186064296,
            "shaderIrArtifactId": 10040528947,
            "shaderIrArtifactDigest": "sha256:4ec20867435160f98d0c323d8408f9550b3bfde3a4da3885f0539149b9b0db98",
            "lod0CensusRun": 34185771413,
            "lod0CensusArtifactId": 10040436636,
            "lod0CensusArtifactDigest": "sha256:1900f6f19944534fd23541544e77cd072c41d319eccdb0b85d6270caeacfa3eb",
            "normalizer": "tools/t6_seal6_cloth_lit_semantics_v1.py",
        },
        "proofBoundary": (
            "Every family claim is conditioned on the exact VS/PS DXBC SHA pair and the exact seven-material native OAT census. The translated GLSL is whole-file SHA-pinned before reviewed instruction anchors are accepted. Unit normal/specular/reflection controls are literal executable behavior, not defaults inferred from absent Material constants. Runtime model-lighting/probe/SH/fog/HDR values remain external and therefore complete Blender retail output remains false."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ir", type=Path, required=True)
    ap.add_argument("--ir-root", type=Path, required=True)
    ap.add_argument("--census", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = build(_load(args.ir), _load(args.census), args.ir_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"format": out["format"], "summary": out["summary"], "family": out["family"]["id"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
