#!/usr/bin/env python3
"""Fail-closed retail census for the T6 layered texture projection itself.

This deliberately separates the two remaining candidate mutations after retail
proved global argument-hash ordering and disproved BO1-style mip promotion:
  A) preserve standalone sampler + mature state; append only the layer suffix
  B) preserve sampler, append suffix, recompute mature-content from image name
No recovery is performed here. Known rows must compare/subtract as exact JSON.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

from t6_layered_material_name_v1 import parse_layered_material_name
from t6_oat_material_manifest_v2 import _index_oat_materials
from t6_oat_material_manifest_v6 import _storage_identity

FORMAT = "t6-oat-layered-t6-projection-census-v1"
MOD = 1 << 32
MATURE_FALSE = {"2D", "function", "waterMap"}


def canon(v: object) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def name_hash(name: str) -> int:
    h = 0
    for ch in name:
        h = (ord(ch) ^ (33 * h)) & 0xFFFFFFFF
    return h


def row_hash(row: dict) -> int:
    name = row.get("name")
    if isinstance(name, str) and name:
        return name_hash(name)
    h = row.get("nameHash")
    if isinstance(h, int) and 0 <= h < MOD:
        return h
    raise RuntimeError(f"texture row lacks usable argument identity: {row!r}")


def textures(identity: str, source: dict) -> list[dict]:
    rows = source["doc"].get("textures", [])
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        raise RuntimeError(f"{identity!r}: invalid textures[]")
    return rows


def mature(row: dict) -> bool:
    sem = row.get("semantic")
    if sem in MATURE_FALSE:
        return False
    image = row.get("image")
    if not isinstance(image, str):
        raise RuntimeError(f"cannot recompute mature-content without image name: {row!r}")
    return "_mature" in image


def suffix_row(source: dict, layer_index: int, *, recompute_mature: bool) -> dict:
    if not 0 <= layer_index <= 3:
        raise RuntimeError(f"layer index {layer_index} outside 0..3")
    row = copy.deepcopy(source)
    if layer_index:
        digit = str(layer_index)
        name = row.get("name")
        if isinstance(name, str) and name:
            row["name"] = name + digit
        else:
            h = row.get("nameHash")
            if not isinstance(h, int) or not 0 <= h < MOD:
                raise RuntimeError(f"fallback texture identity unavailable: {row!r}")
            row["nameHash"] = (ord(digit) ^ (33 * h)) & 0xFFFFFFFF
            row["nameEnd"] = digit
    if recompute_mature:
        row["isMatureContent"] = mature(row)
    return row


def project_components(components: list[str], indexed: dict, *, recompute_mature: bool) -> list[dict]:
    rows: list[dict] = []
    for layer_index, component in enumerate(components):
        for row in textures(component, indexed[component]):
            rows.append(suffix_row(row, layer_index, recompute_mature=recompute_mature))
    return sorted(rows, key=row_hash)


def subtract_exact(generated: list[dict], known: list[dict]) -> tuple[bool, list[dict], dict | None]:
    pool = Counter(canon(x) for x in generated)
    for row in known:
        key = canon(row)
        if pool[key] <= 0:
            return False, [], row
        pool[key] -= 1
    left = Counter(pool)
    residual: list[dict] = []
    for row in generated:
        key = canon(row)
        if left[key] > 0:
            residual.append(row)
            left[key] -= 1
    if any(left.values()):
        raise RuntimeError("internal residual accounting failure")
    return True, residual, None


def first_diff(expected: object, actual: object, path: str = "$") -> dict | None:
    if type(expected) is not type(actual):
        return {"path": path, "kind": "type", "expected": expected, "actual": actual}
    if isinstance(expected, dict):
        ek, ak = set(expected), set(actual)
        if ek != ak:
            return {"path": path, "kind": "keys", "expectedOnly": sorted(ek-ak), "actualOnly": sorted(ak-ek)}
        for k in sorted(ek):
            d = first_diff(expected[k], actual[k], f"{path}.{k}")
            if d is not None: return d
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return {"path": path, "kind": "length", "expected": len(expected), "actual": len(actual)}
        for i, (e, a) in enumerate(zip(expected, actual)):
            d = first_diff(e, a, f"{path}[{i}]")
            if d is not None: return d
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

    catalog = json.loads(a.catalog_json.read_text())
    indexed, skipped = _index_oat_materials(a.material_root)
    referenced: set[str] = set()
    rows: list[dict] = []
    all_available = missing_family = 0
    preserve_exact = recompute_exact = 0
    preserve_subtract = recompute_subtract = 0
    first_preserve = first_recompute = None
    first_preserve_sub = first_recompute_sub = None

    for cat in catalog.get("materials", []):
        material = str(cat.get("name") or "")
        if not material.startswith("*"):
            continue
        parsed = parse_layered_material_name(material)
        components = [str(x["componentMaterial"]) for x in parsed["layers"]]
        referenced.update(components)
        generated_source = indexed.get(_storage_identity(material))
        if generated_source is None:
            raise RuntimeError(f"{material!r}: generated Material unavailable")
        generated = textures(material, generated_source)
        if not all(row_hash(x) <= row_hash(y) for x, y in zip(generated, generated[1:])):
            raise RuntimeError(f"{material!r}: generated texture hashes are not nondecreasing")
        missing = sorted({x for x in components if x not in indexed})
        row = {"material": material, "components": components, "missingStandaloneComponents": missing}
        if not missing:
            all_available += 1
            p = project_components(components, indexed, recompute_mature=False)
            r = project_components(components, indexed, recompute_mature=True)
            pe = canon(p) == canon(generated)
            re = canon(r) == canon(generated)
            preserve_exact += int(pe); recompute_exact += int(re)
            row.update({"suffixPreserveExact": pe, "suffixRecomputeMatureExact": re})
            if not pe and first_preserve is None:
                first_preserve = {"material": material, "firstDifference": first_diff(p, generated)}
            if not re and first_recompute is None:
                first_recompute = {"material": material, "firstDifference": first_diff(r, generated)}
        else:
            missing_family += 1
            known_p: list[dict] = []
            known_r: list[dict] = []
            for li, component in enumerate(components):
                if component not in indexed:
                    continue
                for source_row in textures(component, indexed[component]):
                    known_p.append(suffix_row(source_row, li, recompute_mature=False))
                    known_r.append(suffix_row(source_row, li, recompute_mature=True))
            p_ok, p_residual, p_bad = subtract_exact(generated, known_p)
            r_ok, r_residual, r_bad = subtract_exact(generated, known_r)
            preserve_subtract += int(p_ok); recompute_subtract += int(r_ok)
            row.update({"suffixPreserveKnownSubtractExact": p_ok, "suffixRecomputeMatureKnownSubtractExact": r_ok,
                        "preserveResidual": p_residual if p_ok else None,
                        "recomputeResidual": r_residual if r_ok else None})
            if not p_ok and first_preserve_sub is None:
                first_preserve_sub = {"material": material, "missingKnownRow": p_bad}
            if not r_ok and first_recompute_sub is None:
                first_recompute_sub = {"material": material, "missingKnownRow": r_bad}
        rows.append(row)

    observed = sorted(x for x in referenced if x not in indexed)
    if observed != sorted(a.expected_missing):
        raise RuntimeError(f"standalone-missing set mismatch observed={observed!r} expected={sorted(a.expected_missing)!r}")
    summary = {
        "generatedMaterialCount": len(rows),
        "allStandaloneComponentsAvailableCount": all_available,
        "missingStandaloneFamilyCount": missing_family,
        "standaloneMissingComponentCount": len(observed),
        "suffixPreserveExactAllStandaloneCount": preserve_exact,
        "suffixRecomputeMatureExactAllStandaloneCount": recompute_exact,
        "suffixPreserveKnownSubtractExactMissingFamilyCount": preserve_subtract,
        "suffixRecomputeMatureKnownSubtractExactMissingFamilyCount": recompute_subtract,
    }
    out = {"format": FORMAT, "catalogFormat": catalog.get("format"), "catalogMap": catalog.get("map"),
           "indexedOatMaterialCount": len(indexed), "skippedNonT6MaterialJsonCount": len(skipped),
           "standaloneMissingComponents": observed, "summary": summary,
           "firstSuffixPreserveMismatch": first_preserve, "firstSuffixRecomputeMatureMismatch": first_recompute,
           "firstSuffixPreserveSubtractionFailure": first_preserve_sub,
           "firstSuffixRecomputeMatureSubtractionFailure": first_recompute_sub,
           "materials": rows,
           "proofBoundary": "Retail generated OAT JSON projection census only. No missing component is promoted or reconstructed."}
    a.output_json.parent.mkdir(parents=True, exist_ok=True)
    a.output_json.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"summary": summary, "firstSuffixPreserveMismatch": first_preserve,
                      "firstSuffixRecomputeMatureMismatch": first_recompute,
                      "firstSuffixPreserveSubtractionFailure": first_preserve_sub,
                      "firstSuffixRecomputeMatureSubtractionFailure": first_recompute_sub}, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
