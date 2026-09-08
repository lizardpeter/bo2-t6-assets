#!/usr/bin/env python3
"""Fail-closed join of the complete T6 SndAlias census to physical SABS/SABL IDs.

The alias side must be the complete 215-FastFile structural census. The physical
side must be the complete 116-bank SHA-pinned table manifest. Non-zero
SndAlias.assetId is joined only by its exact 32-bit identifier.

Duplicate physical identifier occurrences are retained. They are considered
non-divergent only when every occurrence agrees on the stored 128-bit checksum
record and all parsed audio metadata fields. This does not prove payload-byte
identity; payload bytes are not present in the compact physical manifest.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

ALIAS_FORMAT = "t6-sndalias-all-fastfile-census-v1"
PHYSICAL_FORMAT = "t6-audio-physical-id-manifest-v1"
HEX_ID = re.compile(r"^[0-9A-F]{8}$")
DUPLICATE_IDENTITY_FIELDS = (
    "checksum128Hex", "dataBytes", "sampleCount", "sampleRateFlag",
    "sampleRateHz", "channels", "loopRaw", "formatCode", "formatName",
)


class JoinError(RuntimeError):
    pass


def _check_id_map(obj: object, label: str) -> dict[str, int]:
    if not isinstance(obj, dict):
        raise JoinError(f"{label} must be an object")
    out: dict[str, int] = {}
    for key, value in obj.items():
        if not isinstance(key, str) or not HEX_ID.fullmatch(key):
            raise JoinError(f"{label}: invalid exact ID {key!r}")
        if not isinstance(value, int) or value <= 0:
            raise JoinError(f"{label}: invalid occurrence count for {key}: {value!r}")
        out[key] = value
    return out


def _entry_signature(entry: dict) -> tuple:
    return tuple(entry.get(field) for field in DUPLICATE_IDENTITY_FIELDS)


def build(alias: dict, physical: dict) -> dict:
    if alias.get("format") != ALIAS_FORMAT:
        raise JoinError(f"unexpected alias format {alias.get('format')!r}")
    if physical.get("format") != PHYSICAL_FORMAT:
        raise JoinError(f"unexpected physical format {physical.get('format')!r}")

    a_summary = alias.get("summary", {})
    p_summary = physical.get("summary", {})
    if a_summary.get("fastFileCount") != 215 or a_summary.get("greenFastFileCount") != 215:
        raise JoinError("alias census is not exact green 215/215 coverage")
    if p_summary.get("bankCount") != 116 or p_summary.get("invalidDataEntryCount") != 0:
        raise JoinError("physical manifest is not exact green 116-bank coverage")

    alias_counts = _check_id_map(alias.get("assetIdCounts"), "assetIdCounts")
    physical_counts = _check_id_map(physical.get("identifierOccurrenceCounts"), "identifierOccurrenceCounts")
    if len(alias_counts) != a_summary.get("uniqueNonzeroAssetIdCount"):
        raise JoinError("alias unique nonzero asset-ID summary mismatch")
    if sum(alias_counts.values()) != a_summary.get("nonzeroAssetIdOccurrenceCount"):
        raise JoinError("alias nonzero asset-ID occurrence summary mismatch")
    if len(physical_counts) != p_summary.get("uniqueIdentifierCount"):
        raise JoinError("physical unique identifier summary mismatch")
    if sum(physical_counts.values()) != p_summary.get("entryCount"):
        raise JoinError("physical identifier occurrence summary mismatch")

    entries = physical.get("entries")
    if not isinstance(entries, list) or len(entries) != p_summary.get("entryCount"):
        raise JoinError("physical entries array does not match physical entry count")
    by_id: dict[str, list[dict]] = collections.defaultdict(list)
    for entry in entries:
        if not isinstance(entry, dict):
            raise JoinError("physical entries contains a non-object row")
        ident = entry.get("identifierHex")
        if not isinstance(ident, str) or not HEX_ID.fullmatch(ident):
            raise JoinError(f"physical entry has invalid identifierHex {ident!r}")
        by_id[ident].append(entry)
    observed_counts = {key: len(rows) for key, rows in by_id.items()}
    if observed_counts != physical_counts:
        raise JoinError("physical entry rows disagree with identifierOccurrenceCounts")

    alias_ids = set(alias_counts)
    physical_ids = set(physical_counts)
    unmatched = sorted(alias_ids - physical_ids)
    physical_only = sorted(physical_ids - alias_ids)

    duplicate_groups = []
    divergent_duplicate_ids = []
    alias_used_duplicate_ids = []
    joins = []
    for ident in sorted(alias_ids & physical_ids):
        rows = by_id[ident]
        signatures = {_entry_signature(row) for row in rows}
        consistent = len(signatures) == 1
        if len(rows) > 1:
            alias_used_duplicate_ids.append(ident)
            duplicate_groups.append({
                "identifierHex": ident,
                "aliasOccurrenceCount": alias_counts[ident],
                "physicalOccurrenceCount": len(rows),
                "storedChecksumAndMetadataIdentical": consistent,
                "bankPaths": sorted(row["bankPath"] for row in rows),
                "signature": {
                    field: rows[0].get(field) for field in DUPLICATE_IDENTITY_FIELDS
                } if consistent else None,
            })
            if not consistent:
                divergent_duplicate_ids.append(ident)
        joins.append({
            "identifierHex": ident,
            "aliasOccurrenceCount": alias_counts[ident],
            "physicalOccurrenceCount": len(rows),
            "physicalBankPaths": sorted(row["bankPath"] for row in rows),
            "uniquePhysicalOccurrence": len(rows) == 1,
            "storedChecksumAndMetadataIdenticalAcrossPhysicalCopies": consistent,
        })

    all_duplicate_ids = [ident for ident, rows in by_id.items() if len(rows) > 1]
    all_divergent_duplicates = [
        ident for ident in all_duplicate_ids
        if len({_entry_signature(row) for row in by_id[ident]}) != 1
    ]
    physical_only_entry_occurrences = sum(physical_counts[ident] for ident in physical_only)
    alias_occurrences_on_duplicate_ids = sum(alias_counts[ident] for ident in alias_used_duplicate_ids)
    matched_occurrences = sum(alias_counts[ident] for ident in alias_ids & physical_ids)

    if unmatched:
        raise JoinError(f"nonzero alias asset IDs absent from physical banks: {unmatched[:20]} (count={len(unmatched)})")
    if all_divergent_duplicates:
        raise JoinError(
            "physical duplicate identifier(s) diverge in stored checksum/audio metadata: "
            f"{all_divergent_duplicates[:20]} (count={len(all_divergent_duplicates)})"
        )

    return {
        "format": "t6-audio-alias-physical-join-v1",
        "source": {
            "aliasFormat": ALIAS_FORMAT,
            "aliasRemoteZip": alias.get("remoteZip"),
            "physicalFormat": PHYSICAL_FORMAT,
            "physicalRemoteZip": physical.get("remoteZip"),
        },
        "summary": {
            "fastFileCount": 215,
            "physicalBankCount": 116,
            "aliasDefinitionOccurrenceCount": a_summary.get("aliasDefinitionOccurrenceCount"),
            "uniqueAliasIdCount": a_summary.get("uniqueAliasIdCount"),
            "uniqueSemanticVariantCount": a_summary.get("uniqueSemanticVariantCount"),
            "zeroAssetIdOccurrenceCount": a_summary.get("zeroAssetIdOccurrenceCount"),
            "nonzeroAssetIdOccurrenceCount": a_summary.get("nonzeroAssetIdOccurrenceCount"),
            "uniqueNonzeroAssetIdCount": len(alias_ids),
            "matchedUniqueNonzeroAssetIdCount": len(alias_ids & physical_ids),
            "unmatchedUniqueNonzeroAssetIdCount": len(unmatched),
            "matchedNonzeroAssetIdOccurrenceCount": matched_occurrences,
            "nonzeroAssetIdUniqueCoverageFraction": len(alias_ids & physical_ids) / len(alias_ids) if alias_ids else 1.0,
            "nonzeroAssetIdOccurrenceCoverageFraction": matched_occurrences / sum(alias_counts.values()) if alias_counts else 1.0,
            "physicalEntryCount": p_summary.get("entryCount"),
            "physicalUniqueIdentifierCount": len(physical_ids),
            "physicalOnlyUniqueIdentifierCount": len(physical_only),
            "physicalOnlyEntryOccurrenceCount": physical_only_entry_occurrences,
            "physicalDuplicateIdentifierCount": len(all_duplicate_ids),
            "physicalDuplicateExtraOccurrenceCount": sum(physical_counts[i] - 1 for i in all_duplicate_ids),
            "aliasUsedPhysicalDuplicateIdentifierCount": len(alias_used_duplicate_ids),
            "aliasOccurrencesReferencingDuplicatePhysicalIdentifiers": alias_occurrences_on_duplicate_ids,
            "storedChecksumAndMetadataDivergentDuplicateIdentifierCount": 0,
            "maxPhysicalIdentifierMultiplicity": max(physical_counts.values()) if physical_counts else 0,
        },
        "unmatchedNonzeroAssetIds": unmatched,
        "physicalOnlyIdentifiers": physical_only,
        "aliasUsedDuplicatePhysicalIdentifiers": duplicate_groups,
        "joins": joins,
        "proofBoundary": (
            "Complete exact 32-bit identifier join between the green 215/215 FastFile SndAlias census and the green 116-bank physical SABS/SABL manifest from the same referenced ZIP64 archive. Every nonzero SndAlias.assetId is physically present. Duplicate physical identifier occurrences are retained and are proven identical only for the stored 128-bit checksum record plus parsed audio metadata fields; payload-byte identity is not claimed because payload bytes are not retained in the compact join inputs. assetId==0 occurrences remain intentional/unclassified here and are never treated as missing physical audio. Runtime alias/variant selection, bank dependency activation, mixing, spatialization, and playback semantics remain separate proof tasks."
        ),
    }


def load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise JoinError(f"expected JSON object in {path}")
    return obj


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--aliases", type=Path, required=True)
    p.add_argument("--physical", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(load(a.aliases), load(a.physical))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
