#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_audio_alias_physical_join_v1 as mod


def alias_fixture() -> dict:
    return {
        "format": mod.ALIAS_FORMAT,
        "remoteZip": {"etag": "fixture"},
        "summary": {
            "fastFileCount": 215,
            "greenFastFileCount": 215,
            "aliasDefinitionOccurrenceCount": 7,
            "uniqueAliasIdCount": 2,
            "uniqueSemanticVariantCount": 3,
            "zeroAssetIdOccurrenceCount": 2,
            "nonzeroAssetIdOccurrenceCount": 5,
            "uniqueNonzeroAssetIdCount": 2,
        },
        "assetIdCounts": {"11111111": 4, "22222222": 1},
    }


def entry(ident: str, bank: str, checksum: str, size: int = 10) -> dict:
    return {
        "identifierHex": ident,
        "bankPath": bank,
        "checksum128Hex": checksum,
        "dataBytes": size,
        "sampleCount": 100,
        "sampleRateFlag": 6,
        "sampleRateHz": 48000,
        "channels": 1,
        "loopRaw": 0,
        "formatCode": 8,
        "formatName": "FLAC",
    }


def physical_fixture() -> dict:
    rows = [
        entry("11111111", "a.sabs", "AA" * 16),
        entry("11111111", "b.sabs", "AA" * 16),
        entry("22222222", "c.sabs", "BB" * 16),
        entry("33333333", "d.sabs", "CC" * 16),
    ]
    return {
        "format": mod.PHYSICAL_FORMAT,
        "remoteZip": {"etag": "fixture"},
        "summary": {
            "bankCount": 116,
            "entryCount": 4,
            "uniqueIdentifierCount": 3,
            "invalidDataEntryCount": 0,
        },
        "identifierOccurrenceCounts": {"11111111": 2, "22222222": 1, "33333333": 1},
        "entries": rows,
    }


def main() -> int:
    result = mod.build(alias_fixture(), physical_fixture())
    s = result["summary"]
    assert s["uniqueNonzeroAssetIdCount"] == 2
    assert s["matchedUniqueNonzeroAssetIdCount"] == 2
    assert s["unmatchedUniqueNonzeroAssetIdCount"] == 0
    assert s["matchedNonzeroAssetIdOccurrenceCount"] == 5
    assert s["nonzeroAssetIdUniqueCoverageFraction"] == 1.0
    assert s["nonzeroAssetIdOccurrenceCoverageFraction"] == 1.0
    assert s["physicalOnlyUniqueIdentifierCount"] == 1
    assert s["physicalDuplicateIdentifierCount"] == 1
    assert s["aliasUsedPhysicalDuplicateIdentifierCount"] == 1
    assert s["aliasOccurrencesReferencingDuplicatePhysicalIdentifiers"] == 4
    assert s["storedChecksumAndMetadataDivergentDuplicateIdentifierCount"] == 0
    assert result["aliasUsedDuplicatePhysicalIdentifiers"][0]["storedChecksumAndMetadataIdentical"] is True

    bad = alias_fixture()
    bad["assetIdCounts"] = {"11111111": 4, "99999999": 1}
    try:
        mod.build(bad, physical_fixture())
    except mod.JoinError as exc:
        assert "absent from physical banks" in str(exc)
    else:
        raise AssertionError("unmatched nonzero asset ID must fail closed")

    bad_phys = physical_fixture()
    bad_phys["entries"][1] = copy.deepcopy(bad_phys["entries"][1])
    bad_phys["entries"][1]["checksum128Hex"] = "DD" * 16
    try:
        mod.build(alias_fixture(), bad_phys)
    except mod.JoinError as exc:
        assert "diverge" in str(exc)
    else:
        raise AssertionError("divergent duplicate physical identifier must fail closed")

    bad_summary = alias_fixture()
    bad_summary["summary"]["greenFastFileCount"] = 214
    try:
        mod.build(bad_summary, physical_fixture())
    except mod.JoinError:
        pass
    else:
        raise AssertionError("incomplete FastFile coverage must fail closed")

    print("PASS: exact T6 alias/physical join requires 215/215 + 116-bank coverage and rejects unmatched/divergent IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
