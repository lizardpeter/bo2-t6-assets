#!/usr/bin/env python3
"""Retail T6 XAnim delta-branch census v3.

V3 closes the two remaining structural-count gaps from v2 by recognizing a directly
observed retail empty-placeholder XAnimParts serialization class.

The class is intentionally exact and narrow:
  - fixed XAnimParts bytes are exactly: namePtr=FOLLOW + 100 zero bytes
  - therefore numframes/framerate/frequency/flags/counts/pointers/assetType are all zero
  - the only serialized child is the inline name
  - the inline name begins with ',' and the remainder uses the normal T6 asset-name
    character set

Direct retained fixtures:
  - zm_tomb XAsset indices 3480..3501: 22 consecutive `,viewmodel_raygun_mk2_*`
    empty records
  - mp_nuketown_2020 XAsset index 787: `,viewmodel_m67_idle`

These records were invisible to the v1/v2 24/30-Hz anchor scan by construction.  V3
adds them only after the ordinary structural census and never treats arbitrary zero-frame
or assetType-0 candidates as XAnimParts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import t6_xanim_retail_delta_branch_census_v2 as v2

base = v2.v1
EMPTY_FIXED = base.FOLLOW.to_bytes(4, "little") + (b"\0" * 100)
EMPTY_FIXED_SHA256 = hashlib.sha256(EMPTY_FIXED).hexdigest()
EMPTY_NAME_RE = re.compile(r",[A-Za-z0-9_./+\-]{2,254}\Z")


def empty_placeholders(data: bytes):
    out = []
    search = 0
    while True:
        start = data.find(EMPTY_FIXED, search)
        if start < 0:
            break
        search = start + 1
        name_start = start + base.XANIM_SIZE
        name_end = data.find(b"\0", name_start, min(len(data), name_start + 256))
        if name_end <= name_start:
            continue
        try:
            name = data[name_start:name_end].decode("ascii")
        except UnicodeDecodeError:
            continue
        if not EMPTY_NAME_RE.fullmatch(name):
            continue
        out.append({
            "start": start,
            "end": name_end + 1,
            "bytes": name_end + 1 - start,
            "name": name,
            "numframes": 0,
            "framerate": 0.0,
            "frequency": 0.0,
            "assetType": 0,
            "fixedSha256": EMPTY_FIXED_SHA256,
        })
    return out


def census(path: Path):
    result = base.census(path)
    data = path.read_bytes()
    empty = empty_placeholders(data)
    result["emptyPlaceholderCount"] = len(empty)
    result["emptyPlaceholders"] = empty
    result["structuralRecordCount"] += len(empty)
    result["inlineNames"] += len(empty)
    result["countClosesExactly"] = result["structuralRecordCount"] == result["expectedXAnimCount"]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    zones = [census(path) for path in args.expanded]
    exact = [z for z in zones if z["countClosesExactly"]]
    keys = ("transKeyed", "transConstant", "quat2Keyed", "quat2Constant", "quatKeyed", "quatConstant")
    result = {
        "format": "t6-retail-xanim-delta-branch-census-v3",
        "zones": zones,
        "summary": {
            "zonesScanned": len(zones),
            "zonesCountClosed": len(exact),
            "expectedXAnimRecordsAllZones": sum(z["expectedXAnimCount"] for z in zones),
            "structuralRecordsIdentifiedAllZones": sum(z["structuralRecordCount"] for z in zones),
            "emptyPlaceholderRecords": sum(z["emptyPlaceholderCount"] for z in zones),
            "exactCountXAnimRecords": sum(z["expectedXAnimCount"] for z in exact),
            "exactCountBranchTotals": {k: sum(z["branches"][k] for z in exact) for k in keys},
            "constantFullQuatObservedInExactCountZones": sum(z["branches"]["quatConstant"] for z in exact),
            "dynamicFullQuatObservedInExactCountZones": sum(z["branches"]["quatKeyed"] for z in exact),
        },
        "proofBoundary": (
            "All supplied zones are exhaustive branch evidence only when countClosesExactly is true. "
            "The empty-placeholder class is admitted only by its exact retail fixed-byte signature "
            "and comma-prefixed inline-name contract; no broad zero-frame/type-0 relaxation is used."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
