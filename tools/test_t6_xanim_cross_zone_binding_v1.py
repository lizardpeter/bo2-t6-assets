#!/usr/bin/env python3
"""Regression for T6 cross-zone ScriptString animation binding."""
from __future__ import annotations

from t6_xanim_gltf_export_v3 import ExportError
from t6_xanim_skinned_gltf_export_v8 import bind_xanim_to_skeleton


def skeleton(sha: str, sid: int = 5):
    return {
        "source": {"expandedSha256": sha},
        "skeleton": {"bones": [{"index": 0, "name": "j_mainroot", "scriptStringId": sid}]},
    }


def anim(sha: str, sid: int = 10, name: str = "j_mainroot"):
    return {
        "expandedSha256": sha,
        "boneTracks": [{"name": name, "scriptString": sid}],
    }


def main() -> int:
    # Different zones: exact resolved text is authoritative; raw numeric IDs are
    # local to each zone and therefore deliberately not compared.
    filtered, stats = bind_xanim_to_skeleton(skeleton("aa", 5), anim("bb", 10))
    assert len(filtered["boneTracks"]) == 1
    assert stats["sameSerializedScriptStringTable"] is False
    assert stats["numericIdComparison"] == "not-comparable-cross-zone"
    assert stats["crossZoneNumericIdMismatchCount"] == 1

    # Same serialized table: numeric mismatch is a real contradiction.
    try:
        bind_xanim_to_skeleton(skeleton("aa", 5), anim("aa", 10))
    except ExportError:
        pass
    else:
        raise AssertionError("same-table numeric ScriptString mismatch was accepted")

    # Same table and same numeric ID succeeds.
    _, stats = bind_xanim_to_skeleton(skeleton("aa", 5), anim("aa", 5))
    assert stats["sameSerializedScriptStringTable"] is True
    assert stats["numericIdComparison"] == "enforced"

    # An animation-only control is omitted, never aliased or fabricated.
    filtered, stats = bind_xanim_to_skeleton(skeleton("aa", 5), anim("bb", 9, "j_face_control"))
    # zero intersections must fail closed, so reaching here is forbidden.
    raise AssertionError((filtered, stats))


if __name__ == "__main__":
    try:
        main()
    except ExportError as exc:
        if "zero exact-name track intersections" not in str(exc):
            raise
        print("PASS: T6 cross-zone ScriptString binding v1 regressions")
