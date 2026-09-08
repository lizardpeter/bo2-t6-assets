#!/usr/bin/env python3
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import t6_oat_zero_secondary_resolver_v1 as mod


def main() -> int:
    bank = "fixture.all"
    a = "alias_a"
    b = "alias_b"
    aid = f"{mod.snd_hash_name(a):08X}"
    bid = f"{mod.snd_hash_name(b):08X}"
    zero = {
        "format": "t6-sndalias-zero-asset-all-fastfile-v1",
        "summary": {"zeroAssetIdOccurrenceCount": 4094},
        "zeroRows": [
            {
                "bankName": bank,
                "source": "fixture.ff",
                "aliasListIdHex": aid,
                "aliasListNameValidatedInline": a,
                "variantIndex": 0,
                "pointers": {"secondary_ptr": {"state": "inline_serialized", "valueHex": "FFFFFFFF"}},
                "inlineStrings": {"secondaryName": "target_inline"},
            },
            {
                "bankName": bank,
                "source": "fixture.ff",
                "aliasListIdHex": aid,
                "aliasListNameValidatedInline": a,
                "variantIndex": 1,
                "pointers": {"secondary_ptr": {"state": "other_u32", "valueHex": "12345678"}},
                "inlineStrings": {"secondaryName": ""},
            },
            {
                "bankName": bank,
                "source": "fixture.ff",
                "aliasListIdHex": bid,
                "aliasListNameValidatedInline": b,
                "variantIndex": 0,
                "pointers": {"secondary_ptr": {"state": "null", "valueHex": "00000000"}},
                "inlineStrings": {"secondaryName": ""},
            },
        ],
    }

    with tempfile.TemporaryDirectory() as td:
        csv_path = Path(td) / "fixture.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Name", "FileSource", "Secondary"])
            w.writeheader()
            w.writerow({"Name": a, "FileSource": "", "Secondary": "target_inline"})
            w.writerow({"Name": a, "FileSource": "", "Secondary": "target_packed"})
            w.writerow({"Name": b, "FileSource": "", "Secondary": ""})
        result = mod.build(zero, {bank: csv_path}, zero_sha256="fixture")
        s = result["summary"]
        assert s["coveredZeroAssetOccurrenceCount"] == 3
        assert s["nonInlineSecondaryPointerOccurrenceCount"] == 1
        assert s["nonInlineSecondaryResolvedNonemptyCount"] == 1
        assert s["nonInlineSecondaryResolvedEmptyCount"] == 0
        rows = {(r["aliasIdHex"], r["variantIndex"]): r for r in result["rows"]}
        assert rows[(aid, 1)]["resolvedSecondaryName"] == "target_packed"
        assert rows[(bid, 0)]["resolvedSecondaryName"] == ""

        bad_csv = Path(td) / "bad.csv"
        with bad_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Name", "FileSource", "Secondary"])
            w.writeheader()
            w.writerow({"Name": a, "FileSource": "unexpected.wav", "Secondary": "target_inline"})
            w.writerow({"Name": a, "FileSource": "", "Secondary": "target_packed"})
            w.writerow({"Name": b, "FileSource": "", "Secondary": ""})
        try:
            mod.build(zero, {bank: bad_csv})
        except ValueError:
            pass
        else:
            raise AssertionError("assetId==0/FileSource disagreement must fail")

        bad_inline = Path(td) / "bad-inline.csv"
        with bad_inline.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Name", "FileSource", "Secondary"])
            w.writeheader()
            w.writerow({"Name": a, "FileSource": "", "Secondary": "different"})
            w.writerow({"Name": a, "FileSource": "", "Secondary": "target_packed"})
            w.writerow({"Name": b, "FileSource": "", "Secondary": ""})
        try:
            mod.build(zero, {bank: bad_inline})
        except ValueError:
            pass
        else:
            raise AssertionError("inline/raw native Secondary disagreement must fail")

    print("PASS: native OAT zero Secondary resolver uses post-loader strings and fails closed on disagreements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
