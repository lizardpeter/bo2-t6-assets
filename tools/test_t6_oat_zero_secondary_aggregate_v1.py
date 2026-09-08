#!/usr/bin/env python3
from __future__ import annotations

import t6_oat_zero_secondary_aggregate_v1 as mod


def main() -> int:
    zero = {
        "format": "t6-sndalias-zero-asset-all-fastfile-v1",
        "summary": {
            "zeroPointerStateCounts": {
                "secondary_ptr": {"inline_serialized": 1, "null": 1, "other_u32": 1}
            }
        },
        "zeroRows": [
            {"bankName": "a.all", "aliasListIdHex": "00000001", "variantIndex": 0},
            {"bankName": "a.all", "aliasListIdHex": "00000002", "variantIndex": 0},
            {"bankName": "b.all", "aliasListIdHex": "00000003", "variantIndex": 0},
        ],
    }
    shard1 = {
        "format": "t6-oat-zero-secondary-resolver-v1",
        "rows": [
            {
                "bankName": "a.all", "aliasIdHex": "00000001", "variantIndex": 0,
                "sourceFastFile": "a.ff", "rawSecondaryPointerState": "inline_serialized",
                "resolvedSecondaryName": "target_a",
            },
            {
                "bankName": "a.all", "aliasIdHex": "00000002", "variantIndex": 0,
                "sourceFastFile": "a.ff", "rawSecondaryPointerState": "null",
                "resolvedSecondaryName": "",
            },
        ],
    }
    shard2 = {
        "format": "t6-oat-zero-secondary-resolver-v1",
        "rows": [
            {
                "bankName": "b.all", "aliasIdHex": "00000003", "variantIndex": 0,
                "sourceFastFile": "b.ff", "rawSecondaryPointerState": "other_u32",
                "resolvedSecondaryName": "target_b",
            }
        ],
    }
    result = mod.build(zero, [(shard1, "sha1"), (shard2, "sha2")], expected_zero_count=3, expected_bank_count=2)
    s = result["summary"]
    assert s["coveredBankCount"] == 2
    assert s["coveredZeroAssetOccurrenceCount"] == 3
    assert s["nonInlineSecondaryPointerOccurrenceCount"] == 1
    assert s["nonInlineSecondaryResolvedNonemptyCount"] == 1
    assert s["nonInlineSecondaryResolvedEmptyCount"] == 0
    assert s["uniqueResolvedNonemptySecondaryNameCount"] == 2

    bad_missing = dict(shard2)
    bad_missing["rows"] = []
    try:
        mod.build(zero, [(shard1, "sha1"), (bad_missing, "sha2")], expected_zero_count=3, expected_bank_count=2)
    except ValueError:
        pass
    else:
        raise AssertionError("missing native row must fail exact coverage")

    bad_null = {
        "format": "t6-oat-zero-secondary-resolver-v1",
        "rows": [
            dict(shard1["rows"][0]),
            dict(shard1["rows"][1], resolvedSecondaryName="impossible"),
        ],
    }
    try:
        mod.build(zero, [(bad_null, "sha1"), (shard2, "sha2")], expected_zero_count=3, expected_bank_count=2)
    except ValueError:
        pass
    else:
        raise AssertionError("null raw Secondary resolving non-empty must fail")

    print("PASS: native zero Secondary aggregate requires exact census coverage and pointer-state consistency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
