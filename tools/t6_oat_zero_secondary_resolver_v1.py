#!/usr/bin/env python3
"""Resolve zero-asset T6 SndAlias Secondary strings from native loaded-SndBank OAT CSV output.

The raw expanded-FastFile census preserves serialized pointer states. Pinned T6 OAT's
SndBank dumper runs after normal loader pointer/backreference fixups and writes the
resolved `alias.secondaryName` C string into the `Secondary` CSV column.

This adapter joins those two views by exact T6 alias hash plus variant ordinal inside
the alias list. It never interprets the raw serialized 32-bit Secondary pointer value.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def snd_hash_name(text: str) -> int:
    if not text:
        return 0
    result = 0x1505
    for c in text.lower().encode("latin1", errors="ignore"):
        result = (c + 0x1003F * result) & 0xFFFFFFFF
    return result or 1


def _load_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def parse_oat_csv(path: Path) -> tuple[dict[tuple[str, int], dict], str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    required = {"Name", "FileSource", "Secondary"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError(f"{path}: missing required OAT alias columns; got {reader.fieldnames}")

    ordinal_by_id: dict[str, int] = defaultdict(int)
    first_name_by_id: dict[str, str] = {}
    rows: dict[tuple[str, int], dict] = {}
    for row_index, row in enumerate(reader):
        name = row.get("Name", "")
        if not name:
            raise ValueError(f"{path}: empty alias Name at CSV data row {row_index}")
        aid = f"{snd_hash_name(name):08X}"
        previous = first_name_by_id.get(aid)
        if previous is not None and previous.lower() != name.lower():
            raise ValueError(f"{path}: alias hash collision {aid}: {previous!r} vs {name!r}")
        first_name_by_id.setdefault(aid, name)
        ordinal = ordinal_by_id[aid]
        ordinal_by_id[aid] += 1
        key = (aid, ordinal)
        if key in rows:
            raise ValueError(f"{path}: duplicate key {key}")
        rows[key] = {
            "csvRowIndex": row_index,
            "aliasName": name,
            "aliasIdHex": aid,
            "variantIndex": ordinal,
            "fileSource": row.get("FileSource", ""),
            "secondaryNameResolved": row.get("Secondary", ""),
        }
    return rows, hashlib.sha256(raw).hexdigest()


def build(zero: dict, bank_csvs: dict[str, Path], *, zero_sha256: str = "") -> dict:
    if zero.get("format") != "t6-sndalias-zero-asset-all-fastfile-v1":
        raise ValueError("unexpected zero census format")
    if int(zero.get("summary", {}).get("zeroAssetIdOccurrenceCount", -1)) != 4094:
        raise ValueError("zero census population changed")

    parsed: dict[str, dict] = {}
    csv_hashes: dict[str, str] = {}
    for bank, path in sorted(bank_csvs.items()):
        rows, sha = parse_oat_csv(path)
        parsed[bank] = rows
        csv_hashes[bank] = sha

    scope = [r for r in zero.get("zeroRows", []) if r.get("bankName") in parsed]
    if not scope:
        raise ValueError("no zero-asset rows are covered by supplied OAT bank CSVs")

    resolved = []
    pointer_state_counts: dict[str, int] = defaultdict(int)
    resolved_secondary_nonempty_by_pointer_state: dict[str, int] = defaultdict(int)
    for raw in scope:
        bank = raw["bankName"]
        key = (raw["aliasListIdHex"], int(raw["variantIndex"]))
        oat = parsed[bank].get(key)
        if oat is None:
            raise ValueError(f"{bank}: OAT CSV missing raw zero alias/variant {key}")
        if oat["fileSource"]:
            raise ValueError(
                f"{bank}: raw assetId==0 row {key} has non-empty OAT FileSource {oat['fileSource']!r}"
            )
        raw_name = raw.get("aliasListNameValidatedInline", "")
        if raw_name and raw_name.lower() != oat["aliasName"].lower():
            raise ValueError(f"{bank}: validated raw/OAT alias name disagreement for {key}: {raw_name!r} vs {oat['aliasName']!r}")

        state = raw["pointers"]["secondary_ptr"]["state"]
        pointer_state_counts[state] += 1
        secondary = oat["secondaryNameResolved"]
        if secondary:
            resolved_secondary_nonempty_by_pointer_state[state] += 1

        inline = raw.get("inlineStrings", {}).get("secondaryName", "")
        if state == "inline_serialized" and inline != secondary:
            raise ValueError(f"{bank}: inline Secondary/OAT mismatch for {key}: {inline!r} vs {secondary!r}")
        if state == "null" and secondary:
            raise ValueError(f"{bank}: null serialized Secondary unexpectedly resolved non-empty for {key}: {secondary!r}")

        resolved.append({
            "bankName": bank,
            "sourceFastFile": raw["source"],
            "aliasIdHex": raw["aliasListIdHex"],
            "aliasNameResolved": oat["aliasName"],
            "variantIndex": int(raw["variantIndex"]),
            "rawSecondaryPointerState": state,
            "rawSecondaryPointerValueHex": raw["pointers"]["secondary_ptr"]["valueHex"],
            "rawInlineSecondaryName": inline,
            "resolvedSecondaryName": secondary,
            "resolvedSecondaryAliasIdHex": f"{snd_hash_name(secondary):08X}" if secondary else "00000000",
            "oatCsvRowIndex": oat["csvRowIndex"],
        })

    unresolved_noninline = [
        r for r in resolved
        if r["rawSecondaryPointerState"] == "other_u32" and not r["resolvedSecondaryName"]
    ]
    return {
        "format": "t6-oat-zero-secondary-resolver-v1",
        "source": {
            "zeroAssetCensusSha256": zero_sha256,
            "oatAliasCsvSha256ByBank": csv_hashes,
        },
        "summary": {
            "coveredBankCount": len(parsed),
            "coveredZeroAssetOccurrenceCount": len(resolved),
            "rawSecondaryPointerStateCounts": dict(sorted(pointer_state_counts.items())),
            "resolvedNonemptySecondaryByRawPointerState": dict(sorted(resolved_secondary_nonempty_by_pointer_state.items())),
            "nonInlineSecondaryPointerOccurrenceCount": int(pointer_state_counts.get("other_u32", 0)),
            "nonInlineSecondaryResolvedNonemptyCount": int(resolved_secondary_nonempty_by_pointer_state.get("other_u32", 0)),
            "nonInlineSecondaryResolvedEmptyCount": len(unresolved_noninline),
        },
        "rows": resolved,
        "proofBoundary": (
            "Native loaded-SndBank Secondary resolution for the supplied OAT alias CSV bank set. Raw serialized pointer values are never interpreted. "
            "Rows are joined by exact T6 SND_HashName(alias Name) plus variant ordinal and require raw assetId==0 to agree with empty native OAT FileSource. "
            "Inline serialized Secondary strings must exactly match OAT. Null serialized Secondary pointers must remain empty. "
            "A non-inline pointer may be called resolved only from OAT's post-loader `alias.secondaryName` CSV value. "
            "This establishes string identity after loader fixups, not retail playback/fallback/recursion semantics."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--zero", type=Path, required=True)
    p.add_argument("--bank-csv", action="append", required=True, help="BANK=PATH, e.g. mpl_common.all=/tmp/out/soundbank/mpl_common.all.aliases.csv")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    zero, zsha = _load_json(a.zero)
    banks: dict[str, Path] = {}
    for spec in a.bank_csv:
        if "=" not in spec:
            raise SystemExit(f"bad --bank-csv spec: {spec!r}")
        bank, path = spec.split("=", 1)
        if not bank or bank in banks:
            raise SystemExit(f"duplicate/empty bank in --bank-csv: {bank!r}")
        banks[bank] = Path(path)
    result = build(zero, banks, zero_sha256=zsha)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
