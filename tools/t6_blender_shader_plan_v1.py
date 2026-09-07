#!/usr/bin/env python3
"""Lower solved T6 shader IR into a fail-closed Blender material plan.

This is deliberately split from bpy node creation.  T6 semantics remain the
source of truth; the Blender plan states which operations are exact node-level
lowerings, which inputs are exact source data, and which retail global resources
still require a Blender capability/bake.  It never turns an unresolved T6 term
into invented metallic/roughness/PBR data.

v1 supports the first source-closed non-generated family registry:
``T6_RETAIL_LPROBE_LIT_SEMANTICS_V1.json``.  Membership is by the exact VS+PS
DXBC SHA-256 pair, never TechniqueSet naming or visual similarity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-blender-shader-plan-v1"
SEMANTICS_FORMAT = "t6-retail-lprobe-lit-semantics-v1"


class BlenderShaderPlanError(RuntimeError):
    pass


def _nonempty(value: Any, label: str) -> str:
    text = str(value or "")
    if not text:
        raise BlenderShaderPlanError(f"empty {label}")
    return text


def _sha(value: Any, label: str) -> str:
    text = _nonempty(value, label).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise BlenderShaderPlanError(f"{label} is not SHA-256")
    return text


def _pass_shader_pair(ir: dict) -> tuple[dict, dict, dict]:
    passes = ir.get("passes")
    if not isinstance(passes, list) or len(passes) != 1:
        raise BlenderShaderPlanError(
            f"v1 Blender planner requires exactly one pass, found {0 if not isinstance(passes, list) else len(passes)}"
        )
    render_pass = passes[0]
    shaders = render_pass.get("shaders")
    if not isinstance(shaders, list):
        raise BlenderShaderPlanError("pass has no shaders array")
    by_stage = {}
    for shader in shaders:
        stage = shader.get("stage")
        if stage in by_stage:
            raise BlenderShaderPlanError(f"duplicate {stage!r} shader in pass")
        by_stage[stage] = shader
    if set(by_stage) != {"vertex", "pixel"}:
        raise BlenderShaderPlanError(f"pass stages are {sorted(by_stage)}, expected vertex+pixel")
    return render_pass, by_stage["vertex"], by_stage["pixel"]


def _shader_sha(shader: dict) -> str:
    dxbc = shader.get("dxbc")
    if not isinstance(dxbc, dict):
        raise BlenderShaderPlanError("shader has no exact DXBC record")
    return _sha(dxbc.get("sha256"), "shader DXBC SHA-256")


def _family(semantics: dict, vs_sha: str, ps_sha: str) -> dict:
    if semantics.get("format") != SEMANTICS_FORMAT:
        raise BlenderShaderPlanError(
            f"unsupported solved semantics format {semantics.get('format')!r}"
        )
    matches = []
    for family in semantics.get("families", []):
        try:
            fvs = _sha(family["vertexShader"]["dxbcSha256"], "family VS SHA-256")
            fps = _sha(family["pixelShader"]["dxbcSha256"], "family PS SHA-256")
        except (KeyError, TypeError) as exc:
            raise BlenderShaderPlanError("malformed solved shader family") from exc
        if fvs == vs_sha and fps == ps_sha:
            matches.append(family)
    if len(matches) != 1:
        raise BlenderShaderPlanError(
            f"exact VS/PS pair {vs_sha[:12]}.../{ps_sha[:12]}... belongs to {len(matches)} solved Blender family rows"
        )
    return matches[0]


def _material_inputs(ir: dict) -> tuple[dict[str, dict], dict[str, list[float]]]:
    source = ir.get("materialInputs")
    if not isinstance(source, dict):
        raise BlenderShaderPlanError("IR has no materialInputs")
    textures: dict[str, dict] = {}
    for row in source.get("textures", []):
        name = _nonempty(row.get("name"), "Material texture name")
        if name in textures:
            raise BlenderShaderPlanError(f"duplicate Material texture {name!r}")
        image = _nonempty(row.get("image"), f"{name} image")
        textures[name] = {
            "name": name,
            "image": image,
            "semantic": row.get("semantic"),
            "samplerState": row.get("samplerState"),
        }
    constants: dict[str, list[float]] = {}
    for row in source.get("constants", []):
        name = _nonempty(row.get("name"), "Material constant name")
        literal = row.get("literal")
        if not isinstance(literal, list) or len(literal) != 4:
            raise BlenderShaderPlanError(f"Material constant {name!r} is not float4")
        constants[name] = [float(v) for v in literal]
    return textures, constants


def _vertex_requirements(family: dict) -> list[dict]:
    result = []
    source_to_blender = {
        "position": {"transport": "POSITION", "usage": "geometry"},
        "color": {"transport": "_T6_COLOR_RGBA", "usage": "shader-data"},
        "texcoord[0]": {"transport": "UVMap", "usage": "shader-data"},
        "normal": {"transport": "_T6_XMODEL_NORMAL", "usage": "shader-data"},
        "tangent": {"transport": "_T6_XMODEL_TANGENT", "usage": "shader-data"},
    }
    for row in family.get("vertexInputs", []):
        source = _nonempty(row.get("t6Source"), "family T6 vertex source")
        if source not in source_to_blender:
            raise BlenderShaderPlanError(f"no Blender transport defined for T6 vertex source {source!r}")
        result.append({
            "semantic": _nonempty(row.get("semantic"), "family DXBC semantic"),
            "t6Source": source,
            **source_to_blender[source],
        })
    if any(row["t6Source"] == "tangent" for row in result):
        result.append({
            "semantic": "POSITION0.w/retail binormal sign",
            "t6Source": "binormalSign",
            "transport": "_T6_TANGENT_HANDEDNESS",
            "usage": "shader-data",
        })
    return result


def _material_role(textures: dict[str, dict], name: str, required: bool = True) -> dict | None:
    row = textures.get(name)
    if row is None and required:
        raise BlenderShaderPlanError(f"solved shader requires Material texture {name!r}")
    return row


def build_plan(ir: dict, semantics: dict) -> dict:
    if ir.get("format") != "t6-shader-ir-v1":
        raise BlenderShaderPlanError(f"unsupported T6 shader IR {ir.get('format')!r}")
    if ir.get("techniqueType") != "lit":
        raise BlenderShaderPlanError("lprobe v1 Blender lowering only accepts exact T6 technique type 'lit'")
    render_pass, vs, ps = _pass_shader_pair(ir)
    vs_sha, ps_sha = _shader_sha(vs), _shader_sha(ps)
    family = _family(semantics, vs_sha, ps_sha)
    textures, constants = _material_inputs(ir)

    expected_material_inputs = set(family.get("materialInputs", []))
    color = _material_role(textures, "colorMap")
    specular = _material_role(textures, "specularMap")
    normal_required = "normalMapSampler" in expected_material_inputs
    normal = _material_role(textures, "normalMap", required=normal_required)
    occlusion = constants.get("occlusionAmount")
    if "occlusionAmount" in expected_material_inputs and occlusion is None:
        raise BlenderShaderPlanError("solved shader requires Material constant 'occlusionAmount'")

    family_id = family["id"]
    if family_id == "lprobe-lit-normal-spec-color-v1":
        local_ops = [
            "sample colorMap as Non-Color shader data at texcoord[0]",
            "encodedRgb = colorMap.rgb * vertexColor.rgb",
            "linearLikeRgb = encodedRgb * encodedRgb",
            "sample normalMap as Non-Color shader data at texcoord[0]",
            "normalXY = normalMap.rg * 4.01574802398681640625 - 2.01574802398681640625",
            "B = handedness * cross(N,T)",
            "surfaceN = normalize(N + normalXY.x*T + normalXY.y*B)",
            "sample specularMap as Non-Color shader data at texcoord[0]",
            "specularRgbSquared = specularMap.rgb * specularMap.rgb",
            "retain specularMap.a for exact Fresnel and reflection-probe LOD",
        ]
        alpha = {"mode": "constant", "value": 1.0}
    elif family_id == "lprobe-lit-glass-spec-color-v1":
        local_ops = [
            "sample colorMap as Non-Color shader data at texcoord[0]",
            "alphaEncoded = colorMap.a * vertexColor.a",
            "encodedRgb = colorMap.rgb * vertexColor.rgb",
            "linearLikeRgb = encodedRgb * encodedRgb",
            "surfaceN = normalize(exact transformed T6 vertex normal)",
            "sample specularMap as Non-Color shader data at texcoord[0]",
            "specularRgbSquared = specularMap.rgb * specularMap.rgb",
            "retain specularMap.a for exact Fresnel and reflection-probe LOD",
            "outputAlpha = sqrt(alphaEncoded)",
        ]
        alpha = {"mode": "expression", "expression": "sqrt(colorMap.a * vertexColor.a)"}
    else:
        raise BlenderShaderPlanError(f"no v1 Blender lowering implemented for solved family {family_id!r}")

    pipeline = ir.get("pipelineState")
    if not isinstance(pipeline, dict):
        raise BlenderShaderPlanError("IR has no exact selected pipelineState")

    return {
        "format": FORMAT,
        "proofBoundary": (
            "Exact-family Blender plan selected only by the source-closed VS+PS DXBC SHA pair. "
            "Material texture/constant ownership comes from native OAT Material inputs; geometry requirements "
            "come from solved DXBC/OAT vertex routing. Global T6 lighting/probe resources are not replaced by PBR guesses."
        ),
        "material": ir.get("material"),
        "techniqueSet": ir.get("techniqueSet"),
        "technique": ir.get("technique"),
        "techniqueType": ir.get("techniqueType"),
        "family": family_id,
        "shaderIdentity": {
            "vertexDxbcSha256": vs_sha,
            "pixelDxbcSha256": ps_sha,
        },
        "pipelineState": pipeline,
        "vertexRequirements": _vertex_requirements(family),
        "materialResources": {
            "colorMap": color,
            "normalMap": normal,
            "specularMap": specular,
            "occlusionAmount": occlusion,
        },
        "exactMaterialLocalOperations": local_ops,
        "exactMaterialLocalAlpha": alpha,
        "globalRetailDependencies": [
            "modelLightingSampler texture3D + lightingLookupScale + gridLightingCoordsAndVis",
            "grid/reflection lighting SH constants and exact VS ratio",
            "reflectionProbeSampler textureCube with explicit specular-alpha LOD",
            "fog constants/VS fog outputs",
            "hdrControl0.x",
        ],
        "blenderLowering": {
            "materialLocal": "exact-node",
            "normalBasis": "exact-node" if family_id == "lprobe-lit-normal-spec-color-v1" else "exact-node-vertex-normal",
            "globalLighting": "requires-exact-global-resource-capability-or-bake",
            "viewportSurface": "authoring-substitute-until-global-resources-are-provided",
            "pipelineState": "authoritative-metadata; arbitrary D3D destination blending is not claimed exact in Blender",
        },
        "forbiddenFallbacks": semantics.get("backendPolicy", {}).get("blender", {}).get("forbiddenFallbacks", []),
        "completeRetailPixelOutputInBlender": false,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ir", type=Path)
    parser.add_argument(
        "--semantics",
        type=Path,
        default=Path("manifests/render/T6_RETAIL_LPROBE_LIT_SEMANTICS_V1.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    ir = json.loads(args.ir.read_text(encoding="utf-8"))
    semantics = json.loads(args.semantics.read_text(encoding="utf-8"))
    plan = build_plan(ir, semantics)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
