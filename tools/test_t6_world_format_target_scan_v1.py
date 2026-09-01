#!/usr/bin/env python3
"""Regression for targeted layered worldVertFormat fixture discovery."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from t6_world_format_target_scan_v1 import scan


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        csv_path = root / "mapping.csv"
        fields = ["materialName"]
        names = [
            "wpc/ordinary",
            "*1n_2(wpc/a:wpc/b)",       # fmt 1
            "*1n_2n(wpc/a:wpc/b)",      # fmt 2
            "*1n_2n_3(wpc/a:wpc/b:wpc/c)",   # fmt 4
            "*1n_2n_3n(wpc/a:wpc/b:wpc/c)",  # fmt 5
            "*1n_2n_3_4(wpc/a:wpc/b:wpc/c:wpc/d)",  # fmt 7
            "*1n_2n_3n_4(wpc/a:wpc/b:wpc/c:wpc/d)", # fmt 8
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for name in names:
                writer.writerow({"materialName": name})

        json_path = root / "catalog.json"
        json_path.write_text(
            json.dumps(
                {
                    "materials": [
                        {"index": i, "name": name} for i, name in enumerate(names)
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        doc = scan([csv_path, json_path])
        assert doc["targetFormats"] == [4, 5, 7, 8]
        assert doc["stats"]["uniqueCompoundMaterialCount"] == 6
        assert doc["stats"]["predictedFormatCounts"] == {
            "1": 1,
            "2": 1,
            "4": 1,
            "5": 1,
            "7": 1,
            "8": 1,
        }
        assert doc["stats"]["targetCandidateCount"] == 4
        assert [row["worldVertFormat"] for row in doc["targetCandidates"]] == [
            4,
            5,
            7,
            8,
        ]
        assert doc["stats"]["invalidCompoundNameCount"] == 0
        assert all(file["compoundMaterialCount"] == 6 for file in doc["files"])
        assert all(len(file["targetMaterials"]) == 4 for file in doc["files"])

    print("PASS t6_world_format_target_scan_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
