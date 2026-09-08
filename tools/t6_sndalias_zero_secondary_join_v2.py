#!/usr/bin/env python3
"""Classify every native-resolved zero-asset T6 SndAlias Secondary target.

Requires the complete native 37-bank OAT resolution, the original zero census,
the complete all-FastFile alias census, and the independently complete physical
asset-ID join. No runtime playback semantics are inferred.
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


def _read(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def classify_target(target_id: int, alias_counts: dict[int, int], zero_counts: dict[int, int]) -> tuple[str, int, int, int]:
    total = alias_counts.get(target_id, 0)
    zero_occ = zero_counts.get(target_id, 0)
    nonzero_occ = total - zero_occ
    if total == 0:
        return "missing_alias_id", total, zero_occ, nonzero_occ
    if zero_occ and nonzero_occ:
        return "mixed_zero_and_nonzero_target", total, zero_occ, nonzero_occ
    if nonzero_occ:
        return "nonzero_only_target", total, zero_occ, nonzero_occ
    if zero_occ:
        return "zero_only_target", total, zero_occ, nonzero_occ
    raise ValueError(f"impossible target counts for {target_id:08X}")


def build(native: dict, zero: dict, aliases: dict, physical: dict, *, source_hashes: dict | None = None) -> dict:
    if native.get("format") != "t6-oat-zero-secondary-all-fastfile-v1":
        raise ValueError("unexpected native Secondary aggregate format")
    if zero.get("format") != "t6-sndalias-zero-asset-all-fastfile-v1":
        raise ValueError("unexpected zero census format")
    if aliases.get("format") != "t6-sndalias-all-fastfile-census-v1":
        raise ValueError("unexpected complete alias census format")
    if physical.get("format") != "t6-audio-alias-physical-join-v1":
        raise ValueError("unexpected physical join format")

    ns = native.get("summary", {})
    if int(ns.get("coveredBankCount", -1)) != 37 or int(ns.get("coveredZeroAssetOccurrenceCount", -1)) != 4094:
        raise ValueError("native Secondary aggregate does not cover exact 37-bank / 4094-row population")
    if int(ns.get("nonInlineSecondaryPointerOccurrenceCount", -1)) != 1334:
        raise ValueError("native non-inline Secondary population changed")
    if int(ns.get("nonInlineSecondaryResolvedEmptyCount", -1)) != 0:
        raise ValueError("native Secondary aggregate still contains unresolved non-inline pointers")
    if int(ns.get("nonInlineSecondaryResolvedNonemptyCount", -1)) != 1334:
        raise ValueError("native Secondary aggregate did not resolve all 1334 non-inline pointers")

    zs = zero.get("summary", {})
    ass = aliases.get("summary", {})
    for key, expected in (
        ("aliasDefinitionOccurrenceCount", 445664),
        ("nonzeroAssetIdOccurrenceCount", 441570),
        ("zeroAssetIdOccurrenceCount", 4094),
        ("uniqueAliasIdCount", 18103),
        ("fastFileCount", 215),
    ):
        for label, summary in (("zero", zs), ("aliases", ass)):
            if int(summary.get(key, -1)) != expected:
                raise ValueError(f"{label} {key} changed: {summary.get(key)!r} != {expected}")

    ps = physical.get("summary", {})
    if int(ps.get("unmatchedUniqueNonzeroAssetIdCount", -1)) != 0:
        raise ValueError("physical join has unmatched nonzero asset IDs")
    if int(ps.get("matchedUniqueNonzeroAssetIdCount", -1)) != 24481:
        raise ValueError("physical unique match population changed")
    if int(ps.get("matchedNonzeroAssetIdOccurrenceCount", -1)) != 441570:
        raise ValueError("physical occurrence match population changed")

    alias_counts = {int(k, 16): int(v) for k, v in aliases["aliasIdCounts"].items()}
    zero_counts = {int(k, 16): int(v) for k, v in zero["zeroAliasIdCounts"].items()}
    validated_names = {int(k, 16): v for k, v in aliases.get("validatedInlineAliasNames", {}).items()}

    resolved_rows = [r for r in native.get("rows", []) if r.get("resolvedSecondaryName")]
    expected_nonempty = int(ns.get("totalResolvedNonemptySecondaryOccurrenceCount", -1))
    if len(resolved_rows) != expected_nonempty:
        raise ValueError("native resolved nonempty Secondary count disagrees with row population")

    target_name_counts = Counter(r["resolvedSecondaryName"] for r in resolved_rows)
    unique_class = Counter()
    occurrence_class = Counter()
    target_rows = []
    physical_unique = 0
    physical_occ = 0
    for name, occurrence_count in sorted(target_name_counts.items()):
        target_id = snd_hash_name(name)
        classification, total, zero_occ, nonzero_occ = classify_target(target_id, alias_counts, zero_counts)
        unique_class[classification] += 1
        occurrence_class[classification] += occurrence_count
        if nonzero_occ:
            physical_unique += 1
            physical_occ += occurrence_count
        target_rows.append({
            "secondaryName": name,
            "secondaryAliasIdHex": f"{target_id:08X}",
            "occurrenceCount": occurrence_count,
            "classification": classification,
            "targetAliasOccurrenceCount": total,
            "targetZeroAssetOccurrenceCount": zero_occ,
            "targetNonzeroAssetOccurrenceCount": nonzero_occ,
            "targetHasPhysicalBackedVariant": nonzero_occ > 0,
            "targetValidatedInlineName": validated_names.get(target_id, ""),
        })

    occurrence_rows = []
    for row in resolved_rows:
        name = row["resolvedSecondaryName"]
        target_id = snd_hash_name(name)
        classification, total, zero_occ, nonzero_occ = classify_target(target_id, alias_counts, zero_counts)
        occurrence_rows.append({
            "sourceBankName": row["bankName"],
            "sourceFastFile": row["sourceFastFile"],
            "sourceAliasIdHex": row["aliasIdHex"],
            "sourceAliasName": row["aliasNameResolved"],
            "sourceVariantIndex": int(row["variantIndex"]),
            "rawSecondaryPointerState": row["rawSecondaryPointerState"],
            "secondaryName": name,
            "secondaryAliasIdHex": f"{target_id:08X}",
            "classification": classification,
            "targetHasPhysicalBackedVariant": nonzero_occ > 0,
        })

    return {
        "format": "t6-sndalias-zero-secondary-join-v2",
        "source": source_hashes or {},
        "summary": {
            "zeroAssetOccurrenceCount": 4094,
            "resolvedNonemptySecondaryOccurrenceCount": len(resolved_rows),
            "uniqueResolvedSecondaryNameCount": len(target_rows),
            "targetUniqueClassificationCounts": dict(sorted(unique_class.items())),
            "targetOccurrenceClassificationCounts": dict(sorted(occurrence_class.items())),
            "uniqueSecondaryNamesWithPhysicalBackedTargetVariant": physical_unique,
            "secondaryOccurrencesWithPhysicalBackedTargetVariant": physical_occ,
            "missingTargetUniqueNameCount": int(unique_class.get("missing_alias_id", 0)),
            "missingTargetOccurrenceCount": int(occurrence_class.get("missing_alias_id", 0)),
        },
        "secondaryTargets": target_rows,
        "secondaryOccurrences": occurrence_rows,
        "proofBoundary": (
            "Complete structural classification of every non-empty Secondary string resolved by pinned native OAT for the exact 4,094 zero-asset rows. "
            "Targets are T6 SND_HashName-joined to the complete 215-FastFile alias census. A target is marked physical-backed only because the independent 116-bank join proves all 24,481 unique / 441,570 occurrence nonzero asset IDs physically exist. "
            "This does not assert that retail playback follows Secondary, nor any recursion, fallback, ordering, randomization, selection, or zone-precedence behavior."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--native", type=Path, required=True)
    p.add_argument("--zero", type=Path, required=True)
    p.add_argument("--aliases", type=Path, required=True)
    p.add_argument("--physical-join", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    native, nsha = _read(a.native)
    zero, zsha = _read(a.zero)
    aliases, asha = _read(a.aliases)
    physical, psha = _read(a.physical_join)
    result = build(native, zero, aliases, physical, source_hashes={
        "nativeSecondaryAggregateSha256": nsha,
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
