#!/usr/bin/env python3
"""Compile solved T6 lprobe-lit material-local arithmetic into Blender nodes.

The input is a validated ``t6-blender-shader-plan-v1``.  This backend creates
real Blender nodes for every currently source-closed material-local operation:

- exact source image sampling as Non-Color data;
- T6 vertex color as ``_T6_COLOR_RGBA`` shader data;
- explicit encoded RGB square;
- exact lprobe normal RG decode;
- exact imported T6 N/T/handedness reconstruction;
- exact specular RGB square and retained alpha;
- exact glass ``sqrt(color.a * vertex.a)`` output alpha.

The final Surface socket is an *authoring substitute* using Blender Principled
lighting because modelLightingSampler (3D), reflectionProbeSampler (cube+LOD),
T6 SH/grid constants, fog, and HDR output transfer are global retail resources
that are not supplied by this v1 node backend.  The unconnected exact specular
subgraph is intentionally preserved.  No T6 specular value is mapped to
Principled metallic/roughness/specular.
"""
from __future__ import annotations

import json
from typing import Any

try:
    import bpy  # type: ignore
except ImportError:  # permits ordinary Python validation/import
    bpy = None

import t6_blender_generated_normal_nodes_v2 as basis_nodes

FORMAT = "t6-blender-lprobe-nodes-v1"
PLAN_FORMAT = "t6-blender-shader-plan-v1"
OPAQUE_FAMILY = "lprobe-lit-normal-spec-color-v1"
GLASS_FAMILY = "lprobe-lit-glass-spec-color-v1"


class BlenderLprobeNodeError(RuntimeError):
    pass


def _socket(collection, name: str):
    value = collection.get(name)
    if value is None:
        raise BlenderLprobeNodeError(f"Blender node lacks {name!r} socket")
    return value


def _require_bpy() -> None:
    if bpy is None:
        raise BlenderLprobeNodeError("bpy is unavailable; run node compilation inside Blender")


def _image_exact(name: str):
    exact = bpy.data.images.get(name)
    if exact is not None:
        return exact
    matches = [image for image in bpy.data.images if image.name == name or image.name.startswith(name + ".")]
    if len(matches) != 1:
        raise BlenderLprobeNodeError(f"exact T6 image {name!r} is not uniquely loaded in Blender")
    return matches[0]


def _data_image(name: str, role: str, cache: dict[tuple[str, str], Any]):
    key = (name, role)
    if key in cache:
        return cache[key]
    source = _image_exact(name)
    image = source.copy()
    image.name = f"{name}__T6_{role}_DATA"
    try:
        image.colorspace_settings.name = "Non-Color"
    except Exception as exc:
        raise BlenderLprobeNodeError(f"cannot force Non-Color sampling for {name!r}: {exc}") from exc
    cache[key] = image
    return image


def _uv(nodes):
    node = nodes.new("ShaderNodeUVMap")
    node.uv_map = "UVMap"
    node.label = "T6 exact texcoord[0]"
    return _socket(node.outputs, "UV")


def _texture(nodes, links, plan: dict, role: str, cache: dict, x: float, y: float):
    resource = plan["materialResources"].get(role)
    if not isinstance(resource, dict):
        raise BlenderLprobeNodeError(f"plan lacks exact Material resource {role!r}")
    image_name = str(resource.get("image") or "")
    if not image_name:
        raise BlenderLprobeNodeError(f"plan resource {role!r} has empty image identity")
    node = nodes.new("ShaderNodeTexImage")
    node.name = f"T6_{role}"
    node.label = f"T6 exact {role}: {image_name}"
    node.image = _data_image(image_name, role, cache)
    node.interpolation = "Linear"
    node.extension = "REPEAT"
    node.location = (x, y)
    uv = _uv(nodes)
    uv.location = (x - 220, y)
    links.new(uv, _socket(node.inputs, "Vector"))
    return node


def _attribute(nodes, name: str, label: str):
    node = nodes.new("ShaderNodeAttribute")
    node.attribute_name = name
    node.label = label
    return node


def _attr_vector(nodes, name: str, label: str):
    node = _attribute(nodes, name, label)
    value = node.outputs.get("Vector") or node.outputs.get("Color")
    if value is None:
        raise BlenderLprobeNodeError(f"Blender cannot expose vector attribute {name!r}")
    return node, value


def _attr_color(nodes, name: str, label: str):
    node = _attribute(nodes, name, label)
    color = node.outputs.get("Color")
    alpha = node.outputs.get("Alpha") or node.outputs.get("Fac")
    if color is None or alpha is None:
        raise BlenderLprobeNodeError(f"Blender cannot expose color/alpha attribute {name!r}")
    return node, color, alpha


def _attr_scalar(nodes, name: str, label: str):
    node = _attribute(nodes, name, label)
    value = node.outputs.get("Fac") or node.outputs.get("Alpha")
    if value is None:
        raise BlenderLprobeNodeError(f"Blender cannot expose scalar attribute {name!r}")
    return node, value


