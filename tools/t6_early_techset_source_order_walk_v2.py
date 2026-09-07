#!/usr/bin/env python3
"""T6 early source-order walker v2: exact inline FX Material dispatch.

V1 deliberately failed closed when an FxElemVisuals Material handle used a
FOLLOWING/INSERT sentinel. Retail faction_seals_mp reaches that case in q8.
T6 ZoneCode marks this union member as a Material asset reference, so an inline
handle must invoke the ordinary Material loader at the current source cursor.
This adapter changes only that one dispatch rule and delegates all other source
consumption to v1.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import t6_early_techset_source_order_walk_v1 as v1


def fx_visual(c: v1.Cursor, raw: int, elem_type: int, label: str) -> dict[str, Any]:
    if elem_type == v1.FX_ELEM_TYPE_SOUND:
        return {"kind": "soundName", "value": v1.load_string(c, raw, label + ".soundName")}
    if elem_type == v1.FX_ELEM_TYPE_RUNNER:
        return {"kind": "effectDef", "value": v1.fx_effect_ref(c, raw, label + ".effectDef")}
    if elem_type == v1.FX_ELEM_TYPE_MODEL:
        return {"kind": "model", "pointer": v1.pointer_only(raw, c.blocks, label + ".model")}
    if elem_type == v1.FX_ELEM_TYPE_SPOT_LIGHT:
        return {"kind": "lightDef", "pointer": v1.pointer_only(raw, c.blocks, label + ".lightDef")}
    if elem_type in v1.FX_MATERIAL_TYPES:
        p = v1.dec(raw, c.blocks)
        node = None
        if v1.inline(raw):
            node = c.material()
            node["kind"] = "MATERIAL"
        return {"kind": "material", "pointer": p, "inlineMaterial": node}
    if elem_type == v1.FX_ELEM_TYPE_DECAL:
        raise ValueError(f"{label}: decal must be processed through FxElemMarkVisuals")
    if raw:
        raise ValueError(f"{label}: unsupported FxElemVisuals elemType={elem_type} raw=0x{raw:08X}")
    return {"kind": "anonymous", "pointer": v1.dec(raw, c.blocks)}


def install() -> None:
    # walk_fx_elem_nested resolves this symbol from the v1 module globals.
    v1.fx_visual = fx_visual


def walk(expanded: Path, start_asset: int, end_asset: int, targets: set[int]) -> dict[str, Any]:
    install()
    out = v1.walk(expanded, start_asset, end_asset, targets)
    out["format"] = "t6-early-techset-source-order-walk-v2"
    out["v2Rule"] = (
        "FxElemVisuals material FOLLOWING/INSERT handles dispatch Cursor.material() "
        "at the exact current source cursor; packed/null handles consume no source bytes."
    )
    return out


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
