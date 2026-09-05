#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import struct
import urllib.error
import urllib.request
import zlib
from collections import defaultdict
from pathlib import Path

EXPECTED_REMAINDER_BINDINGS = 37
EXPECTED_REMAINDER_IMAGES = 28


def zjson(path: Path) -> dict:
    return json.loads(zlib.decompress(base64.b64decode(path.read_text().strip())))


def range_get(url: str, start: int, end: int) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "bo2-t6-assets-ipak-census/1"})
    with urllib.request.urlopen(req, timeout=60) as response:
        if response.status != 206:
            raise RuntimeError(f"range not honored: HTTP {response.status}")
        data = response.read()
        content_range = response.headers.get("Content-Range", "")
    if len(data) != end - start + 1:
        raise RuntimeError(f"range length mismatch: {content_range}")
    return data, content_range


def parse_source(spec: str) -> tuple[str, str, int | None]:
    parts = spec.split("|", 2)
    if len(parts) not in (2, 3):
        raise ValueError("--source must be label|url[|expectedBytes]")
    expected = int(parts[2], 0) if len(parts) == 3 and parts[2] else None
    return parts[0], parts[1], expected


def read_index(url: str, expected_bytes: int | None) -> dict:
    head, head_range = range_get(url, 0, 65535)
    magic, version, total, section_count = struct.unpack_from("<4sIII", head, 0)
    if magic != b"KAPI" or version != 0x50000:
        raise ValueError(f"invalid T6 IPAK header: magic={magic!r} version={version:#x}")
    if expected_bytes is not None and total != expected_bytes:
        raise ValueError(f"IPAK byte count {total} != expected {expected_bytes}")
    sections = [struct.unpack_from("<IIII", head, 16 + 16 * i) for i in range(section_count)]
    index_sections = [s for s in sections if s[0] == 1]
    data_sections = [s for s in sections if s[0] == 2]
    if len(index_sections) != 1 or len(data_sections) != 1:
        raise ValueError("expected one index and one data section")
    _, offset, size, count = index_sections[0]
    if count * 16 > size:
        raise ValueError("index entry count exceeds section size")
    raw, index_range = range_get(url, offset, offset + count * 16 - 1)
    entries = [struct.unpack_from("<IIII", raw, i * 16) for i in range(count)]
    return {
        "bytes": total,
        "sectionCount": section_count,
        "indexEntryCount": count,
        "indexOffset": offset,
        "indexSectionBytes": size,
        "headContentRange": head_range,
        "indexContentRange": index_range,
        "networkBytes": len(head) + len(raw),
        "entries": entries,
    }


