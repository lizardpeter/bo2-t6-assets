#!/usr/bin/env python3
"""Regression for the v2 world-mesh retail format gate."""
from __future__ import annotations

from t6_world_mesh_normalize_v2 import NormalizeV2Error, validate_registry_for_proof
from t6_zone_core import WORLD_VERTEX_FORMATS


def _registry(enabled: set[int], contradiction: dict[int, list[int]] | None = None) -> dict:
    contradiction = contradiction or {}
    rows = {}
    for fmt_enum, spec in WORLD_VERTEX_FORMATS.items():
        fmt = int(fmt_enum)
        bad = list(contradiction.get(fmt, []))
        is_enabled = fmt in enabled and not bad
        rows[str(fmt)] = {
            "format": fmt,
            "name": fmt_enum.name,
            "sourceClosedFamily": {
                "uvCount": spec.uv_count,
                "normalCount": spec.normal_count,
                "vd1Stride": spec.vd1_stride,
                "vd1Fields": list(spec.vd1_fields),
            },
            "retailByteProven": is_enabled,
            "exportEnabled": is_enabled,
            "contradictoryRawStrides": bad,
            "status": "export-enabled" if is_enabled else ("contradicted" if bad else "pending-retail-byte-proof"),
        }
    return {
        "format": "t6-world-vertex-format-registry-v1",
        "formats": rows,
        "coverage": {
            "exportEnabledFormats": sorted(enabled - set(contradiction)),
            "allFormatsExportEnabled": len(enabled) == 9 and not contradiction,
        },
    }


def _proof(formats: list[int]) -> dict:
    return {
        "format": "t6-world-vertex-proof-v1",
        "badGroupCount": 0,
        "groups": [
            {
                "groupIndex": i,
                "worldVertFormat": fmt,
            }
            for i, fmt in enumerate(formats)
        ],
    }


def _must_fail(proof: dict, registry: dict, contains: str) -> None:
    try:
        validate_registry_for_proof(proof, registry)
    except NormalizeV2Error as exc:
        assert contains in str(exc), str(exc)
    else:
        raise AssertionError("expected NormalizeV2Error")


def main() -> int:
    current = _registry({0, 1, 2, 3, 6})
    gate = validate_registry_for_proof(_proof([0, 1, 2, 3, 6]), current)
    assert gate["observedFormats"] == [0, 1, 2, 3, 6]
    assert gate["allObservedFormatsExportEnabled"] is True
    assert gate["registryAllFormatsExportEnabled"] is False

    _must_fail(_proof([0, 4]), current, "4:TEX_3_NRM_2[pending-retail-byte-proof]")
    _must_fail(_proof([8]), current, "8:TEX_4_NRM_3[pending-retail-byte-proof]")

    complete = _registry(set(range(9)))
    gate = validate_registry_for_proof(_proof([4, 5, 7, 8]), complete)
    assert gate["observedFormats"] == [4, 5, 7, 8]
    assert gate["registryAllFormatsExportEnabled"] is True

    contradicted = _registry(set(range(9)), {7: [20]})
    _must_fail(_proof([7]), contradicted, "7:TEX_4_NRM_2[contradicted]")

    malformed = _registry(set(range(9)))
    malformed["formats"]["8"]["sourceClosedFamily"]["vd1Stride"] = 16
    _must_fail(_proof([0]), malformed, "registry format 8: vd1Stride=16 != canonical 20")

    print("PASS t6_world_mesh_normalize_v2 retail format gate regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
