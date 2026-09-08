#!/usr/bin/env python3
"""Measure Blender's numeric transport of a proven T6 shader carrier without admitting it.

This diagnostic intentionally does not inject custom attributes or write a final
asset.  It imports the application-attribute-stripped carrier through Blender's
normal glTF skin path and measures same-index error against the authoritative
source sequence for position, UV, and named skin weights across every vertex.
The output is used to set a source-derived transport bound rather than guessing
an epsilon.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

import bpy

import t6_blender_import_xmodel_shader_carrier_v1 as carrier

FORMAT = "t6-blender-xmodel-import-sequence-probe-v1"


def main() -> int:
    raw_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(raw_args)

    doc, raw, prims = carrier._source(args.source)
    with tempfile.TemporaryDirectory(prefix="t6-seal6-sequence-probe-") as td:
        safe = Path(td) / "safe.glb"
        carrier._make_import_safe(args.source, safe)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(safe), import_pack_images=True)
    obj = carrier._main_mesh_object()
    mesh = obj.data

    positions = carrier._flatten_source(doc, raw, prims, "POSITION")
    uvs = carrier._flatten_source(doc, raw, prims, "TEXCOORD_0")
    expected_skin = carrier._expected_skin_rows(doc, raw, prims)
    imported_uvs = carrier._vertex_uvs(mesh)
    if not (len(positions) == len(uvs) == len(expected_skin) == len(imported_uvs) == len(mesh.vertices) == 13490):
        raise RuntimeError("cardinality mismatch before probe")

    max_pos = {"abs": -1.0, "vertex": None, "component": None, "actual": None, "expected": None}
    max_uv = {"abs": -1.0, "vertex": None, "component": None, "actual": None, "expected": None}
    max_weight = {"abs": -1.0, "vertex": None, "group": None, "actual": None, "expected": None}
    skin_name_mismatches = []
    nonfinite = 0

    for i, vertex in enumerate(mesh.vertices):
        actual_pos = tuple(float(x) for x in vertex.co)
        expected_pos = carrier._gltf_to_blender_vec(positions[i])
        for c, (a, e) in enumerate(zip(actual_pos, expected_pos)):
            if not math.isfinite(a) or not math.isfinite(e):
                nonfinite += 1
                continue
            delta = abs(a - e)
            if delta > max_pos["abs"]:
                max_pos = {"abs": delta, "vertex": i, "component": c, "actual": a, "expected": e}

        expected_uv = carrier._uv_to_blender(uvs[i])
        actual_uv = imported_uvs[i]
        for c, (a, e) in enumerate(zip(actual_uv, expected_uv)):
            if not math.isfinite(a) or not math.isfinite(e):
                nonfinite += 1
                continue
            delta = abs(a - e)
            if delta > max_uv["abs"]:
                max_uv = {"abs": delta, "vertex": i, "component": c, "actual": a, "expected": e}

        actual_skin = carrier._actual_skin_row(obj, vertex)
        exp = expected_skin[i]
        exp_names = [x[0] for x in exp]
        act_names = [x[0] for x in actual_skin]
        if exp_names != act_names:
            if len(skin_name_mismatches) < 20:
                skin_name_mismatches.append({"vertex": i, "expected": exp_names, "actual": act_names})
            continue
        for (name, ew), (_, aw) in zip(exp, actual_skin):
            delta = abs(float(aw) - float(ew))
            if delta > max_weight["abs"]:
                max_weight = {"abs": delta, "vertex": i, "group": name, "actual": float(aw), "expected": float(ew)}

    out = {
        "format": FORMAT,
        "source": str(args.source),
        "vertices": 13490,
        "triangles": len(mesh.polygons),
        "blenderVersion": bpy.app.version_string,
        "sameIndexProbe": True,
        "maxPositionAbsError": max_pos,
        "maxUvAbsError": max_uv,
        "skinNameMismatchCount": len(skin_name_mismatches),
        "skinNameMismatchExamples": skin_name_mismatches,
        "maxNamedSkinWeightAbsError": max_weight,
        "nonFiniteComparisonCount": nonfinite,
        "proofBoundary": (
            "Diagnostic only. No custom shader attribute is injected and no asset is promoted. Errors are measured at identical source/imported vertex indices over all vertices after normal Blender glTF skin import."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("T6_BLENDER_SEQUENCE_PROBE=" + json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
