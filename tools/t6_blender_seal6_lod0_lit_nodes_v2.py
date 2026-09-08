#!/usr/bin/env python3
"""Lower exact ordinary-lit material-local math for all 12 SEAL6 LOD0 Materials.

The existing five-material hero/standard/cornea backend remains authoritative for
those families. This adapter reuses it unchanged and adds only the independently
closed cloth family. Runtime-global model lighting, reflection probes, SH/sun,
fog and HDR remain explicitly unbound.
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

import t6_blender_seal6_lit_nodes_v1 as char

PLAN_FORMAT = "t6-seal6-lod0-blender-shader-plan-v2"
FORMAT = "t6-blender-seal6-lod0-lit-nodes-v2"
CLOTH = "seal6-char-cloth-lit-v1"
CHAR_FAMILIES = {char.HERO, char.STANDARD, char.CORNEA}


class Seal6Lod0LitNodeError(RuntimeError):
    pass


def _require_bpy() -> None:
    if bpy is None:
        raise Seal6Lod0LitNodeError("bpy unavailable; run inside Blender")


def _material_exact(name: str):
    exact = bpy.data.materials.get(name)
    if exact is not None:
        return exact
    matches = [m for m in bpy.data.materials if m.name == name or m.name.startswith(name + ".")]
    if len(matches) != 1:
        raise Seal6Lod0LitNodeError(f"exact Material {name!r} is not uniquely present")
    return matches[0]


def _source_any(nodes, slot_index: int):
    prefix = f"T6_SLOT_{slot_index:02d}_"
    matches = [n for n in nodes if n.name.startswith(prefix)]
    if len(matches) != 1:
        raise Seal6Lod0LitNodeError(f"native slot {slot_index} maps to {len(matches)} role nodes")
    return matches[0]


def validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("format") != PLAN_FORMAT:
        raise Seal6Lod0LitNodeError(f"unsupported shader plan {plan.get('format')!r}")
    s = plan.get("summary") or {}
    expected = {
        "targetMaterials": 12,
        "nativeTextureSlotsPreserved": 41,
        "ordinaryLitReferencedTextureSlots": 36,
        "preservedNativeTextureSlotsNotReferencedByOrdinaryLit": 5,
        "nativeMaterialConstants": 22,
        "exactVsPsMaterialArgumentBindings": 58,
        "clothMaterials": 7,
        "characterSpecializedMaterials": 5,
    }
    for key, value in expected.items():
        if int(s.get(key, -1)) != value:
            raise Seal6Lod0LitNodeError(f"shader plan {key}={s.get(key)!r} != {value}")
    if s.get("allOrdinaryLitMaterialArgumentsClosed") is not True or s.get("exactOrdinaryLitEquationsClosed") is not True:
        raise Seal6Lod0LitNodeError("shader plan has not closed ordinary-lit ABI/equations")
    if s.get("globalRuntimeLightingInputsBoundInBlender") is not False or s.get("completeRetailPixelOutputInBlender") is not False:
        raise Seal6Lod0LitNodeError("runtime-global proof boundary drift")
    rows = plan.get("materials")
    if not isinstance(rows, list) or len(rows) != 12:
        raise Seal6Lod0LitNodeError("shader plan materials[] malformed")
    fams = [str(r.get("shaderFamilyId") or "") for r in rows]
    if fams.count(CLOTH) != 7 or sum(f in CHAR_FAMILIES for f in fams) != 5:
        raise Seal6Lod0LitNodeError("shader-family population drift")


def _literal_unit(nodes, frame, name: str, y: float):
    node = nodes.new("ShaderNodeValue")
    node.name = f"T6_EXEC_LITERAL_UNIT_{name}"
    node.label = f"exact executable literal {name} = 1.0 (not a Material constant)"
    node.outputs[0].default_value = 1.0
    node.location = (-100, y)
    node.parent = frame
    node["t6_shader_executable_literal"] = name
    node["t6_literal_source"] = "SHA-pinned cloth pixel shader instruction stream"
    node["t6_not_native_material_constant"] = True
    return node.outputs[0]


def _compile_cloth(material, plan: dict[str, Any]) -> dict[str, Any]:
    if material.get("t6_role_complete_native_inputs") is not True:
        raise Seal6Lod0LitNodeError(f"{material.name}: exact role nodes must be compiled first")
    tree = material.node_tree
    if tree is None:
        raise Seal6Lod0LitNodeError(f"{material.name}: no node tree")
    nodes, links = tree.nodes, tree.links
    preview = nodes.get("T6_AUTHORING_PREVIEW_BSDF")
    output = nodes.get("T6_AUTHORING_OUTPUT")
    source_frame = nodes.get("T6_EXACT_NATIVE_SOURCE_SLOTS")
    if preview is None or output is None or source_frame is None:
        raise Seal6Lod0LitNodeError(f"{material.name}: role-node structure missing")

    exact_frame = nodes.new("NodeFrame")
    exact_frame.name = "T6_EXACT_ORDINARY_LIT_LOCAL_MATH"
    exact_frame.label = "EXACT T6 CLOTH ORDINARY-LIT MATERIAL-LOCAL MATH"
    exact_frame.location = (100, -800)
    global_frame = nodes.new("NodeFrame")
    global_frame.name = "T6_UNRESOLVED_RETAIL_GLOBALS"
    global_frame.label = "RETAIL GLOBALS REQUIRED: model-lighting/probe/SH/sun/fog/HDR — NOT APPROXIMATED"
    global_frame.location = (700, -900)

    source_by_arg = {}
    for slot in plan.get("nativeTextureSlots") or []:
        node = _source_any(nodes, int(slot.get("slotIndex", -1)))
        binding = slot.get("ordinaryLitBinding") or {}
        if binding.get("referenced") is not True:
            raise Seal6Lod0LitNodeError(f"{material.name}: cloth has unexpected preserved non-lit slot")
        arg = str(binding.get("shaderArgument") or "")
        if not arg or arg in source_by_arg or node.bl_idname != "ShaderNodeTexImage":
            raise Seal6Lod0LitNodeError(f"{material.name}: invalid exact cloth source {arg!r}")
        source_by_arg[arg] = node
        node["t6_ordinary_lit_referenced"] = True
        node["t6_ordinary_lit_argument"] = arg
        node["t6_ordinary_lit_stage"] = "pixel"
        node.label = "LIT-REFERENCED | " + node.label
    if set(source_by_arg) != {"SpecularAndGloss", "Normal_Map", "Diffuse_Map"}:
        raise Seal6Lod0LitNodeError(f"{material.name}: exact cloth texture ABI drift")
    if plan.get("nativeConstants") != []:
        raise Seal6Lod0LitNodeError(f"{material.name}: cloth must have zero native Material constants")

    diffuse = source_by_arg["Diffuse_Map"]
    normal = source_by_arg["Normal_Map"]
    specular = source_by_arg["SpecularAndGloss"]

    color_node, vertex_rgb, vertex_alpha = char.lprobe._attr_color(
        nodes, "_T6_COLOR_RGBA", "T6 exact SEAL6 cloth vertex color shader data"
    )
    color_node.name = "T6_EXACT_VERTEX_COLOR_RGBA"
    color_node.parent = exact_frame
    vc2 = char.lprobe._vector_mul(nodes, links, vertex_rgb, vertex_rgb, "T6 exact vertexColor.rgb^2")
    encoded = char.lprobe._vector_mul(nodes, links, char._socket(diffuse.outputs, "Color"), vc2,
                                      "T6 exact encoded = Diffuse_Map.rgb * vertexColor.rgb^2")
    linear_like = char.lprobe._vector_mul(nodes, links, encoded, encoded, "T6 exact linearLike = encoded^2")
    linear_like.node.name = "T6_EXACT_CLOTH_LINEARLIKE_RGB"

    nbase, tangent, binormal = char._exact_basis(nodes, links)
    x, y = char._normal_xy(nodes, links, normal, "T6 cloth Normal_Map")
    nlighting = char._normal_from_xy(nodes, links, nbase, tangent, binormal, x, y, "T6_EXACT_CLOTH_NLIGHTING")
    # Retail cloth uses the exact same normalized decoded normal for both paths.
    nlighting.node["t6_exact_aliases"] = "Ndiff=Nspec=Nlighting"

    height_unit = _literal_unit(nodes, exact_frame, "Diffuse_Normal_Height_Facing", -100)
    spec_unit = _literal_unit(nodes, exact_frame, "Specular_Amount", -300)
    reflection_unit = _literal_unit(nodes, exact_frame, "Reflection_Amount", -500)
    for socket in (height_unit, spec_unit, reflection_unit):
        socket.node["t6_exact_unit_control"] = True

    # Material-local specular/reflection coefficient arithmetic from the exact
    # cloth PS. Runtime light/view/probe inputs remain deliberately absent.
    alpha = char._socket(specular.outputs, "Alpha")
    alpha13 = char._math(nodes, links, "MULTIPLY", alpha, 13.0, label="T6 cloth 13*SpecularAndGloss.a")
    p_node = nodes.new("ShaderNodeMath")
    p_node.operation = "POWER"
    p_node.label = "T6 cloth P = exp2(13*SpecularAndGloss.a)"
    p_node.inputs[0].default_value = 2.0
    links.new(alpha13, p_node.inputs[1])
    p_node.name = "T6_EXACT_SPECULAR_P"
    coeffs = (
        ("T6_EXACT_REFLECTION_P0", "MULTIPLY", 1.0416667461395263671875, 0.0),
        ("T6_EXACT_REFLECTION_P1", "MULTIPLY", 0.4749999940395355224609375, 0.0),
        ("T6_EXACT_REFLECTION_P2", "ADD_AFTER_MUL", 0.01822919957339763641357421875, -0.015625),
        ("T6_EXACT_REFLECTION_P3", "ADD_AFTER_MUL", 0.25, 0.75),
    )
    for name, mode, mul, add in coeffs:
        value = char._math(nodes, links, "MULTIPLY", alpha, mul, label=f"{name} mul")
        if mode == "ADD_AFTER_MUL":
            value = char._math(nodes, links, "ADD", value, add, label=name)
        value.node.name = name
    lod = char._math(nodes, links, "ADD", char._math(nodes, links, "MULTIPLY", alpha, -4.0,
                                                      label="T6 cloth reflection -4*a"), 4.0,
                     label="T6 cloth reflection LOD = 4-4*a")
    lod.node.name = "T6_EXACT_REFLECTION_LOD"
    reflection_weight = char._math(nodes, links, "MULTIPLY", vertex_alpha, reflection_unit,
                                   label="T6 exact cloth vertexColor.a*1.0 reflection weight")
    reflection_weight.node.name = "T6_EXACT_REFLECTION_WEIGHT"

    char._replace_input_link(links, char._socket(preview.inputs, "Base Color"), linear_like)
    char._replace_input_link(links, char._socket(preview.inputs, "Normal"), nlighting)
    preview.label = "AUTHORING SUBSTITUTE — exact cloth local diffuse/Nlighting; runtime globals unresolved"
    old_normal = nodes.get("T6_AUTHORING_PREVIEW_NORMAL")
    if old_normal is not None:
        old_normal.label = "SUPERSEDED raw preview — exact cloth Ndiff=Nspec=Nlighting present"

    material["t6_shader_backend"] = FORMAT
    material["t6_shader_family"] = CLOTH
    material["t6_exact_ordinary_lit_equations_closed"] = True
    material["t6_exact_material_local_nodes_compiled"] = True
    material["t6_ordinary_lit_referenced_texture_slots"] = 3
    material["t6_preserved_nonlit_texture_slots"] = 0
    material["t6_native_material_constant_count"] = 0
    material["t6_executable_literal_unit_control_count"] = 3
    material["t6_global_runtime_lighting_inputs_bound"] = False
    material["t6_complete_retail_pixel_output"] = False
    material["t6_shader_identity_json"] = json.dumps(plan.get("shaderIdentity"), sort_keys=True)

    return {
        "material": str(plan.get("material") or ""),
        "shaderFamilyId": CLOTH,
        "nativeSourceNodesRetained": 3,
        "ordinaryLitReferencedSourceNodes": 3,
        "preservedNonLitSourceNodes": 0,
        "constantNodes": 0,
        "executableLiteralUnitNodes": 3,
        "skinLocalDiffuseGraph": False,
        "clothLocalDiffuseGraph": True,
        "heroDetailNormalGraph": False,
        "corneaLocalGraph": False,
        "globalRuntimeLightingInputsBound": False,
        "completeRetailPixelOutput": False,
    }


def compile_plan(plan: dict[str, Any]) -> dict[str, Any]:
    _require_bpy()
    validate_plan(plan)
    # v1 looked only for image nodes because all twenty of its source slots were
    # streamed. v2 has one exact built-in alias, so allow any unique exact slot
    # node; the alias is non-lit and therefore never consumed as a texture.
    char._source_node = _source_any

    rows = []
    for material_plan in plan["materials"]:
        material = _material_exact(str(material_plan.get("material") or ""))
        family = str(material_plan.get("shaderFamilyId") or "")
        if family == CLOTH:
            row = _compile_cloth(material, material_plan)
        elif family in CHAR_FAMILIES:
            row = char.compile_material(material, material_plan)
            row["clothLocalDiffuseGraph"] = False
            row["executableLiteralUnitNodes"] = 0
            material["t6_shader_backend"] = FORMAT
        else:
            raise Seal6Lod0LitNodeError(f"{material.name}: unsupported exact family {family!r}")
        rows.append(row)

    summary = {
        "materialsCompiled": len(rows),
        "nativeSourceNodesRetained": sum(r["nativeSourceNodesRetained"] for r in rows),
        "ordinaryLitReferencedSourceNodes": sum(r["ordinaryLitReferencedSourceNodes"] for r in rows),
        "preservedNonLitSourceNodes": sum(r["preservedNonLitSourceNodes"] for r in rows),
        "nativeConstantNodes": sum(r["constantNodes"] for r in rows),
        "executableLiteralUnitNodes": sum(r["executableLiteralUnitNodes"] for r in rows),
        "skinLocalDiffuseGraphs": sum(1 for r in rows if r["skinLocalDiffuseGraph"]),
        "clothLocalDiffuseGraphs": sum(1 for r in rows if r["clothLocalDiffuseGraph"]),
        "heroDetailNormalGraphs": sum(1 for r in rows if r["heroDetailNormalGraph"]),
        "corneaLocalGraphs": sum(1 for r in rows if r["corneaLocalGraph"]),
        "allExactOrdinaryLitEquationsClosed": True,
        "globalRuntimeLightingInputsBound": False,
        "completeRetailPixelOutput": False,
    }
    expected = {
        "materialsCompiled": 12,
        "nativeSourceNodesRetained": 41,
        "ordinaryLitReferencedSourceNodes": 36,
        "preservedNonLitSourceNodes": 5,
        "nativeConstantNodes": 22,
        "executableLiteralUnitNodes": 21,
        "skinLocalDiffuseGraphs": 4,
        "clothLocalDiffuseGraphs": 7,
        "heroDetailNormalGraphs": 1,
        "corneaLocalGraphs": 1,
        "allExactOrdinaryLitEquationsClosed": True,
        "globalRuntimeLightingInputsBound": False,
        "completeRetailPixelOutput": False,
    }
    if summary != expected:
        raise Seal6Lod0LitNodeError(f"compiled summary drift: {summary!r}")
    return {"format": FORMAT, "summary": summary, "materials": rows, "proofBoundary": plan.get("proofBoundary")}


def _script_args(argv: list[str]) -> list[str]:
    return argv[argv.index("--")+1:] if "--" in argv else argv[1:]


def main() -> int:
    _require_bpy()
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args(_script_args(sys.argv))
    plan = json.loads(a.plan.read_text(encoding="utf-8-sig"))
    result = compile_plan(plan)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print("T6_SEAL6_LOD0_LIT_NODES_V2="+json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
