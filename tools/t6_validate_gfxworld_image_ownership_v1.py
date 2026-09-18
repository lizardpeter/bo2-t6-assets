#!/usr/bin/env python3
"""Validate exact T6 GfxWorld lightmap/reflection ownership catalogs.

This validator deliberately does NOT encode expected production counts. Counts are
observations from the retail dump, not proof inputs. It validates only structural
invariants needed to consume the catalogs safely and emits identity-level sets for
the production GfxImage union.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _finite(v: Any) -> bool:
    if isinstance(v, (int, str, type(None), bool)):
        return True
    if isinstance(v, float):
        return math.isfinite(v)
    if isinstance(v, list):
        return all(_finite(x) for x in v)
    if isinstance(v, dict):
        return all(_finite(x) for x in v.values())
    return False


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(lightmap_path: Path, reflection_path: Path) -> dict[str, Any]:
    lm = json.loads(lightmap_path.read_text())
    rp = json.loads(reflection_path.read_text())

    assert lm.get("format") == "t6-gfxworld-lightmap-catalog-v1", lm.get("format")
    assert rp.get("format") == "t6-gfxworld-reflection-probe-catalog-v1", rp.get("format")

    lightmaps = lm.get("lightmaps")
    probes = rp.get("reflectionProbes")
    assert isinstance(lightmaps, list)
    assert isinstance(probes, list)
    assert lm.get("lightmapCount") == len(lightmaps)
    assert rp.get("reflectionProbeCount") == len(probes)
    assert [x.get("index") for x in lightmaps] == list(range(len(lightmaps)))
    assert [x.get("index") for x in probes] == list(range(len(probes)))
    assert _finite(lm)
    assert _finite(rp)

    # Identity extraction is role-specific and null-preserving. Runtime texture
    # pointers, dimensions, ordering, adjacency, and filename similarity are not
    # accepted as archival identity evidence.
    lightmap_images = sorted({
        image
        for record in lightmaps
        for image in (record.get("primaryImage"), record.get("secondaryImage"))
        if isinstance(image, str) and image
    })
    reflection_images = sorted({
        image for record in probes
        for image in (record.get("reflectionImage"),)
        if isinstance(image, str) and image
    })
    nullable_reflection_entries = sorted(
        {record.get("reflectionImage") for record in probes},
        key=lambda x: "" if x is None else str(x),
    )

    return {
        "format": "t6-gfxworld-image-ownership-validation-v1",
        "lightmapCatalog": {
            "bytes": lightmap_path.stat().st_size,
            "sha256": _sha256(lightmap_path),
            "recordCount": len(lightmaps),
        },
        "reflectionCatalog": {
            "bytes": reflection_path.stat().st_size,
            "sha256": _sha256(reflection_path),
            "recordCount": len(probes),
        },
        "lightmapImages": lightmap_images,
        "reflectionImages": reflection_images,
        "distinctNullableReflectionImageCount": len(nullable_reflection_entries),
        "gfxWorldImageUnion": sorted(set(lightmap_images) | set(reflection_images)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lightmap_catalog", type=Path)
    ap.add_argument("reflection_catalog", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    result = validate(args.lightmap_catalog, args.reflection_catalog)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
