#!/usr/bin/env python3
"""Parse native OAT T6 WEAPONFILE output without losing duplicate keys.

The T6 WeaponFields source contains 1028 rows but 1027 authored names because
``guidedMissileType`` occurs twice.  A dict-only parser would silently erase a
source row.  This parser therefore preserves exact key/value order and occurrence
indices, then optionally joins rows to the pinned gameplay field contract.

This parser does not claim the InfoString representation is the raw in-memory
representation. In particular CSPFT_MILLISECONDS values are authored seconds
produced from the native integer milliseconds by OAT's source-closed writer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

FORMAT = "t6-oat-weapon-info-v1"
CONTRACT_FORMAT = "t6-weapon-gameplay-field-contract-v1"
PREFIX = "WEAPONFILE"


class WeaponInfoError(RuntimeError):
    pass


def parse_bytes(data: bytes) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WeaponInfoError("native OAT weapon output is not UTF-8 text") from exc
    parts = text.split("\\")
    if not parts or parts[0] != PREFIX:
        raise WeaponInfoError(f"unexpected weapon info prefix {parts[0] if parts else None!r}")
    if (len(parts) - 1) % 2:
        raise WeaponInfoError("weapon info key/value token count is odd")
    occurrence = Counter()
    rows = []
    for i in range(1, len(parts), 2):
        name, value = parts[i], parts[i + 1]
        if not name:
            raise WeaponInfoError(f"empty key at token {i}")
        rows.append({
            "rowIndex": len(rows),
            "name": name,
            "nameOccurrence": occurrence[name],
            "value": value,
        })
        occurrence[name] += 1
    return rows


def _ms_candidate(value: str) -> dict[str, Any]:
    if value == "":
        return {"authoredSeconds": value, "integerMillisecondCandidate": None, "decimalTimes1000Integral": False}
    try:
        d = Decimal(value)
    except InvalidOperation:
        return {"authoredSeconds": value, "integerMillisecondCandidate": None, "decimalTimes1000Integral": False}
    ms = d * Decimal(1000)
    integral = ms == ms.to_integral_value()
    return {
        "authoredSeconds": value,
        "integerMillisecondCandidate": int(ms) if integral else None,
        "decimalTimes1000Integral": bool(integral),
        "candidateStatus": (
            "candidate-requires-native-integer-crosscheck"
            if integral
            else "not-an-exact-integer-millisecond-decimal"
        ),
    }


def build(data: bytes, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = parse_bytes(data)
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_name[row["name"]].append(row)

    if contract is not None:
        if contract.get("format") != CONTRACT_FORMAT:
            raise WeaponInfoError(f"unsupported field contract {contract.get('format')!r}")
        crows = contract.get("fields")
        if not isinstance(crows, list):
            raise WeaponInfoError("field contract has no fields[]")
        if len(crows) != len(rows):
            raise WeaponInfoError(f"native OAT row count {len(rows)} != contract {len(crows)}")
        for got, expected in zip(rows, crows):
            if got["name"] != expected.get("name") or got["nameOccurrence"] != expected.get("nameOccurrence"):
                raise WeaponInfoError(
                    f"row {got['rowIndex']}: OAT key occurrence {(got['name'], got['nameOccurrence'])!r} "
                    f"!= contract {(expected.get('name'), expected.get('nameOccurrence'))!r}"
                )
            got["member"] = expected.get("member")
            got["fieldType"] = expected.get("type")
            got["category"] = expected.get("category")
            if got["fieldType"] == "CSPFT_MILLISECONDS":
                got["milliseconds"] = _ms_candidate(got["value"])

    duplicate_names = {name: len(copies) for name, copies in by_name.items() if len(copies) > 1}
    nonempty = sum(1 for row in rows if row["value"] != "")
    ms_rows = [r for r in rows if r.get("fieldType") == "CSPFT_MILLISECONDS"]
    ms_integral = sum(1 for r in ms_rows if r.get("milliseconds", {}).get("decimalTimes1000Integral") is True)
    return {
        "format": FORMAT,
        "source": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "summary": {
            "rowCount": len(rows),
            "uniqueAuthoredNames": len(by_name),
            "duplicateAuthoredNameCount": len(duplicate_names),
            "nonemptyValueRows": nonempty,
            "contractJoined": contract is not None,
            "millisecondRows": len(ms_rows),
            "millisecondRowsWithIntegralDecimalCandidate": ms_integral,
            "rawNativeMillisecondIntegersCrosschecked": False,
        },
        "duplicateAuthoredNames": duplicate_names,
        "rows": rows,
        "proofBoundary": (
            "Rows are exact OAT-authored values from the pinned native dump and preserve source order/duplicates. "
            "When joined to the pinned field contract, field identity/type is exact. CSPFT_MILLISECONDS decimal values are only converted to integer-millisecond candidates when decimal*1000 is integral; those candidates are not promoted as raw native integers until independently cross-checked."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weapon", type=Path, required=True)
    ap.add_argument("--contract", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8-sig")) if args.contract else None
    out = build(args.weapon.read_bytes(), contract)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
