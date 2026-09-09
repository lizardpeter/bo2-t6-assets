#!/usr/bin/env python3
"""Classify exact retail T6 layered Material texture-table ordering.

The generated OAT Material JSON is the authority. This census does not reorder or
recover anything. It measures direct-concatenation equality and independently
records whether each generated runtime table is nondecreasing by Treyarch's
32-bit material-name hash recurrence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from t6_layered_material_name_v1 import parse_layered_material_name
from t6_oat_material_manifest_v2 import _index_oat_materials
from t6_oat_material_manifest_v6 import _storage_identity

FORMAT = "t6-oat-layered-texture-order-census-v1"
MOD = 1 << 32


def canonical(v: object) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(v: object) -> str:
    return hashlib.sha256(canonical(v)).hexdigest()


def name_hash(name: str) -> int:
    h = 0
    for ch in name:
        h = (ord(ch) ^ (33 * h)) & 0xFFFFFFFF
    return h


def texture_hash(row: dict) -> tuple[int, str]:
    name = row.get("name")
    if isinstance(name, str) and name:
        return name_hash(name), "computed-from-name"
    h = row.get("nameHash")
    if isinstance(h, int) and 0 <= h < MOD:
        return h, "serialized-nameHash"
    raise RuntimeError(f"texture row lacks usable argument identity: {row!r}")


def textures(identity: str, source: dict) -> list[dict]:
    rows = source["doc"].get("textures", [])
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        raise RuntimeError(f"{identity!r}: invalid textures[]")
    return rows


def first_diff(expected: object, actual: object, path: str = "$") -> dict | None:
    if type(expected) is not type(actual):
        return {"path": path, "kind": "type", "expected": expected, "actual": actual}
    if isinstance(expected, dict):
        ek, ak = set(expected), set(actual)
        if ek != ak:
            return {"path": path, "kind": "keys", "expectedOnly": sorted(ek-ak), "actualOnly": sorted(ak-ek)}
        for key in sorted(ek):
            d = first_diff(expected[key], actual[key], f"{path}.{key}")
            if d is not None:
                return d
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return {"path": path, "kind": "length", "expectedLength": len(expected), "actualLength": len(actual)}
        for i, (e, g) in enumerate(zip(expected, actual)):
            d = first_diff(e, g, f"{path}[{i}]")
            if d is not None:
                return d
        return None
    if expected != actual:
        return {"path": path, "kind": "value", "expected": expected, "actual": actual}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("material_root", type=Path)
    ap.add_argument("catalog_json", type=Path)
    ap.add_argument("output_json", type=Path)
    ap.add_argument("--expected-missing", action="append", default=[])
    a = ap.parse_args()

    catalog = json.loads(a.catalog_json.read_text(encoding="utf-8"))
    indexed, skipped = _index_oat_materials(a.material_root)
    rows = []
    referenced = set()
    compound_count = all_available_count = direct_count = 0
    sorted_count = missing_family_count = missing_family_sorted = 0
    all_available_sorted = 0
    texture_total = 0
    hash_source_counts = Counter()
    first_direct_mismatch = None

    for cat in catalog.get("materials", []):
        material = str(cat.get("name") or "")
        if not material.startswith("*"):
            continue
        compound_count += 1
        parsed = parse_layered_material_name(material)
        components = [str(x["componentMaterial"]) for x in parsed["layers"]]
        referenced.update(components)
        storage = _storage_identity(material)
        source = indexed.get(storage)
        if source is None:
            raise RuntimeError(f"{material!r}: generated storage {storage!r} unavailable")
        generated = textures(material, source)
        texture_total += len(generated)
        hashes = []
        compact = []
        for i, tex in enumerate(generated):
            h, hsrc = texture_hash(tex)
            hash_source_counts[hsrc] += 1
            hashes.append(h)
            compact.append({
                "index": i,
                "argument": tex.get("name"),
                "nameHash": tex.get("nameHash"),
                "effectiveNameHash": h,
                "effectiveNameHashHex": f"0x{h:08x}",
                "hashSource": hsrc,
                "semantic": tex.get("semantic"),
                "image": tex.get("image"),
            })
        nondecreasing = all(x <= y for x, y in zip(hashes, hashes[1:]))
        sorted_count += int(nondecreasing)

        missing = sorted({x for x in components if x not in indexed})
        all_available = not missing
        direct_exact = None
        direct_sha = None
        direct_diff = None
        if all_available:
            all_available_count += 1
            concat = []
            for component in components:
                concat.extend(textures(component, indexed[component]))
            direct_exact = canonical(concat) == canonical(generated)
            direct_sha = sha(concat)
            direct_count += int(direct_exact)
            all_available_sorted += int(nondecreasing)
            if not direct_exact:
                direct_diff = first_diff(concat, generated)
                if first_direct_mismatch is None:
                    first_direct_mismatch = {"material": material, "firstDifference": direct_diff}
        else:
            missing_family_count += 1
            missing_family_sorted += int(nondecreasing)

        rows.append({
            "material": material,
            "storageIdentity": storage,
            "components": components,
            "layers": parsed["layers"],
            "missingStandaloneComponents": missing,
            "allStandaloneComponentsAvailable": all_available,
            "textureCount": len(generated),
            "generatedTextureTableSha256": sha(generated),
            "directConcatenationExact": direct_exact,
            "directConcatenationSha256": direct_sha,
            "directConcatenationFirstDifference": direct_diff,
            "effectiveNameHashesNondecreasing": nondecreasing,
            "textureOrder": compact,
        })

    observed_missing = sorted(x for x in referenced if x not in indexed)
    if sorted(a.expected_missing) != observed_missing:
        raise RuntimeError(f"exact standalone-missing set mismatch observed={observed_missing!r} expected={sorted(a.expected_missing)!r}")

    summary = {
        "generatedMaterialCount": compound_count,
        "generatedTextureRowCount": texture_total,
        "allStandaloneComponentsAvailableCount": all_available_count,
        "exactDirectConcatenationCount": direct_count,
        "directConcatenationMismatchCount": all_available_count - direct_count,
        "missingStandaloneFamilyCount": missing_family_count,
        "hashNondecreasingGeneratedCount": sorted_count,
        "hashNondecreasingAllStandaloneCount": all_available_sorted,
        "hashNondecreasingMissingStandaloneCount": missing_family_sorted,
        "standaloneMissingComponentCount": len(observed_missing),
        "hashSourceCounts": dict(sorted(hash_source_counts.items())),
    }
    out = {
        "format": FORMAT,
        "catalogFormat": catalog.get("format"),
        "catalogMap": catalog.get("map"),
        "indexedOatMaterialCount": len(indexed),
        "skippedNonT6MaterialJsonCount": len(skipped),
        "standaloneMissingComponents": observed_missing,
        "hashRecurrence": "h0=0; h[n+1]=(ASCII(char) XOR 33*h[n]) mod 2^32",
        "summary": summary,
        "firstDirectConcatenationMismatch": first_direct_mismatch,
        "materials": rows,
        "proofBoundary": "Exact generated/standalone OAT JSON census only. Direct concatenation and hash ordering are measured, not assumed; no missing component recovery, ownership inference, or shader/blend semantics are promoted here."
    }
    payload = (json.dumps(out, indent=2, sort_keys=True) + "\n").encode("utf-8")
    a.output_json.parent.mkdir(parents=True, exist_ok=True)
    a.output_json.write_bytes(payload)
    print(json.dumps({"summary": summary, "firstDirectConcatenationMismatch": first_direct_mismatch}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
