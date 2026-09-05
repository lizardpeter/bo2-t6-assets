#!/usr/bin/env python3
"""Compatibility frontend for character material binding-plan v1.

v2 adds support for the durable `t6-xmodel-surface-material-assignments-v1`
manifest. It adapts only that explicit surface evidence into the historical v1
shape, then delegates all material/image/alias/IPAK joining and glTF role policy
to the proven v1 compiler.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "t6_character_material_binding_plan_v1.py"


def _load_v1():
    spec = importlib.util.spec_from_file_location("t6_character_material_binding_plan_v1", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_v1()
_original_load = base.load


def load_with_surface_v2(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if doc.get("format") != "t6-xmodel-surface-material-assignments-v1":
        return doc

    rows = doc.get("assignments")
    if not isinstance(rows, list):
        raise RuntimeError("surface assignment manifest lacks assignments[]")
    expected = int((doc.get("summary") or {}).get("surfaces", len(rows)))
    if len(rows) != expected:
        raise RuntimeError(f"surface assignment row count {len(rows)} != expected {expected}")

    indices = [int(r["surfaceIndex"]) for r in rows]
    if indices != list(range(expected)):
        raise RuntimeError("surface assignment indices are not exact contiguous 0..N-1")

    legacy = []
    for r in rows:
        evidence = (
            "exact-inline-retail-material"
            if r.get("handleKind") == "inline-following"
            else "exact-packed-virtual-material-owner"
        )
        legacy.append(
            {
                "surfaceIndex": int(r["surfaceIndex"]),
                "lod": int(r["lodIndex"]),
                "lodLocalSurfaceIndex": int(r["lodLocalSurfaceIndex"]),
                "materialName": r["material"],
                "materialPointerRaw": r["handleRaw"],
                "evidence": evidence,
            }
        )

    return {
        "format": "t6-surface-proof-v2-adapted-for-binding-v1",
        "source": doc.get("source"),
        "bodyMaterials": {"surfaceAssignments": legacy},
        "adapterProof": {
            "inputFormat": doc["format"],
            "inputRows": len(rows),
            "allSurfaceIndicesContiguous": True,
            "noIdentityInferencePerformed": True,
        },
    }


def main() -> int:
    base.load = load_with_surface_v2
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
