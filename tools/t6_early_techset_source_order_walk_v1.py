#!/usr/bin/env python3
"""Exact early T6 PC32 XAsset source-order walker for character TechniqueSets.

This module advances a single serialized-source cursor through early retail T6
XAssets without scanning for names or fixed-record byte patterns. It supports
exactly the asset classes needed to reach the faction_seals_mp SEAL6
TechniqueSets q10/q17/q20:

- KEYVALUEPAIRS (49)
- SCRIPTPARSETREE (48)
- MATERIAL (6)
- TECHNIQUE_SET (7)
- FX (33)
- XMODEL (5)

Material/TechniqueSet replay is delegated to the source-closed Cursor in
`t6_material_techset_top_level_walk_v1.py`. XModel replay is delegated to the
retail-validated `XModelWalker`. The FX walker follows the T6 ZoneCode contract
for FxEffectDef/FxElemDef exactly, including counted velocity/visual samples,
conditional visual unions, effect-name refs, trails, spot lights and spawn
sounds. Packed/null references consume zero source bytes; unsupported inline
external XAssets fail closed.

No serialized start is selected by name, scan rank, adjacency heuristic, or
visual matching.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from t6_asset_types_v1 import ASSET_TYPE_BY_NAME, asset_type_name
from t6_material_techset_top_level_walk_v1 import Cursor, FOLLOW, INSERT, dec, parse_front
from t6_xmodel_serialized_walker import XModelWalker

KEYVALUEPAIRS = ASSET_TYPE_BY_NAME["KEYVALUEPAIRS"]
SCRIPTPARSETREE = ASSET_TYPE_BY_NAME["SCRIPTPARSETREE"]
MATERIAL = ASSET_TYPE_BY_NAME["MATERIAL"]
TECHSET = ASSET_TYPE_BY_NAME["TECHNIQUE_SET"]
FX = ASSET_TYPE_BY_NAME["FX"]
XMODEL = ASSET_TYPE_BY_NAME["XMODEL"]

FX_EFFECT_DEF_SIZE = 76
FX_ELEM_DEF_SIZE = 292
FX_ELEM_VEL_STATE_SAMPLE_SIZE = 96
FX_ELEM_VIS_STATE_SAMPLE_SIZE = 48
FX_ELEM_MARK_VISUALS_SIZE = 8
FX_ELEM_VISUALS_SIZE = 4
FX_TRAIL_DEF_SIZE = 28
FX_TRAIL_VERTEX_SIZE = 20
FX_SPOT_LIGHT_DEF_SIZE = 12

FX_ELEM_TYPE_TRAIL = 5
FX_ELEM_TYPE_MODEL = 7
FX_ELEM_TYPE_SPOT_LIGHT = 9
FX_ELEM_TYPE_SOUND = 10
FX_ELEM_TYPE_DECAL = 11
FX_ELEM_TYPE_RUNNER = 12
FX_MATERIAL_TYPES = frozenset((0, 1, 2, 3, 4, 5, 6))


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def i16(data: bytes, off: int) -> int:
    return struct.unpack_from("<h", data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def i32(data: bytes, off: int) -> int:
    return struct.unpack_from("<i", data, off)[0]


def inline(raw: int) -> bool:
    return raw in (FOLLOW, INSERT)


def pointer_only(raw: int, blocks: tuple[int, ...], label: str) -> dict[str, Any]:
    p = dec(raw, blocks)
    if p["kind"] in ("following", "insert"):
        raise ValueError(f"{label}: inline external XAsset requires dispatch")
    return p


def load_string(c: Cursor, raw: int, label: str) -> dict[str, Any]:
    try:
        return c.string(raw)
    except Exception as exc:
        raise ValueError(f"{label}: {exc}") from exc


def walk_keyvaluepairs(c: Cursor) -> dict[str, Any]:
    d = c.d
    s = c.take(12)
    name_raw = u32(d, s)
    count = u32(d, s + 4)
    rows_raw = u32(d, s + 8)
    if count > 1_000_000:
        raise ValueError(f"KeyValuePairs implausible count {count} at {s}")
    name = load_string(c, name_raw, "KeyValuePairs.name")
    rows = []
    rows_ptr = dec(rows_raw, c.blocks)
    if inline(rows_raw):
        rs = c.take(count * 12)
        for i in range(count):
            o = rs + i * 12
            value_raw = u32(d, o + 8)
            value = load_string(c, value_raw, f"KeyValuePairs[{i}].value")
            rows.append({
                "index": i,
                "keyHash": u32(d, o),
                "namespaceHash": u32(d, o + 4),
                "valuePointer": dec(value_raw, c.blocks),
                "value": value,
            })
    elif count:
        raise ValueError(f"KeyValuePairs count={count} but keyValuePairs table is not inline")
    return {
        "kind": "KEYVALUEPAIRS",
        "fixedStart": s,
        "end": c.p,
        "namePointer": dec(name_raw, c.blocks),
        "name": name,
        "numVariables": count,
        "keyValuePairsPointer": rows_ptr,
        "rows": rows,
    }


def walk_scriptparsetree(c: Cursor) -> dict[str, Any]:
    d = c.d
    s = c.take(12)
    name_raw = u32(d, s)
    length = i32(d, s + 4)
    buffer_raw = u32(d, s + 8)
    if length < 0 or length > len(d):
        raise ValueError(f"ScriptParseTree invalid len {length} at {s}")
    name = load_string(c, name_raw, "ScriptParseTree.name")
    buffer_start = None
    bp = dec(buffer_raw, c.blocks)
    if inline(buffer_raw):
        buffer_start = c.take(length + 1)
    elif length:
        if bp["kind"] == "null":
            raise ValueError(f"ScriptParseTree len={length} with null buffer at {s}")
    return {
        "kind": "SCRIPTPARSETREE",
        "fixedStart": s,
        "end": c.p,
        "namePointer": dec(name_raw, c.blocks),
        "name": name,
        "len": length,
        "bufferPointer": bp,
        "bufferStart": buffer_start,
        "bufferSerializedBytes": (length + 1) if buffer_start is not None else 0,
    }


def fx_effect_ref(c: Cursor, raw: int, label: str) -> dict[str, Any]:
    return load_string(c, raw, label)


def fx_visual(c: Cursor, raw: int, elem_type: int, label: str) -> dict[str, Any]:
    if elem_type == FX_ELEM_TYPE_SOUND:
        return {"kind": "soundName", "value": load_string(c, raw, label + ".soundName")}
    if elem_type == FX_ELEM_TYPE_RUNNER:
        return {"kind": "effectDef", "value": fx_effect_ref(c, raw, label + ".effectDef")}
    if elem_type == FX_ELEM_TYPE_MODEL:
        return {"kind": "model", "pointer": pointer_only(raw, c.blocks, label + ".model")}
    if elem_type == FX_ELEM_TYPE_SPOT_LIGHT:
        return {"kind": "lightDef", "pointer": pointer_only(raw, c.blocks, label + ".lightDef")}
    if elem_type in FX_MATERIAL_TYPES:
        return {"kind": "material", "pointer": pointer_only(raw, c.blocks, label + ".material")}
    if elem_type == FX_ELEM_TYPE_DECAL:
        raise ValueError(f"{label}: decal must be processed through FxElemMarkVisuals")
    if raw:
        raise ValueError(f"{label}: unsupported FxElemVisuals elemType={elem_type} raw=0x{raw:08X}")
    return {"kind": "anonymous", "pointer": dec(raw, c.blocks)}


def walk_fx_trail(c: Cursor, raw: int, label: str) -> dict[str, Any]:
    p = dec(raw, c.blocks)
    if not inline(raw):
        return {"pointer": p, "inline": None}
    d = c.d
    s = c.take(FX_TRAIL_DEF_SIZE)
    vert_count = i32(d, s + 12)
    verts_raw = u32(d, s + 16)
    ind_count = i32(d, s + 20)
    inds_raw = u32(d, s + 24)
    if vert_count < 0 or ind_count < 0 or vert_count > 1_000_000 or ind_count > 4_000_000:
        raise ValueError(f"{label}: invalid trail counts {vert_count}/{ind_count}")
    verts_start = None
    inds_start = None
    if inline(verts_raw):
        verts_start = c.take(vert_count * FX_TRAIL_VERTEX_SIZE)
    elif vert_count and dec(verts_raw, c.blocks)["kind"] == "null":
        raise ValueError(f"{label}: vertCount={vert_count} with null verts")
    if inline(inds_raw):
        inds_start = c.take(ind_count * 2)
    elif ind_count and dec(inds_raw, c.blocks)["kind"] == "null":
        raise ValueError(f"{label}: indCount={ind_count} with null inds")
    return {
        "pointer": p,
        "inline": {
            "fixedStart": s,
            "end": c.p,
            "vertCount": vert_count,
            "vertsPointer": dec(verts_raw, c.blocks),
            "vertsStart": verts_start,
            "indCount": ind_count,
            "indsPointer": dec(inds_raw, c.blocks),
            "indsStart": inds_start,
        },
    }


def walk_fx_elem_nested(c: Cursor, base: int, index: int) -> dict[str, Any]:
    d = c.d
    elem_type = d[base + 184]
    visual_count = d[base + 185]
    vel_count = d[base + 186]
    vis_count = d[base + 187]
    if elem_type > FX_ELEM_TYPE_RUNNER:
        raise ValueError(f"FxElemDef[{index}] invalid elemType {elem_type}")

    vel_raw = u32(d, base + 188)
    vis_raw = u32(d, base + 192)
    visuals_raw = u32(d, base + 196)
    vel_start = None
    vis_start = None
    if inline(vel_raw):
        vel_start = c.take((vel_count + 1) * FX_ELEM_VEL_STATE_SAMPLE_SIZE)
    else:
        dec(vel_raw, c.blocks)
    if inline(vis_raw):
        vis_start = c.take((vis_count + 1) * FX_ELEM_VIS_STATE_SAMPLE_SIZE)
    else:
        dec(vis_raw, c.blocks)

    visuals: dict[str, Any]
    if elem_type == FX_ELEM_TYPE_DECAL:
        vp = dec(visuals_raw, c.blocks)
        marks = []
        if inline(visuals_raw):
            ms = c.take(visual_count * FX_ELEM_MARK_VISUALS_SIZE)
            for j in range(visual_count):
                m = ms + j * FX_ELEM_MARK_VISUALS_SIZE
                mats = []
                for k in range(2):
                    raw = u32(d, m + 4 * k)
                    mats.append(pointer_only(raw, c.blocks, f"FxElemDef[{index}].mark[{j}].material[{k}]"))
                marks.append({"index": j, "materials": mats})
            visuals = {"mode": "markArray", "pointer": vp, "fixedStart": ms, "marks": marks}
        else:
            visuals = {"mode": "markArray", "pointer": vp, "fixedStart": None, "marks": marks}
    elif visual_count > 1:
        vp = dec(visuals_raw, c.blocks)
        values = []
        vs = None
        if inline(visuals_raw):
            vs = c.take(visual_count * FX_ELEM_VISUALS_SIZE)
            for j in range(visual_count):
                values.append(fx_visual(c, u32(d, vs + 4 * j), elem_type, f"FxElemDef[{index}].visuals[{j}]"))
        visuals = {"mode": "array", "pointer": vp, "fixedStart": vs, "values": values}
    else:
        visuals = {"mode": "instance", "value": fx_visual(c, visuals_raw, elem_type, f"FxElemDef[{index}].visual")}

    refs = {}
    for name, off in (
        ("effectOnImpact", 224),
        ("effectOnDeath", 228),
        ("effectEmitted", 232),
        ("effectAttached", 252),
    ):
        raw = u32(d, base + off)
        refs[name] = fx_effect_ref(c, raw, f"FxElemDef[{index}].{name}")

    ext_raw = u32(d, base + 256)
    if elem_type == FX_ELEM_TYPE_TRAIL:
        extended = {"kind": "trail", **walk_fx_trail(c, ext_raw, f"FxElemDef[{index}].extended.trail")}
    elif elem_type == FX_ELEM_TYPE_SPOT_LIGHT:
        ep = dec(ext_raw, c.blocks)
        es = c.take(FX_SPOT_LIGHT_DEF_SIZE) if inline(ext_raw) else None
        extended = {"kind": "spotLight", "pointer": ep, "fixedStart": es}
    else:
        ep = dec(ext_raw, c.blocks)
        if ep["kind"] in ("following", "insert"):
            raise ValueError(f"FxElemDef[{index}].extended inline for elemType={elem_type}")
        extended = {"kind": "none", "pointer": ep}

    spawn_sound_raw = u32(d, base + 280)
    spawn_sound = load_string(c, spawn_sound_raw, f"FxElemDef[{index}].spawnSound")

    return {
        "index": index,
        "fixedStart": base,
        "elemType": elem_type,
        "visualCount": visual_count,
        "velIntervalCount": vel_count,
        "visStateIntervalCount": vis_count,
        "velSamplesPointer": dec(vel_raw, c.blocks),
        "velSamplesStart": vel_start,
        "visSamplesPointer": dec(vis_raw, c.blocks),
        "visSamplesStart": vis_start,
        "visuals": visuals,
        "effectRefs": refs,
        "extended": extended,
        "spawnSound": spawn_sound,
    }


def walk_fx(c: Cursor) -> dict[str, Any]:
    d = c.d
    s = c.take(FX_EFFECT_DEF_SIZE)
    name_raw = u32(d, s)
    looping = i16(d, s + 8)
    one_shot = i16(d, s + 10)
    emission = i16(d, s + 12)
    if min(looping, one_shot, emission) < 0:
        raise ValueError(f"FxEffectDef negative elem counts at {s}: {looping}/{one_shot}/{emission}")
    total = looping + one_shot + emission
    if total > 100_000:
        raise ValueError(f"FxEffectDef implausible elem count {total} at {s}")
    elem_raw = u32(d, s + 28)
    name = load_string(c, name_raw, "FxEffectDef.name")
    ep = dec(elem_raw, c.blocks)
    elems = []
    elem_start = None
    if inline(elem_raw):
        elem_start = c.take(total * FX_ELEM_DEF_SIZE)
        for i in range(total):
            elems.append(walk_fx_elem_nested(c, elem_start + i * FX_ELEM_DEF_SIZE, i))
    elif total:
        if ep["kind"] == "null":
            raise ValueError(f"FxEffectDef elemCount={total} with null elemDefs")
    return {
        "kind": "FX",
        "fixedStart": s,
        "end": c.p,
        "namePointer": dec(name_raw, c.blocks),
        "name": name,
        "elemDefCountLooping": looping,
        "elemDefCountOneShot": one_shot,
        "elemDefCountEmission": emission,
        "elemDefCount": total,
        "elemDefsPointer": ep,
        "elemDefsStart": elem_start,
        "elemDefs": elems,
    }


def walk(expanded: Path, start_asset: int, end_asset: int, targets: set[int]) -> dict[str, Any]:
    data = expanded.read_bytes()
    blocks, assets, source = parse_front(data)
    if not (0 <= start_asset <= end_asset < len(assets)):
        raise ValueError(f"invalid XAsset range {start_asset}..{end_asset} for {len(assets)} assets")
    if start_asset != 0:
        raise ValueError("v1 is fail-closed to source replay beginning at XAsset 0")

    c = Cursor(data, source, blocks)
    rows = []
    target_nodes = []
    for q in range(start_asset, end_asset + 1):
        a = assets[q]
        raw = int(a["headerRaw"])
        if not inline(raw):
            raise ValueError(f"XAsset {q} top-level header is not inline: 0x{raw:08X}")
        typ = int(a["type"])
        before = c.p
        if typ == KEYVALUEPAIRS:
            node = walk_keyvaluepairs(c)
        elif typ == SCRIPTPARSETREE:
            node = walk_scriptparsetree(c)
        elif typ == MATERIAL:
            node = c.material()
            node["kind"] = "MATERIAL"
        elif typ == TECHSET:
            node = c.techset()
            node["kind"] = "TECHNIQUE_SET"
        elif typ == FX:
            node = walk_fx(c)
        elif typ == XMODEL:
            xw = XModelWalker(data, before).walk_xmodel()
            if xw.get("blockers"):
                raise ValueError(f"XAsset {q} XModel blockers: {xw['blockers']}")
            end = int(xw["assetSerializedEnd"])
            if end <= before:
                raise ValueError(f"XAsset {q} XModel did not advance")
            c.p = end
            node = {
                "kind": "XMODEL",
                "xmodelName": (xw.get("xmodel") or {}).get("name"),
                "numBones": (xw.get("xmodel") or {}).get("numBones"),
                "numSurfs": (xw.get("xmodel") or {}).get("numSurfs"),
                "walkerAssetSerializedEnd": end,
            }
        else:
            raise ValueError(f"unsupported top-level XAsset type {typ} ({asset_type_name(typ)}) at q{q}")

        row = {
            "xassetIndex": q,
            "xassetType": typ,
            "xassetTypeName": asset_type_name(typ),
            "sourceStart": before,
            "sourceEnd": c.p,
            "serializedBytes": c.p - before,
            "node": node,
        }
        rows.append(row)
        if q in targets:
            if typ != TECHSET:
                raise ValueError(f"target q{q} is not a TechniqueSet")
            target_nodes.append(row)

    missing = sorted(targets - {x["xassetIndex"] for x in target_nodes})
    if missing:
        raise ValueError(f"target TechniqueSets not replayed: {missing}")

    return {
        "format": "t6-early-techset-source-order-walk-v1",
        "source": {
            "expandedBytes": len(data),
            "expandedSha256": hashlib.sha256(data).hexdigest(),
            "assetBodySourceStart": source,
            "blockSizes": list(blocks),
        },
        "startAssetIndex": start_asset,
        "endAssetIndex": end_asset,
        "sourceStart": source,
        "sourceEnd": c.p,
        "rows": rows,
        "targetTechniqueSets": target_nodes,
        "directInlineShaders": [x for x in c.inlineShaders if x.get("program") and x["program"].get("direct")],
        "proofBoundary": (
            "Every serialized start in this report is obtained by one continuous top-level XAsset source-order replay from the exact post-XAsset-array source cursor. "
            "No TechniqueSet start is selected by raw-byte scanning, name matching, scan rank, adjacency, or visual similarity. Packed/null references consume zero source bytes; unsupported inline external XAssets fail closed."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--start-asset", type=int, default=0)
    ap.add_argument("--end-asset", type=int, default=20)
    ap.add_argument("--targets", default="10,17,20")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    targets = {int(x, 0) for x in a.targets.split(",") if x.strip()}
    out = walk(a.expanded, a.start_asset, a.end_asset, targets)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "sourceEnd": out["sourceEnd"],
        "assetCount": len(out["rows"]),
        "targets": [
            {
                "q": r["xassetIndex"],
                "start": r["sourceStart"],
                "end": r["sourceEnd"],
                "name": ((r.get("node") or {}).get("name") or {}).get("value"),
            }
            for r in out["targetTechniqueSets"]
        ],
        "directInlineShaderCount": len(out["directInlineShaders"]),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
