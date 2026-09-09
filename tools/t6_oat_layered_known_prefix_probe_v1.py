#!/usr/bin/env python3
"""Evidence-only probe for an exact known-component prefix in a T6 layered Material.

This tool does not recover, transform, normalize, or promote anything. It compares
one generated Material's leading known component textures[] against the exact
standalone OAT Material textures[] and records the first structural difference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_layered_material_name_v1 import parse_layered_material_name
from t6_oat_material_manifest_v2 import _index_oat_materials
from t6_oat_material_manifest_v6 import _storage_identity

FORMAT = "t6-oat-layered-known-prefix-probe-v1"


def canon(v: object) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(v: object) -> str:
    return hashlib.sha256(canon(v)).hexdigest()


def first_diff(expected: object, actual: object, path: str = "$") -> dict | None:
    if type(expected) is not type(actual):
        return {"path": path, "kind": "type", "expectedType": type(expected).__name__, "actualType": type(actual).__name__, "expected": expected, "actual": actual}
    if isinstance(expected, dict):
        ek, ak = set(expected), set(actual)
        if ek != ak:
            return {"path": path, "kind": "keys", "expectedOnly": sorted(ek-ak), "actualOnly": sorted(ak-ek), "expected": expected, "actual": actual}
        for key in sorted(ek):
            d = first_diff(expected[key], actual[key], f"{path}.{key}")
            if d is not None:
                return d
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return {"path": path, "kind": "length", "expectedLength": len(expected), "actualLength": len(actual)}
        for i, (e, a) in enumerate(zip(expected, actual)):
            d = first_diff(e, a, f"{path}[{i}]")
            if d is not None:
                return d
        return None
    if expected != actual:
        return {"path": path, "kind": "value", "expected": expected, "actual": actual}
    return None


def textures(identity: str, source: dict) -> list[dict]:
    rows = source["doc"].get("textures", [])
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        raise RuntimeError(f"{identity!r}: invalid textures[]")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("material_root", type=Path)
    ap.add_argument("catalog_json", type=Path)
    ap.add_argument("output_json", type=Path)
    ap.add_argument("--generated", required=True)
    ap.add_argument("--known-prefix", required=True)
    ap.add_argument("--unknown", required=True)
    a = ap.parse_args()

    catalog = json.loads(a.catalog_json.read_text(encoding="utf-8"))
    names = [str(r.get("name") or "") for r in catalog.get("materials", [])]
    if names.count(a.generated) != 1:
        raise RuntimeError(f"generated catalog identity count={names.count(a.generated)} for {a.generated!r}")
    parsed = parse_layered_material_name(a.generated)
    components = [str(x["componentMaterial"]) for x in parsed["layers"]]
    if components != [a.known_prefix, a.unknown]:
        raise RuntimeError(f"unexpected component sequence {components!r}")

    indexed, skipped = _index_oat_materials(a.material_root)
    if a.known_prefix not in indexed:
        raise RuntimeError(f"known prefix {a.known_prefix!r} absent from exact root union")
    if a.unknown in indexed:
        raise RuntimeError(f"unknown {a.unknown!r} unexpectedly exists standalone")
    storage = _storage_identity(a.generated)
    if storage not in indexed:
        raise RuntimeError(f"generated storage {storage!r} absent from exact root union")

    expected = textures(a.known_prefix, indexed[a.known_prefix])
    generated = textures(a.generated, indexed[storage])
    if len(generated) < len(expected):
        raise RuntimeError("generated texture table shorter than known prefix")
    actual = generated[:len(expected)]
    diff = first_diff(expected, actual)

    row_index = None
    expected_row = actual_row = None
    if diff is not None and diff["path"].startswith("$["):
        try:
            row_index = int(diff["path"].split("[",1)[1].split("]",1)[0])
            expected_row = expected[row_index]
            actual_row = actual[row_index]
        except Exception:
            pass

    out = {
        "format": FORMAT,
        "catalogFormat": catalog.get("format"),
        "catalogMap": catalog.get("map"),
        "generatedMaterial": a.generated,
        "generatedStorageIdentity": storage,
        "components": components,
        "knownPrefix": a.known_prefix,
        "unknownStandaloneMissing": a.unknown,
        "indexedOatMaterialCount": len(indexed),
        "skippedNonT6MaterialJsonCount": len(skipped),
        "knownTextureCount": len(expected),
        "generatedTextureCount": len(generated),
        "knownPrefixExact": diff is None,
        "knownTextureTableSha256": sha(expected),
        "generatedPrefixSha256": sha(actual),
        "firstDifference": diff,
        "firstDifferenceTextureIndex": row_index,
        "expectedStandaloneTextureRow": expected_row,
        "actualGeneratedTextureRow": actual_row,
        "proofBoundary": "Exact OAT JSON observation only; no transform, normalization, ownership inference, recovery, or promotion."
    }
    payload = (json.dumps(out, indent=2, sort_keys=True) + "\n").encode("utf-8")
    a.output_json.parent.mkdir(parents=True, exist_ok=True)
    a.output_json.write_bytes(payload)
    print(payload.decode("utf-8"))
    # The expected diagnostic condition is a real mismatch. Fail if it disappears.
    if diff is None:
        raise RuntimeError("known prefix unexpectedly became exact; historical v1 blocker not reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
