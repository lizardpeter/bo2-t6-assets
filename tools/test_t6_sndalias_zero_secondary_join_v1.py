#!/usr/bin/env python3
from __future__ import annotations

import t6_sndalias_zero_secondary_join_v1 as mod


def alias_id(name: str) -> str:
    return f"{mod.snd_hash_name(name):08X}"


def fixture():
    direct = "direct_target"
    zero_only = "zero_target"
    mixed = "mixed_target"
    missing = "missing_target"
    source = "source_zero"
    ids = {name: alias_id(name) for name in (direct, zero_only, mixed, source)}

    zero_rows = []
    for i, sec in enumerate((direct, zero_only, mixed, missing)):
        zero_rows.append({
            "aliasListIdHex": ids[source],
            "aliasListNameValidatedInline": source,
            "source": "fixture.ff",
            "bankName": "fixture.all",
            "variantIndex": i,
            "inlineStrings": {"secondaryName": sec},
        })
    zero = {
        "format": "t6-sndalias-zero-asset-all-fastfile-v1",
        "summary": {
            "aliasDefinitionOccurrenceCount": 445664,
            "nonzeroAssetIdOccurrenceCount": 441570,
            "zeroAssetIdOccurrenceCount": 4094,
            "uniqueAliasIdCount": 18103,
            "fastFileCount": 215,
            "zeroRowsWithNonemptyInlineStrings": {"secondaryName": 4},
            "zeroPointerStateCounts": {
                "secondary_ptr": {"inline_serialized": 4, "other_u32": 1334, "null": 2756}
            },
        },
        "zeroAliasIdCounts": {
            ids[zero_only]: 2,
            ids[mixed]: 1,
            ids[source]: 4,
        },
        "zeroRows": zero_rows,
    }
    aliases = {
        "format": "t6-sndalias-all-fastfile-census-v1",
        "summary": {
            "aliasDefinitionOccurrenceCount": 445664,
            "nonzeroAssetIdOccurrenceCount": 441570,
            "zeroAssetIdOccurrenceCount": 4094,
            "uniqueAliasIdCount": 18103,
            "fastFileCount": 215,
        },
        "aliasIdCounts": {
            ids[direct]: 3,
            ids[zero_only]: 2,
            ids[mixed]: 5,
            ids[source]: 4,
        },
        "validatedInlineAliasNames": {v: k for k, v in ids.items()},
    }
    physical = {
        "format": "t6-audio-alias-physical-join-v1",
        "summary": {
            "unmatchedUniqueNonzeroAssetIdCount": 0,
            "matchedUniqueNonzeroAssetIdCount": 24481,
            "matchedNonzeroAssetIdOccurrenceCount": 441570,
        },
    }
    return zero, aliases, physical


def main() -> int:
    zero, aliases, physical = fixture()
    result = mod.build(zero, aliases, physical)
    s = result["summary"]
    assert s["inlineSecondaryOccurrenceCount"] == 4
    assert s["uniqueInlineSecondaryNameCount"] == 4
    assert s["uniqueInlineSecondaryNamesWithPhysicalBackedTargetVariant"] == 2
    assert s["inlineSecondaryOccurrencesWithPhysicalBackedTargetVariant"] == 2
    assert s["unresolvedInlineSecondaryTargetUniqueNameCount"] == 1
    assert s["unresolvedInlineSecondaryTargetOccurrenceCount"] == 1
    classes = {r["secondaryName"]: r["classification"] for r in result["secondaryTargets"]}
    assert classes["direct_target"] == "nonzero_only_target"
    assert classes["zero_target"] == "zero_only_target"
    assert classes["mixed_target"] == "mixed_zero_and_nonzero_target"
    assert classes["missing_target"] == "missing_alias_id"

    bad = dict(physical)
    bad["summary"] = dict(physical["summary"], unmatchedUniqueNonzeroAssetIdCount=1)
    try:
        mod.build(zero, aliases, bad)
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete physical join must fail closed")

    bad_zero = dict(zero)
    bad_zero["summary"] = dict(zero["summary"], zeroAssetIdOccurrenceCount=4093)
    try:
        mod.build(bad_zero, aliases, physical)
    except ValueError:
        pass
    else:
        raise AssertionError("population drift must fail closed")

    print("PASS: zero-asset inline Secondary join classifies only structurally proven targets and fails closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
