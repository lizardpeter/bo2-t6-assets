#!/usr/bin/env python3
"""Build a fail-closed union of exact OAT Material JSON roots.

This is intentionally not an XAsset precedence resolver. For each relative
Material identity across supplied roots:

- one physical owner -> admit it;
- multiple owners with byte-identical JSON -> admit one and record all owners;
- multiple owners with byte-different JSON -> reject that identity unless it is
  not selected by a caller-specific allow list (future extension).

The current v1 rejects every divergent duplicate globally. That is stronger than
needed for some maps, but prevents silently inventing retail client override
precedence while still allowing dependency-owned generated components to be
reconstructed exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

FORMAT = "t6-oat-material-root-union-v1"


class UnionError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def index_root(label: str, root: Path) -> dict[str, dict]:
    if not root.is_dir():
        raise UnionError(f"root {label!r} is not a directory: {root}")
    out = {}
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise UnionError(f"{label}:{rel}: invalid JSON: {exc}") from exc
        if doc.get("_game") != "t6" or doc.get("_type") != "material":
            continue
        if rel in out:
            raise UnionError(f"{label}: duplicate relative Material path {rel!r}")
        out[rel] = {
            "label": label,
            "path": path,
            "relative": rel,
            "bytes": len(raw),
            "sha256": sha256(raw),
            "raw": raw,
        }
    return out


def build(roots: list[tuple[str, Path]], out_root: Path) -> dict:
    if not roots:
        raise UnionError("no Material roots supplied")
    indexed = {label: index_root(label, root) for label, root in roots}
    by_rel: dict[str, list[dict]] = defaultdict(list)
    for label in sorted(indexed):
        for rel, row in indexed[label].items():
            by_rel[rel].append(row)

    divergent = []
    rows = []
    out_root.mkdir(parents=True, exist_ok=True)
    admitted = 0
    byte_identical_duplicate_count = 0
    for rel in sorted(by_rel):
        copies = by_rel[rel]
        shas = {row["sha256"] for row in copies}
        owners = [row["label"] for row in copies]
        if len(shas) != 1:
            divergent.append({
                "relative": rel,
                "owners": owners,
                "copies": [
                    {"owner": row["label"], "bytes": row["bytes"], "sha256": row["sha256"]}
                    for row in copies
                ],
            })
            continue
        selected = copies[0]
        dst = out_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(selected["raw"])
        if dst.read_bytes() != selected["raw"]:
            raise UnionError(f"write/readback mismatch for {rel}")
        admitted += 1
        if len(copies) > 1:
            byte_identical_duplicate_count += 1
        rows.append({
            "relative": rel,
            "owners": owners,
            "ownerCount": len(copies),
            "bytes": selected["bytes"],
            "sha256": selected["sha256"],
            "byteIdenticalAcrossOwners": len(shas) == 1,
        })

    summary = {
        "rootCount": len(roots),
        "physicalMaterialJsonCount": sum(len(x) for x in indexed.values()),
        "uniqueRelativeMaterialIdentityCount": len(by_rel),
        "admittedMaterialIdentityCount": admitted,
        "singleOwnerIdentityCount": sum(1 for x in by_rel.values() if len(x) == 1),
        "multipleOwnerIdentityCount": sum(1 for x in by_rel.values() if len(x) > 1),
        "byteIdenticalMultipleOwnerIdentityCount": byte_identical_duplicate_count,
        "divergentMultipleOwnerIdentityCount": len(divergent),
    }
    doc = {
        "format": FORMAT,
        "summary": summary,
        "roots": [
            {"label": label, "path": str(root), "materialJsonCount": len(indexed[label])}
            for label, root in roots
        ],
        "materials": rows,
        "divergent": divergent,
        "proofBoundary": (
            "No runtime owner priority is inferred. A relative Material identity is admitted only when it has one physical owner or every supplied owner is byte-identical. Any byte-divergent duplicate is a hard blocker."
        ),
    }
    if divergent:
        first = divergent[0]
        raise UnionError(
            f"{len(divergent)} byte-divergent duplicate Material identities; first={first['relative']!r} owners={first['owners']}"
        )
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", required=True, help="LABEL=PATH")
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    args = ap.parse_args()
    roots = []
    labels = set()
    for spec in args.root:
        if "=" not in spec:
            raise UnionError(f"invalid --root {spec!r}; expected LABEL=PATH")
        label, raw_path = spec.split("=", 1)
        if not label or label in labels:
            raise UnionError(f"empty/duplicate root label {label!r}")
        labels.add(label)
        roots.append((label, Path(raw_path)))

    try:
        doc = build(roots, args.out_root)
    except UnionError:
        # A divergent union is intentionally not emitted as a usable root.
        if args.out_root.exists():
            shutil.rmtree(args.out_root)
        raise
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_bytes(payload)
    print(json.dumps({"manifest": str(args.manifest), "bytes": len(payload), "sha256": sha256(payload), **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
