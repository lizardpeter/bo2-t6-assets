#!/usr/bin/env python3
"""Regression for retail-closed ordinary root/non-root translation composition."""
from __future__ import annotations

from t6_xanim_gltf_export_v3 import ExportError
from t6_xanim_skinned_gltf_export_v7 import ordinary_translation_values


def main() -> int:
    root = {
        "name": "tag_origin",
        "parentIndex": None,
        # Deliberately nonzero: the proof says ordinary root animation must NOT
        # add model bind-local translation even if a normalized document carries one.
        "localTranslation": [100.0, 200.0, 300.0],
    }
    child = {
        "name": "j_spine4",
        "parentIndex": 0,
        "localTranslation": [10.0, 20.0, 30.0],
    }

    constant = {"trans": {"type": "TRANS_NO_SIZE", "constant": [1.0, 2.0, 3.0]}}
    values, kind = ordinary_translation_values(constant, root)
    assert kind == "rootRawXAnim"
    assert values == [[1.0, 2.0, 3.0]]

    values, kind = ordinary_translation_values(constant, child)
    assert kind == "nonRootBindPlusDelta"
    assert values == [[11.0, 22.0, 33.0]]

    dynamic = {
        "trans": {
            "type": "FULL_TRANS",
            "decodedFrames": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        }
    }
    values, kind = ordinary_translation_values(dynamic, root)
    assert kind == "rootRawXAnim"
    assert values == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]

    values, kind = ordinary_translation_values(dynamic, child)
    assert kind == "nonRootBindPlusDelta"
    assert values == [[11.0, 22.0, 33.0], [14.0, 25.0, 36.0]]

    no_trans, kind = ordinary_translation_values({"trans": {"type": "NO_TRANS"}}, root)
    assert no_trans is None and kind is None

    try:
        ordinary_translation_values({"trans": {"type": "UNKNOWN"}}, root)
    except ExportError as exc:
        assert "unsupported translation UNKNOWN" in str(exc), str(exc)
    else:
        raise AssertionError("unknown translation type must fail closed")

    print("PASS t6_xanim_skinned_gltf_export_v7 ordinary root/non-root translation regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
