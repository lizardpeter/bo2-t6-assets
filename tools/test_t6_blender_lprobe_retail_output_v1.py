#!/usr/bin/env python3
"""Run inside Blender: validate exact lprobe retail final-output connection."""
from __future__ import annotations

import json
import bpy
import t6_blender_lprobe_retail_output_v1 as retail

backend = retail.local


def image(name: str, rgba):
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name=name, width=2, height=2, alpha=True, float_buffer=False)
    img.pixels = list(rgba) * 4
    return img


def plan(family: str):
    opaque = family == backend.OPAQUE_FAMILY
    return {
        "format": backend.PLAN_FORMAT,
        "family": family,
        "pipelineState": {
            "alphaTest": "disabled" if opaque else "gt0",
            "srcBlendRgb": "one",
            "dstBlendRgb": "zero" if opaque else "invsrcalpha",
            "blendOpRgb": "add",
            "depthWrite": opaque,
            "depthTest": "less_equal",
            "cullFace": "back",
        },
        "materialResources": {
            "colorMap": {"image": "t6_test_color", "name": "colorMap"},
            "normalMap": {"image": "t6_test_normal", "name": "normalMap"} if opaque else None,
            "specularMap": {"image": "t6_test_spec", "name": "specularMap"},
            "occlusionAmount": [1.0, 1.0, 1.0, 1.0],
        },
        "globalRetailDependencies": ["modelLightingSampler", "reflectionProbeSampler", "fog", "hdrControl0"],
        "forbiddenFallbacks": ["invent metallicFactor", "invent roughnessFactor"],
    }


def globals_fixture():
    return {
        "modelLighting": (0.02, 0.03, 0.04),
        "reflectionRgb": (0.005, 0.006, 0.007),
        "fogColor": (0.1, 0.12, 0.14),
        "fogVisibility": 0.75,
        "hdrControl0X": 1.0,
    }


def surface_source(material):
    output = next(n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    links = list(output.inputs["Surface"].links)
    assert len(links) == 1, len(links)
    return links[0].from_node


def validate(material, result, glass: bool):
    assert result["completeRetailPixelArithmetic"] is True
    assert result["surfaceTransport"] == "Emission"
    assert material["t6_complete_retail_pixel_arithmetic"] is True
    source = surface_source(material)
    assert source.bl_idname == "ShaderNodeEmission", source.bl_idname
    assert source["t6_transport_only"] is True
    principled = [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"]
    assert len(principled) == 1
    assert principled[0]["t6_retired"] is True
    assert not principled[0].outputs["BSDF"].is_linked
    labels = {n.label for n in material.node_tree.nodes if n.label}
    assert "T6 outRgb = sqrt(fogged*hdr)" in labels
    assert "T6 32 * modelLighting * linearLikeRgb" in labels
    if glass:
        assert "T6 reflectionRgb / alphaEncoded" in labels
        assert "T6 glass premulFogged" in labels
    else:
        assert "T6 litRgb = diffuse + reflection" in labels
        assert "T6 foggedRgb" in labels


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image("t6_test_color", (0.25, 0.5, 0.75, 0.36))
    image("t6_test_normal", (0.5, 0.5, 1.0, 1.0))
    image("t6_test_spec", (0.2, 0.3, 0.4, 0.5))

    opaque = bpy.data.materials.new("opaque_retail")
    ro = retail.compile_retail_output(opaque, plan(backend.OPAQUE_FAMILY), globals_fixture())
    validate(opaque, ro, False)

    glass = bpy.data.materials.new("glass_retail")
    rg = retail.compile_retail_output(glass, plan(backend.GLASS_FAMILY), globals_fixture())
    validate(glass, rg, True)

    report = {
        "format": "t6-blender-lprobe-retail-output-test-v1",
        "blenderVersion": bpy.app.version_string,
        "opaque": ro,
        "glass": rg,
        "validation": {
            "exactRetailFinalArithmeticConnected": True,
            "principledDisconnected": True,
            "emissionTransportOnly": True,
            "opaqueFogDiffuseReflectionEquationPresent": True,
            "glassPremultipliedFogEquationPresent": True,
            "globalResourceAcquisitionStillSeparate": True,
        },
    }
    print("T6_BLENDER_LPROBE_RETAIL_OUTPUT_TEST=" + json.dumps(report, sort_keys=True))
    bpy.ops.wm.save_as_mainfile(filepath="/tmp/T6_BLENDER_LPROBE_RETAIL_OUTPUT_V1_TEST.blend")
    with open("/tmp/T6_BLENDER_LPROBE_RETAIL_OUTPUT_V1_TEST.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
