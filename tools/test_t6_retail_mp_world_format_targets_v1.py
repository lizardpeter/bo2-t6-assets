#!/usr/bin/env python3
"""Regression for the hash-pinned retail MP world-format hunt corpus."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "manifests" / "world" / "T6_RETAIL_MP_WORLD_FORMAT_TARGETS_V1.json"
    doc = json.loads(path.read_text(encoding="utf-8"))

    assert doc["format"] == "t6-retail-mp-world-format-targets-v1"
    assert doc["targetFormats"] == [4, 5, 7, 8]
    assert doc["source"]["multiplayerMapFastfileCount"] == 31

    maps = doc["maps"]
    assert len(maps) == 31
    zones = [str(row["zone"]) for row in maps]
    assert len(zones) == len(set(zones)) == 31
    assert zones == sorted(zones)

    scan_order = [str(value) for value in doc["scanOrder"]]
    assert len(scan_order) == 31
    assert len(scan_order) == len(set(scan_order))
    assert set(scan_order) == set(zones)
    assert scan_order[0] == "mp_raid"
    assert scan_order[1:] == sorted(zone for zone in zones if zone != "mp_raid")

    known = doc["knownCompleted"]
    assert set(known) == {"mp_nuketown_2020"}
    assert known["mp_nuketown_2020"]["observedFormats"] == [0, 1, 2, 3, 6]
    assert known["mp_nuketown_2020"]["targetHit"] is False

    by_zone = {str(row["zone"]): row for row in maps}
    raid = by_zone["mp_raid"]
    assert raid["bytes"] == 35_718_144
    assert raid["sha256"] == "bca3b74d8df5a27b82e77f39ef82cbd87a19dedf30884600b73eb563acba5888"
    assert by_zone["mp_nuketown_2020"]["sha256"] == "6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0"

    for row in maps:
        zone = str(row["zone"])
        assert zone.startswith("mp_")
        assert row["path"] == f"zone/all/{zone}.ff"
        assert int(row["bytes"]) > 1_000_000
        digest = str(row["sha256"])
        assert len(digest) == 64
        assert digest == digest.lower()
        int(digest, 16)

    canonical = (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest()

    print("PASS T6 retail MP world-format target corpus regression (31/31)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
