#!/usr/bin/env python3
"""Join inline Secondary names from zero-asset T6 SndAlias rows to the complete alias/physical universe.

This is deliberately narrower than runtime sound-selection semantics. It proves only:

* the exact SND_HashName identity of each inline Secondary string;
* whether that target alias ID exists in the complete structural SndAlias census;
* whether the target alias family has zero-only, nonzero-only, or mixed serialized variants;
* whether any nonzero target variants may be called physically backed, and only when an
  independently complete alias->physical join is supplied and fully green.

Packed/non-inline secondary pointers are preserved as unresolved by this tool. No playback,
recursion, fallback, sequencing, or precedence behavior is inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def snd_hash_name(text: str) -> int:
    if not text:
        return 0
    result = 0x1505
    for c in text.lower().encode("latin1", errors="ignore"):
        result = (c + 0x1003F * result) & 0xFFFFFFFF
    return result or 1


def _load(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def build(zero: dict, aliases: dict, physical_join: dict, *, source_hashes: dict | None = None) -> dict:
    if zero.get("format") != "t6-sndalias-zero-asset-all-fastfile-v1":
        raise ValueError("unexpected zero-asset census format")
    if aliases.get("format") != "t6-sndalias-all-fastfile-census-v1":
        raise ValueError("unexpected complete alias census format")
    if physical_join.get("format") != "t6-audio-alias-physical-join-v1":
        raise ValueError("unexpected alias-physical join format")

    zs = zero.get("summary", {})
    ass = aliases.get("summary", {})
    ps = physical_join.get("summary", {})
    parity = {
        "aliasDefinitionOccurrenceCount": 445664,
        "nonzeroAssetIdOccurrenceCount": 441570,
        "zeroAssetIdOccurrenceCount": 4094,
        "uniqueAliasIdCount": 18103,
        "fastFileCount": 215,
    }
    for key, expected in parity.items():
        for label, summary in (("zero", zs), ("aliases", ass)):
            if int(summary.get(key, -1)) != expected:
                raise ValueError(f"{label} {key} changed: {summary.get(key)!r} != {expected}")
    if int(ps.get("unmatchedUniqueNonzeroAssetIdCount", -1)) != 0:
        raise ValueError("physical join is not complete: unmatched nonzero asset IDs remain")
    if int(ps.get("matchedUniqueNonzeroAssetIdCount", -1)) != 24481:
        raise ValueError("physical join unique matched population changed")
    if int(ps.get("matchedNonzeroAssetIdOccurrenceCount", -1)) != 441570:
        raise ValueError("physical join occurrence coverage changed")

    alias_counts = {int(k, 16): int(v) for k, v in aliases["aliasIdCounts"].items()}
    zero_counts = {int(k, 16): int(v) for k, v in zero["zeroAliasIdCounts"].items()}
    validated_names = {int(k, 16): v for k, v in aliases.get("validatedInlineAliasNames", {}).items()}

    inline_rows = []
    unique_names = Counter()
    for row in zero.get("zeroRows", []):
        secondary = row.get("inlineStrings", {}).get("secondaryName", "")
        if not secondary:
            continue
        unique_names[secondary] += 1
        target_id = snd_hash_name(secondary)
        total = alias_counts.get(target_id, 0)
        zero_occ = zero_counts.get(target_id, 0)
        nonzero_occ = total - zero_occ
        if total == 0:
            classification = "missing_alias_id"
        elif zero_occ and nonzero_occ:
            classification = "mixed_zero_and_nonzero_target"
        elif nonzero_occ:
            classification = "nonzero_only_target"
        elif zero_occ:
            classification = "zero_only_target"
        else:
            raise ValueError(f"impossible target counts for {secondary!r}")
        inline_rows.append({
            "sourceAliasIdHex": row["aliasListIdHex"],
            "sourceAliasName": row.get("aliasListNameValidatedInline", ""),
            "sourceFastFile": row["source"],
            "sourceSndBankName": row["bankName"],
            "sourceVariantIndex": row["variantIndex"],
            "secondaryName": secondary,
            "secondaryAliasIdHex": f"{target_id:08X}",
            "targetAliasOccurrenceCount": total,
            "targetZeroAssetOccurrenceCount": zero_occ,
            "targetNonzeroAssetOccurrenceCount": nonzero_occ,
            "targetHasPhysicalBackedVariant": nonzero_occ > 0,
            "targetValidatedInlineName": validated_names.get(target_id, ""),
            "classification": classification,
        })

    by_name = []
    class_unique = Counter()
    class_occ = Counter()
    physical_unique = 0
    physical_occ = 0
    for secondary, occurrence_count in sorted(unique_names.items()):
        target_id = snd_hash_name(secondary)
        total = alias_counts.get(target_id, 0)
        zero_occ = zero_counts.get(target_id, 0)
        nonzero_occ = total - zero_occ
        if total == 0:
            classification = "missing_alias_id"
        elif zero_occ and nonzero_occ:
            classification = "mixed_zero_and_nonzero_target"
        elif nonzero_occ:
            classification = "nonzero_only_target"
        elif zero_occ:
            classification = "zero_only_target"
        else:
            raise ValueError(f"impossible target counts for {secondary!r}")
        class_unique[classification] += 1
        class_occ[classification] += occurrence_count
        if nonzero_occ > 0:
            physical_unique += 1
            physical_occ += occurrence_count
        by_name.append({
            "secondaryName": secondary,
            "occurrenceCount": occurrence_count,
            "secondaryAliasIdHex": f"{target_id:08X}",
            "targetAliasOccurrenceCount": total,
            "targetZeroAssetOccurrenceCount": zero_occ,
            "targetNonzeroAssetOccurrenceCount": nonzero_occ,
            "targetHasPhysicalBackedVariant": nonzero_occ > 0,
            "targetValidatedInlineName": validated_names.get(target_id, ""),
            "classification": classification,
        })

    expected_inline = int(zs.get("zeroRowsWithNonemptyInlineStrings", {}).get("secondaryName", -1))
    if len(inline_rows) != expected_inline:
        raise ValueError(f"inline Secondary row count mismatch: {len(inline_rows)} != {expected_inline}")

    packed_secondary = int(zs.get("zeroPointerStateCounts", {}).get("secondary_ptr", {}).get("other_u32", 0))
    null_secondary = int(zs.get("zeroPointerStateCounts", {}).get("secondary_ptr", {}).get("null", 0))
    inline_secondary = int(zs.get("zeroPointerStateCounts", {}).get("secondary_ptr", {}).get("inline_serialized", 0))
    if packed_secondary + null_secondary + inline_secondary != 4094:
        raise ValueError("secondary pointer-state population does not sum to all zero rows")

    return {
        "format": "t6-sndalias-zero-secondary-join-v1",
        "source": source_hashes or {},
        "summary": {
            "zeroAssetOccurrenceCount": 4094,
            "inlineSecondaryOccurrenceCount": len(inline_rows),
            "uniqueInlineSecondaryNameCount": len(by_name),
            "inlineSecondaryTargetUniqueClassificationCounts": dict(sorted(class_unique.items())),
            "inlineSecondaryTargetOccurrenceClassificationCounts": dict(sorted(class_occ.items())),
            "uniqueInlineSecondaryNamesWithPhysicalBackedTargetVariant": physical_unique,
            "inlineSecondaryOccurrencesWithPhysicalBackedTargetVariant": physical_occ,
            "packedOrBackreferenceSecondaryPointerOccurrenceCount": packed_secondary,
            "nullSecondaryPointerOccurrenceCount": null_secondary,
            "unresolvedInlineSecondaryTargetOccurrenceCount": int(class_occ.get("missing_alias_id", 0)),
            "unresolvedInlineSecondaryTargetUniqueNameCount": int(class_unique.get("missing_alias_id", 0)),
        },
        "secondaryTargets": by_name,
        "inlineSecondaryRows": inline_rows,
        "proofBoundary": (
            "Exact structural join for inline-serialized Secondary strings on the 4,094 assetId==0 SndAlias rows. "
            "Secondary names are converted to T6 SND_HashName IDs and compared with the complete 215-FastFile alias census. "
            "A target is marked as having a physical-backed variant only because the supplied independent 116-bank join proves "
            "24,481/24,481 unique nonzero asset IDs and 441,570/441,570 nonzero occurrences physically match. "
            "The 1,334 non-null non-inline Secondary pointer values are intentionally unresolved here. "
            "No runtime Secondary playback, recursion, fallback, variant selection, sequencing, or zone-precedence semantics are inferred."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--zero", type=Path, required=True)
    p.add_argument("--aliases", type=Path, required=True)
    p.add_argument("--physical-join", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    zero, zsha = _load(a.zero)
    aliases, asha = _load(a.aliases)
    physical, psha = _load(a.physical_join)
    result = build(zero, aliases, physical, source_hashes={
        "zeroAssetCensusSha256": zsha,
        "completeAliasCensusSha256": asha,
        "aliasPhysicalJoinSha256": psha,
    })
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
