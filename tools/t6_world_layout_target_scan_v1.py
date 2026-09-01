#!/usr/bin/env python3
"""Conservatively scan standalone T6 world-layout audit JSON for observed formats.

This stage is intentionally schema-tolerant but proof-strict. It may inspect an
unknown/revisioned standalone `*.layout.json`, yet it only promotes a
`worldVertFormat` when the value is attached to strong observation evidence:

- explicit observed-format arrays/maps (for example `observedFormats` or
  `observedFormatGroupCounts`); or
- a surface/group-like object containing `worldVertFormat` plus serialized
  geometry evidence such as surface/group index, vertex count, or vertex-data
  offsets.

Reference/enum/format tables may be reported as weak candidates but can never
trigger a target hit. This prevents a table listing formats 0..8 from being
mistaken for retail observation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TARGET_DEFAULT = {4, 5, 7, 8}
VALID_FORMATS = set(range(9))

EXPLICIT_OBSERVED_ARRAY_KEYS = {
    "observedFormats",
    "observedWorldVertFormats",
    "observedWorldVertexFormats",
    "worldVertFormatsObserved",
    "worldVertexFormatsObserved",
}
EXPLICIT_OBSERVED_MAP_KEYS = {
    "observedFormatCounts",
    "observedFormatGroupCounts",
    "observedWorldVertFormatCounts",
    "worldVertFormatCounts",
}

SURFACE_GROUP_EVIDENCE_KEYS = {
    "surfaceIndex",
    "surfaceIndices",
    "surfaceCount",
    "groupIndex",
    "vertexCount",
    "vertexDataOffset0",
    "vertexDataOffset1",
    "vd0Offset",
    "vd1Offset",
    "firstVertex",
    "firstIndex",
    "baseIndex",
    "triCount",
}

REFERENCE_PATH_TOKENS = {
    "formattable",
    "formats",
    "knownformats",
    "enum",
    "enums",
    "reference",
    "references",
    "worldvertexformats",
    "worldvertformats",
}


class LayoutScanError(RuntimeError):
    pass


def _json_path(parts: tuple[str, ...]) -> str:
    if not parts:
        return "$"
    out = "$"
    for part in parts:
        if part.startswith("["):
            out += part
        else:
            out += "." + part
    return out


def _format_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result in VALID_FORMATS else None


def _path_is_reference(path: tuple[str, ...]) -> bool:
    for token in path:
        normalized = token.lower().replace("_", "").replace("-", "")
        if normalized in REFERENCE_PATH_TOKENS:
            return True
    return False


def _surface_group_record(obj: dict[str, Any]) -> bool:
    if "worldVertFormat" not in obj:
        return False
    return bool(SURFACE_GROUP_EVIDENCE_KEYS.intersection(obj.keys()))


def _add_evidence(
    evidence: list[dict],
    *,
    fmt: int,
    confidence: str,
    kind: str,
    path: tuple[str, ...],
    detail: dict | None = None,
) -> None:
    evidence.append(
        {
            "worldVertFormat": fmt,
            "confidence": confidence,
            "kind": kind,
            "path": _json_path(path),
            "detail": detail or {},
        }
    )


def scan_document(document: Any, *, source: str, target_formats: set[int]) -> dict:
    strong: list[dict] = []
    weak: list[dict] = []

    def walk(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key in EXPLICIT_OBSERVED_ARRAY_KEYS:
                values = node.get(key)
                if isinstance(values, list):
                    for i, value in enumerate(values):
                        fmt = _format_int(value)
                        if fmt is not None:
                            _add_evidence(
                                strong,
                                fmt=fmt,
                                confidence="strong",
                                kind="explicit-observed-array",
                                path=path + (key, f"[{i}]"),
                            )

            for key in EXPLICIT_OBSERVED_MAP_KEYS:
                values = node.get(key)
                if isinstance(values, dict):
                    for raw_fmt, count in values.items():
                        fmt = _format_int(raw_fmt)
                        try:
                            observed_count = int(count)
                        except (TypeError, ValueError):
                            observed_count = 0
                        if fmt is not None and observed_count > 0:
                            _add_evidence(
                                strong,
                                fmt=fmt,
                                confidence="strong",
                                kind="explicit-observed-count",
                                path=path + (key, str(raw_fmt)),
                                detail={"count": observed_count},
                            )

            if _surface_group_record(node):
                fmt = _format_int(node.get("worldVertFormat"))
                if fmt is not None:
                    evidence_keys = sorted(
                        SURFACE_GROUP_EVIDENCE_KEYS.intersection(node.keys())
                    )
                    target = weak if _path_is_reference(path) else strong
                    _add_evidence(
                        target,
                        fmt=fmt,
                        confidence=("weak" if target is weak else "strong"),
                        kind="surface-or-group-record",
                        path=path + ("worldVertFormat",),
                        detail={"evidenceKeys": evidence_keys},
                    )
            elif "worldVertFormat" in node:
                fmt = _format_int(node.get("worldVertFormat"))
                if fmt is not None:
                    _add_evidence(
                        weak,
                        fmt=fmt,
                        confidence="weak",
                        kind="unqualified-worldVertFormat",
                        path=path + ("worldVertFormat",),
                        detail={"parentKeys": sorted(node.keys())[:32]},
                    )

            for key, value in node.items():
                walk(value, path + (str(key),))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + (f"[{index}]",))

    walk(document, ())

    observed = sorted({int(row["worldVertFormat"]) for row in strong})
    target_hits = sorted(set(observed).intersection(target_formats))
    weak_only = sorted(
        {int(row["worldVertFormat"]) for row in weak}.difference(observed)
    )
    return {
        "source": source,
        "observedFormats": observed,
        "targetHits": target_hits,
        "strongEvidenceCount": len(strong),
        "weakCandidateCount": len(weak),
        "weakOnlyFormats": weak_only,
        "strongEvidence": strong,
        "weakCandidates": weak,
    }


def _candidate_files(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in inputs:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.layout.json")))
        else:
            raise LayoutScanError(f"input does not exist: {path}")
    unique: dict[str, Path] = {}
    for path in files:
        unique[str(path.resolve())] = path
    return [unique[key] for key in sorted(unique)]


def scan_files(
    inputs: list[Path],
    *,
    target_formats: set[int] | None = None,
    map_name: str | None = None,
) -> dict:
    target_formats = set(target_formats or TARGET_DEFAULT)
    if not target_formats or not target_formats.issubset(VALID_FORMATS):
        raise LayoutScanError(
            f"target formats must be a non-empty subset of 0..8: {sorted(target_formats)}"
        )

    files = _candidate_files(inputs)
    if not files:
        raise LayoutScanError("no layout JSON files found")

    reports: list[dict] = []
    parse_errors: list[dict] = []
    for path in files:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            parse_errors.append({"file": str(path), "error": str(exc)})
            continue

        declared_map = None
        if isinstance(document, dict):
            for key in ("map", "mapName", "worldName", "zone"):
                value = document.get(key)
                if isinstance(value, str) and value:
                    declared_map = value
                    break
        if map_name:
            lower = map_name.lower()
            path_match = lower in str(path).lower()
            declared_match = declared_map is not None and lower in declared_map.lower()
            if not path_match and not declared_match:
                continue

        report = scan_document(
            document,
            source=str(path),
            target_formats=target_formats,
        )
        report["declaredMap"] = declared_map
        reports.append(report)

    observed = sorted(
        {
            fmt
            for report in reports
            for fmt in report["observedFormats"]
        }
    )
    hits = sorted(set(observed).intersection(target_formats))
    return {
        "format": "t6-world-layout-target-scan-v1",
        "mapFilter": map_name,
        "targetFormats": sorted(target_formats),
        "inputPathCount": len(inputs),
        "candidateLayoutFileCount": len(files),
        "matchedLayoutFileCount": len(reports),
        "parseErrorCount": len(parse_errors),
        "parseErrors": parse_errors,
        "observedFormats": observed,
        "targetHits": hits,
        "targetHit": bool(hits),
        "reports": reports,
        "proofBoundary": (
            "Only explicit observed-format fields or surface/group records with "
            "serialized geometry evidence promote a format. Reference tables and "
            "unqualified worldVertFormat values cannot trigger a target hit."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--map", dest="map_name")
    parser.add_argument(
        "--target-format", action="append", type=int, dest="target_formats"
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    doc = scan_files(
        args.inputs,
        target_formats=(set(args.target_formats) if args.target_formats else None),
        map_name=args.map_name,
    )
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "observedFormats": doc["observedFormats"],
                    "targetHits": doc["targetHits"],
                    "matchedLayoutFileCount": doc["matchedLayoutFileCount"],
                },
                indent=2,
            )
        )
    else:
        print(payload, end="")

    if doc["parseErrorCount"]:
        return 3
    if doc["matchedLayoutFileCount"] == 0:
        return 2
    return 0 if doc["targetHit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
