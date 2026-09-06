#!/usr/bin/env python3
"""Catalog pinned OpenAssetTools T6 XModel dumps with retail provenance.

Pinned OAT emits one JSON descriptor at xmodel/<asset-name>.json plus one model
file per LOD.  The JSON's `type` is especially useful because OAT derives T6
`viewhands` from native structure, not from the filename:

  animated && HasNulledTrans(model) && HasNonNullBoneInfoTrans(model)

This adapter does not make OAT output magically authoritative on its own.  The
caller must provide the source zone identity and SHA-256 used for the dump.  The
catalog then hashes every descriptor and present LOD file so it can be joined to
raw-byte proofs and reproduced later.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

PINNED_OAT_COMMIT = "7d027e8f89118196713e955b0e11f8404149c54d"
SCHEMA = "http://openassettools.dev/schema/xmodel.v1.json"
VALID_TYPES = {"rigid", "animated", "viewhands"}
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def asset_name(xmodel_root: Path, path: Path) -> str:
    rel = path.relative_to(xmodel_root).as_posix()
    if not rel.endswith(".json"):
        raise ValueError(path)
    return rel[:-5]


def resolve_lod_path(dump_root: Path, descriptor: Path, raw: str) -> Path:
    p = Path(raw.replace("\\", "/"))
    if p.is_absolute():
        return p
    # OAT paths are asset-output-root relative (`model_export/...`).
    direct = dump_root / p
    if direct.exists():
        return direct
    # Retain a second deterministic interpretation for callers that point at a
    # nested zone output directory; never search by basename.
    return descriptor.parent.parent / p


def parse_descriptor(dump_root: Path, xmodel_root: Path, path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if doc.get("$schema") != SCHEMA:
        raise ValueError(f"{path}: unexpected xmodel schema {doc.get('$schema')!r}")
    if doc.get("_type") != "xmodel" or doc.get("_game") != "t6":
        raise ValueError(f"{path}: not a T6 xmodel descriptor")
    model_type = doc.get("type")
    if model_type is not None and model_type not in VALID_TYPES:
        raise ValueError(f"{path}: unknown model type {model_type!r}")
    lods = []
    for i, lod in enumerate(doc.get("lods", [])):
        if not isinstance(lod, dict) or not isinstance(lod.get("file"), str):
            raise ValueError(f"{path}: malformed lod[{i}]")
        file_path = resolve_lod_path(dump_root, path, lod["file"])
        present = file_path.is_file()
        lods.append({
            "index": i,
            "distance": lod.get("distance"),
            "declaredFile": lod["file"],
            "resolvedPath": str(file_path),
            "present": present,
            "bytes": file_path.stat().st_size if present else None,
            "sha256": sha256(file_path) if present else None,
        })
    return {
        "name": asset_name(xmodel_root, path),
        "type": model_type,
        "descriptorPath": str(path),
        "descriptorBytes": path.stat().st_size,
        "descriptorSha256": sha256(path),
        "rootBoneName": doc.get("rootBoneName"),
        "collLod": doc.get("collLod"),
        "physPreset": doc.get("physPreset"),
        "physConstraints": doc.get("physConstraints"),
        "flags": doc.get("flags"),
        "lightingOriginOffset": doc.get("lightingOriginOffset"),
        "lightingOriginRange": doc.get("lightingOriginRange"),
        "lods": lods,
        "allDeclaredLodFilesPresent": all(l["present"] for l in lods),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump-root", type=Path, required=True)
    ap.add_argument("--zone-name", required=True)
    ap.add_argument("--source-sha256", required=True, help="SHA-256 of the retail source/expanded stream used by OAT")
    ap.add_argument("--source-kind", default="retail-zone", choices=["retail-zone", "expanded-xfile", "retail-container"])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if not HEX64.fullmatch(args.source_sha256):
        raise ValueError("--source-sha256 must be exactly 64 hexadecimal characters")

    dump_root = args.dump_root.resolve()
    xmodel_root = dump_root / "xmodel"
    if not xmodel_root.is_dir():
        raise ValueError(f"missing OAT xmodel directory: {xmodel_root}")
    descriptors = sorted(xmodel_root.rglob("*.json"))
    models = [parse_descriptor(dump_root, xmodel_root, p) for p in descriptors]
    names = [m["name"] for m in models]
    if len(names) != len(set(names)):
        dupes = sorted(name for name, count in Counter(names).items() if count > 1)
        raise ValueError(f"duplicate OAT XModel identities: {dupes}")

    type_counts = Counter((m["type"] or "unspecified") for m in models)
    missing_lods = [m["name"] for m in models if not m["allDeclaredLodFilesPresent"]]
    viewhands = sorted(m["name"] for m in models if m["type"] == "viewhands")
    animated = sorted(m["name"] for m in models if m["type"] == "animated")

    out = {
        "format": "t6-oat-xmodel-catalog-v1",
        "source": {
            "zoneName": args.zone_name,
            "sourceKind": args.source_kind,
            "retailSourceSha256": args.source_sha256.lower(),
            "dumpRoot": str(dump_root),
        },
        "producer": {
            "repository": "Laupetin/OpenAssetTools",
            "commit": PINNED_OAT_COMMIT,
            "descriptorPathRule": "xmodel/<asset-name>.json",
            "lodPathRule": "model_export/<asset-name>_lodN.<configured-extension>",
            "viewhandsClassification": "animated && HasNulledTrans(model) && HasNonNullBoneInfoTrans(model)",
        },
        "summary": {
            "xmodelCount": len(models),
            "typeCounts": dict(sorted(type_counts.items())),
            "viewhandsCount": len(viewhands),
            "animatedCount": len(animated),
            "missingDeclaredLodFileCount": len(missing_lods),
            "missingDeclaredLodFilesFor": missing_lods,
        },
        "viewhands": viewhands,
        "animated": animated,
        "models": models,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0 if not missing_lods else 2


if __name__ == "__main__":
    raise SystemExit(main())
