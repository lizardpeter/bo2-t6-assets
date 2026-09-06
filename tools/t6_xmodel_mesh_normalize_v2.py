#!/usr/bin/env python3
"""T6 XModel mesh normalizer v2: allow independently proven packed skeleton reuse.

v1 correctly fails when any skeleton array pointer is packed because it cannot
itself prove the reusable owner. v2 keeps v1's render-surface decoder unchanged,
but permits packed skeleton header pointers to consume zero source bytes only
when a supplied t6-xmodel-skeleton-normalized-v2 artifact independently closes
that same model/skeleton in the same expanded XFile.

Packed/reused render-surface data remains unsupported and still fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-xmodel-mesh-normalized-v2"
SKELETON_FORMAT = "t6-xmodel-skeleton-normalized-v2"
SKELETON_POINTER_OFFSETS = {
    8: "boneNames", 12: "parentList", 16: "quats", 20: "trans",
    24: "partClassification", 28: "baseMat",
}
FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_json(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected JSON object")
    return doc


def ptr_kind(raw: int) -> dict[str, Any]:
    if raw == 0:
        return {"kind": "null", "raw": raw, "rawHex": "0x00000000"}
    if raw == FOLLOWING:
        return {"kind": "following", "raw": raw, "rawHex": "0xFFFFFFFF"}
    if raw == INSERT:
        return {"kind": "insert", "raw": raw, "rawHex": "0xFFFFFFFE"}
    enc = (raw - 1) & 0xFFFFFFFF
    return {"kind": "packed", "raw": raw, "rawHex": f"0x{raw:08X}", "block": enc >> 29, "offset": enc & 0x1FFFFFFF}


def verify_skeleton_dependency(skeleton: dict[str, Any], *, expanded_sha: str, asset_start: int) -> None:
    if skeleton.get("format") != SKELETON_FORMAT:
        raise ValueError(f"skeleton format must be {SKELETON_FORMAT}")
    src = skeleton.get("source")
    ident = skeleton.get("identity")
    sk = skeleton.get("skeleton")
    val = skeleton.get("validation")
    if not all(isinstance(x, dict) for x in (src, ident, sk, val)):
        raise ValueError("skeleton dependency is missing source/identity/skeleton/validation")
    if src.get("expandedSha256") != expanded_sha:
        raise ValueError("skeleton dependency expandedSha256 mismatch")
    if int(src.get("xmodelFixedStart", -1)) != int(asset_start):
        raise ValueError("skeleton dependency XModel fixed start mismatch")
    if val.get("allBoneNamesResolved") is not True or val.get("hierarchyValid") is not True:
        raise ValueError("skeleton dependency integrity is not closed")


def normalize_mesh(data: bytes, asset_start: int, skeleton: dict[str, Any], *, base_module=None) -> dict[str, Any]:
    expanded_sha = hashlib.sha256(data).hexdigest()
    verify_skeleton_dependency(skeleton, expanded_sha=expanded_sha, asset_start=asset_start)
    base = base_module or load_module(Path(__file__).with_name("t6_xmodel_mesh_normalize_v1.py"), "t6_xmodel_mesh_v2_base")

    class ReuseAwareNormalizer(base.Normalizer):
        def __init__(self, raw: bytes, start: int):
            super().__init__(raw, start)
            self.packed_skeleton_pointers: dict[str, dict[str, Any]] = {}

        def u32(self, b, o):
            value = super().u32(b, o)
            if b == self.start and o in SKELETON_POINTER_OFFSETS and value not in (0, FOLLOWING, INSERT):
                kind = ptr_kind(value)
                if kind["kind"] == "packed":
                    self.packed_skeleton_pointers[SKELETON_POINTER_OFFSETS[o]] = kind
                    # Packed arrays consume no serialized source bytes here. The
                    # supplied skeleton-v2 proof independently resolves them.
                    return 0
            return value

    normalizer = ReuseAwareNormalizer(data, asset_start)
    mesh = normalizer.normalize()
    ident = mesh.get("identity") or {}
    xm = mesh.get("xmodel") or {}
    sk_ident = skeleton["identity"]
    sk = skeleton["skeleton"]
    if ident.get("name") != sk_ident.get("name"):
        raise ValueError(f"mesh/skeleton identity mismatch: {ident.get('name')!r} != {sk_ident.get('name')!r}")
    if int(xm.get("numBones", -1)) != int(sk.get("numBones", -2)):
        raise ValueError("mesh/skeleton numBones mismatch")
    if int(xm.get("numRootBones", -1)) != int(sk.get("numRootBones", -2)):
        raise ValueError("mesh/skeleton numRootBones mismatch")

    packed = normalizer.packed_skeleton_pointers
    source_mode = (skeleton.get("skeletonSource") or {}).get("mode")
    if packed and source_mode != "packed_reusable_owner":
        raise ValueError(f"packed skeleton pointers require skeletonSource.mode=packed_reusable_owner; got {source_mode!r}")

    out = dict(mesh)
    out["format"] = FORMAT
    out["expandedSha256"] = expanded_sha
    out["skeletonDependency"] = {
        "format": skeleton.get("format"),
        "identity": sk_ident.get("name"),
        "xassetIndex": sk_ident.get("xassetIndex"),
        "sourceMode": source_mode,
        "packedSkeletonPointers": packed,
        "allBoneNamesResolved": True,
        "hierarchyValid": True,
    }
    validation = dict(out.get("validation") or {})
    validation.update({
        "packedSkeletonArraysConsumeSourceBytes": False,
        "packedSkeletonArraysIndependentlyResolved": bool(packed),
        "packedRenderSurfaceReuseSupported": False,
    })
    out["validation"] = validation
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--asset-start", required=True, type=lambda x: int(x, 0))
    ap.add_argument("--skeleton", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    data = a.expanded.read_bytes()
    skeleton = load_json(a.skeleton)
    out = normalize_mesh(data, a.asset_start, skeleton)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(a.out), "name": out["identity"]["name"],
        "surfaces": len(out["surfaces"]),
        "vertices": sum(int(s["vertCount"]) for s in out["surfaces"]),
        "triangles": sum(int(s["triCount"]) for s in out["surfaces"]),
        "packedSkeletonFields": sorted(out["skeletonDependency"]["packedSkeletonPointers"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
