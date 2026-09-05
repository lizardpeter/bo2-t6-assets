#!/usr/bin/env python3
"""Nuketown generated normal-layer -> world transform-slot binding v1.

This is deliberately map-gated.  The retained Nuketown layered-material fixture
proves two independent facts for all 120 compound materials:

* an ``n`` marker on component token N means that component really has a normal
  map (Material_LoadLayered validates it against Material_HasNormalMap);
* world ``normalCount == max(1, count(n-marked components))`` with zero layout
  failures.

T6 world vertex layout independently proves that vd0 owns the first normal/
tangent basis and vd1 appends exactly ``normalCount-1`` packed transform words
in order as normalTransform0, normalTransform1.

Therefore, for *Nuketown's proven compound population only*:

* the first n-marked component owns the direct normal basis and consumes no
  `_T6_NORMAL_TRANSFORM_*` attribute;
* each later n-marked component consumes the next transform slot in component
  order: slot 0, then slot 1.

The canonical generated shader recipe is cross-checked against this ownership:
secondary recipe steps declaring ``hasNormal`` must equal the n-marked component
indices > 0.  Every observed worldVertFormat must have the exact normalCount
required by the material.  No shader-name or layer-index-to-slot shortcut is
used.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from t6_zone_core import MaterialWorldVertexFormat, WORLD_VERTEX_FORMATS


FORMAT = "t6-nuketown-generated-normal-transform-binding-v1"
MAP = "mp_nuketown_2020"
TOKEN_RE = re.compile(r"^(\d+)([nx]?)$")


class NuketownNormalTransformBindingError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def component_tokens(material: str) -> list[dict]:
    if not material.startswith("*") or "(" not in material:
        raise NuketownNormalTransformBindingError(
            f"not a generated compound material name: {material!r}"
        )
    prefix = material[1:material.index("(")]
    raw_tokens = prefix.split("_")
    if not 2 <= len(raw_tokens) <= 4:
        raise NuketownNormalTransformBindingError(
            f"{material!r}: generated component count {len(raw_tokens)} outside 2..4"
        )
    out = []
    for layer, raw in enumerate(raw_tokens):
        match = TOKEN_RE.match(raw)
        if not match:
            raise NuketownNormalTransformBindingError(
                f"{material!r}: invalid retained component token {raw!r}"
            )
        marker = match.group(2) or None
        out.append({
            "layerIndex": layer,
            "token": raw,
            "bspMaterialIndex": int(match.group(1)),
            "marker": marker,
            "hasNormal": marker == "n",
        })
    return out


def _normal_count_for_format(value: int) -> int:
    try:
        spec = WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(int(value))]
    except Exception as exc:
        raise NuketownNormalTransformBindingError(
            f"unknown T6 worldVertFormat {value}"
        ) from exc
    return int(spec.normal_count)


def bind_recipe(recipe: dict, *, map_name: str = MAP) -> dict:
    if map_name != MAP:
        raise NuketownNormalTransformBindingError(
            f"normal transform binding v1 is source-gated to {MAP!r}, got {map_name!r}"
        )
    material = str(recipe.get("material") or "")
    components = component_tokens(material)
    n_layers = [row["layerIndex"] for row in components if row["hasNormal"]]
    expected_normal_count = max(1, len(n_layers))

    world_formats_raw = recipe.get("worldVertFormats")
    if not isinstance(world_formats_raw, list) or not world_formats_raw:
        raise NuketownNormalTransformBindingError(
            f"{material!r}: canonical recipe has no observed worldVertFormats"
        )
    world_formats = sorted({int(value) for value in world_formats_raw})
    format_counts = {value: _normal_count_for_format(value) for value in world_formats}
    bad = {fmt: count for fmt, count in format_counts.items() if count != expected_normal_count}
    if bad:
        raise NuketownNormalTransformBindingError(
            f"{material!r}: world format normalCount {bad} != retained compound requirement {expected_normal_count}"
        )

    program = recipe.get("layerProgram")
    if not isinstance(program, list):
        raise NuketownNormalTransformBindingError(
            f"{material!r}: canonical recipe lacks layerProgram"
        )
    recipe_secondary_normals = sorted(
        int(step["layerIndex"])
        for step in program
        if bool(step.get("hasNormal"))
    )
    material_secondary_normals = [layer for layer in n_layers if layer > 0]
    if recipe_secondary_normals != material_secondary_normals:
        raise NuketownNormalTransformBindingError(
            f"{material!r}: recipe secondary normal layers {recipe_secondary_normals} != "
            f"retail n-marked component layers {material_secondary_normals}"
        )

    # The first n-marked component is represented by the base normal basis in
    # vd0 even when that first normal-bearing component is a secondary material.
    # Subsequent n components consume vd1 transform words sequentially.
    first_normal_layer = n_layers[0] if n_layers else None
    bindings = []
    for layer in material_secondary_normals:
        normal_ordinal = n_layers.index(layer)
        if normal_ordinal == 0:
            mode = "direct"
            slot = None
            semantic = None
        else:
            mode = "transform2x2"
            slot = normal_ordinal - 1
            semantic = f"_T6_NORMAL_TRANSFORM_{slot}"
        bindings.append({
            "layerIndex": layer,
            "normalComponentOrdinal": normal_ordinal,
            "mode": mode,
            "transformSlot": slot,
            "attribute": semantic,
        })

    required_slots = sum(1 for row in bindings if row["mode"] == "transform2x2")
    available_extra = expected_normal_count - 1
    if required_slots != available_extra:
        raise NuketownNormalTransformBindingError(
            f"{material!r}: bound transform slots {required_slots} != world layout extras {available_extra}"
        )
    if required_slots > 2:
        raise NuketownNormalTransformBindingError(
            f"{material!r}: T6 normalized contract only exposes two extra transform slots"
        )

    result = {
        "format": FORMAT,
        "map": MAP,
        "material": material,
        "componentCount": len(components),
        "components": components,
        "normalMarkedLayers": n_layers,
        "firstNormalBasisLayer": first_normal_layer,
        "expectedWorldNormalCount": expected_normal_count,
        "worldVertFormats": world_formats,
        "worldVertFormatNormalCounts": {str(k): v for k, v in sorted(format_counts.items())},
        "secondaryNormalBindings": bindings,
        "extraTransformSlotCount": required_slots,
        "allSecondaryNormalLayersBound": len(bindings) == len(material_secondary_normals),
        "proof": (
            "Nuketown retained n-marker/component bijection + zero-failure normalCount relationship; "
            "T6 vd0 first normal basis and ordered vd1 normalTransform words; exact canonical recipe "
            "hasNormal layers and observed worldVertFormats cross-checked"
        ),
    }
    result["bindingSha256"] = _jhash({
        "material": material,
        "normalMarkedLayers": n_layers,
        "worldVertFormats": world_formats,
        "secondaryNormalBindings": bindings,
    })
    return result


def build_manifest(recipe_manifest: dict, *, map_name: str = MAP) -> dict:
    if recipe_manifest.get("format") != "t6-generated-world-shader-recipe-manifest-v1":
        raise NuketownNormalTransformBindingError(
            f"unsupported canonical recipe manifest {recipe_manifest.get('format')!r}"
        )
    recipes = recipe_manifest.get("materials")
    if not isinstance(recipes, list) or not recipes:
        raise NuketownNormalTransformBindingError("canonical recipe manifest has no materials")
    rows = [bind_recipe(recipe, map_name=map_name) for recipe in recipes]
    normal_rows = [row for row in rows if row["secondaryNormalBindings"]]
    direct = sum(
        1 for row in normal_rows for binding in row["secondaryNormalBindings"]
        if binding["mode"] == "direct"
    )
    transformed = sum(
        1 for row in normal_rows for binding in row["secondaryNormalBindings"]
        if binding["mode"] == "transform2x2"
    )
    return {
        "format": "t6-nuketown-generated-normal-transform-binding-manifest-v1",
        "map": MAP,
        "materials": rows,
        "summary": {
            "generatedMaterialCount": len(rows),
            "secondaryNormalMaterialCount": len(normal_rows),
            "secondaryNormalLayerCount": direct + transformed,
            "directSecondaryNormalLayerCount": direct,
            "transformedSecondaryNormalLayerCount": transformed,
            "allWorldFormatNormalCountsExact": True,
            "allRecipeNormalLayersExact": True,
            "rowsSha256": _jhash(rows),
        },
        "proofBoundary": (
            "Nuketown-only transform-slot ownership from retained material n markers and exact world layout. "
            "This does not prove normal-map sample channel decode or generalize the slot rule to other maps."
        ),
    }
