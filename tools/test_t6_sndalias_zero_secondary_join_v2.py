#!/usr/bin/env python3
from __future__ import annotations

import t6_sndalias_zero_secondary_join_v2 as mod


def hid(name: str) -> str:
    return f"{mod.snd_hash_name(name):08X}"


def main() -> int:
    direct="direct_target"
    zero_only="zero_target"
    mixed="mixed_target"
    missing="missing_target"
    native={
        "format":"t6-oat-zero-secondary-all-fastfile-v1",
        "summary":{
            "coveredBankCount":37,
            "coveredZeroAssetOccurrenceCount":4094,
            "nonInlineSecondaryPointerOccurrenceCount":1334,
            "nonInlineSecondaryResolvedEmptyCount":0,
            "nonInlineSecondaryResolvedNonemptyCount":1334,
            "totalResolvedNonemptySecondaryOccurrenceCount":4,
        },
        "rows":[
            {"bankName":"a.all","sourceFastFile":"a.ff","aliasIdHex":"00000001","aliasNameResolved":"a","variantIndex":0,"rawSecondaryPointerState":"other_u32","resolvedSecondaryName":direct},
            {"bankName":"a.all","sourceFastFile":"a.ff","aliasIdHex":"00000002","aliasNameResolved":"b","variantIndex":0,"rawSecondaryPointerState":"other_u32","resolvedSecondaryName":zero_only},
            {"bankName":"a.all","sourceFastFile":"a.ff","aliasIdHex":"00000003","aliasNameResolved":"c","variantIndex":0,"rawSecondaryPointerState":"inline_serialized","resolvedSecondaryName":mixed},
            {"bankName":"a.all","sourceFastFile":"a.ff","aliasIdHex":"00000004","aliasNameResolved":"d","variantIndex":0,"rawSecondaryPointerState":"inline_serialized","resolvedSecondaryName":missing},
        ],
    }
    zero={
        "format":"t6-sndalias-zero-asset-all-fastfile-v1",
        "summary":{
            "aliasDefinitionOccurrenceCount":445664,
            "nonzeroAssetIdOccurrenceCount":441570,
            "zeroAssetIdOccurrenceCount":4094,
            "uniqueAliasIdCount":18103,
            "fastFileCount":215,
        },
        "zeroAliasIdCounts":{hid(zero_only):2,hid(mixed):1},
    }
    aliases={
        "format":"t6-sndalias-all-fastfile-census-v1",
        "summary":{
            "aliasDefinitionOccurrenceCount":445664,
            "nonzeroAssetIdOccurrenceCount":441570,
            "zeroAssetIdOccurrenceCount":4094,
            "uniqueAliasIdCount":18103,
            "fastFileCount":215,
        },
        "aliasIdCounts":{hid(direct):3,hid(zero_only):2,hid(mixed):5},
        "validatedInlineAliasNames":{},
    }
    physical={
        "format":"t6-audio-alias-physical-join-v1",
        "summary":{
            "unmatchedUniqueNonzeroAssetIdCount":0,
            "matchedUniqueNonzeroAssetIdCount":24481,
            "matchedNonzeroAssetIdOccurrenceCount":441570,
        },
    }
    result=mod.build(native,zero,aliases,physical)
    s=result["summary"]
    assert s["resolvedNonemptySecondaryOccurrenceCount"]==4
    assert s["uniqueResolvedSecondaryNameCount"]==4
    assert s["uniqueSecondaryNamesWithPhysicalBackedTargetVariant"]==2
    assert s["secondaryOccurrencesWithPhysicalBackedTargetVariant"]==2
    assert s["missingTargetUniqueNameCount"]==1
    classes={r["secondaryName"]:r["classification"] for r in result["secondaryTargets"]}
    assert classes[direct]=="nonzero_only_target"
    assert classes[zero_only]=="zero_only_target"
    assert classes[mixed]=="mixed_zero_and_nonzero_target"
    assert classes[missing]=="missing_alias_id"

    bad=dict(native)
    bad["summary"]=dict(native["summary"],nonInlineSecondaryResolvedEmptyCount=1)
    try:
        mod.build(bad,zero,aliases,physical)
    except ValueError:
        pass
    else:
        raise AssertionError("unresolved native non-inline pointer must fail")

    print("PASS: complete native zero Secondary join requires full resolution and preserves target proof boundaries")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