def _vector_mul(nodes, links, a, b, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = "MULTIPLY"
    node.label = label
    links.new(a, node.inputs[0])
    links.new(b, node.inputs[1])
    return _socket(node.outputs, "Vector")


def _vector_add(nodes, links, a, b, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = "ADD"
    node.label = label
    links.new(a, node.inputs[0])
    links.new(b, node.inputs[1])
    return _socket(node.outputs, "Vector")


def _scale_vector(nodes, links, vector, scalar, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = "SCALE"
    node.label = label
    links.new(vector, node.inputs[0])
    links.new(scalar, _socket(node.inputs, "Scale"))
    return _socket(node.outputs, "Vector")


def _normalize(nodes, links, vector, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = "NORMALIZE"
    node.label = label
    links.new(vector, node.inputs[0])
    return _socket(node.outputs, "Vector")


def _math_mul(nodes, links, a, b, label: str):
    node = nodes.new("ShaderNodeMath")
    node.operation = "MULTIPLY"
    node.label = label
    if hasattr(a, "bl_idname") or hasattr(a, "is_output"):
        links.new(a, node.inputs[0])
    else:
        node.inputs[0].default_value = float(a)
    if hasattr(b, "bl_idname") or hasattr(b, "is_output"):
        links.new(b, node.inputs[1])
    else:
        node.inputs[1].default_value = float(b)
    return node.outputs[0]


def _math_add(nodes, links, a, b, label: str):
    node = nodes.new("ShaderNodeMath")
    node.operation = "ADD"
    node.label = label
    if hasattr(a, "bl_idname") or hasattr(a, "is_output"):
        links.new(a, node.inputs[0])
    else:
        node.inputs[0].default_value = float(a)
    if hasattr(b, "bl_idname") or hasattr(b, "is_output"):
        links.new(b, node.inputs[1])
    else:
        node.inputs[1].default_value = float(b)
    return node.outputs[0]


def _sqrt(nodes, links, value, label: str):
    node = nodes.new("ShaderNodeMath")
    node.operation = "SQRT"
    node.label = label
    links.new(value, node.inputs[0])
    return node.outputs[0]


def _basis_world(nodes, links, attribute: str, short: str):
    _, raw = _attr_vector(nodes, attribute, f"T6 exact glTF-space {short}")
    obj = basis_nodes.gltf_to_blender_object_vector(nodes, links, raw, f"T6 exact {short}")
    transform = nodes.new("ShaderNodeVectorTransform")
    transform.vector_type = "VECTOR"
    transform.convert_from = "OBJECT"
    transform.convert_to = "WORLD"
    transform.label = f"T6 exact {short} Blender-object->world"
    links.new(obj, _socket(transform.inputs, "Vector"))
    return _normalize(nodes, links, _socket(transform.outputs, "Vector"), f"T6 normalize transformed {short}")


def _exact_surface_normal(nodes, links, normal_tex):
    normal = _basis_world(nodes, links, "_T6_XMODEL_NORMAL", "N")
    tangent = _basis_world(nodes, links, "_T6_XMODEL_TANGENT", "T")
    _, sign = _attr_scalar(nodes, "_T6_TANGENT_HANDEDNESS", "T6 exact retail binormal sign")

    cross = nodes.new("ShaderNodeVectorMath")
    cross.operation = "CROSS_PRODUCT"
    cross.label = "T6 cross(N,T)"
    links.new(normal, cross.inputs[0])
    links.new(tangent, cross.inputs[1])
    binormal = _scale_vector(nodes, links, _socket(cross.outputs, "Vector"), sign, "T6 B = handedness * cross(N,T)")

    separate = nodes.new("ShaderNodeSeparateRGB")
    separate.label = "T6 normalMap RG"
    links.new(_socket(normal_tex.outputs, "Color"), _socket(separate.inputs, "Image"))
    x = _math_add(
        nodes, links,
        _math_mul(nodes, links, _socket(separate.outputs, "R"), 4.01574802398681640625, "T6 normal.r * 4.015748024"),
        -2.01574802398681640625,
        "T6 normal X decode",
    )
    y = _math_add(
        nodes, links,
        _math_mul(nodes, links, _socket(separate.outputs, "G"), 4.01574802398681640625, "T6 normal.g * 4.015748024"),
        -2.01574802398681640625,
        "T6 normal Y decode",
    )
    tx = _scale_vector(nodes, links, tangent, x, "T6 normalX * T")
    by = _scale_vector(nodes, links, binormal, y, "T6 normalY * B")
    raw = _vector_add(nodes, links, normal, tx, "T6 N + X*T")
    raw = _vector_add(nodes, links, raw, by, "T6 N + X*T + Y*B")
    return _normalize(nodes, links, raw, "T6 retail normalize(surface normal)")


def _vertex_normal_only(nodes, links):
    return _basis_world(nodes, links, "_T6_XMODEL_NORMAL", "N")


def _configure_preview_blend(material, transparent: bool) -> str:
    if not transparent:
        return "opaque-authoring"
    # Blender changed the Eevee transparency API. Use it only when the running
    # version exposes a known property; T6 state remains in custom metadata.
    if hasattr(material, "surface_render_method"):
        for value in ("DITHERED", "BLENDED"):
            try:
                material.surface_render_method = value
                return f"surface_render_method={value}"
            except Exception:
                pass
    if hasattr(material, "blend_method"):
        try:
            material.blend_method = "BLEND"
            return "blend_method=BLEND"
        except Exception:
            pass
    return "no-compatible-Blender-transparency-property"


def compile_material(material, plan: dict, *, image_cache: dict | None = None) -> dict:
    _require_bpy()
    if plan.get("format") != PLAN_FORMAT:
        raise BlenderLprobeNodeError(f"unsupported Blender plan {plan.get('format')!r}")
    family = plan.get("family")
    if family not in {OPAQUE_FAMILY, GLASS_FAMILY}:
        raise BlenderLprobeNodeError(f"unsupported lprobe family {family!r}")
    cache = image_cache if image_cache is not None else {}

    material.use_nodes = True
    tree = material.node_tree
    if tree is None:
        raise BlenderLprobeNodeError("material has no node tree")
    nodes, links = tree.nodes, tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1050, 0)
    output.label = "T6 Blender authoring surface"
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (760, 0)
    principled.label = "AUTHORING SUBSTITUTE: T6 global lighting unresolved"
    links.new(_socket(principled.outputs, "BSDF"), _socket(output.inputs, "Surface"))

    color_tex = _texture(nodes, links, plan, "colorMap", cache, -1250, 350)
    spec_tex = _texture(nodes, links, plan, "specularMap", cache, -1250, -500)
    color_attr, vertex_color, vertex_alpha = _attr_color(
        nodes, "_T6_COLOR_RGBA", "T6 exact packed vertex color"
    )
    color_attr.location = (-1250, 80)

    encoded = _vector_mul(
        nodes, links,
        _socket(color_tex.outputs, "Color"), vertex_color,
        "T6 encodedRgb = colorMap.rgb * vertexColor.rgb",
    )
    linear_like = _vector_mul(
        nodes, links, encoded, encoded,
        "T6 explicit encoded RGB square",
    )
    links.new(linear_like, _socket(principled.inputs, "Base Color"))

    spec_squared = _vector_mul(
        nodes, links,
        _socket(spec_tex.outputs, "Color"), _socket(spec_tex.outputs, "Color"),
        "T6 exact specularMap.rgb square (NOT Principled roughness)",
    )
    # Keep this exact subgraph visible and source-addressable, but deliberately
    # leave it disconnected from Principled physical parameters.
    if getattr(spec_squared, "node", None) is not None:
        spec_squared.node.label += " | retained for Fresnel/probe backend"

    if family == OPAQUE_FAMILY:
        normal_tex = _texture(nodes, links, plan, "normalMap", cache, -1250, -100)
        surface_normal = _exact_surface_normal(nodes, links, normal_tex)
        links.new(surface_normal, _socket(principled.inputs, "Normal"))
        alpha_mode = "constant-1"
        transparent = False
    else:
        surface_normal = _vertex_normal_only(nodes, links)
        links.new(surface_normal, _socket(principled.inputs, "Normal"))
        alpha_encoded = _math_mul(
            nodes, links,
            _socket(color_tex.outputs, "Alpha"), vertex_alpha,
            "T6 alphaEncoded = colorMap.a * vertexColor.a",
        )
        alpha = _sqrt(nodes, links, alpha_encoded, "T6 output alpha = sqrt(alphaEncoded)")
        links.new(alpha, _socket(principled.inputs, "Alpha"))
        alpha_mode = "sqrt(color.a*vertex.a)"
        transparent = True

    preview_blend = _configure_preview_blend(material, transparent)
    material["t6_shader_backend"] = FORMAT
    material["t6_shader_family"] = str(family)
    material["t6_complete_retail_pixel_output"] = False
    material["t6_material_local_nodes_exact"] = True
    material["t6_global_lighting_status"] = "requires exact 3D model-light/probe/SH/fog/HDR capability or bake"
    material["t6_pipeline_state_json"] = json.dumps(plan.get("pipelineState"), sort_keys=True)
    material["t6_forbidden_fallbacks_json"] = json.dumps(plan.get("forbiddenFallbacks", []), sort_keys=True)
    material["t6_preview_surface"] = "Blender Principled authoring substitute; no T6 specular->PBR mapping"

    # Make the lack of an invented PBR mapping inspectable directly in the node.
    principled["t6_authoring_substitute"] = True
    principled["t6_specular_physical_mapping"] = "UNRESOLVED - exact specular nodes retained unconnected"

    return {
        "format": FORMAT,
        "material": material.name,
        "family": family,
        "nodeCount": len(nodes),
        "imageResources": {
            role: plan["materialResources"][role]["image"]
            for role in ("colorMap", "specularMap")
            if isinstance(plan["materialResources"].get(role), dict)
        } | ({
            "normalMap": plan["materialResources"]["normalMap"]["image"]
        } if isinstance(plan["materialResources"].get("normalMap"), dict) and family == OPAQUE_FAMILY else {}),
        "alpha": alpha_mode,
        "previewBlend": preview_blend,
        "materialLocalExact": True,
        "completeRetailPixelOutput": False,
        "globalDependencies": plan.get("globalRetailDependencies", []),
    }
