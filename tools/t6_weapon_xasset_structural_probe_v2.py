#!/usr/bin/env python3
"""T6 WEAPON structural probe v2 with strict packed-front XString resolution.

v2 preserves the complete v1 structural/cardinality proof and adds one narrow
identity promotion path: a packed WeaponVariantDef.szInternalName may be named
only when its VIRTUAL offset lands exactly on the first byte of a FOLLOWING
ScriptString/dependency string in the independently replayed XAssetList front.

Important block correction
--------------------------
WeaponVariantDef itself is a TEMP-block asset, but member loading occurs under
T6's default normal VIRTUAL block. szInternalName is an XString. Therefore a
packed szInternalName is converted as a normal VIRTUAL block offset, not as a
TEMP alias. This matches the generated T6 loading contract and is kept separate
from retail promotion: exact identities still require exact retained bytes.

This tool deliberately does not replay later asset-body VIRTUAL allocations.
Such targets remain unresolved instead of being guessed from nearby strings.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def enrich_packed_names(result: dict[str, Any], frontmap, front: dict[str, Any]) -> dict[str, Any]:
    raw_front = result.get("front") or {}
    if int(front["assetCount"]) != int(raw_front.get("assetCount", -1)):
        raise ValueError("front-map asset count disagrees with raw XAsset parser")
    if int(front["assetBodyRawOffset"]) != int(raw_front.get("assetBodyStreamRawOffset", -1)):
        raise ValueError("front-map asset-body source offset disagrees with raw XAsset parser")

    attempted = 0
    exact = 0
    classifications: dict[str, int] = {}
    for rec in result.get("structuralCandidates", []):
        if rec.get("internalNameStatus") != "unresolved-packed-name-pointer":
            continue
        pointer = rec.get("internalNamePointer") or {}
        raw = pointer.get("raw_u32")
        if not isinstance(raw, int):
            continue
        attempted += 1
        resolution = frontmap.resolve_packed_pointer(front, raw)
        rec["packedInternalNameResolution"] = resolution
        status = str(resolution.get("status"))
        classifications[status] = classifications.get(status, 0) + 1
        if status == "exact-front-xstring":
            text = resolution.get("text")
            if not isinstance(text, str) or not text:
                raise ValueError("exact-front-xstring result has no nonempty text")
            rec["internalName"] = text
            rec["internalNameStatus"] = "exact-packed-front-xstring"
            exact += 1

    # v1 lists/bindings retain references to the same candidate dictionaries.
    # Recompute only the summary fields affected by this enrichment.
    bindings = result.get("bindings", [])
    exact_names = sum(
        1 for b in bindings
        if b.get("status") == "exact-by-single-inline-weapon-cardinality"
        and (b.get("weaponVariantDef") or {}).get("internalNameStatus")
        in {"exact-inline-following", "exact-packed-front-xstring"}
    )
    result.setdefault("summary", {})["exactInternalNames"] = exact_names
    result["summary"]["exactPackedFrontInternalNames"] = sum(
        1 for b in bindings
        if b.get("status") == "exact-by-single-inline-weapon-cardinality"
        and (b.get("weaponVariantDef") or {}).get("internalNameStatus") == "exact-packed-front-xstring"
    )
    result["packedXStringFrontReplay"] = {
        "format": front.get("format"),
        "assetBodyRawOffset": front["assetBodyRawOffset"],
        "virtualOffsetAfterAssetArray": front["virtualOffsetAfterAssetArray"],
        "attemptedPackedInternalNames": attempted,
        "exactFrontXStrings": exact,
        "classifications": classifications,
        "scope": "VIRTUAL front allocations only; no asset-body allocation replay",
    }
    result["format"] = "t6-weapon-xasset-structural-probe-v2"
    result["proofBoundaryV2"] = (
        "All v1 WeaponVariantDef structural and cardinality gates remain unchanged. "
        "v2 promotes a packed szInternalName only when its block-5 VIRTUAL offset "
        "matches exactly the first byte of a replayed FOLLOWING ScriptString or "
        "dependency string before the XAsset body stream. String interiors, front "
        "pointer/asset arrays, alignment holes, other blocks, and later VIRTUAL "
        "asset-body allocations are not promoted. WeaponVariantDef root allocation "
        "is TEMP, while szInternalName XString loading occurs in the default normal "
        "VIRTUAL block; packed-name resolution is therefore a normal-offset problem, "
        "not TEMP alias replay."
    )
    return result


def probe(data: bytes, rawmod, v1mod, frontmap) -> dict[str, Any]:
    result = v1mod.probe(data, rawmod)
    front = frontmap.build_front_map(data)
    return enrich_packed_names(result, frontmap, front)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--raw-parser", type=Path, default=Path(__file__).with_name("t6_raw_xasset_inventory_v2.py"))
    ap.add_argument("--v1-probe", type=Path, default=Path(__file__).with_name("t6_weapon_xasset_structural_probe_v1.py"))
    ap.add_argument("--front-map", type=Path, default=Path(__file__).with_name("t6_virtual_front_map_v1.py"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = args.expanded.read_bytes()
    rawmod = load_module(args.raw_parser, "t6_raw_xasset_inventory_v2_for_weapon_probe")
    v1mod = load_module(args.v1_probe, "t6_weapon_xasset_structural_probe_v1_for_v2")
    frontmap = load_module(args.front_map, "t6_virtual_front_map_v1_for_weapon_probe")
    out = probe(data, rawmod, v1mod, frontmap)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
