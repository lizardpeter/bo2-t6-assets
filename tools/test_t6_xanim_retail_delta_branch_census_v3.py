#!/usr/bin/env python3
"""Regression for the narrow v3 empty-placeholder XAnim classifier.

This is a code regression only.  Retail proof remains the hash-pinned V3 census manifest;
synthetic bytes here are never promoted to retail evidence.
"""
from __future__ import annotations

import hashlib

import t6_xanim_retail_delta_branch_census_v3 as census


def placeholder(name: str) -> bytes:
    return census.EMPTY_FIXED + name.encode("ascii") + b"\0"


def main() -> int:
    assert len(census.EMPTY_FIXED) == 104
    assert hashlib.sha256(census.EMPTY_FIXED).hexdigest() == (
        "c084814eb5a0112d1b22bd723c31b6e092aba5f45746ae022d43663fae1220d9"
    )

    a = placeholder(",viewmodel_raygun_mk2_idle")
    b = placeholder(",viewmodel_m67_idle")
    blob = b"prefix" + a + b + b"suffix"
    got = census.empty_placeholders(blob)
    assert [r["name"] for r in got] == [
        ",viewmodel_raygun_mk2_idle",
        ",viewmodel_m67_idle",
    ]
    assert got[0]["start"] == len(b"prefix")
    assert got[0]["end"] == len(b"prefix") + len(a)
    assert got[1]["start"] == got[0]["end"]
    assert got[1]["end"] == got[1]["start"] + len(b)
    assert all(r["numframes"] == 0 for r in got)
    assert all(r["assetType"] == 0 for r in got)
    assert all(r["fixedSha256"] == census.EMPTY_FIXED_SHA256 for r in got)

    # A generic all-zero XAnim-looking header is not enough: the retail class uses a
    # comma-prefixed inline name.
    assert census.empty_placeholders(placeholder("viewmodel_m67_idle")) == []

    # A single non-zero fixed field must also reject the candidate; v3 is not a broad
    # zero-frame/type-0 fallback.
    mutated = bytearray(placeholder(",viewmodel_m67_idle"))
    mutated[20] = 1  # streamedFileSize low byte
    assert census.empty_placeholders(bytes(mutated)) == []

    print("PASS t6_xanim_retail_delta_branch_census_v3 empty-placeholder regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
