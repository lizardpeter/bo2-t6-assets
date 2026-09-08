#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import t6_oat_exact_technique_absence_v1 as M

TARGET_NAME = "pimp_technique_shadowoverlay_5255c888"
TARGET = b"x" * 592
TARGET_SHA = hashlib.sha256(TARGET).hexdigest()


def make_root(base: Path, name: str) -> Path:
    root = base / name
    (root / "techniques").mkdir(parents=True)
    (root / "techsets").mkdir(parents=True)
    (root / "techsets" / "fixture.techset").write_text("fixture\n", encoding="utf-8")
    return root


def expect_error(fn, contains: str) -> None:
    try:
        fn()
    except M.AbsenceError as exc:
        assert contains in str(exc), (contains, str(exc))
    else:
        raise AssertionError(f"expected AbsenceError containing {contains!r}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        a = make_root(base, "a")
        b = make_root(base, "b")
        (a / "techniques" / "other.tech").write_bytes(b"other")
        (b / "techniques" / "different.tech").write_bytes(b"different")

        result = M.build(
            {"a": a, "b": b},
            {"a": 0, "b": 0},
            TARGET_NAME,
            len(TARGET),
            TARGET_SHA,
        )
        assert result["authoritativeWithinSuppliedSuccessfulRoots"] is True
        assert result["globalRetailAbsenceClaim"] is False
        assert result["summary"]["exactTechniqueAbsentWithinSuppliedRoots"] is True
        assert result["summary"]["targetFilenameHitCount"] == 0
        assert result["summary"]["targetExactPayloadHitCount"] == 0
        assert result["summary"]["techniqueCount"] == 2
        assert result["summary"]["techniqueSetCount"] == 2

        renamed = b / "techniques" / "renamed_payload.tech"
        renamed.write_bytes(TARGET)
        result = M.build(
            {"a": a, "b": b},
            {"a": 0, "b": 0},
            TARGET_NAME,
            len(TARGET),
            TARGET_SHA,
        )
        assert result["summary"]["exactTechniqueAbsentWithinSuppliedRoots"] is False
        assert result["summary"]["targetFilenameHitCount"] == 0
        assert result["summary"]["targetExactPayloadHitCount"] == 1
        assert result["targetExactPayloadHits"][0]["relativeFile"] == "techniques/renamed_payload.tech"

        renamed.unlink()
        named = a / "techniques" / f"{TARGET_NAME}.tech"
        named.write_bytes(b"wrong bytes")
        result = M.build(
            {"a": a, "b": b},
            {"a": 0, "b": 0},
            TARGET_NAME,
            len(TARGET),
            TARGET_SHA,
        )
        assert result["summary"]["exactTechniqueAbsentWithinSuppliedRoots"] is False
        assert result["summary"]["targetFilenameHitCount"] == 1
        assert result["summary"]["targetExactPayloadHitCount"] == 0
        assert result["summary"]["targetExactNamedIdentityHitCount"] == 0

        expect_error(
            lambda: M.build(
                {"a": a, "b": b},
                {"a": 0},
                TARGET_NAME,
                len(TARGET),
                TARGET_SHA,
            ),
            "exactly match roots",
        )
        expect_error(
            lambda: M.build(
                {"a": a, "b": b},
                {"a": 0, "b": 1},
                TARGET_NAME,
                len(TARGET),
                TARGET_SHA,
            ),
            "not successful",
        )

    print("PASS exact Technique absence fail-closed tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
