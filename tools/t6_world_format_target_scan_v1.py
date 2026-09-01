#!/usr/bin/env python3
"""Scan T6 map material inventories for layered worldVertFormat proof targets.

This is a fixture-discovery tool, not a byte validator. It uses the source-closed
Treyarch layered-material name grammar and world-format selection rule to find
which generated materials should require MaterialWorldVertexFormat 1..8. It is
especially useful for locating retail fixtures for formats not yet byte-proven.

Accepted inputs:
- CSV with a `materialName` column (surface-material mapping), or
- JSON with `materials[]` entries containing `name` (material catalog).
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from t6_layered_material_name_v1 import LayeredMaterialError
from t6_layered_world_format_v1 import LayeredWorldFormatError, predict_from_name


class TargetScanError(RuntimeError):
    pass


def _names_from_csv(path: Path) -> list[str]:
    reader = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
    if "materialName" not in (reader.fieldnames or []):
        raise TargetScanError(f"{path}: CSV lacks materialName column")
    return [str(row.get("materialName") or "") for row in reader]


def _names_from_json(path: Path) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("materials")
    if not isinstance(rows, list):
        raise TargetScanError(f"{path}: JSON lacks materials[]")
    return [str(row.get("name") or "") for row in rows]


def scan(paths: list[Path], target_formats: set[int] | None = None) -> dict:
    target_formats = set(target_formats or {4, 5, 7, 8})
    files: list[dict] = []
    all_unique: dict[str, dict] = {}
    invalid: list[dict] = []

    for path in paths:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            names = _names_from_csv(path)
        elif suffix == ".json":
            names = _names_from_json(path)
        else:
            raise TargetScanError(f"{path}: expected .csv or .json")

        unique_names = sorted(set(name for name in names if name))
        predicted = []
        counts = Counter()
        for name in unique_names:
            if not name.startswith("*"):
                continue
            try:
                row = predict_from_name(name)
            except (LayeredMaterialError, LayeredWorldFormatError) as exc:
                invalid.append({"file": str(path), "material": name, "error": str(exc)})
                continue
            counts[int(row["worldVertFormat"])] += 1
            predicted.append(row)
            all_unique.setdefault(name, row)

        files.append(
            {
                "file": str(path),
                "rowCount": len(names),
                "uniqueMaterialCount": len(unique_names),
                "compoundMaterialCount": len(predicted),
                "predictedFormatCounts": {
                    str(k): v for k, v in sorted(counts.items())
                },
                "targetMaterials": [
                    row for row in predicted if int(row["worldVertFormat"]) in target_formats
                ],
            }
        )

    global_counts = Counter(
        int(row["worldVertFormat"]) for row in all_unique.values()
    )
    candidates = [
        row for row in all_unique.values() if int(row["worldVertFormat"]) in target_formats
    ]
    candidates.sort(key=lambda row: (int(row["worldVertFormat"]), row["material"]))

    return {
        "format": "t6-world-format-target-scan-v1",
        "targetFormats": sorted(target_formats),
        "inputFileCount": len(paths),
        "files": files,
        "stats": {
            "uniqueCompoundMaterialCount": len(all_unique),
            "predictedFormatCounts": {
                str(k): v for k, v in sorted(global_counts.items())
            },
            "targetCandidateCount": len(candidates),
            "invalidCompoundNameCount": len(invalid),
        },
        "targetCandidates": candidates,
        "invalidCompoundNames": invalid,
        "proofBoundary": (
            "predicted format selection is source-closed; candidate formats are not "
            "retail-byte-proven until vd0/vd1 bytes pass t6_world_vertex_audit_v2"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--target-format", action="append", type=int, dest="targets")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    doc = scan(args.inputs, set(args.targets) if args.targets else None)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(json.dumps({"out": str(args.out), **doc["stats"]}, indent=2))
    else:
        print(text, end="")
    return 0 if not doc["invalidCompoundNames"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
