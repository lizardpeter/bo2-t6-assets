#!/usr/bin/env python3
"""Deterministic regressions for the T6 non-map extraction track v1."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from t6_character_bundle_pipeline_v1 import safe_name, verify_xanim
from t6_nonmap_asset_coverage_v1 import ASSET_TYPES, MAP_ONLY, classification


def main() -> int:
    assert len(ASSET_TYPES) == len(set(ASSET_TYPES))
    assert classification("XMODEL")[1] == "usable"
    assert classification("XANIMPARTS")[1] == "usable"
    assert classification("PHYSPRESET")[1] == "oat-dumpable"
    assert classification("SOUND")[1] == "oat-dumpable"
    assert classification("VEHICLEDEF")[1] == "oat-dumpable"
    assert classification("CHARACTER")[1] == "inventory-only"
    assert classification("MPBODY")[1] == "inventory-only"
    assert classification("GFXWORLD")[1] == "handled-by-map-track"
    for asset_type in ASSET_TYPES:
        category, status, tools = classification(asset_type)
        assert category
        assert status in {
            "usable", "oat-dumpable", "partial", "inventory-only", "open",
            "handled-by-map-track"
        }
        assert isinstance(tools, list)
        if asset_type in MAP_ONLY:
            assert status == "handled-by-map-track"

    assert safe_name("characters/usa/seal\\body") == "body"
    assert safe_name("***") == "asset"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = root / "idle.json"
        good.write_text(json.dumps({
            "format": "t6-xanim-normalized-v1",
            "name": "pb_idle",
        }), encoding="utf-8")
        doc, name = verify_xanim(good)
        assert doc["format"] == "t6-xanim-normalized-v1"
        assert name == "pb_idle"

        bad = root / "bad.json"
        bad.write_text(json.dumps({"format": "not-t6-xanim"}), encoding="utf-8")
        try:
            verify_xanim(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("bad XAnim format must fail closed")

    print("PASS: T6 non-map extraction track v1 regressions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
