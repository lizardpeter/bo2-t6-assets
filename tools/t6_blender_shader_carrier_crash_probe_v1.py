#!/usr/bin/env python3
"""Stage-by-stage crash probe for the exact SEAL6 Blender shader carrier.

This is diagnostic only. It reuses the source-specific v2 transport contract and
prints a flushed marker after each Blender mutation so a native Blender 4.0.2
crash can be assigned to one exact storage/save stage without weakening any
asset proof.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import bpy  # type: ignore
import t6_blender_import_xmodel_shader_carrier_v1 as v1
import t6_blender_import_xmodel_shader_carrier_v2 as v2


def mark(name: str) -> None:
    print(f"T6_CRASH_PROBE={name}", flush=True)


def main() -> int:
    args_raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args(args_raw)

    # Install the exact measured v2 transport contract into v1 helpers.
    v1._source = v2._source_exact
    v1._prove_vertex_sequence = v2._prove_vertex_sequence_measured
    mark("contract-installed")

    doc, raw, prims = v1._source(a.source)
    mark("source-opened")
    with tempfile.TemporaryDirectory(prefix="t6-seal6-crash-probe-") as td:
        safe = Path(td) / "carrier_import_safe.glb"
        v1._make_import_safe(a.source, safe)
        mark("import-safe-written")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(safe), import_pack_images=True)
    mark("gltf-imported")

    obj = v1._main_mesh_object()
    v1._prove_vertex_sequence(obj, doc, raw, prims)
    mark("sequence-proven")
    mesh = obj.data
    source = {name: v1._flatten_source(doc, raw, prims, name) for name in v1.CUSTOM}
    mark("custom-accessors-read")

    for name in v1.CUSTOM:
        v1._remove_existing(mesh, name)
    mark("old-attributes-cleared")

    color = mesh.color_attributes.new(name="_T6_COLOR_RGBA", type="FLOAT_COLOR", domain="POINT")
    mark("color-created")
    color.data.foreach_set("color", [float(v) for row in source["_T6_COLOR_RGBA"] for v in row])
    mark("color-written")
    _ = tuple(color.data[0].color), tuple(color.data[-1].color)
    mark("color-readback")

    normal = mesh.attributes.new(name="_T6_XMODEL_NORMAL", type="FLOAT_VECTOR", domain="POINT")
    mark("normal-created")
    normal.data.foreach_set("vector", [float(v) for row in source["_T6_XMODEL_NORMAL"] for v in row])
    mark("normal-written")
    _ = tuple(normal.data[0].vector), tuple(normal.data[-1].vector)
    mark("normal-readback")

    tangent = mesh.attributes.new(name="_T6_XMODEL_TANGENT", type="FLOAT_VECTOR", domain="POINT")
    mark("tangent-created")
    tangent.data.foreach_set("vector", [float(v) for row in source["_T6_XMODEL_TANGENT"] for v in row])
    mark("tangent-written")
    _ = tuple(tangent.data[0].vector), tuple(tangent.data[-1].vector)
    mark("tangent-readback")

    handed = mesh.attributes.new(name="_T6_TANGENT_HANDEDNESS", type="FLOAT", domain="POINT")
    mark("handed-created")
    handed.data.foreach_set("value", [float(row[0]) for row in source["_T6_TANGENT_HANDEDNESS"]])
    mark("handed-written")
    _ = float(handed.data[0].value), float(handed.data[-1].value)
    mark("handed-readback")

    # Full original readback loop, still before pack/save.
    for i in range(13490):
        if not v1._row_close(tuple(color.data[i].color), source["_T6_COLOR_RGBA"][i]):
            raise RuntimeError(f"color drift at {i}")
        if not v1._row_close(tuple(normal.data[i].vector), source["_T6_XMODEL_NORMAL"][i]):
            raise RuntimeError(f"normal drift at {i}")
        if not v1._row_close(tuple(tangent.data[i].vector), source["_T6_XMODEL_TANGENT"][i]):
            raise RuntimeError(f"tangent drift at {i}")
        if not v1._close(float(handed.data[i].value), float(source["_T6_TANGENT_HANDEDNESS"][i][0])):
            raise RuntimeError(f"handedness drift at {i}")
    mark("full-readback")

    scene = bpy.context.scene
    scene["t6_crash_probe"] = True
    notice = bpy.data.texts.new("T6_CRASH_PROBE.txt")
    notice.write("diagnostic\n")
    mark("metadata-written")

    bpy.ops.file.pack_all()
    mark("pack-all-complete")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output), compress=False)
    mark("save-complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
