#!/usr/bin/env python3
"""Aggregate T6 world-vertex proof reports into a retail coverage census.

Input files are t6-world-vertex-proof-v1 JSON reports produced from exact map
GfxWorld surface/vd0/vd1 bytes. The census answers the question that matters for
universal export: which MaterialWorldVertexFormat values have actually been
observed and byte-validated on retail fixtures, and which remain formula-only.

No format is marked solved merely because its stride/layout is known. A format
becomes retail-proven only when at least one input proof reports it as observed
with zero bad vertex groups.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ALL_FORMATS = range(9)


class CensusError(RuntimeError):
    pass


def load_report(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("format") != "t6-world-vertex-proof-v1":
        raise CensusError(f"{path}: unsupported report format {doc.get('format')!r}")
    if int(doc.get("badGroupCount", 0)) != 0:
        raise CensusError(f"{path}: report contains {doc.get('badGroupCount')} bad vertex groups")
    return doc


def aggregate(paths: list[Path]) -> dict:
    if not paths:
        raise CensusError("at least one proof report is required")

    per_format = {
        str(i): {
            "format": i,
            "name": None,
            "uvCount": None,
            "normalCount": None,
            "vd1Stride": None,
            "vd1Fields": None,
            "observed": False,
            "retailByteProven": False,
            "maps": [],
            "groupCount": 0,
            "surfaceCount": 0,
            "vertexCount": 0,
        }
        for i in ALL_FORMATS
    }
    maps = []
    total_groups = total_surfaces = total_vertices = 0

    for path in paths:
        doc = load_report(path)
        map_name = doc.get("map") or path.stem
        observed = {int(k): int(v) for k, v in doc.get("observedFormatGroupCounts", {}).items()}
        group_rows = defaultdict(lambda: {"surfaces": 0, "vertices": 0})
        for row in doc.get("groups", []):
            fmt = int(row["worldVertFormat"])
            group_rows[fmt]["surfaces"] += int(row.get("surfaceCount", 0))
            group_rows[fmt]["vertices"] += int(row.get("vertexCount", 0))

        map_entry = {
            "map": map_name,
            "sourceReport": str(path),
            "surfaceCount": int(doc.get("surfaceCount", 0)),
            "uniqueVertexGroups": int(doc.get("uniqueVertexGroups", 0)),
            "vd0Bytes": int(doc.get("vd0Bytes", 0)),
            "vd1Bytes": int(doc.get("vd1Bytes", 0)),
            "observedFormats": sorted(observed),
            "observedFormatGroupCounts": {str(k): v for k, v in sorted(observed.items())},
        }
        maps.append(map_entry)
        total_groups += map_entry["uniqueVertexGroups"]
        total_surfaces += map_entry["surfaceCount"]

        table = doc.get("formatTable", {})
        for i in ALL_FORMATS:
            key = str(i)
            if key in table:
                spec = table[key]
                dst = per_format[key]
                values = {
                    "name": spec.get("name"),
                    "uvCount": spec.get("uvCount"),
                    "normalCount": spec.get("normalCount"),
                    "vd1Stride": spec.get("vd1Stride"),
                    "vd1Fields": spec.get("vd1Fields"),
                }
                for field, value in values.items():
                    if dst[field] is None:
                        dst[field] = value
                    elif dst[field] != value:
                        raise CensusError(
                            f"format {i}: inconsistent {field}: {dst[field]!r} vs {value!r} in {path}"
                        )

        for fmt, groups in observed.items():
            if fmt not in ALL_FORMATS:
                raise CensusError(f"{path}: invalid worldVertFormat {fmt}")
            dst = per_format[str(fmt)]
            dst["observed"] = True
            dst["retailByteProven"] = True
            dst["maps"].append(map_name)
            dst["groupCount"] += groups
            dst["surfaceCount"] += group_rows[fmt]["surfaces"]
            dst["vertexCount"] += group_rows[fmt]["vertices"]
            total_vertices += group_rows[fmt]["vertices"]

    proven = [i for i in ALL_FORMATS if per_format[str(i)]["retailByteProven"]]
    missing = [i for i in ALL_FORMATS if not per_format[str(i)]["retailByteProven"]]

    return {
        "format": "t6-world-vertex-format-census-v1",
        "inputProofCount": len(paths),
        "maps": maps,
        "totals": {
            "surfaceRecords": total_surfaces,
            "uniqueVertexGroups": total_groups,
            "verticesAcrossGroups": total_vertices,
        },
        "coverage": {
            "formatCount": len(list(ALL_FORMATS)),
            "retailByteProvenCount": len(proven),
            "retailByteProvenFormats": proven,
            "pendingRetailProofCount": len(missing),
            "pendingRetailProofFormats": missing,
            "allFormatsRetailByteProven": not missing,
        },
        "formats": per_format,
        "policy": {
            "retailByteProvenRequiresObservedFixture": True,
            "formulaOnlyDoesNotCountAsProven": True,
            "badGroupReportsRejected": True,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("proofs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    census = aggregate(args.proofs)
    args.out.write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(args.out),
        "proofs": census["inputProofCount"],
        "maps": len(census["maps"]),
        "proven": census["coverage"]["retailByteProvenFormats"],
        "pending": census["coverage"]["pendingRetailProofFormats"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
