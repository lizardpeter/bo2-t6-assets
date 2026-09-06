#!/usr/bin/env python3
"""Exact proof for Nuketown's final unresolved static Material alias.

This does not infer identity from order, naming, mesh similarity, or appearance.
It proves the retail Material* alias path used by XAssets 289 -> 296:

* XAsset 289 has one VIRTUAL materialHandles pointer slot whose serialized value
  is FOLLOWING, and that slot dispatches the unique inline Material
  mc/mtl_ac_prs_vehicle_sheet_a.
* XAssets 290..296 each have one packed block-5 Material* reference to exact
  offset 26,834,420.
* no earlier XModel in the reconstructed prefix refers to that target, and the
  exact inline material has one origin before the consumers.
* pinned OpenAssetTools T6 loader-generation source is checked for the retail
  semantics that register asset pointer-array slots with AddPointerLookup and
  resolve packed TEMP-asset pointers through ConvertOffsetToAliasLookup.

Under those semantics a later packed Material* can resolve only through an alias
slot already registered in the VIRTUAL block.  Since the x289 Material* is
FOLLOWING (not INSERT), the registered alias is its materialHandles[0] slot.
Therefore block 5 / 26,834,420 is that exact slot and its Material identity is
mc/mtl_ac_prs_vehicle_sheet_a.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from t6_clipmap_normalize_v5 import ASSET_TYPE_XMODEL, parse_top_level_xasset_table
from t6_clipmap_normalize_v6 import scan_required_xmodels, walk_map_prefix_stringtable
from t6_xmodel_serialized_walker import XModelWalker

EXPECTED_EXPANDED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
EXPECTED_OAT_COMMIT = "2ca512abe7cb82d70a94d5ad7846043c3978862d"
TARGET_BLOCK = 5
TARGET_OFFSET = 26_834_420
ORIGIN_XASSET = 289
CONSUMERS = tuple(range(290, 297))
MATERIAL = "mc/mtl_ac_prs_vehicle_sheet_a"
EXPECTED_ORIGIN_MODEL = "ny_harbor_veh_civ_car_a_10"
EXPECTED_CONSUMER_MODELS = {
    290: "ny_harbor_veh_civ_car_a_11",
    291: "ny_harbor_veh_civ_car_a_2",
    292: "ny_harbor_veh_civ_car_a_4",
    293: "ny_harbor_veh_civ_car_a_6",
    294: "ny_harbor_veh_civ_car_a_7",
    295: "ny_harbor_veh_civ_car_a_8",
    296: "ny_harbor_veh_civ_car_a_9",
}

FOLLOW = 0xFFFFFFFF


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def require_text(path: Path, snippets: list[str]) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    missing = [s for s in snippets if s not in text]
    if missing:
        raise ValueError(f"{path}: missing required loader semantics: {missing}")
    return {"path": str(path), "bytes": len(raw), "sha256": sha256_bytes(raw), "checkedSnippets": snippets}


def pointer_tuple(h: dict) -> tuple[int, int] | None:
    p = h.get("pointer") or h
    if p.get("kind") == "packed" and p.get("block") is not None and p.get("offset") is not None:
        return int(p["block"]), int(p["offset"])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--oat-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    data = a.expanded.read_bytes()
    expanded_sha = sha256_bytes(data)
    if expanded_sha != EXPECTED_EXPANDED_SHA256:
        raise SystemExit(f"expanded SHA mismatch {expanded_sha} != {EXPECTED_EXPANDED_SHA256}")

    oat_commit = subprocess.check_output(["git", "-C", str(a.oat_root), "rev-parse", "HEAD"], text=True).strip()
    if oat_commit != EXPECTED_OAT_COMMIT:
        raise SystemExit(f"OAT commit mismatch {oat_commit} != {EXPECTED_OAT_COMMIT}")

    loader_sources = {
        "xmodelZoneCode": require_text(
            a.oat_root / "src/ZoneCode/Game/T6/XAssets/XModel.txt",
            ["use XModel;", "set block XFILE_BLOCK_TEMP;", "set count materialHandles numsurfs;"],
        ),
        "materialZoneCode": require_text(
            a.oat_root / "src/ZoneCode/Game/T6/XAssets/Material.txt",
            ["use Material;", "set block XFILE_BLOCK_TEMP;"],
        ),
        "loadTemplate": require_text(
            a.oat_root / "src/ZoneCodeGeneratorLib/Generating/Templates/ZoneLoadTemplate.cpp",
            [
                "m_stream.AddPointerLookup(&{0}[index]",
                "StructureComputations(info).IsAsset()",
                "ConvertOffsetToAliasLookup",
            ],
        ),
        "zoneInputStream": require_text(
            a.oat_root / "src/ZoneLoading/Zone/Stream/ZoneInputStream.cpp",
            [
                "void AddPointerLookup(void* alias, const void* blockPtr) override",
                "void* ConvertOffsetToAliasLookup(const void* offset) override",
                "m_pointer_redirect_lookup.find(offsetInt)",
            ],
        ),
    }

    table = parse_top_level_xasset_table(data)
    prefix = walk_map_prefix_stringtable(data, table)
    entries = table["entries"]
    xmodel_indices = [i for i, e in enumerate(entries) if e["type"] == ASSET_TYPE_XMODEL and i <= max(CONSUMERS)]
    records = scan_required_xmodels(data, prefix["sourceEnd"], len(xmodel_indices), prefix["logicalToText"])
    if len(records) != len(xmodel_indices):
        raise ValueError("XModel scan count mismatch")
    by_record = {idx: rec for idx, rec in zip(xmodel_indices, records)}

    walked: dict[int, dict] = {}
    inline_before_consumers: list[dict] = []
    target_refs_before_consumers: list[dict] = []
    for idx in xmodel_indices:
        rec = by_record[idx]
        w = XModelWalker(data, rec["fixedSourceStart"]).walk_xmodel()
        if w.get("blockers"):
            raise ValueError(f"XAsset {idx} walker blockers: {w['blockers']}")
        walked[idx] = w
        if idx <= ORIGIN_XASSET:
            for row in (w.get("details") or {}).get("inlineMaterials") or []:
                if row.get("name") == MATERIAL:
                    inline_before_consumers.append({"xassetIndex": idx, "modelName": rec["name"], **row})
        if idx < min(CONSUMERS):
            for si, h in enumerate((w.get("xmodel") or {}).get("materialHandles") or []):
                if pointer_tuple(h) == (TARGET_BLOCK, TARGET_OFFSET):
                    target_refs_before_consumers.append({"xassetIndex": idx, "modelName": rec["name"], "surfaceIndex": si})

    if ORIGIN_XASSET not in walked or any(i not in walked for i in CONSUMERS):
        raise ValueError("required XAssets were not reconstructed")

    origin_rec = by_record[ORIGIN_XASSET]
    origin = walked[ORIGIN_XASSET]
    ox = origin["xmodel"]
    if origin_rec["name"] != EXPECTED_ORIGIN_MODEL:
        raise ValueError(f"X289 model mismatch {origin_rec['name']}")
    if int(ox["numSurfs"]) != 1 or len(ox.get("materialHandles") or []) != 1:
        raise ValueError("X289 is not the expected one-slot Material* owner")
    oh = ox["materialHandles"][0]
    if oh.get("kind") != "following" or int(oh.get("raw", -1)) != FOLLOW:
        raise ValueError(f"X289 materialHandles[0] is not FOLLOWING: {oh}")
    mh_sections = [s for s in origin["sections"] if s["name"] == "XModel.materialHandles.fixed"]
    if len(mh_sections) != 1 or int(mh_sections[0].get("count", -1)) != 1 or int(mh_sections[0].get("bytes", -1)) != 4:
        raise ValueError(f"X289 materialHandles fixed section mismatch: {mh_sections}")
    origin_inline = [r for r in (origin.get("details") or {}).get("inlineMaterials") or [] if r.get("name") == MATERIAL]
    if len(origin_inline) != 1 or origin_inline[0].get("label") != "XModel.materialHandles[0]":
        raise ValueError(f"X289 inline Material origin mismatch: {origin_inline}")
    if len(inline_before_consumers) != 1 or inline_before_consumers[0]["xassetIndex"] != ORIGIN_XASSET:
        raise ValueError(f"Material has competing inline origins before consumers: {inline_before_consumers}")
    if target_refs_before_consumers:
        raise ValueError(f"target packed alias appears before first consumer: {target_refs_before_consumers}")

    consumer_rows = []
    for idx in CONSUMERS:
        rec = by_record[idx]
        w = walked[idx]
        if rec["name"] != EXPECTED_CONSUMER_MODELS[idx]:
            raise ValueError(f"consumer XAsset {idx} name mismatch {rec['name']}")
        hs = w["xmodel"].get("materialHandles") or []
        if len(hs) != 1:
            raise ValueError(f"consumer XAsset {idx} does not have exactly one material handle")
        h = hs[0]
        if pointer_tuple(h) != (TARGET_BLOCK, TARGET_OFFSET):
            raise ValueError(f"consumer XAsset {idx} packed target mismatch: {h}")
        consumer_rows.append({
            "xassetIndex": idx,
            "modelName": rec["name"],
            "raw": int(h["raw"]),
            "rawHex": h.get("rawHex"),
            "block": int(h["block"]),
            "offset": int(h["offset"]),
        })

    proof = {
        "format": "t6-nuketown-car-material-alias-proof-v1",
        "map": "mp_nuketown_2020",
        "source": {"expandedBytes": len(data), "expandedSha256": expanded_sha},
        "loader": {
            "project": "Laupetin/OpenAssetTools",
            "commit": oat_commit,
            "sourceChecks": loader_sources,
            "semantics": [
                "XModel and Material fixed objects are TEMP assets while materialHandles is loaded from the normal VIRTUAL block.",
                "asset pointer-array slots are registered with AddPointerLookup at their block-buffer address.",
                "packed TEMP-asset pointers resolve with ConvertOffsetToAliasLookup against an already registered alias/pointer slot.",
                "therefore a packed Material target cannot resolve to a future, not-yet-registered pointer slot.",
            ],
        },
        "origin": {
            "xassetIndex": ORIGIN_XASSET,
            "modelName": origin_rec["name"],
            "surfaceCount": int(ox["numSurfs"]),
            "materialHandleRaw": int(oh["raw"]),
            "materialHandleKind": oh["kind"],
            "materialHandleSourceOffset": int(mh_sections[0]["start"]),
            "inlineMaterial": MATERIAL,
            "uniqueInlineOriginBeforeConsumers": True,
        },
        "packedConsumers": consumer_rows,
        "packedConsumerCount": len(consumer_rows),
        "conclusion": {
            "block": TARGET_BLOCK,
            "offset": TARGET_OFFSET,
            "material": MATERIAL,
            "status": "exact-retail-material-pointer-resolution",
            "conflicts": 0,
        },
        "proofBoundary": "No old GLB assignment, render appearance, material/model name similarity, mesh similarity, adjacency-only inference, or fitted cursor constant participates. The identity follows from the exact retail pointer values plus pinned TEMP-asset alias-registration/resolution semantics.",
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw = a.out.read_bytes()
    print(json.dumps({
        "out": str(a.out),
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "mapping": f"{TARGET_BLOCK}:{TARGET_OFFSET} -> {MATERIAL}",
        "packedConsumers": len(consumer_rows),
        "conflicts": 0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
