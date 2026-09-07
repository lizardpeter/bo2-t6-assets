#!/usr/bin/env python3
"""Run inside Blender: structural tests for exact-local T6 lprobe nodes."""
from __future__ import annotations

import json

import bpy

import t6_blender_lprobe_nodes_v1 as backend


def image(name: str, rgba):
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name=name, width=2, height=2, alpha=True, float_buffer=False)
    img.pixels = list(rgba) * 4
    return img


def base_plan(family: str):
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
        "globalRetailDependencies": ["modelLightingSampler", "reflectionProbeSampler"],
        "forbiddenFallbacks": ["invent metallicFactor", "invent roughnessFactor"],
    }


def labels(material):
    return {node.label for node in material.node_tree.nodes if node.label}


def principled(material):
    matches = [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"]
    assert len(matches) == 1, len(matches)
    return matches[0]


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image("t6_test_color", (0.25, 0.5, 0.75, 0.36))
    image("t6_test_normal", (0.5, 0.5, 1.0, 1.0))
    image("t6_test_spec", (0.2, 0.3, 0.4, 0.5))

    opaque = bpy.data.materials.new("opaque")
    result_o = backend.compile_material(opaque, base_plan(backend.OPAQUE_FAMILY))
    assert result_o["materialLocalExact"] is True
    assert result_o["completeRetailPixelOutput"] is False
    labs = labels(opaque)
    assert "T6 explicit encoded RGB square" in labs
    assert "T6 normal X decode" in labs
    assert "T6 normal Y decode" in labs
    assert "T6 B = handedness * cross(N,T)" in labs
    assert any("specularMap.rgb square" in value for value in labs)
    p = principled(opaque)
    assert p["t6_authoring_substitute"] is True
    assert not p.inputs["Metallic"].is_linked
    assert not p.inputs["Roughness"].is_linked
    assert p.inputs["Base Color"].is_linked
    assert p.inputs["Normal"].is_linked
    assert opaque["t6_complete_retail_pixel_output"] is False

    glass = bpy.data.materials.new("glass")
    result_g = backend.compile_material(glass, base_plan(backend.GLASS_FAMILY))
    assert result_g["alpha"] == "sqrt(color.a*vertex.a)"
    gp = principled(glass)
    assert gp.inputs["Alpha"].is_linked
    assert gp.inputs["Normal"].is_linked
    glabs = labels(glass)
    assert "T6 alphaEncoded = colorMap.a * vertexColor.a" in glabs
    assert "T6 output alpha = sqrt(alphaEncoded)" in glabs
    assert "T6 normal X decode" not in glabs

    data_images = [img for img in bpy.data.images if "__T6_" in img.name and img.name.endswith("_DATA")]
    assert data_images, "backend created no role-specific data images"
    assert all(img.colorspace_settings.name == "Non-Color" for img in data_images)

    report = {
        "format": "t6-blender-lprobe-nodes-test-v1",
        "blenderVersion": bpy.app.version_string,
        "opaque": result_o,
        "glass": result_g,
        "dataImages": [img.name for img in data_images],
        "validation": {
            "materialLocalNodesExact": True,
            "specularNotMappedToPbr": True,
            "normalDecodeGraphPresentOpaqueOnly": True,
            "glassSqrtAlphaPresent": True,
            "allRoleCopiesNonColor": True,
        },
    }
    print("T6_BLENDER_LPROBE_TEST=" + json.dumps(report, sort_keys=True))
    bpy.ops.wm.save_as_mainfile(filepath="/tmp/T6_BLENDER_LPROBE_NODES_V1_TEST.blend")
    with open("/tmp/T6_BLENDER_LPROBE_NODES_V1_TEST.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
