#!/usr/bin/env python3
"""Report exact top-level T6 XAsset type/order runs from XAssetList front matter."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_asset_types_v1 import asset_type_name
from t6_material_techset_top_level_walk_v1 import FOLLOW, INSERT, parse_front


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    data = a.expanded.read_bytes()
    blocks, assets, source = parse_front(data)
    runs = []
    if assets:
        start = 0
        typ = int(assets[0]["type"])
        for i in range(1, len(assets) + 1):
            next_typ = int(assets[i]["type"]) if i < len(assets) else None
            if next_typ != typ:
                rows = assets[start:i]
                runs.append({
                    "startXAssetIndex": start,
                    "endXAssetIndex": i - 1,
                    "count": i - start,
                    "xassetType": typ,
                    "xassetTypeName": asset_type_name(typ),
                    "inlineCount": sum(1 for x in rows if int(x["headerRaw"]) in (FOLLOW, INSERT)),
                    "packedOrNullCount": sum(1 for x in rows if int(x["headerRaw"]) not in (FOLLOW, INSERT)),
                })
                if i < len(assets):
                    start = i
                    typ = next_typ
    techsets = [
        {
            "xassetIndex": i,
            "headerRaw": f"0x{int(x['headerRaw']):08X}",
            "inline": int(x["headerRaw"]) in (FOLLOW, INSERT),
        }
        for i, x in enumerate(assets)
        if asset_type_name(int(x["type"])) == "TECHNIQUE_SET"
    ]
    out = {
        "format": "t6-xasset-type-run-report-v1",
        "zone": a.zone,
        "source": {
            "expandedBytes": len(data),
            "expandedSha256": hashlib.sha256(data).hexdigest(),
            "assetBodySourceStart": source,
            "blockSizes": list(blocks),
        },
        "assetCount": len(assets),
        "typeRuns": runs,
        "techniqueSetEntries": techsets,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"assetCount": len(assets), "typeRunCount": len(runs), "techniqueSetCount": len(techsets)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