def build(role_plan_path: Path, sources: list[str], out_path: Path) -> dict:
    role = zjson(role_plan_path) if role_plan_path.name.endswith(".zlib.b64") else json.loads(role_plan_path.read_text())
    bindings = [r for r in role.get("bindings", []) if not r.get("baseIpakExact43")]
    if len(bindings) != EXPECTED_REMAINDER_BINDINGS:
        raise ValueError(f"remaining binding count {len(bindings)} != {EXPECTED_REMAINDER_BINDINGS}")
    by_image: dict[str, dict] = {}
    for row in bindings:
        name = row["image"]
        identity = {
            "image": name,
            "nameHash": int(row["aliasHash"]),
            "dataHash": int(row["aliasDataHash"]),
            "rawSemantic": int(row["rawSemantic"]),
            "roles": sorted({r["gltfRole"] for r in bindings if r["image"] == name}),
            "materials": sorted({r["material"] for r in bindings if r["image"] == name}),
        }
        prior = by_image.get(name)
        if prior is not None and (prior["nameHash"], prior["dataHash"]) != (identity["nameHash"], identity["dataHash"]):
            raise ValueError(f"conflicting identity for {name}")
        by_image[name] = identity
    if len(by_image) != EXPECTED_REMAINDER_IMAGES:
        raise ValueError(f"remaining unique image count {len(by_image)} != {EXPECTED_REMAINDER_IMAGES}")

    source_reports = []
    exact_sources_by_image: dict[str, list[str]] = defaultdict(list)
    for raw_spec in sources:
        label, url, expected = parse_source(raw_spec)
        record = {"label": label, "url": url, "expectedBytes": expected}
        try:
            index = read_index(url, expected)
            entries = index.pop("entries")
            by_name: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
            by_data: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
            by_pair: dict[tuple[int, int], list[tuple[int, int, int, int]]] = defaultdict(list)
            for e in entries:
                data_hash, name_hash, rel, raw_size = e
                by_name[name_hash].append(e)
                by_data[data_hash].append(e)
                by_pair[(name_hash, data_hash)].append(e)
            rows = []
            exact_count = name_only_count = data_only_count = 0
            for name in sorted(by_image):
                ident = by_image[name]
                nh, dh = ident["nameHash"], ident["dataHash"]
                exact = by_pair.get((nh, dh), [])
                name_hits = by_name.get(nh, [])
                data_hits = by_data.get(dh, [])
                state = "absent"
                if exact:
                    state = "exact-pair"
                    exact_count += 1
                    exact_sources_by_image[name].append(label)
                elif name_hits:
                    state = "name-hash-only"
                    name_only_count += 1
                elif data_hits:
                    state = "data-hash-only"
                    data_only_count += 1
                rows.append({
                    **ident,
                    "state": state,
                    "exactPairCount": len(exact),
                    "nameHashEntryCount": len(name_hits),
                    "nameHashAvailableDataHashes": sorted({int(e[0]) for e in name_hits}),
                    "dataHashEntryCount": len(data_hits),
                    "dataHashAvailableNameHashes": sorted({int(e[1]) for e in data_hits}),
                    "exactEntries": [list(e) for e in exact],
                })
            record.update({
                "status": "scanned",
                **index,
                "exactPairCount": exact_count,
                "nameHashOnlyCount": name_only_count,
                "dataHashOnlyCount": data_only_count,
                "rows": rows,
            })
        except Exception as exc:
            record.update({"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"})
        source_reports.append(record)

    identity_rows = []
    for name in sorted(by_image):
        identity_rows.append({**by_image[name], "exactSources": sorted(exact_sources_by_image.get(name, []))})
    report = {
        "format": "t6-nuketown-remaining-alias-remote-ipak-census-v1",
        "rolePlan": role_plan_path.name,
        "remainingBindingCount": len(bindings),
        "remainingUniqueImageCount": len(by_image),
        "identities": identity_rows,
        "sources": source_reports,
        "summary": {
            "sourceCount": len(source_reports),
            "scannedSourceCount": sum(r["status"] == "scanned" for r in source_reports),
            "unavailableSourceCount": sum(r["status"] != "scanned" for r in source_reports),
            "imagesWithExactPairInAnySource": sum(bool(r["exactSources"]) for r in identity_rows),
            "imagesStillWithoutExactPair": sum(not r["exactSources"] for r in identity_rows),
        },
        "proofBoundary": "Index-only census. Exact availability requires the current role-plan image nameHash and dataHash to occur together in one IPAK index entry. Name-only and data-only hits are reported but never promoted.",
    }
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role-plan", type=Path, required=True)
    ap.add_argument("--source", action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = build(args.role_plan, args.source, args.out)
    print(json.dumps(report["summary"], indent=2))
    for source in report["sources"]:
        print(json.dumps({k: source.get(k) for k in ("label", "status", "bytes", "indexEntryCount", "exactPairCount", "nameHashOnlyCount", "dataHashOnlyCount", "error") if k in source}, indent=2))
    for row in report["identities"]:
        if row["exactSources"]:
            print("EXACT", row["image"], row["exactSources"])


if __name__ == "__main__":
    main()
