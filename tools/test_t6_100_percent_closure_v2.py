#!/usr/bin/env python3
"""Regressions for the version-aware T6 100-percent closure validator."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from t6_100_percent_closure_v2 import ClosureError, validate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load(name: str) -> dict:
    return json.loads((ROOT / "manifests" / name).read_text(encoding="utf-8"))


def must_fail(doc: dict, needle: str) -> None:
    try:
        validate(doc)
    except ClosureError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected closure failure containing {needle!r}")


def main() -> int:
    v1 = validate(load("T6_100_PERCENT_CLOSURE_V1.json"))
    assert v1["sourceFormat"] == "t6-100-percent-closure-v1"
    assert v1["release100Percent"] is False

    v2_doc = load("T6_100_PERCENT_CLOSURE_V2.json")
    v2 = validate(v2_doc)
    assert v2["sourceFormat"] == "t6-100-percent-closure-v2"
    assert v2["gateCount"] == 19
    assert v2["closedGateCount"] == 7
    assert v2["implementedAwaitingRetailGateCount"] == 4
    assert v2["partialGateCount"] == 8
    assert v2["openGateCount"] == 0
    assert v2["release100Percent"] is False

    bad = copy.deepcopy(v2_doc)
    bad["summary"]["closed"] += 1
    must_fail(bad, "contradicts computed")

    bad = copy.deepcopy(v2_doc)
    bad["gates"][1]["id"] = bad["gates"][0]["id"]
    must_fail(bad, "duplicate gate id")

    bad = copy.deepcopy(v2_doc)
    bad["gates"][0]["status"] = "looks-good"
    must_fail(bad, "invalid status")

    synthetic = {
        "format": "t6-100-percent-closure-v3",
        "goal": "synthetic all-closed regression",
        "gates": [
            {
                "id": "a",
                "title": "A",
                "status": "closed",
                "evidence": ["fixture"],
                "closureRequirement": "A is proven"
            },
            {
                "id": "b",
                "title": "B",
                "status": "closed",
                "evidence": ["fixture"],
                "closureRequirement": "B is proven"
            }
        ],
        "summary": {"gateCount": 2, "closed": 2, "partial": 0, "open": 0, "implementedAwaitingRetail": 0, "release100Percent": True}
    }
    s = validate(synthetic)
    assert s["release100Percent"] is True
    assert s["blockerCount"] == 0

    print("PASS: T6 100-percent closure validator v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
