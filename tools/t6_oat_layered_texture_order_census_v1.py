#!/usr/bin/env python3
"""Classify exact retail T6 layered Material texture-table ordering.

The generated OAT Material JSON is the authority. This census measures raw
concatenation, the layer transform + global hash-sort equation, and whether every
known projected row can be subtracted exactly from copy-elided generated tables.
It does not recover or promote missing components.
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
from t6_oat_layered_component_texture_recovery_v2 import project

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
            if d is not None: return d
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return {"path": path, "kind": "length", "expectedLength": len(expected), "actualLength": len(actual)}
        for i, (e, g) in enumerate(zip(expected, actual)):
            d = first_diff(e, g, f"{path}[{i}]")
            if d is not None: return d
        return None
    if expected != actual:
        return {"path": path, "kind": "value", "expected": expected, "actual": actual}
    return None


def sorted_projected(components: list[str], indexed: dict[str, dict]) -> list[dict]:
    out = []
    for li, component in enumerate(components):
        out.extend(project(textures(component, indexed[component]), li))
    return sorted(out, key=lambda row: texture_hash(row)[0])


def subtract_exact(generated: list[dict], known: list[dict]) -> tuple[bool, list[dict], dict | None]:
    pool = Counter(canonical(x) for x in generated)
    for row in known:
        key = canonical(row)
        if pool[key] <= 0:
            return False, [], row
        pool[key] -= 1
    residual = []
    remaining = Counter(pool)
    for row in generated:
        key = canonical(row)
        if remaining[key] > 0:
            residual.append(row); remaining[key] -= 1
    return True, residual, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("material_root", type=Path)
    ap.add_argument("catalog_json", type=Path)
    ap.add_argument("output_json", type=Path)
    ap.add_argument("--expected-missing", action="append", default=[])
    a = ap.parse_args()

    catalog = json.loads(a.catalog_json.read_text(encoding="utf-8"))
    indexed, skipped = _index_oat_materials(a.material_root)
    rows=[]; referenced=set(); hash_sources=Counter()
    generated_count=texture_total=all_available=direct_exact_count=hash_sorted_count=0
    projected_exact_count=missing_family=missing_sorted=known_subtractable=0
    first_direct=first_projected=first_subtract=None

    for cat in catalog.get("materials", []):
        material=str(cat.get("name") or "")
        if not material.startswith("*"): continue
        generated_count += 1
        parsed=parse_layered_material_name(material)
        components=[str(x["componentMaterial"]) for x in parsed["layers"]]
        referenced.update(components)
        storage=_storage_identity(material); source=indexed.get(storage)
        if source is None: raise RuntimeError(f"{material!r}: generated storage unavailable")
        generated=textures(material, source); texture_total += len(generated)
        hashes=[]; compact=[]
        for i, tex in enumerate(generated):
            h,src=texture_hash(tex); hash_sources[src]+=1; hashes.append(h)
            compact.append({"index":i,"argument":tex.get("name"),"effectiveNameHash":h,"effectiveNameHashHex":f"0x{h:08x}","semantic":tex.get("semantic"),"image":tex.get("image")})
        nondec=all(x<=y for x,y in zip(hashes,hashes[1:])); hash_sorted_count += int(nondec)
        missing=sorted({x for x in components if x not in indexed})
        direct=None; projected_exact=None; subtractable=None; residual=[]; projection_diff=None
        if not missing:
            all_available += 1
            concat=[]
            for c in components: concat.extend(textures(c,indexed[c]))
            direct=canonical(concat)==canonical(generated); direct_exact_count += int(direct)
            if not direct and first_direct is None: first_direct={"material":material,"firstDifference":first_diff(concat,generated)}
            proj=sorted_projected(components,indexed)
            projected_exact=canonical(proj)==canonical(generated); projected_exact_count += int(projected_exact)
            if not projected_exact:
                projection_diff=first_diff(proj,generated)
                if first_projected is None: first_projected={"material":material,"firstDifference":projection_diff}
        else:
            missing_family += 1; missing_sorted += int(nondec)
            known=[]
            for li,c in enumerate(components):
                if c in indexed: known.extend(project(textures(c,indexed[c]),li))
            subtractable,residual,bad=subtract_exact(generated,known)
            known_subtractable += int(subtractable)
            if not subtractable and first_subtract is None: first_subtract={"material":material,"missingKnownProjectedRow":bad}
        rows.append({"material":material,"components":components,"layers":parsed["layers"],"missingStandaloneComponents":missing,
                     "textureCount":len(generated),"hashNondecreasing":nondec,"directConcatenationExact":direct,
                     "projectedHashSortedExact":projected_exact,"projectedFirstDifference":projection_diff,
                     "knownProjectedRowsSubtractExactly":subtractable,"residualAfterKnownProjection":residual,
                     "textureOrder":compact})

    observed=sorted(x for x in referenced if x not in indexed)
    if sorted(a.expected_missing)!=observed:
        raise RuntimeError(f"exact standalone-missing set mismatch observed={observed!r} expected={sorted(a.expected_missing)!r}")
    summary={"generatedMaterialCount":generated_count,"generatedTextureRowCount":texture_total,
             "allStandaloneComponentsAvailableCount":all_available,"exactDirectConcatenationCount":direct_exact_count,
             "projectedHashSortedExactAllStandaloneCount":projected_exact_count,
             "missingStandaloneFamilyCount":missing_family,"knownProjectedRowsSubtractExactlyMissingFamilyCount":known_subtractable,
             "hashNondecreasingGeneratedCount":hash_sorted_count,"hashNondecreasingMissingStandaloneCount":missing_sorted,
             "standaloneMissingComponentCount":len(observed),"hashSourceCounts":dict(sorted(hash_sources.items()))}
    out={"format":FORMAT,"catalogFormat":catalog.get("format"),"catalogMap":catalog.get("map"),"standaloneMissingComponents":observed,
         "hashRecurrence":"h0=0; h[n+1]=(ASCII(char) XOR 33*h[n]) mod 2^32",
         "projection":"component texture rows receive Material_CreateLayered layer transform, then all rows are globally sorted by effective texture argument hash",
         "summary":summary,"firstDirectConcatenationMismatch":first_direct,"firstProjectedHashSortedMismatch":first_projected,
         "firstKnownProjectionSubtractionFailure":first_subtract,"materials":rows,
         "proofBoundary":"Exact retail OAT JSON classification only. Missing component rows are exposed only as residual generated rows; no recovered standalone Material, ownership, TechniqueSet, constants, render state, or shader/blend semantics are promoted."}
    payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode(); a.output_json.parent.mkdir(parents=True,exist_ok=True); a.output_json.write_bytes(payload)
    print(json.dumps({"summary":summary,"firstProjected":first_projected,"firstSubtract":first_subtract},indent=2,sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
