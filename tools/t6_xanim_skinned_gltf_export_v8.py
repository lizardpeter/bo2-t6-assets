#!/usr/bin/env python3
"""T6 skinned glTF exporter v8: exact-name runtime-style XAnim binding.

T6 multiplayer playeranim tables can bind an XAnim authored on a superset rig to
an XModel that lacks some of those controls. v8 preserves v7's proven transform
semantics while filtering only animation tracks whose exact ScriptString/name is
absent from the target skeleton. No replacement bones or guessed aliases exist.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from t6_xanim_gltf_export_v3 import ExportError
from t6_xanim_skinned_gltf_export_v7 import export as export_v7

BINDING_PROOF = "manifests/nonmap/retail/seal6_smg_playeranim_core_v1.json"


def bind_xanim_to_skeleton(skeleton_doc: dict, xanim_doc: dict) -> tuple[dict, dict]:
    bones = skeleton_doc.get("skeleton", {}).get("bones", [])
    by_name = {}
    for bone in bones:
        name = bone.get("name")
        if not isinstance(name, str) or not name:
            raise ExportError("skeleton contains an unnamed bone")
        if name in by_name:
            raise ExportError(f"duplicate skeleton bone name {name!r}")
        by_name[name] = bone

    key = "boneTracks" if isinstance(xanim_doc.get("boneTracks"), list) else "tracks"
    tracks = xanim_doc.get(key)
    if not isinstance(tracks, list):
        raise ExportError("XAnim has no boneTracks/tracks array")

    seen = set()
    bound, unbound = [], []
    for track in tracks:
        name = track.get("name")
        if not isinstance(name, str) or not name:
            raise ExportError("XAnim contains an unnamed track")
        if name in seen:
            raise ExportError(f"duplicate XAnim track name {name!r}")
        seen.add(name)
        bone = by_name.get(name)
        if bone is None:
            unbound.append({"name": name, "scriptString": track.get("scriptString")})
            continue
        tsid = track.get("scriptString")
        bsid = bone.get("scriptStringId")
        if tsid is not None and bsid is not None and int(tsid) != int(bsid):
            raise ExportError(
                f"ScriptString mismatch for exact-name binding {name!r}: {tsid} != {bsid}"
            )
        bound.append(track)

    if tracks and not bound:
        raise ExportError("XAnim and skeleton have zero exact-name track intersections")

    filtered = copy.deepcopy(xanim_doc)
    filtered[key] = copy.deepcopy(bound)
    stats = {
        "policy": "exact ScriptString/name intersection; animation-only tracks omitted",
        "originalTrackCount": len(tracks),
        "boundTrackCount": len(bound),
        "unboundTrackCount": len(unbound),
        "unboundTracks": unbound,
        "skeletonBoneCount": len(bones),
        "noFabricatedBones": True,
        "noTrackNameAliases": True,
        "proofManifest": BINDING_PROOF,
    }
    filtered.setdefault("extras", {}).setdefault("T6", {})["runtimeBinding"] = stats
    return filtered, stats


def export(mesh_doc: dict, skeleton_doc: dict, xanim_doc: dict | None = None, lod: int = 0) -> dict:
    if xanim_doc is None:
        return export_v7(mesh_doc, skeleton_doc, None, lod)
    filtered, stats = bind_xanim_to_skeleton(skeleton_doc, xanim_doc)
    gltf = export_v7(mesh_doc, skeleton_doc, filtered, lod)
    gltf["asset"]["generator"] = "bo2-t6-assets t6_xanim_skinned_gltf_export_v8.py"
    gltf.setdefault("extras", {}).setdefault("T6", {})["runtimeTrackBinding"] = stats
    if gltf.get("animations"):
        gltf["animations"][0].setdefault("extras", {}).setdefault("T6", {})[
            "runtimeTrackBinding"
        ] = stats
    return gltf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh_json", type=Path)
    ap.add_argument("skeleton_json", type=Path)
    ap.add_argument("output_gltf", type=Path)
    ap.add_argument("--xanim", type=Path)
    ap.add_argument("--lod", type=int, default=0)
    args = ap.parse_args()
    mesh = json.loads(args.mesh_json.read_text(encoding="utf-8"))
    skeleton = json.loads(args.skeleton_json.read_text(encoding="utf-8"))
    xanim = json.loads(args.xanim.read_text(encoding="utf-8")) if args.xanim else None
    gltf = export(mesh, skeleton, xanim, args.lod)
    text = json.dumps(gltf, indent=2, sort_keys=True) + "\n"
    args.output_gltf.write_text(text, encoding="utf-8")
    print(json.dumps({
        "out": str(args.output_gltf),
        "bytes": len(text.encode("utf-8")),
        "runtimeTrackBinding": gltf.get("extras", {}).get("T6", {}).get("runtimeTrackBinding"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
