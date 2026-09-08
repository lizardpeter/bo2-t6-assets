#!/usr/bin/env python3
"""Upgrade role-complete SEAL6 Blender materials with exact ordinary-lit local math.

This backend runs *after* ``t6_blender_seal6_role_nodes_v1``.  The role backend
remains the owner of the twenty SHA-verified retail image nodes.  This adapter
joins those source nodes to the exact ``t6-seal6-blender-shader-plan-v1`` and
creates only the material-local arithmetic already closed from the SHA-pinned
retail DXBC programs.

For skin-family materials the former raw diffuse/normal authoring preview is
upgraded to the exact closed local diffuse expression and exact Ndiff normal:

    vc2       = vertexColor.rgb * vertexColor.rgb
    encoded   = Diffuse_Map.rgb * vc2
    linearLike= encoded * encoded

Standard skin creates both Nspec and Ndiff from Normal_Map.  Hero skin also
samples Normal_Detail_Map at UV0*Normal_Detail_Scale and adds its decoded RG to
the base decoded normal before creating Nspec/Ndiff.

Cornea creates its exact Surface_Normal_Map perturbation, Mask.r source,
OverallBrightness^2 and all literal Material constants, but the highlight lobes
are not connected to final output because F1/F2 require the exact T6 inverse-view
transport and final RGB still requires T6 model lighting, sun, fog and HDR.

The final Material Output remains an explicitly labelled Blender authoring
substitute.  No T6 specular/gloss value is mapped to Principled physical
parameters and complete retail pixel output remains false.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import bpy  # type: ignore
except ImportError:
    bpy = None

import t6_blender_lprobe_nodes_v1 as lprobe
import t6_blender_seal6_role_nodes_v1 as role_nodes

PLAN_FORMAT = "t6-seal6-blender-shader-plan-v1"
FORMAT = "t6-blender-seal6-lit-nodes-v1"
HERO = "seal6-char-skin-hero-lit-v1"
STANDARD = "seal6-char-skin-standard-lit-v1"
CORNEA = "seal6-char-eye-cornea-lit-v1"

EXPECTED = {
    "materials": 5,
    "nativeSlots": 20,
    "litSlots": 15,
    "preservedNonLit": 5,
    "constants": 22,
    "argumentBindings": 37,
}


class Seal6LitNodeError(RuntimeError):
    pass


def _require_bpy() -> None:
    if bpy is None:
        raise Seal6LitNodeError("bpy is unavailable; run this backend inside Blender")


def _socket(collection, name: str):
    value = collection.get(name)
    if value is None:
        raise Seal6LitNodeError(f"Blender node lacks {name!r} socket")
    return value


def _material_exact(name: str):
    exact = bpy.data.materials.get(name)
    if exact is not None:
        return exact
    matches = [m for m in bpy.data.materials if m.name == name or m.name.startswith(name + ".")]
    if len(matches) != 1:
        raise Seal6LitNodeError(f"exact SEAL6 Material {name!r} is not uniquely present in Blender")
    return matches[0]


def _source_node(nodes, slot_index: int):
    prefix = f"T6_SLOT_{slot_index:02d}_"
    matches = [n for n in nodes if n.bl_idname == "ShaderNodeTexImage" and n.name.startswith(prefix)]
    if len(matches) != 1:
        raise Seal6LitNodeError(f"native slot {slot_index} maps to {len(matches)} role-source nodes")
    return matches[0]


def _separate_rgb(nodes, links, color, label: str):
    try:
        node = nodes.new("ShaderNodeSeparateColor")
        if hasattr(node, "mode"):
            node.mode = "RGB"
        names = ("Red", "Green", "Blue")
    except Exception:
        node = nodes.new("ShaderNodeSeparateRGB")
        names = ("R", "G", "B")
    node.label = label
    links.new(color, node.inputs[0])
    return node, _socket(node.outputs, names[0]), _socket(node.outputs, names[1]), _socket(node.outputs, names[2])


def _math(nodes, links, operation: str, a, b=None, *, label: str):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    node.label = label
    if hasattr(a, "is_output") or hasattr(a, "bl_idname"):
        links.new(a, node.inputs[0])
    else:
        node.inputs[0].default_value = float(a)
    if b is not None:
        if hasattr(b, "is_output") or hasattr(b, "bl_idname"):
            links.new(b, node.inputs[1])
        else:
            node.inputs[1].default_value = float(b)
    return node.outputs[0]


def _vector_scale(nodes, links, vector, scalar, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = "SCALE"
    node.label = label
    links.new(vector, node.inputs[0])
    links.new(scalar, _socket(node.inputs, "Scale"))
    return _socket(node.outputs, "Vector")


def _vector_add(nodes, links, a, b, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = "ADD"
    node.label = label
    links.new(a, node.inputs[0])
    links.new(b, node.inputs[1])
    return _socket(node.outputs, "Vector")


def _normalize(nodes, links, value, label: str):
    node = nodes.new("ShaderNodeVectorMath")
    node.operation = "NORMALIZE"
    node.label = label
    links.new(value, node.inputs[0])
    return _socket(node.outputs, "Vector")


def _constant_nodes(nodes, frame, constants: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for index, row in enumerate(constants):
        name = str(row.get("name") or "")
        literal = row.get("literal")
        binding = row.get("ordinaryLitBinding") or {}
        if not name or not isinstance(literal, list) or len(literal) != 4:
            raise Seal6LitNodeError(f"malformed native Material constant {name!r}")
        if binding.get("referenced") is not True or binding.get("stage") not in {"vertex", "pixel"}:
            raise Seal6LitNodeError(f"{name}: constant is not closed to an exact VS/PS argument")
        if name in {"Fill_Direction", "Fill_Direction2"}:
            node = nodes.new("ShaderNodeCombineXYZ")
            node.inputs[0].default_value = float(literal[0])
            node.inputs[1].default_value = float(literal[1])
            node.inputs[2].default_value = float(literal[2])
            value = _socket(node.outputs, "Vector")
        else:
            node = nodes.new("ShaderNodeValue")
            node.outputs[0].default_value = float(literal[0])
            value = node.outputs[0]
        node.name = f"T6_CONST_{name}"
        node.label = f"T6 exact {binding['stage']} Material arg {name} = {literal}"
        node.location = (-150, -260 * index)
        node.parent = frame
        node["t6_material_argument"] = name
        node["t6_stage"] = str(binding["stage"])
        node["t6_literal_float4"] = json.dumps([float(v) for v in literal])
        out[name] = value
    return out


def _exact_basis(nodes, links):
    nbase = lprobe._basis_world(nodes, links, "_T6_XMODEL_NORMAL", "SEAL6 Nbase")
    tangent = lprobe._basis_world(nodes, links, "_T6_XMODEL_TANGENT", "SEAL6 T")
    hand_node, handedness = lprobe._attr_scalar(
        nodes, "_T6_TANGENT_HANDEDNESS", "T6 exact retail tangent handedness"
    )
    hand_node.name = "T6_EXACT_TANGENT_HANDEDNESS"
    cross = nodes.new("ShaderNodeVectorMath")
    cross.operation = "CROSS_PRODUCT"
    cross.label = "T6 exact cross(Nbase,T)"
    links.new(nbase, cross.inputs[0])
    links.new(tangent, cross.inputs[1])
    binormal = _vector_scale(nodes, links, _socket(cross.outputs, "Vector"), handedness,
                             "T6 exact B = handedness*cross(Nbase,T)")
    return nbase, tangent, binormal


def _normal_xy(nodes, links, tex_node, prefix: str):
    _sep, r, g, _b = _separate_rgb(nodes, links, _socket(tex_node.outputs, "Color"), f"{prefix} RG")
    x = _math(nodes, links, "ADD",
              _math(nodes, links, "MULTIPLY", r, 4.01574802398681640625,
                    label=f"{prefix} r*4.01574802398681640625"),
              -2.01574802398681640625, label=f"{prefix} X decode")
    y = _math(nodes, links, "ADD",
              _math(nodes, links, "MULTIPLY", g, 4.01574802398681640625,
                    label=f"{prefix} g*4.01574802398681640625"),
              -2.01574802398681640625, label=f"{prefix} Y decode")
    return x, y


def _normal_from_xy(nodes, links, nbase, tangent, binormal, x, y, label: str):
    tx = _vector_scale(nodes, links, tangent, x, f"{label}: X*T")
    by = _vector_scale(nodes, links, binormal, y, f"{label}: Y*B")
    value = _vector_add(nodes, links, nbase, tx, f"{label}: Nbase+X*T")
    value = _vector_add(nodes, links, value, by, f"{label}: Nbase+X*T+Y*B")
    result = _normalize(nodes, links, value, f"{label}: normalize")
    if getattr(result, "node", None) is not None:
        result.node.name = label
    return result


def _replace_input_link(links, socket, source) -> None:
    for link in list(socket.links):
        links.remove(link)
    links.new(source, socket)


def _skin_local_graph(nodes, links, plan: dict[str, Any], source_by_arg: dict[str, Any], constants: dict[str, Any], frame):
    diffuse = source_by_arg.get("Diffuse_Map")
    normal = source_by_arg.get("Normal_Map")
    specular = source_by_arg.get("SpecularAndGloss")
    if diffuse is None or normal is None or specular is None:
        raise Seal6LitNodeError(f"{plan['material']}: skin family lacks exact diffuse/normal/specular sources")

    color_node, vertex_rgb, vertex_alpha = lprobe._attr_color(
        nodes, "_T6_COLOR_RGBA", "T6 exact SEAL6 vertex color shader data"
    )
    color_node.name = "T6_EXACT_VERTEX_COLOR_RGBA"
    color_node.parent = frame

    vc2 = lprobe._vector_mul(nodes, links, vertex_rgb, vertex_rgb,
                             "T6 exact vertexColor.rgb^2")
    encoded = lprobe._vector_mul(nodes, links, _socket(diffuse.outputs, "Color"), vc2,
                                 "T6 exact encoded = Diffuse_Map.rgb * vertexColor.rgb^2")
    linear_like = lprobe._vector_mul(nodes, links, encoded, encoded,
                                     "T6 exact linearLike = encoded^2")
    linear_like.node.name = "T6_EXACT_SKIN_LINEARLIKE_RGB"

    nbase, tangent, binormal = _exact_basis(nodes, links)
    base_x, base_y = _normal_xy(nodes, links, normal, "T6 Normal_Map")

    family = str(plan.get("shaderFamilyId") or "")
    if family == HERO:
        detail = source_by_arg.get("Normal_Detail_Map")
        scale = constants.get("Normal_Detail_Scale")
        height = constants.get("Diffuse_Normal_Height")
        if detail is None or scale is None or height is None:
            raise Seal6LitNodeError(f"{plan['material']}: hero detail-normal inputs incomplete")
        uv = nodes.new("ShaderNodeUVMap")
        uv.name = "T6_EXACT_HERO_DETAIL_UV0"
        uv.label = "T6 exact hero detail UV0"
        uv.uv_map = "UVMap"
        uv.parent = frame
        detail_uv = _vector_scale(nodes, links, _socket(uv.outputs, "UV"), scale,
                                  "T6 exact detailUV = UV0*Normal_Detail_Scale")
        _replace_input_link(links, _socket(detail.inputs, "Vector"), detail_uv)
        dx, dy = _normal_xy(nodes, links, detail, "T6 Normal_Detail_Map")
        combined_x = _math(nodes, links, "ADD", base_x, dx, label="T6 hero combinedXY.x")
        combined_y = _math(nodes, links, "ADD", base_y, dy, label="T6 hero combinedXY.y")
        x, y = combined_x, combined_y
        detail_graph = True
    elif family == STANDARD:
        height = constants.get("Diffuse_Normal_Height_Facing")
        if height is None:
            raise Seal6LitNodeError(f"{plan['material']}: standard skin height input missing")
        x, y = base_x, base_y
        detail_graph = False
    else:
        raise Seal6LitNodeError(f"unsupported skin family {family!r}")

    nspec = _normal_from_xy(nodes, links, nbase, tangent, binormal, x, y, "T6_EXACT_NSPEC")
    dx = _math(nodes, links, "MULTIPLY", x, height, label="T6 exact diffuse normal X*height")
    dy = _math(nodes, links, "MULTIPLY", y, height, label="T6 exact diffuse normal Y*height")
    ndiff = _normal_from_xy(nodes, links, nbase, tangent, binormal, dx, dy, "T6_EXACT_NDIFF")

    # Material-local specular/reflection terms which do not require the unresolved
    # runtime lighting/probe resources.  They are intentionally not connected to
    # Principled physical parameters.
    _sep, _sr, _sg, _sb = _separate_rgb(nodes, links, _socket(specular.outputs, "Color"),
                                         "T6 SpecularAndGloss RGB")
    alpha = _socket(specular.outputs, "Alpha")
    alpha13 = _math(nodes, links, "MULTIPLY", alpha, 13.0, label="T6 13*SpecularAndGloss.a")
    p_node = nodes.new("ShaderNodeMath")
    p_node.operation = "POWER"
    p_node.label = "T6 P = exp2(13*SpecularAndGloss.a)"
    p_node.inputs[0].default_value = 2.0
    links.new(alpha13, p_node.inputs[1])
    p_node.name = "T6_EXACT_SPECULAR_P"
    p0 = _math(nodes, links, "MULTIPLY", alpha, 1.0416667461395263671875, label="T6 reflection p0")
    p1 = _math(nodes, links, "MULTIPLY", alpha, 0.4749999940395355224609375, label="T6 reflection p1")
    p2 = _math(nodes, links, "ADD",
               _math(nodes, links, "MULTIPLY", alpha, 0.01822919957339763641357421875,
                     label="T6 reflection p2 mul"),
               -0.015625, label="T6 reflection p2")
    p3 = _math(nodes, links, "ADD",
               _math(nodes, links, "MULTIPLY", alpha, 0.25, label="T6 reflection p3 mul"),
               0.75, label="T6 reflection p3")
    lod = _math(nodes, links, "ADD",
                _math(nodes, links, "MULTIPLY", alpha, -4.0, label="T6 reflection -4*a"),
                4.0, label="T6 reflection probe LOD = 4-4*a")
    for socket, name in ((p0, "T6_EXACT_REFLECTION_P0"), (p1, "T6_EXACT_REFLECTION_P1"),
                         (p2, "T6_EXACT_REFLECTION_P2"), (p3, "T6_EXACT_REFLECTION_P3"),
                         (lod, "T6_EXACT_REFLECTION_LOD")):
        if getattr(socket, "node", None) is not None:
            socket.node.name = name
    reflection_amount = constants.get("Reflection_Amount")
    if reflection_amount is None:
        raise Seal6LitNodeError(f"{plan['material']}: Reflection_Amount missing")
    reflection_weight = _math(nodes, links, "MULTIPLY", vertex_alpha, reflection_amount,
                              label="T6 exact vertexColor.a*Reflection_Amount")
    reflection_weight.node.name = "T6_EXACT_REFLECTION_WEIGHT"

    return {
        "linearLike": linear_like,
        "Nspec": nspec,
        "Ndiff": ndiff,
        "heroDetailNormal": detail_graph,
    }


def _cornea_local_graph(nodes, links, plan: dict[str, Any], source_by_arg: dict[str, Any], constants: dict[str, Any], frame):
    mask = source_by_arg.get("Mask")
    surface = source_by_arg.get("Surface_Normal_Map")
    if mask is None or surface is None:
        raise Seal6LitNodeError(f"{plan['material']}: cornea lacks Mask/Surface_Normal_Map")
    for required in (
        "Hightlight_1_Size", "Highlight_2_Brightness", "Highlight_1_Sharpness",
        "Highlight_2_Size", "Highlight_2_Sharpness", "Highlight_1_Brightness",
        "OverallBrightness", "Fill_Direction", "Fill_Direction2",
    ):
        if required not in constants:
            raise Seal6LitNodeError(f"{plan['material']}: cornea constant {required!r} missing")

    nbase, tangent, binormal = _exact_basis(nodes, links)
    x, y = _normal_xy(nodes, links, surface, "T6 cornea Surface_Normal_Map")
    nsurface = _normal_from_xy(nodes, links, nbase, tangent, binormal, x, y, "T6_EXACT_CORNEA_NSURFACE")
    _mask_sep, mask_r, _mg, _mb = _separate_rgb(nodes, links, _socket(mask.outputs, "Color"), "T6 cornea Mask.r")
    mask_r.node.name = "T6_EXACT_CORNEA_MASK_R"
    brightness = _math(nodes, links, "MULTIPLY", constants["OverallBrightness"], constants["OverallBrightness"],
                       label="T6 exact cornea OverallBrightness^2")
    brightness.node.name = "T6_EXACT_CORNEA_BRIGHTNESS2"

    # Precompute the constant-only half of both exact highlight windows.  The
    # remaining power/side terms require Nsurface plus F1/F2, and F1/F2 remain
    # gated on exact inverse-view transport rather than approximated from Blender
    # camera vectors.
    for index, (size_name, sharp_name, bright_name) in enumerate((
        ("Hightlight_1_Size", "Highlight_1_Sharpness", "Highlight_1_Brightness"),
        ("Highlight_2_Size", "Highlight_2_Sharpness", "Highlight_2_Brightness"),
    ), start=1):
        a = _math(nodes, links, "SUBTRACT", 1.0, constants[sharp_name], label=f"T6 cornea lobe{index} a=1-Sharpness")
        delta = _math(nodes, links, "MULTIPLY", a, 0.180000007152557373046875,
                      label=f"T6 cornea lobe{index} 0.18*a")
        lower = _math(nodes, links, "SUBTRACT", 0.7200000286102294921875, delta,
                      label=f"T6 cornea lobe{index} lower")
        upper = _math(nodes, links, "ADD", 0.7200000286102294921875, delta,
                      label=f"T6 cornea lobe{index} upper")
        lower.node.name = f"T6_EXACT_CORNEA_LOBE{index}_LOWER"
        upper.node.name = f"T6_EXACT_CORNEA_LOBE{index}_UPPER"
        constants[size_name].node["t6_cornea_highlight_role"] = f"lobe{index}-size"
        constants[bright_name].node["t6_cornea_highlight_role"] = f"lobe{index}-brightness"

    return {"Nsurface": nsurface, "maskR": mask_r, "brightness2": brightness}


def validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("format") != PLAN_FORMAT:
        raise Seal6LitNodeError(f"unsupported shader plan {plan.get('format')!r}")
    summary = plan.get("summary") or {}
    checks = {
        "targetMaterials": EXPECTED["materials"],
        "nativeTextureSlotsPreserved": EXPECTED["nativeSlots"],
        "ordinaryLitReferencedTextureSlots": EXPECTED["litSlots"],
        "preservedNativeTextureSlotsNotReferencedByOrdinaryLit": EXPECTED["preservedNonLit"],
        "nativeMaterialConstants": EXPECTED["constants"],
        "exactVsPsMaterialArgumentBindings": EXPECTED["argumentBindings"],
    }
    for key, expected in checks.items():
        if int(summary.get(key, -1)) != expected:
            raise Seal6LitNodeError(f"shader plan {key}={summary.get(key)!r}, expected {expected}")
    if summary.get("allOrdinaryLitMaterialArgumentsClosed") is not True:
        raise Seal6LitNodeError("shader plan does not close all ordinary-lit Material arguments")
    if summary.get("exactOrdinaryLitEquationsClosed") is not True:
        raise Seal6LitNodeError("shader plan does not close exact ordinary-lit equations")
    if summary.get("globalRuntimeLightingInputsBoundInBlender") is not False:
        raise Seal6LitNodeError("v1 requires global runtime lighting inputs to remain unbound")
    if summary.get("completeRetailPixelOutputInBlender") is not False:
        raise Seal6LitNodeError("v1 must not claim complete retail pixel output")
    rows = plan.get("materials")
    if not isinstance(rows, list) or len(rows) != EXPECTED["materials"]:
        raise Seal6LitNodeError("shader plan materials[] malformed")


def compile_material(material, plan: dict[str, Any]) -> dict[str, Any]:
    _require_bpy()
    if material.get("t6_role_complete_native_inputs") is not True:
        raise Seal6LitNodeError(f"{material.name}: role-complete native inputs were not compiled first")
    if material.get("t6_complete_retail_pixel_output") is not False:
        raise Seal6LitNodeError(f"{material.name}: unexpected pre-existing complete-retail claim")
    tree = material.node_tree
    if tree is None:
        raise Seal6LitNodeError(f"{material.name}: no Blender node tree")
    nodes, links = tree.nodes, tree.links

    source_frame = nodes.get("T6_EXACT_NATIVE_SOURCE_SLOTS")
    preview = nodes.get("T6_AUTHORING_PREVIEW_BSDF")
    output = nodes.get("T6_AUTHORING_OUTPUT")
    if source_frame is None or preview is None or output is None:
        raise Seal6LitNodeError(f"{material.name}: role-node backend structure missing")

    exact_frame = nodes.new("NodeFrame")
    exact_frame.name = "T6_EXACT_ORDINARY_LIT_LOCAL_MATH"
    exact_frame.label = "EXACT T6 ORDINARY-LIT MATERIAL-LOCAL MATH"
    exact_frame.location = (100, -800)
    global_frame = nodes.new("NodeFrame")
    global_frame.name = "T6_UNRESOLVED_RETAIL_GLOBALS"
    global_frame.label = "RETAIL GLOBALS REQUIRED: lighting/probe/fog/HDR — NOT APPROXIMATED"
    global_frame.location = (650, -900)

    constants = _constant_nodes(nodes, exact_frame, list(plan.get("nativeConstants") or []))
    source_by_arg = {}
    referenced_count = 0
    preserved_count = 0
    for slot in plan.get("nativeTextureSlots") or []:
        index = int(slot.get("slotIndex", -1))
        node = _source_node(nodes, index)
        binding = slot.get("ordinaryLitBinding") or {}
        referenced = binding.get("referenced") is True
        node["t6_ordinary_lit_referenced"] = referenced
        node["t6_ordinary_lit_stage"] = str(binding.get("stage") or "")
        node["t6_ordinary_lit_argument"] = str(binding.get("shaderArgument") or "")
        if referenced:
            arg = str(binding.get("shaderArgument") or "")
            if not arg or arg in source_by_arg:
                raise Seal6LitNodeError(f"{material.name}: invalid/duplicate ordinary-lit texture argument {arg!r}")
            source_by_arg[arg] = node
            referenced_count += 1
            node.label = "LIT-REFERENCED | " + node.label
        else:
            preserved_count += 1
            node.label = "PRESERVED NON-LIT | " + node.label
            # Unreferenced native slots must stay disconnected from the exact lit
            # subgraph.  They may also not remain accidentally connected through
            # the old authoring preview.
            for link in list(node.outputs[0].links):
                if link.to_node == preview or link.to_node.name == "T6_AUTHORING_PREVIEW_NORMAL":
                    links.remove(link)

    family = str(plan.get("shaderFamilyId") or "")
    if family in {HERO, STANDARD}:
        local = _skin_local_graph(nodes, links, plan, source_by_arg, constants, exact_frame)
        _replace_input_link(links, _socket(preview.inputs, "Base Color"), local["linearLike"])
        _replace_input_link(links, _socket(preview.inputs, "Normal"), local["Ndiff"])
        preview.label = "AUTHORING SUBSTITUTE — exact T6 local diffuse/Ndiff; global retail lighting unresolved"
        old_normal = nodes.get("T6_AUTHORING_PREVIEW_NORMAL")
        if old_normal is not None:
            old_normal.label = "SUPERSEDED raw normal preview — exact T6 Ndiff/Nspec graphs now present"
        skin = True
        hero_detail = bool(local["heroDetailNormal"])
        cornea = False
    elif family == CORNEA:
        _cornea_local_graph(nodes, links, plan, source_by_arg, constants, exact_frame)
        preview.label = "CORNEA AUTHORING SUBSTITUTE — exact local mask/normal/brightness present; highlights/globals unresolved"
        skin = False
        hero_detail = False
        cornea = True
    else:
        raise Seal6LitNodeError(f"{material.name}: unsupported exact family {family!r}")

    material["t6_shader_backend"] = FORMAT
    material["t6_shader_family"] = family
    material["t6_exact_ordinary_lit_equations_closed"] = True
    material["t6_exact_material_local_nodes_compiled"] = True
    material["t6_ordinary_lit_referenced_texture_slots"] = referenced_count
    material["t6_preserved_nonlit_texture_slots"] = preserved_count
    material["t6_native_material_constant_count"] = len(constants)
    material["t6_global_runtime_lighting_inputs_bound"] = False
    material["t6_complete_retail_pixel_output"] = False
    material["t6_shader_identity_json"] = json.dumps(plan.get("shaderIdentity"), sort_keys=True)
    material["t6_global_runtime_dependencies_json"] = json.dumps(plan.get("globalRuntimeDependencies", []), sort_keys=True)
    material["t6_proof_boundary"] = (
        "Exact ordinary-lit material-local math is compiled from SHA-locked SEAL6 semantics. "
        "Native non-lit slots remain preserved. T6 runtime lighting/probe/fog/HDR are not approximated, "
        "so Blender Material Output remains an authoring substitute and complete retail output is false."
    )

    return {
        "material": str(plan.get("material") or ""),
        "shaderFamilyId": family,
        "nativeSourceNodesRetained": len(list(plan.get("nativeTextureSlots") or [])),
        "ordinaryLitReferencedSourceNodes": referenced_count,
        "preservedNonLitSourceNodes": preserved_count,
        "constantNodes": len(constants),
        "skinLocalDiffuseGraph": skin,
        "heroDetailNormalGraph": hero_detail,
        "corneaLocalGraph": cornea,
        "globalRuntimeLightingInputsBound": False,
        "completeRetailPixelOutput": False,
    }


def compile_plan(plan: dict[str, Any]) -> dict[str, Any]:
    _require_bpy()
    validate_plan(plan)
    rows = []
    for material_plan in plan["materials"]:
        material = _material_exact(str(material_plan.get("material") or ""))
        rows.append(compile_material(material, material_plan))
    summary = {
        "materialsCompiled": len(rows),
        "nativeSourceNodesRetained": sum(r["nativeSourceNodesRetained"] for r in rows),
        "ordinaryLitReferencedSourceNodes": sum(r["ordinaryLitReferencedSourceNodes"] for r in rows),
        "preservedNonLitSourceNodes": sum(r["preservedNonLitSourceNodes"] for r in rows),
        "constantNodes": sum(r["constantNodes"] for r in rows),
        "skinLocalDiffuseGraphs": sum(1 for r in rows if r["skinLocalDiffuseGraph"]),
        "heroDetailNormalGraphs": sum(1 for r in rows if r["heroDetailNormalGraph"]),
        "corneaLocalGraphs": sum(1 for r in rows if r["corneaLocalGraph"]),
        "allExactOrdinaryLitEquationsClosed": True,
        "globalRuntimeLightingInputsBound": False,
        "completeRetailPixelOutput": False,
    }
    expected = {
        "materialsCompiled": 5,
        "nativeSourceNodesRetained": 20,
        "ordinaryLitReferencedSourceNodes": 15,
        "preservedNonLitSourceNodes": 5,
        "constantNodes": 22,
        "skinLocalDiffuseGraphs": 4,
        "heroDetailNormalGraphs": 1,
        "corneaLocalGraphs": 1,
    }
    for key, value in expected.items():
        if summary[key] != value:
            raise Seal6LitNodeError(f"compiled summary {key}={summary[key]}, expected {value}")
    return {
        "format": FORMAT,
        "summary": summary,
        "materials": rows,
        "proofBoundary": plan.get("proofBoundary"),
        "globalRuntimeDependencies": plan.get("globalRuntimeDependencies", []),
        "forbiddenFallbacks": plan.get("forbiddenFallbacks", []),
    }


def _script_args(argv: list[str]) -> list[str]:
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args(_script_args(sys.argv))
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    result = compile_plan(plan)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
