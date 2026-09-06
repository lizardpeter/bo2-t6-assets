#!/usr/bin/env python3
"""Resolve exact final-output `.tech code.*` cbuffer sources to T6 identities.

Consumes:
- t6-generated-final-output-cbuffer-signature-v1;
- t6-code-constant-source-table-v1 parsed from pinned OpenAssetTools sources.

Every exact `.tech` assignment classified as `code` must resolve to one T6
commonCodeConstSources accessor. Array accessors require an explicit `[index]`
and are mapped to base MaterialConstantSource enum value + index, with all enum
aliases at the resulting numeric value retained.

This proves engine code-constant identity/index/update-frequency metadata only.
It does not recover runtime values and does not assign physical semantics based
on accessor or enum names.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT = "t6-generated-final-output-code-constant-identity-v1"
CBUFFER_FORMAT = "t6-generated-final-output-cbuffer-signature-v1"
TABLE_FORMAT = "t6-code-constant-source-table-v1"
INDEXED_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]$")
SCALAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class FinalOutputCodeConstantIdentityError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _table_by_accessor(table_doc: dict) -> dict[str, dict]:
    out = {}
    for row in table_doc.get("rows", []):
        accessor = str(row.get("accessor") or "")
        if not accessor or accessor in out:
            raise FinalOutputCodeConstantIdentityError(
                f"invalid/duplicate code-constant accessor {accessor!r}"
            )
        out[accessor] = row
    if not out:
        raise FinalOutputCodeConstantIdentityError("code-constant table contains no rows")
    return out


def resolve_source_name(source_name: str, table_doc: dict) -> dict:
    rows = _table_by_accessor(table_doc)
    aliases = {
        int(key): [str(x) for x in value]
        for key, value in dict(table_doc.get("enumAliasesByValue", {})).items()
    }
    indexed = INDEXED_RE.fullmatch(source_name)
    if indexed:
        base = indexed.group(1)
        index = int(indexed.group(2))
        row = rows.get(base)
        if row is None:
            raise FinalOutputCodeConstantIdentityError(
                f"indexed code accessor base {base!r} is absent from pinned table"
            )
        count = int(row.get("arrayCount", 0))
        if count <= 0:
            raise FinalOutputCodeConstantIdentityError(
                f"code accessor {base!r} is scalar but source uses index [{index}]"
            )
        if not 0 <= index < count:
            raise FinalOutputCodeConstantIdentityError(
                f"code accessor {base!r}[{index}] outside arrayCount={count}"
            )
        numeric = int(row["enumValue"]) + index
        return {
            "sourceName": source_name,
            "accessor": base,
            "arrayIndex": index,
            "arrayCount": count,
            "baseEnumSymbol": row["enumSymbol"],
            "baseEnumValue": int(row["enumValue"]),
            "baseEnumValueHex": row.get("enumValueHex", f"0x{int(row['enumValue']):x}"),
            "resolvedEnumValue": numeric,
            "resolvedEnumValueHex": f"0x{numeric:x}",
            "resolvedEnumAliases": aliases.get(numeric, []),
            "updateFrequency": row["updateFrequency"],
            "techFlags": row.get("techFlags"),
            "transposedMatrixEnumSymbol": row.get("transposedMatrixEnumSymbol"),
            "transposedMatrixEnumValue": row.get("transposedMatrixEnumValue"),
        }

    if not SCALAR_RE.fullmatch(source_name):
        raise FinalOutputCodeConstantIdentityError(
            f"unsupported code source expression name {source_name!r}"
        )
    row = rows.get(source_name)
    if row is None:
        raise FinalOutputCodeConstantIdentityError(
            f"code accessor {source_name!r} is absent from pinned table"
        )
    count = int(row.get("arrayCount", 0))
    if count > 0:
        raise FinalOutputCodeConstantIdentityError(
            f"array code accessor {source_name!r} requires an explicit [index]"
        )
    numeric = int(row["enumValue"])
    return {
        "sourceName": source_name,
        "accessor": source_name,
        "arrayIndex": None,
        "arrayCount": 0,
        "baseEnumSymbol": row["enumSymbol"],
        "baseEnumValue": numeric,
        "baseEnumValueHex": row.get("enumValueHex", f"0x{numeric:x}"),
        "resolvedEnumValue": numeric,
        "resolvedEnumValueHex": f"0x{numeric:x}",
        "resolvedEnumAliases": aliases.get(numeric, []),
        "updateFrequency": row["updateFrequency"],
        "techFlags": row.get("techFlags"),
        "transposedMatrixEnumSymbol": row.get("transposedMatrixEnumSymbol"),
        "transposedMatrixEnumValue": row.get("transposedMatrixEnumValue"),
    }


def build(cbuffer_doc: dict, table_doc: dict) -> dict:
    if cbuffer_doc.get("format") != CBUFFER_FORMAT:
        raise FinalOutputCodeConstantIdentityError(
            f"unexpected cbuffer format {cbuffer_doc.get('format')!r}"
        )
    if table_doc.get("format") != TABLE_FORMAT:
        raise FinalOutputCodeConstantIdentityError(
            f"unexpected code-constant table format {table_doc.get('format')!r}"
        )

    rows = []
    assignment_count = 0
    array_assignment_count = 0
    frequency_counts = Counter()
    accessor_counts = Counter()
    resolved_enum_values = set()
    for shader in cbuffer_doc.get("shaders", []):
        sha = str(shader.get("sha256") or "")
        if not sha:
            raise FinalOutputCodeConstantIdentityError("cbuffer shader row lacks SHA")
        assignments = []
        for item in shader.get("usedCbufferSymbols", []):
            symbol = str(item.get("symbol") or "")
            for assignment in item.get("techniqueAssignments", []):
                if str(assignment.get("sourceClass") or "") != "code":
                    continue
                technique = str(assignment.get("techniqueSet") or "")
                source_name = str(assignment.get("sourceName") or "")
                source_expr = str(assignment.get("sourceExpression") or "")
                if not technique or not source_name:
                    raise FinalOutputCodeConstantIdentityError(
                        f"shader {sha} {symbol}: code assignment lacks TechniqueSet/sourceName"
                    )
                if source_expr != f"code.{source_name}":
                    raise FinalOutputCodeConstantIdentityError(
                        f"shader {sha} {symbol}: code expression {source_expr!r} != code.{source_name}"
                    )
                identity = resolve_source_name(source_name, table_doc)
                row = {
                    "symbol": symbol,
                    "nodeIds": sorted(int(x) for x in item.get("nodeIds", [])),
                    "buffer": copy.deepcopy(item.get("buffer")),
                    "variable": copy.deepcopy(item.get("variable")),
                    "techniqueSet": technique,
                    "sourceExpression": source_expr,
                    **identity,
                    "runtimeValueResolved": False,
                }
                assignments.append(row)
                assignment_count += 1
                array_assignment_count += int(identity["arrayIndex"] is not None)
                frequency_counts[str(identity["updateFrequency"])] += 1
                accessor_counts[str(identity["accessor"])] += 1
                resolved_enum_values.add(int(identity["resolvedEnumValue"]))
        rows.append({
            "sha256": sha,
            "techniqueSets": sorted(str(x) for x in shader.get("techniqueSets", [])),
            "codeConstantAssignmentCount": len(assignments),
            "assignments": sorted(
                assignments,
                key=lambda row: (row["techniqueSet"], row["symbol"], row["sourceName"]),
            ),
        })

    rows.sort(key=lambda row: row["sha256"])
    return {
        "format": FORMAT,
        "sourceCbufferFormat": CBUFFER_FORMAT,
        "sourceCodeConstantTableFormat": TABLE_FORMAT,
        "codeConstantTableSource": copy.deepcopy(table_doc.get("source")),
        "shaders": rows,
        "summary": {
            "shaderCount": len(rows),
            "codeConstantAssignmentCount": assignment_count,
            "arrayCodeConstantAssignmentCount": array_assignment_count,
            "uniqueAccessorCount": len(accessor_counts),
            "uniqueResolvedEnumValueCount": len(resolved_enum_values),
            "updateFrequencyAssignmentCounts": dict(sorted(frequency_counts.items())),
            "accessorAssignmentCounts": dict(sorted(accessor_counts.items())),
            "rowsSha256": _jhash(rows),
        },
        "proofBoundary": (
            "Exact .tech code.* assignment identity joined to the pinned OAT T6 commonCodeConstSources and "
            "MaterialConstantSource enum. Scalar/array index, numeric enum value, update frequency, optional flags, "
            "and matrix-pair metadata are retained. Runtime values and physical semantics remain unresolved."
        ),
    }


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--cbuffer-signature',type=Path,required=True);p.add_argument('--code-constant-table',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.cbuffer_signature.read_text()),json.loads(a.code_constant_table.read_text()));a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
