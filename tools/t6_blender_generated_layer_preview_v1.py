#!/usr/bin/env python3
"""Build source-backed T6 generated-world layer previews inside Blender.

This is a Blender/Tour authoring adapter, not a claim of complete retail
lighting parity. It reconstructs the source-closed generated diffuse compositor
in the retail encoded texture domain, applies the shader's explicit RGB square,
and then hands that result to Blender's ordinary Principled lighting so artists
can finally SEE secondary T6 layers while the later lightmap/reflection path is
still being reproduced.

The adapter is deliberately fail-closed:
- material/image joins are exact source identities from GLB extras;
- A/B/M/T operations come from the exact generated TechniqueSet;
- alpha/vertex/x/threshold weight classes use the recovered retail dispatcher;
- vN height layers are refused unless a future exact Blender DAG compiler is
  attached. No generic height-blend approximation is used;
- layered specular dependencies are preserved and tagged, but are NOT mapped to
  Principled specular/roughness because that would invent a PBR conversion.

It accepts the generated TechniqueSet either from material extras or an optional
sidecar. Sidecar format:

  {
    "format": "t6-generated-world-shader-recipes-v1",
    "materials": [
      {"material": "*...", "techniqueSet": "lit_sm_..."}
    ]
  }

Run from Blender, for example:

  blender --background --python tools/t6_blender_generated_layer_preview_v1.py -- \
      input.glb output.blend --recipes generated_recipes.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

try:
    import bpy  # type: ignore
except ImportError:  # permits syntax/import checks outside Blender
    bpy = None

from t6_generated_world_shader_semantics_v1 import (
    parse_generated_layer_tokens,
    layer_weight_class,
)


class BlenderLayerPreviewError(RuntimeError):
    pass


WEIGHT_OUTPUT = {1: "G", 2: "B", 3: "A"}
UV_MAP = {0: "UVMap", 1: "UVMap.002", 2: "UVMap.003", 3: "UVMap.004"}
RECIPE_KEYS = (
    "generatedShaderRecipeV1",
    "generatedShaderRecipe",
    "retailShaderRecipe",
    "shaderRecipe",
)


def _read_gltf_json(path: Path) -> dict:
    data = path.read_bytes()
    if path.suffix.lower() == ".gltf":
        return json.loads(data.decode("utf-8"))
    if path.suffix.lower() != ".glb":
        raise BlenderLayerPreviewError("input must be .glb or .gltf")
    if len(data) < 20 or data[:4] != b"glTF":
        raise BlenderLayerPreviewError("invalid GLB header")
    version, total = struct.unpack_from("<II", data, 4)
    if version != 2 or total != len(data):
        raise BlenderLayerPreviewError("unsupported/corrupt GLB")
    off = 12
    while off + 8 <= len(data):
        length, kind = struct.unpack_from("<II", data, off)
        off += 8
        chunk = data[off:off + length]
        off += length
        if kind == 0x4E4F534A:  # JSON
            return json.loads(chunk.rstrip(b" \t\r\n\0").decode("utf-8"))
    raise BlenderLayerPreviewError("GLB has no JSON chunk")


def _recipe_map(sidecar: Path | None) -> dict[str, dict]:
    if sidecar is None:
        return {}
    doc = json.loads(sidecar.read_text(encoding="utf-8"))
    if doc.get("format") != "t6-generated-world-shader-recipes-v1":
        raise BlenderLayerPreviewError(f"unsupported recipe sidecar {doc.get('format')!r}")
    out: dict[str, dict] = {}
    for row in doc.get("materials", []):
        name = str(row.get("material") or "")
        technique = str(row.get("techniqueSet") or "")
        if not name or not technique:
            raise BlenderLayerPreviewError("recipe sidecar contains empty material/techniqueSet")
        if name in out:
            raise BlenderLayerPreviewError(f"duplicate recipe material {name!r}")
        out[name] = row
    return out


def _embedded_dependencies(t6: dict) -> list[dict]:
    rows = t6.get("embeddedDependencyTextures")
    if isinstance(rows, list):
        return rows
    graph = t6.get("materialDependencyGraph")
    if isinstance(graph, dict):
        out: list[dict] = []
        for layer in graph.get("layers", []):
            li = int(layer.get("layerIndex", 0))
            for dep in layer.get("textures", []):
                out.append({
                    "layerIndex": li,
                    "layer": layer.get("layer"),
                    "role": dep.get("role"),
                    "semantic": dep.get("semantic"),
                    "sourceTexture": dep.get("sourceTexture"),
                    "generatedTextureIndex": dep.get("textureIndex"),
                })
        return out
    return []


def _material_technique(name: str, t6: dict, sidecars: dict[str, dict]) -> tuple[str | None, dict | None]:
    row = sidecars.get(name)
    if row is not None:
        return str(row["techniqueSet"]), row
    for key in RECIPE_KEYS:
        candidate = t6.get(key)
        if isinstance(candidate, dict) and candidate.get("techniqueSet"):
            return str(candidate["techniqueSet"]), candidate
    direct = t6.get("techniqueSet")
    if isinstance(direct, str) and direct:
        return direct, None
    return None, None


def _role_dependency(deps: list[dict], layer: int, role: str) -> dict | None:
    matches = [
        row for row in deps
        if int(row.get("layerIndex", -1)) == layer
        and str(row.get("semantic") or row.get("role") or "") == role
    ]
    if len(matches) > 1:
        raise BlenderLayerPreviewError(f"layer {layer}: ambiguous {role} dependencies")
    return matches[0] if matches else None


def _source(dep: dict | None, *, material: str, layer: int, role: str, required: bool) -> str | None:
    if dep is None:
        if required:
            raise BlenderLayerPreviewError(f"{material!r} layer {layer} lacks exact {role}")
        return None
    source = str(dep.get("sourceTexture") or "")
    if not source:
        raise BlenderLayerPreviewError(f"{material!r} layer {layer} {role} has empty sourceTexture")
    return source


def _image_cache_key(source: str, role: str) -> str:
    # Color, normal and specular are all sampled as data for the recovered T6
    # equations. Keeping a role-specific duplicate avoids mutating an imported
    # image's colorspace globally when the same image identity is reused.
    return f"{source}__T6_{role}_DATA"


def _data_image(source: str, role: str, cache: dict[tuple[str, str], object]):
    key = (source, role)
    if key in cache:
        return cache[key]
    original = bpy.data.images.get(source)
    if original is None:
        # Blender may suffix datablock names. Exact source identity is retained
        # in the prefix; accept only one unambiguous candidate.
        candidates = [img for img in bpy.data.images if img.name == source or img.name.startswith(source + ".")]
        if len(candidates) != 1:
            raise BlenderLayerPreviewError(f"embedded image {source!r} not uniquely present after glTF import")
        original = candidates[0]
    image = original.copy()
    image.name = _image_cache_key(source, role)
    try:
        image.colorspace_settings.name = "Non-Color"
    except Exception as exc:
        raise BlenderLayerPreviewError(f"cannot set Non-Color for {source!r}: {exc}") from exc
    cache[key] = image
    return image


def _new_tex(nodes, source: str, role: str, layer: int, image_cache: dict):
    node = nodes.new("ShaderNodeTexImage")
    node.label = f"T6 L{layer} {role}: {source}"
    node.name = f"T6_L{layer}_{role}"
    node.image = _data_image(source, role, image_cache)
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = UV_MAP[layer]
    uv.label = f"T6 material UV{layer}"
    node.inputs["Vector"].default_value = (0.0, 0.0, 0.0)
    return node, uv


def _wire_tex(nodes, links, source: str, role: str, layer: int, image_cache: dict):
    tex, uv = _new_tex(nodes, source, role, layer, image_cache)
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    return tex


def _weight_attribute(nodes):
    attr = nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "_T6_LAYER_WEIGHTS"
    attr.label = "T6 exact layer controls"
    sep = nodes.new("ShaderNodeSeparateRGB")
    sep.label = "T6 G/B controls"
    attr_color = attr.outputs.get("Color")
    if attr_color is None:
        raise BlenderLayerPreviewError("Blender Attribute node has no Color output")
    return attr, sep


def _vertex_weight_socket(nodes, links, attr, sep, layer: int):
    channel = WEIGHT_OUTPUT.get(layer)
    if channel is None:
        raise BlenderLayerPreviewError(f"unsupported generated layer index {layer}")
    links.new(attr.outputs["Color"], sep.inputs["Image"])
    if channel in ("G", "B"):
        return sep.outputs[channel]
    return attr.outputs["Alpha"]


def _mul(nodes, links, a, b, label: str):
    n = nodes.new("ShaderNodeMath")
    n.operation = "MULTIPLY"
    n.label = label
    links.new(a, n.inputs[0]); links.new(b, n.inputs[1])
    return n.outputs[0]


def _threshold_ge_half(nodes, links, scalar, label: str):
    # Blender LESS_THAN gives 1 for x < 0.5. Subtract from 1 to reproduce >=.
    lt = nodes.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    lt.inputs[1].default_value = 0.5
    lt.label = label + " < 0.5"
    links.new(scalar, lt.inputs[0])
    inv = nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    inv.label = label + " >= 0.5"
    links.new(lt.outputs[0], inv.inputs[1])
    return inv.outputs[0]


def _exact_weight(nodes, links, token, color_tex, attr, sep):
    vertex = _vertex_weight_socket(nodes, links, attr, sep, token.layer)
    cls = layer_weight_class(token)
    if cls == "vertex_only":
        return vertex
    if cls == "alpha_vertex":
        return _mul(nodes, links, color_tex.outputs["Alpha"], vertex, f"T6 L{token.layer} alpha*vertex")
    if cls == "threshold_alpha_vertex":
        product = _mul(nodes, links, color_tex.outputs["Alpha"], vertex, f"T6 L{token.layer} threshold product")
        return _threshold_ge_half(nodes, links, product, f"T6 L{token.layer} threshold")
    if cls == "height":
        raise BlenderLayerPreviewError(
            f"layer {token.layer} is vN height-weighted; exact retained DAG execution is required"
        )
    raise BlenderLayerPreviewError(f"unknown T6 weight class {cls!r}")


def _compose(nodes, links, previous, layer_color, factor, operation: str, layer: int):
    mix = nodes.new("ShaderNodeMixRGB")
    mix.use_clamp = False
    mix.label = f"T6 exact L{layer} {operation}"
    if operation == "add":
        mix.blend_type = "ADD"
    elif operation == "blend":
        mix.blend_type = "MIX"
    elif operation == "multiply":
        mix.blend_type = "MULTIPLY"
    elif operation == "threshold":
        mix.blend_type = "MIX"
    else:
        raise BlenderLayerPreviewError(f"unsupported operation {operation!r}")
    links.new(factor, mix.inputs["Fac"])
    links.new(previous, mix.inputs[1])
    links.new(layer_color, mix.inputs[2])
    return mix.outputs["Color"]


def _square_rgb(nodes, links, encoded_rgb):
    square = nodes.new("ShaderNodeVectorMath")
    square.operation = "MULTIPLY"
    square.label = "T6 encoded RGB square (retail shader)"
    links.new(encoded_rgb, square.inputs[0])
    links.new(encoded_rgb, square.inputs[1])
    return square.outputs["Vector"]


def _build_material(blender_material, gltf_material: dict, technique: str, recipe: dict | None, image_cache: dict) -> dict:
    t6 = gltf_material.get("extras", {}).get("T6", {})
    deps = _embedded_dependencies(t6)
    tokens = parse_generated_layer_tokens(technique)
    if not tokens:
        raise BlenderLayerPreviewError("TechniqueSet contains no secondary generated layers")

    base_dep = _role_dependency(deps, 0, "colorMap")
    base_source = _source(base_dep, material=blender_material.name, layer=0, role="colorMap", required=True)

    # Verify every color dependency before replacing the material graph.
    layer_sources: dict[int, str] = {}
    for token in tokens:
        dep = _role_dependency(deps, token.layer, "colorMap")
        layer_sources[token.layer] = _source(
            dep, material=blender_material.name, layer=token.layer, role="colorMap", required=True
        )
        if token.height_variant:
            raise BlenderLayerPreviewError(
                f"TechniqueSet {technique!r} uses v{token.layer}; exact height DAG is preserved but not yet executable in Blender v1"
            )

    blender_material.use_nodes = True
    tree = blender_material.node_tree
    nodes, links = tree.nodes, tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (900, 0)
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (650, 0)
    principled.label = "Blender lighting preview ONLY"
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    base_tex = _wire_tex(nodes, links, base_source, "colorMap", 0, image_cache)
    base_tex.location = (-1200, 250)
    composed = base_tex.outputs["Color"]

    attr, sep = _weight_attribute(nodes)
    attr.location = (-1200, -350)
    sep.location = (-1000, -350)

    layer_nodes = []
    for order, token in enumerate(tokens):
        tex = _wire_tex(nodes, links, layer_sources[token.layer], "colorMap", token.layer, image_cache)
        tex.location = (-950 + order * 40, 250 - token.layer * 180)
        factor = _exact_weight(nodes, links, token, tex, attr, sep)
        composed = _compose(nodes, links, composed, tex.outputs["Color"], factor, token.operation, token.layer)
        layer_nodes.append({
            "layer": token.layer,
            "operation": token.operation,
            "weightClass": layer_weight_class(token),
            "hasNormal": token.has_normal,
            "hasSpecular": token.has_specular,
        })

    linear_preview = _square_rgb(nodes, links, composed)
    links.new(linear_preview, principled.inputs["Base Color"])

    # Keep standard preview lighting neutral. Exact T6 lightmap/reflection/specular
    # are intentionally NOT fabricated through Principled controls.
    if "Metallic" in principled.inputs:
        principled.inputs["Metallic"].default_value = 0.0
    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.5

    # Preserve exact dependency identity for the seven/etc. layered-spec cases;
    # v1 does not pretend their XYZW state is a Principled roughness workflow.
    spec_sources = []
    normal_sources = []
    for layer in range(4):
        s = _role_dependency(deps, layer, "specularMap")
        n = _role_dependency(deps, layer, "normalMap")
        if s is not None:
            spec_sources.append({"layer": layer, "sourceTexture": _source(s, material=blender_material.name, layer=layer, role="specularMap", required=False)})
        if n is not None:
            normal_sources.append({"layer": layer, "sourceTexture": _source(n, material=blender_material.name, layer=layer, role="normalMap", required=False)})

    blender_material["T6_preview_status"] = "exact generated diffuse through RGB-square; Blender downstream lighting"
    blender_material["T6_technique_set"] = technique
    blender_material["T6_layer_steps_json"] = json.dumps(layer_nodes, sort_keys=True)
    blender_material["T6_layered_specular_dependencies_json"] = json.dumps(spec_sources, sort_keys=True)
    blender_material["T6_layered_normal_dependencies_json"] = json.dumps(normal_sources, sort_keys=True)
    blender_material["T6_preview_proof_boundary"] = (
        "exact A/B/M/T encoded-domain compositor for non-vN weights + exact RGB square; "
        "Principled lighting is preview-only; T6 specular/lightmap/reflection not remapped"
    )
    return {"layers": layer_nodes, "specularDependencies": len(spec_sources), "normalDependencies": len(normal_sources)}


def apply_preview(input_path: Path, output_blend: Path, *, recipes: Path | None = None, strict: bool = False) -> dict:
    if bpy is None:
        raise BlenderLayerPreviewError("this adapter must run inside Blender's Python")
    doc = _read_gltf_json(input_path)
    sidecars = _recipe_map(recipes)

    # Start from a clean scene so exact glTF material names remain unambiguous.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(input_path))

    gltf_by_name: dict[str, dict] = {}
    for row in doc.get("materials", []):
        name = str(row.get("name") or "")
        if name:
            gltf_by_name[name] = row

    image_cache: dict[tuple[str, str], object] = {}
    rebuilt = []
    skipped = []
    for name, row in gltf_by_name.items():
        if not name.startswith("*"):
            continue
        blender_material = bpy.data.materials.get(name)
        if blender_material is None:
            skipped.append({"material": name, "reason": "material not present after glTF import"})
            continue
        t6 = row.get("extras", {}).get("T6", {})
        technique, recipe = _material_technique(name, t6, sidecars)
        if technique is None:
            skipped.append({"material": name, "reason": "no generated TechniqueSet recipe attached"})
            continue
        try:
            details = _build_material(blender_material, row, technique, recipe, image_cache)
            rebuilt.append({"material": name, "techniqueSet": technique, **details})
        except BlenderLayerPreviewError as exc:
            skipped.append({"material": name, "techniqueSet": technique, "reason": str(exc)})
            if strict:
                raise

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    result = {
        "format": "t6-blender-generated-layer-preview-v1",
        "input": str(input_path),
        "output": str(output_blend),
        "generatedMaterialCount": sum(1 for n in gltf_by_name if n.startswith("*")),
        "rebuiltMaterialCount": len(rebuilt),
        "skippedMaterialCount": len(skipped),
        "rebuilt": rebuilt,
        "skipped": skipped,
        "proofBoundary": (
            "Exact source-closed generated diffuse compositor and encoded RGB square for supported non-vN layers. "
            "Blender Principled provides preview lighting only. Layered specular/normal/lightmap/reflection dependencies remain preserved and are not silently PBR-remapped."
        ),
    }
    report = output_blend.with_suffix(output_blend.suffix + ".t6_preview.json")
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _argv() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_blend", type=Path)
    parser.add_argument("--recipes", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(_argv())
    result = apply_preview(args.input, args.output_blend, recipes=args.recipes, strict=args.strict)
    print(json.dumps({
        "out": result["output"],
        "generatedMaterialCount": result["generatedMaterialCount"],
        "rebuiltMaterialCount": result["rebuiltMaterialCount"],
        "skippedMaterialCount": result["skippedMaterialCount"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
