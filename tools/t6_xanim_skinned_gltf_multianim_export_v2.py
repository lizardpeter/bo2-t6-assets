#!/usr/bin/env python3
"""Blender-safe multi-animation T6 XModel GLB export, v2.

v1 transported the decoded retail GfxPackedVertex.color field as glTF COLOR_0.
That is not lossless once standard glTF PBR materials are attached: COLOR_0 has
specified base-color/alpha multiplication semantics, while T6 exposes the same
bytes to the selected retail technique and their meaning is technique-dependent.

v2 deliberately keeps the exact accessor but renames the attribute to the custom
_T6_COLOR_RGBA semantic.  No color values are changed or discarded.  This is a
transport correction only; it does not infer how a retail T6 technique consumes
the field and it does not claim retail shader equivalence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_xanim_skinned_gltf_multianim_export_v1 as v1

ExportError = v1.ExportError


def demote_t6_color(doc: dict) -> dict:
    changed = 0
    primitive_count = 0
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            primitive_count += 1
            attrs = prim.get("attributes", {})
            if "_T6_COLOR_RGBA" in attrs:
                raise ExportError("primitive already contains _T6_COLOR_RGBA")
            if "COLOR_0" not in attrs:
                raise ExportError("expected exact T6 color accessor as COLOR_0 from v1")
            attrs["_T6_COLOR_RGBA"] = attrs.pop("COLOR_0")
            changed += 1

    if primitive_count == 0 or changed != primitive_count:
        raise ExportError(f"T6 color transport conversion incomplete: {changed}/{primitive_count}")

    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            attrs = prim.get("attributes", {})
            if "COLOR_0" in attrs:
                raise ExportError("standard glTF COLOR_0 remained after T6 color demotion")
            if "_T6_COLOR_RGBA" not in attrs:
                raise ExportError("custom T6 color accessor missing after demotion")

    t6 = doc.setdefault("extras", {}).setdefault("T6", {})
    t6["vertexColorTransport"] = {
        "attribute": "_T6_COLOR_RGBA",
        "decodedRetailAccessorPreserved": True,
        "standardGltfColor0Emitted": False,
        "retailTechniqueUseInferred": False,
        "reason": "T6 GfxPackedVertex.color is technique input; glTF COLOR_0 would impose base-color/alpha multiplication semantics",
    }
    doc.setdefault("asset", {})["generator"] = "bo2-t6-assets t6_xanim_skinned_gltf_multianim_export_v2.py"
    return doc


def build(mesh: dict, skel: dict, proof: dict, anims: list[dict], lod: int = 0):
    doc, bin_data = v1.build(mesh, skel, proof, anims, lod)
    return demote_t6_color(doc), bin_data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh_json", type=Path)
    ap.add_argument("skeleton_json", type=Path)
    ap.add_argument("surface_proof", type=Path)
    ap.add_argument("output_glb", type=Path)
    ap.add_argument("--xanim", type=Path, action="append", required=True)
    ap.add_argument("--lod", type=int, default=0)
    ap.add_argument("--manifest", type=Path)
    a = ap.parse_args()

    mesh = json.loads(a.mesh_json.read_text(encoding="utf-8-sig"))
    skel = json.loads(a.skeleton_json.read_text(encoding="utf-8-sig"))
    proof = json.loads(a.surface_proof.read_text(encoding="utf-8-sig"))
    anims = [json.loads(p.read_text(encoding="utf-8-sig")) for p in a.xanim]
    if len({x.get("name") for x in anims}) != len(anims):
        raise ExportError("duplicate or unnamed XAnim inputs")

    doc, bin_data = build(mesh, skel, proof, anims, a.lod)
    sha, n = v1.write_glb(doc, bin_data, a.output_glb)
    t6 = doc["extras"]["T6"]
    out = {
        "format": "t6-xanim-skinned-gltf-multianim-export-v2",
        "outputGlb": {"path": str(a.output_glb), "sha256": sha, "bytes": n},
        "xmodelName": mesh["identity"]["name"],
        "lod": a.lod,
        "vertices": t6["vertices"],
        "triangles": t6["triangles"],
        "joints": t6["joints"],
        "materials": [m["name"] for m in doc["materials"]],
        "animations": [
            {
                "name": x["name"],
                "channels": len(x["channels"]),
                "runtimeTrackBinding": x["extras"]["T6"]["runtimeTrackBinding"],
            }
            for x in doc["animations"]
        ],
        "validation": {
            "bindHierarchy": t6["bindHierarchyValidation"],
            "noFabricatedBones": all(x["extras"]["T6"]["runtimeTrackBinding"]["noFabricatedBones"] for x in doc["animations"]),
            "noTrackNameAliases": all(x["extras"]["T6"]["runtimeTrackBinding"]["noTrackNameAliases"] for x in doc["animations"]),
            "noStandardGltfColor0": True,
            "retailColorAccessorPreservedAsCustomAttribute": True,
            "retailTechniqueUseOfPackedColorNotInferred": True,
        },
    }
    if a.manifest:
        a.manifest.parent.mkdir(parents=True, exist_ok=True)
        a.manifest.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "glb": str(a.output_glb), "sha256": sha, "bytes": n,
        "vertices": out["vertices"], "triangles": out["triangles"],
        "joints": out["joints"], "materials": len(out["materials"]),
        "animations": len(out["animations"]), "noStandardGltfColor0": True,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
