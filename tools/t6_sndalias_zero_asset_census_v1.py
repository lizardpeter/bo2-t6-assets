#!/usr/bin/env python3
"""Characterize serialized T6 SndAlias rows with assetId == 0.

This reuses the already fail-closed SndBank/SndAliasList/SndAlias structural
parser. It does not assign a runtime meaning to a zero assetId. Instead it
retains exact source location, alias identity, semantic variant, raw playback
fields, serialized pointer states, and inline strings so zero-only and mixed
zero/nonzero alias families can be separated without guesswork.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import t6_sndalias_expanded_census_v1 as base


def pointer_state(value: int) -> str:
    value &= 0xFFFFFFFF
    if value == 0:
        return "null"
    if value == 0xFFFFFFFF:
        return "inline_serialized"
    return "other_u32"


def census_zero(blob: bytes, bank_bases: list[str], source: str = "") -> dict:
    pattern = base.compile_bank_regex(bank_bases)
    candidate_count = 0
    accepted_sections = []
    rejected = collections.Counter()
    alias_class_counts: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    zero_alias_counts = collections.Counter()
    zero_semantic_counts = collections.Counter()
    validated_zero_names: dict[int, str] = {}
    zero_rows = []

    for match in pattern.finditer(blob):
        candidate_count += 1
        bank_name = match.group(1).decode("ascii")
        lists, aliases, end_cursor, issues, learned = base.parse_sndbank_alias_section(
            blob, bank_name, match.start(1)
        )
        if not lists or not aliases or issues:
            if not lists:
                rejected["no_alias_lists"] += 1
            elif issues:
                rejected[issues[0].split(":", 1)[0]] += 1
            else:
                rejected["empty_aliases"] += 1
            continue

        accepted_sections.append({
            "bankName": bank_name,
            "bankNameOffset": match.start(1),
            "aliasListCount": len(lists),
            "aliasOccurrenceCount": len(aliases),
            "endingCursor": end_cursor,
        })

        for alias in aliases:
            aid = int(alias["alias_list_id"]) & 0xFFFFFFFF
            asset = int(alias["asset_id"]) & 0xFFFFFFFF
            alias_class_counts[aid]["zero" if asset == 0 else "nonzero"] += 1
            if asset != 0:
                continue

            digest = base.semantic_digest(alias)
            zero_alias_counts[aid] += 1
            zero_semantic_counts[digest] += 1

            validated_name = str(alias.get("alias_list_name_inline") or "")
            if validated_name:
                old = validated_zero_names.get(aid)
                if old is not None and old != validated_name:
                    raise ValueError(
                        f"zero-asset alias ID 0x{aid:08x} has conflicting validated names {old!r} vs {validated_name!r}"
                    )
                validated_zero_names[aid] = validated_name

            pointers = {}
            for key in ("name_ptr", "subtitle_ptr", "secondary_ptr", "file_ptr"):
                value = int(alias[key]) & 0xFFFFFFFF
                pointers[key] = {
                    "valueHex": f"{value:08X}",
                    "state": pointer_state(value),
                }

            raw_playback = {field: alias[field] for field in base.RAW_PLAYBACK_FIELDS}
            zero_rows.append({
                "source": source,
                "bankName": bank_name,
                "bankNameOffset": match.start(1),
                "aliasListIdHex": f"{aid:08X}",
                "aliasListNameValidatedInline": validated_name,
                "variantIndex": int(alias["variant_index"]),
                "variantCount": int(alias["variant_count"]),
                "semanticDigestSha256": digest,
                "flags0Hex": f"{int(alias['flags0']) & 0xFFFFFFFF:08X}",
                "flags1Hex": f"{int(alias['flags1']) & 0xFFFFFFFF:08X}",
                "pointers": pointers,
                "inlineStrings": {
                    "aliasName": str(alias.get("alias_name_inline") or ""),
                    "subtitle": str(alias.get("subtitle_inline") or ""),
                    "secondaryName": str(alias.get("secondary_name_inline") or ""),
                    "assetFileName": str(alias.get("asset_file_name_inline") or ""),
                },
                "rawPlaybackFields": raw_playback,
            })

    alias_class = {
        f"{aid:08X}": {
            "zeroOccurrenceCount": int(counts.get("zero", 0)),
            "nonzeroOccurrenceCount": int(counts.get("nonzero", 0)),
        }
        for aid, counts in sorted(alias_class_counts.items())
    }
    zero_only = sum(1 for counts in alias_class_counts.values() if counts.get("zero", 0) and not counts.get("nonzero", 0))
    mixed = sum(1 for counts in alias_class_counts.values() if counts.get("zero", 0) and counts.get("nonzero", 0))

    pointer_states = {
        key: dict(sorted(collections.Counter(row["pointers"][key]["state"] for row in zero_rows).items()))
        for key in ("name_ptr", "subtitle_ptr", "secondary_ptr", "file_ptr")
    }
    inline_nonempty = {
        key: sum(bool(row["inlineStrings"][key]) for row in zero_rows)
        for key in ("aliasName", "subtitle", "secondaryName", "assetFileName")
    }

    return {
        "format": "t6-sndalias-zero-asset-census-v1",
        "source": source,
        "expandedBytes": len(blob),
        "summary": {
            "candidateBankStringCount": candidate_count,
            "validatedSndBankSectionCount": len(accepted_sections),
            "aliasDefinitionOccurrenceCount": sum(
                counts.get("zero", 0) + counts.get("nonzero", 0)
                for counts in alias_class_counts.values()
            ),
            "zeroAssetIdOccurrenceCount": len(zero_rows),
            "nonzeroAssetIdOccurrenceCount": sum(counts.get("nonzero", 0) for counts in alias_class_counts.values()),
            "uniqueAliasIdCount": len(alias_class_counts),
            "uniqueAliasIdsWithZeroAssetCount": len(zero_alias_counts),
            "zeroOnlyAliasIdCount": zero_only,
            "mixedZeroAndNonzeroAliasIdCount": mixed,
            "uniqueZeroSemanticVariantCount": len(zero_semantic_counts),
            "validatedInlineNameForZeroAliasIdCount": len(validated_zero_names),
            "rejectedCandidateCount": sum(rejected.values()),
            "zeroRowsWithNonemptyInlineStrings": inline_nonempty,
            "zeroPointerStateCounts": pointer_states,
        },
        "validatedSections": accepted_sections,
        "aliasAssetClassCounts": alias_class,
        "zeroAliasIdCounts": {f"{aid:08X}": n for aid, n in sorted(zero_alias_counts.items())},
        "zeroSemanticVariantCounts": dict(sorted(zero_semantic_counts.items())),
        "validatedInlineZeroAliasNames": {f"{aid:08X}": name for aid, name in sorted(validated_zero_names.items())},
        "rejectedCandidateKinds": dict(sorted(rejected.items())),
        "zeroRows": zero_rows,
        "proofBoundary": (
            "Structural characterization of assetId==0 SndAlias rows in one already source-closed expanded T6 FastFile. "
            "The same exact bank-base nomination and fail-closed SndAliasList/head-ID gates as the complete alias census are reused. "
            "Zero is preserved as a serialized value only. No claim is made that it means silence, indirection, generated audio, streaming, a missing asset, or any other runtime behavior. "
            "Pointer values are classified only as null, inline-serialized sentinel, or other-u32; no meaning is assigned to other pointer values."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("expanded", type=Path)
    p.add_argument("--bank-bases", type=Path, required=True)
    p.add_argument("--source", default="")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    bases = [x.strip() for x in a.bank_bases.read_text(encoding="utf-8").splitlines() if x.strip()]
    result = census_zero(a.expanded.read_bytes(), bases, a.source)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
