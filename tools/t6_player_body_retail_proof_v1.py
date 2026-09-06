#!/usr/bin/env python3
"""Promote one multiplayer T6 XModel into a registry-ready retail body proof.

This layer does not decode XModel bytes itself. It joins already-independent
proof artifacts and fails closed unless they all identify the same model in the
same expanded retail XFile:

- t6-xmodel-target-probe-v1: exact inline XModel identity/fixed record
- t6-xmodel-skeleton-normalized-v2: complete, valid retail skeleton
- t6-xmodel-mesh-normalized-v1: complete decoded render mesh
- exact source fastfile bytes and exact expanded bytes

Candidate naming evidence is never accepted here. A successful output is safe
for t6_player_body_identity_registry_v1.py because both geometry and skeleton
proof gates are closed from hash-pinned retail artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-player-body-retail-proof-v1"
PROBE_FORMAT = "t6-xmodel-target-probe-v1"
SKELETON_FORMAT = "t6-xmodel-skeleton-normalized-v2"
MESH_FORMATS = {"t6-xmodel-mesh-normalized-v1"}


def load(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected JSON object")
    return doc


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_path(path)}


def exact_target(probe: dict[str, Any], name: str) -> dict[str, Any]:
    if probe.get("format") != PROBE_FORMAT:
        raise ValueError(f"probe format must be {PROBE_FORMAT}")
    rows = probe.get("targets")
    if not isinstance(rows, list):
        raise ValueError("probe.targets must be a list")
    matches = [r for r in rows if isinstance(r, dict) and r.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"probe must contain exactly one target row for {name!r}; got {len(matches)}")
    row = matches[0]
    if row.get("status") != "exact_inline_xmodel":
        raise ValueError(f"{name}: probe status is not exact_inline_xmodel")
    for k in ("rawStructOffset", "fixedRecordSha256", "fixedPlusNameSha256", "numBones", "numRootBones", "numSurfs", "numLods"):
        if k not in row:
            raise ValueError(f"{name}: probe row missing {k}")
    return row


def _sha64(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label}: expected 64-character sha256")
    int(value, 16)
    return value.lower()


def verify_probe_source(probe: dict[str, Any], expanded_path: Path) -> tuple[int, str]:
    src = probe.get("source")
    if not isinstance(src, dict):
        raise ValueError("probe.source missing")
    actual_bytes = expanded_path.stat().st_size
    actual_sha = sha256_path(expanded_path)
    if src.get("bytes") != actual_bytes:
        raise ValueError(f"expanded byte count mismatch: probe={src.get('bytes')} actual={actual_bytes}")
    expected_sha = _sha64(src.get("sha256"), "probe.source.sha256")
    if expected_sha != actual_sha:
        raise ValueError(f"expanded sha256 mismatch: probe={expected_sha} actual={actual_sha}")
    return actual_bytes, actual_sha


def verify_skeleton(skeleton: dict[str, Any], row: dict[str, Any], expanded_sha: str, name: str) -> dict[str, Any]:
    if skeleton.get("format") != SKELETON_FORMAT:
        raise ValueError(f"skeleton format must be {SKELETON_FORMAT}")
    ident = skeleton.get("identity")
    src = skeleton.get("source")
    sk = skeleton.get("skeleton")
    val = skeleton.get("validation")
    if not all(isinstance(x, dict) for x in (ident, src, sk, val)):
        raise ValueError("skeleton artifact is missing identity/source/skeleton/validation objects")
    if ident.get("name") != name:
        raise ValueError(f"skeleton identity mismatch: {ident.get('name')!r} != {name!r}")
    if src.get("expandedSha256") != expanded_sha:
        raise ValueError("skeleton expandedSha256 does not match expanded retail artifact")
    if int(src.get("xmodelFixedStart", -1)) != int(row["rawStructOffset"]):
        raise ValueError("skeleton XModel fixed start does not match exact target probe")
    for field, probe_key in (("numBones", "numBones"), ("numRootBones", "numRootBones")):
        if int(sk.get(field, -1)) != int(row[probe_key]):
            raise ValueError(f"skeleton {field} does not match target probe")
    if val.get("allBoneNamesResolved") is not True:
        raise ValueError("skeleton bone-name closure is not exact")
    if val.get("hierarchyValid") is not True:
        raise ValueError("skeleton hierarchy is not valid")
    bones = sk.get("bones")
    if not isinstance(bones, list) or len(bones) != int(row["numBones"]):
        raise ValueError("skeleton bone array cardinality mismatch")
    if any(not isinstance(b, dict) or not isinstance(b.get("name"), str) or not b["name"] for b in bones):
        raise ValueError("skeleton contains unresolved/empty bone names")
    return {
        "allBoneNamesResolved": True,
        "hierarchyValid": True,
        "translationAllocationTailAllZero": bool(sk.get("allocationTailAllZero")),
        "sourceMode": (skeleton.get("skeletonSource") or {}).get("mode"),
        "xassetIndex": ident.get("xassetIndex"),
    }


def verify_mesh(mesh: dict[str, Any], row: dict[str, Any], expanded_sha: str, name: str) -> dict[str, Any]:
    if mesh.get("format") not in MESH_FORMATS:
        raise ValueError(f"mesh format must be one of {sorted(MESH_FORMATS)}")
    ident = mesh.get("identity")
    src = mesh.get("source")
    xm = mesh.get("xmodel")
    val = mesh.get("validation")
    surfaces = mesh.get("surfaces")
    if not all(isinstance(x, dict) for x in (ident, src, xm, val)) or not isinstance(surfaces, list):
        raise ValueError("mesh artifact is missing identity/source/xmodel/surfaces/validation")
    if ident.get("name") != name:
        raise ValueError(f"mesh identity mismatch: {ident.get('name')!r} != {name!r}")
    if mesh.get("expandedSha256") != expanded_sha:
        raise ValueError("mesh expandedSha256 does not match expanded retail artifact")
    fixed_start = src.get("assetFixedStart")
    if fixed_start is None:
        fixed_start = src.get("xmodelFixedStart")
    if int(fixed_start if fixed_start is not None else -1) != int(row["rawStructOffset"]):
        raise ValueError("mesh XModel fixed start does not match exact target probe")
    for field, probe_key in (("numBones", "numBones"), ("numRootBones", "numRootBones"), ("numSurfs", "numSurfs"), ("numLods", "numLods")):
        if int(xm.get(field, -1)) != int(row[probe_key]):
            raise ValueError(f"mesh {field} does not match target probe")
    if len(surfaces) != int(row["numSurfs"]):
        raise ValueError("mesh surface cardinality mismatch")
    if val.get("allLocalTriangleIndicesInRange") is not True:
        raise ValueError("mesh triangle-range validation is not closed")
    vertices = 0
    triangles = 0
    for i, surf in enumerate(surfaces):
        if not isinstance(surf, dict):
            raise ValueError(f"surface {i} is not an object")
        vc = int(surf.get("vertCount", -1))
        tc = int(surf.get("triCount", -1))
        verts = surf.get("vertices")
        tris = surf.get("triangles")
        if vc < 0 or tc < 0 or not isinstance(verts, list) or not isinstance(tris, list):
            raise ValueError(f"surface {i}: malformed geometry arrays")
        if len(verts) != vc or len(tris) != tc:
            raise ValueError(f"surface {i}: geometry cardinality mismatch")
        vertices += vc
        triangles += tc
    return {"vertices": vertices, "triangles": triangles, "fallbackGeometryUsed": False}


def build(*, name: str, zone_name: str, fastfile_path: Path, expanded_path: Path,
          probe_path: Path, skeleton_path: Path, mesh_path: Path) -> dict[str, Any]:
    if not name or not zone_name:
        raise ValueError("name and zone_name must be non-empty")
    probe = load(probe_path)
    skeleton = load(skeleton_path)
    mesh = load(mesh_path)
    expanded_bytes, expanded_sha = verify_probe_source(probe, expanded_path)
    row = exact_target(probe, name)
    sk_summary = verify_skeleton(skeleton, row, expanded_sha, name)
    mesh_summary = verify_mesh(mesh, row, expanded_sha, name)
    ff = artifact(fastfile_path)
    exp = artifact(expanded_path)
    if exp["bytes"] != expanded_bytes or exp["sha256"] != expanded_sha:
        raise AssertionError("expanded artifact changed during proof construction")
    skeleton_art = artifact(skeleton_path)
    mesh_art = artifact(mesh_path)
    probe_art = artifact(probe_path)
    lods = row.get("lods") if isinstance(row.get("lods"), list) else []
    pointers = row.get("pointers") if isinstance(row.get("pointers"), dict) else {}
    return {
        "format": FORMAT,
        "authority": "direct hash-pinned retail T6 PC fastfile/expanded bytes plus exact XModel identity, skeleton, and mesh proof artifacts",
        "sourceFastfile": {"zoneName": zone_name, "bytes": ff["bytes"], "sha256": ff["sha256"]},
        "expandedStream": {"bytes": exp["bytes"], "sha256": exp["sha256"]},
        "fullBody": {
            "name": name,
            "fixedStart": int(row["rawStructOffset"]),
            "fixedStartHex": f"0x{int(row['rawStructOffset']):X}",
            "fixedRecordSha256": _sha64(row["fixedRecordSha256"], "target.fixedRecordSha256"),
            "fixedPlusNameSha256": _sha64(row["fixedPlusNameSha256"], "target.fixedPlusNameSha256"),
            "bones": int(row["numBones"]),
            "rootBones": int(row["numRootBones"]),
            "surfaces": int(row["numSurfs"]),
            "lods": lods,
            "radius": row.get("radius"),
            "mins": row.get("mins"),
            "maxs": row.get("maxs"),
            "skeleton": {**sk_summary, "normalizedJsonSha256": skeleton_art["sha256"]},
            "mesh": {**mesh_summary, "normalizedJsonSha256": mesh_art["sha256"]},
            "topLevelPointers": pointers,
        },
        "status": {
            "fullBodyGeometryRetailProven": True,
            "fullBodySkeletonRetailProven": True,
            "retailCompiledPlayerScriptLocated": False,
            "thirdPersonAnimationClosureComplete": False,
            "completePlayerBundleClosed": False,
        },
        "proofArtifacts": {"xmodelProbe": probe_art, "skeleton": skeleton_art, "mesh": mesh_art},
        "proofBoundary": "This proof closes one exact full-body XModel's identity, decoded skeleton, and decoded render mesh. It does not prove player-script ownership, materials/textures, named-weapon precedence, or third-person animation compatibility.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--zone-name", required=True)
    ap.add_argument("--fastfile", type=Path, required=True)
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--probe", type=Path, required=True)
    ap.add_argument("--skeleton", type=Path, required=True)
    ap.add_argument("--mesh", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = build(name=a.name, zone_name=a.zone_name, fastfile_path=a.fastfile, expanded_path=a.expanded,
                probe_path=a.probe, skeleton_path=a.skeleton, mesh_path=a.mesh)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(a.out), "name": out["fullBody"]["name"], "bones": out["fullBody"]["bones"],
                      "surfaces": out["fullBody"]["surfaces"], "vertices": out["fullBody"]["mesh"]["vertices"],
                      "triangles": out["fullBody"]["mesh"]["triangles"], "status": "retail-proven-full-body"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
