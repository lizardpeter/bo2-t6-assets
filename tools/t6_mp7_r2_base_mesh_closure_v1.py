#!/usr/bin/env python3
"""Close drawable current-R2 MP7 base first-person XModel mesh payloads.

The model names are already source-/raw-bound by retained MP7 proofs. This layer
resolves each target back to its exact inline raw XModel record in the pinned
current-R2 common_mp stream and runs the strict lossless XModel mesh normalizer.
It is specifically intended to determine whether `viewmodel_hands_no_model` is
actually geometry-less or is a drawable first-person hands/arms mesh carrier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_mp7_r2_xmodel_target_probe_v1 import find_inline_xmodel
from t6_xmodel_mesh_normalize_v1 import Normalizer

FORMAT = "t6-mp7-r2-base-mesh-closure-v1"
EXPECTED_STREAM_BYTES = 206_493_911
EXPECTED_STREAM_SHA256 = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"
TARGETS = [
    ("viewHandsSkeletonCarrier", "viewmodel_hands_no_model"),
    ("gunModel", "t6_wpn_smg_mp7_view"),
    ("attachViewModel7", "t6_attach_mag_mp7_view"),
]


class ClosureError(RuntimeError):
    pass


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise ClosureError(msg)


def canonical_sha256(doc: dict) -> str:
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build(stream_path: Path) -> dict:
    data = stream_path.read_bytes()
    require(len(data) == EXPECTED_STREAM_BYTES, f"expanded bytes {len(data)} != {EXPECTED_STREAM_BYTES}")
    sha = hashlib.sha256(data).hexdigest()
    require(sha == EXPECTED_STREAM_SHA256, f"expanded SHA mismatch {sha}")

    rows = []
    for role, name in TARGETS:
        walk = find_inline_xmodel(data, name)
        require(walk["blockers"] == [], f"{name}: full raw XModel walk blockers {walk['blockers']}")
        mesh = Normalizer(data, walk["assetFixedStart"]).normalize()
        require(mesh["identity"]["name"] == name, f"{name}: mesh identity mismatch")
        require(mesh["xmodel"]["numSurfs"] == walk["xmodel"]["numSurfs"], f"{name}: surface count mismatch")
        verts = sum(int(s["vertCount"]) for s in mesh["surfaces"])
        tris = sum(int(s["triCount"]) for s in mesh["surfaces"])
        unweighted = sum(int(s["unweightedVertexCount"]) for s in mesh["surfaces"])
        nonempty_surfs = sum(int(s["vertCount"]) > 0 and int(s["triCount"]) > 0 for s in mesh["surfaces"])
        require(all(int(s["unweightedVertexCount"]) == 0 for s in mesh["surfaces"]), f"{name}: unweighted vertices remain")
        rows.append({
            "role": role,
            "name": name,
            "assetFixedStart": walk["assetFixedStart"],
            "fullXmodelSerializedEnd": walk["assetSerializedEnd"],
            "fullXmodelSerializedBytes": walk["assetSerializedBytes"],
            "fullXmodelSerializedSha256": walk["assetSerializedSha256"],
            "meshOwnedSerializedEnd": mesh["source"]["meshOwnedSerializedEnd"],
            "meshOwnedSerializedBytes": mesh["source"]["meshOwnedSerializedBytes"],
            "meshOwnedSerializedSha256": mesh["source"]["meshOwnedSerializedSha256"],
            "numBones": mesh["xmodel"]["numBones"],
            "numRootBones": mesh["xmodel"]["numRootBones"],
            "numSurfs": mesh["xmodel"]["numSurfs"],
            "numLods": mesh["xmodel"]["numLods"],
            "nonemptySurfaceCount": nonempty_surfs,
            "vertexCount": verts,
            "triangleCount": tris,
            "unweightedVertexCount": unweighted,
            "drawableGeometryPresent": verts > 0 and tris > 0 and nonempty_surfs > 0,
            "surfaceStats": [
                {
                    "index": s["index"],
                    "vertCount": s["vertCount"],
                    "triCount": s["triCount"],
                    "blendCounts": s["blendCounts"],
                    "rigidVertListCount": len(s["rigidVertLists"]),
                    "unweightedVertexCount": s["unweightedVertexCount"],
                }
                for s in mesh["surfaces"]
            ],
            "normalizedMeshCanonicalSha256": canonical_sha256(mesh),
        })

    hands = rows[0]
    return {
        "format": FORMAT,
        "source": {"expandedCommonMp": {"bytes": len(data), "sha256": sha}},
        "models": rows,
        "summary": {
            "modelCount": len(rows),
            "totalSurfaceCount": sum(r["numSurfs"] for r in rows),
            "totalVertexCount": sum(r["vertexCount"] for r in rows),
            "totalTriangleCount": sum(r["triangleCount"] for r in rows),
            "allVerticesWeighted": all(r["unweightedVertexCount"] == 0 for r in rows),
            "viewHandsDrawableGeometryPresent": hands["drawableGeometryPresent"],
            "viewHandsVertexCount": hands["vertexCount"],
            "viewHandsTriangleCount": hands["triangleCount"],
        },
        "proofBoundary": (
            "These three source/raw-bound base first-person XModels are normalized directly from the exact current-R2 common_mp stream using the strict inline XSurface decoder. This closes their mesh payloads, vertices, triangles, and skin weights. Materials and final multi-model DObj assembly are not promoted by this layer."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.stream)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    for row in doc["models"]:
        print(f"{row['role']} {row['name']} bones={row['numBones']} surfs={row['numSurfs']} verts={row['vertexCount']} tris={row['triangleCount']} drawable={row['drawableGeometryPresent']} meshSha={row['normalizedMeshCanonicalSha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
