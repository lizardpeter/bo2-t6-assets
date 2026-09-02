#!/usr/bin/env python3
"""Regression checks for the retained T6 format-4/5 retail proof manifest.

The lightweight path validates the committed proof artifact without requiring
retail FastFiles. With --root it additionally reruns the byte-level verifier
against the expanded Raid/Hijacked fixtures and requires byte-identical JSON.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

EXPECTED = {
    "format": "t6-retail-world-formats-45-proof-v1",
    "summary": {
        "mapCount": 2,
        "format4DirectAllocations": 40,
        "format5DirectAllocations": 13,
        "format4ObservedRawStrides": [12],
        "format5ObservedRawStrides": [16],
        "contradictionCount": 0,
        "formatsPromotable": [4, 5],
    },
    "maps": {
        "mp_raid": {
            "expandedSha256": "d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8",
            "surfaceCount": 5281,
            "materialCount": 352,
            "pointerBase": 13768,
            "techsetBlock": [750, 845],
            "direct": {"4": 17, "5": 4},
        },
        "mp_hijacked": {
            "expandedSha256": "8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b",
            "surfaceCount": 2366,
            "materialCount": 236,
            "pointerBase": 14172,
            "techsetBlock": [751, 821],
            "direct": {"4": 23, "5": 9},
        },
    },
}


def validate(doc: dict) -> None:
    assert doc["format"] == EXPECTED["format"]
    assert doc["summary"] == EXPECTED["summary"]
    maps = {m["map"]: m for m in doc["maps"]}
    assert set(maps) == set(EXPECTED["maps"])
    for name, exp in EXPECTED["maps"].items():
        m = maps[name]
        assert m["expandedSha256"] == exp["expandedSha256"]
        assert m["gfxWorld"]["surfaceCount"] == exp["surfaceCount"]
        assert m["materialMemory"]["count"] == exp["materialCount"]
        assert m["materialMemory"]["end"] == m["materialMemory"]["firstMaterialFixedStart"]
        assert m["techniqueBinding"]["assetPointerVirtualBase"] == exp["pointerBase"]
        assert m["techniqueBinding"]["block"] == exp["techsetBlock"]
        assert m["surfaceArray"]["end"] - m["surfaceArray"]["start"] == 80 * exp["surfaceCount"]
        for fmt, stride in (("4", 12), ("5", 16)):
            row = m["formats"][fmt]
            assert row["directAllocationCount"] == exp["direct"][fmt]
            assert row["expectedStride"] == stride
            assert row["rawStrides"] == [stride]
            assert row["contradictions"] == 0
            for example in row["examples"]:
                assert example["span"] == example["vertexCount"] * stride
                assert example["rawStride"] == stride


def rerun(verifier: Path, root: Path, committed: Path) -> None:
    spec = importlib.util.spec_from_file_location("t6_fmt45", verifier)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {verifier}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    maps = []
    for name, cfg in mod.MAPS.items():
        maps.append(mod.prove(name, (root / f"{name}.expanded.bin").read_bytes(), cfg))
    summary = {
        "mapCount": 2,
        "format4DirectAllocations": sum(x["formats"]["4"]["directAllocationCount"] for x in maps),
        "format5DirectAllocations": sum(x["formats"]["5"]["directAllocationCount"] for x in maps),
        "format4ObservedRawStrides": sorted({v for x in maps for v in x["formats"]["4"]["rawStrides"]}),
        "format5ObservedRawStrides": sorted({v for x in maps for v in x["formats"]["5"]["rawStrides"]}),
        "contradictionCount": 0,
        "formatsPromotable": [4, 5],
    }
    doc = {
        "format": "t6-retail-world-formats-45-proof-v1",
        "producer": "tools/t6_retail_world_formats_45_proof_v1.py",
        "maps": maps,
        "summary": summary,
        "proofBoundary": (
            "worldVertFormat is read from each retail MaterialTechniqueSet reached through "
            "GfxSurface -> MaterialMemory -> Material -> TechniqueSet XAsset. Raw vd1 stride "
            "is independently allocation-span / vd0-derived vertex-count. Shared format-0 "
            "vd1 offsets are retained as non-separable and never used as proof or contradiction. "
            "Shader meaning of normalTransform words is outside this proof."
        ),
    }
    doc = json.loads(json.dumps(doc))
    validate(doc)
    expected = json.loads(committed.read_text(encoding="utf-8"))
    assert doc == expected, "rerun result differs from committed proof manifest"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=Path("manifests/world/T6_RETAIL_WORLD_FORMATS_45_PROOF_V1.json"))
    ap.add_argument("--verifier", type=Path, default=Path("tools/t6_retail_world_formats_45_proof_v1.py"))
    ap.add_argument("--root", type=Path)
    args = ap.parse_args()
    doc = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate(doc)
    if args.root is not None:
        rerun(args.verifier, args.root, args.manifest)
    print("PASS: T6 retail world formats 4/5 proof regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
