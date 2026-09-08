#!/usr/bin/env python3
"""Report exact physical native OAT Material conflicts without selecting a winner.

This is diagnostic evidence for the retail-client duplicate-owner gate. It never
promotes root order, patch naming, server behavior, or byte size into precedence.
It does, however, prove whether the parsed native texture role table is invariant
across every physical copy in the supplied root universe. That lets downstream
material-role work advance only when the role data itself is independent of the
still-unresolved active XAsset owner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-seal6-native-material-conflict-report-v1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("root must be LABEL=PATH")
    label, raw = value.split("=", 1)
    path = Path(raw).resolve()
    if not label.strip() or not path.is_dir():
        raise argparse.ArgumentTypeError(f"invalid root {value!r}")
    return label.strip(), path


def _load(path: Path, target: str) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise RuntimeError(f"{target}: invalid JSON {path}: {exc}") from exc
    if doc.get("_game") != "t6" or doc.get("_type") != "material":
        raise RuntimeError(f"{target}: not native T6 Material JSON: {path}")
    if not isinstance(doc.get("textures"), list):
        raise RuntimeError(f"{target}: textures[] missing: {path}")
    return raw, doc


def _role_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for i, tex in enumerate(doc.get("textures", [])):
        if not isinstance(tex, dict):
            raise RuntimeError(f"texture {i} is not an object")
        rows.append({
            "index": i,
            "semantic": tex.get("semantic"),
            "name": tex.get("name"),
            "image": tex.get("image"),
            "samplerState": tex.get("samplerState"),
            "isMatureContent": tex.get("isMatureContent"),
            "nativeRecord": tex,
        })
    return rows


def _top_level_diff_keys(docs: list[dict[str, Any]]) -> list[str]:
    keys = sorted({k for doc in docs for k in doc})
    different = []
    for key in keys:
        vals = [_canon(doc.get(key)) for doc in docs]
        if len(set(vals)) != 1:
            different.append(key)
    return different


def build(roots: list[tuple[str, Path]], targets: list[str]) -> dict[str, Any]:
    if not roots or not targets:
        raise RuntimeError("roots and targets must be non-empty")
    materials = []
    for target in targets:
        rel = Path("materials") / f"{target}.json"
        copies = []
        docs = []
        raws = []
        for label, root in roots:
            path = root / rel
            if not path.is_file():
                continue
            raw, doc = _load(path, target)
            roles = _role_rows(doc)
            copies.append({
                "rootLabel": label,
                "root": str(root),
                "relativeFile": rel.as_posix(),
                "bytes": len(raw),
                "sha256": _sha(raw),
                "techniqueSet": doc.get("techniqueSet"),
                "textureCount": len(roles),
                "textureArrayStructuralSha256": _sha(_canon(doc.get("textures"))),
                "textureRoleRows": roles,
                "nativeMaterialRecord": doc,
            })
            docs.append(doc)
            raws.append(raw)
        if not copies:
            raise RuntimeError(f"{target}: no physical native Material record")
        texture_hashes = {row["textureArrayStructuralSha256"] for row in copies}
        techsets = {str(row.get("techniqueSet")) for row in copies}
        byte_ids = {(row["bytes"], row["sha256"]) for row in copies}
        materials.append({
            "material": target,
            "physicalCopyCount": len(copies),
            "byteIdenticalAcrossCopies": len(byte_ids) == 1,
            "techniqueSetIdenticalAcrossCopies": len(techsets) == 1,
            "textureRecordsStructurallyIdenticalAcrossCopies": len(texture_hashes) == 1,
            "topLevelFieldsDifferingAcrossCopies": _top_level_diff_keys(docs) if len(docs) > 1 else [],
            "copies": copies,
            "activeRetailClientOwner": None if len(byte_ids) > 1 else "payload-identical-no-winner-required",
            "activeRetailClientOwnerResolved": len(byte_ids) == 1,
        })
    return {
        "format": FORMAT,
        "roots": [{"label": label, "root": str(root)} for label, root in roots],
        "targets": targets,
        "summary": {
            "targetCount": len(materials),
            "physicalCopyCount": sum(m["physicalCopyCount"] for m in materials),
            "divergentBytePayloadTargetCount": sum(not m["byteIdenticalAcrossCopies"] for m in materials),
            "textureRoleInvariantTargetCount": sum(m["textureRecordsStructurallyIdenticalAcrossCopies"] for m in materials),
            "unresolvedRetailClientOwnerTargetCount": sum(not m["activeRetailClientOwnerResolved"] for m in materials),
        },
        "materials": materials,
        "proofBoundary": (
            "Every row is an exact native OAT Material JSON physically present in the explicitly supplied, SHA-pinned root universe. "
            "The report may prove parsed texture-array invariance across copies, but it does not select a divergent retail-client duplicate winner. "
            "Root order, patch naming, OpenBO2 lineage, and PC-server precedence are not owner authority."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", type=_parse_root, required=True, metavar="LABEL=PATH")
    ap.add_argument("--target", action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    result = build(a.root, a.target)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact = {
        "summary": result["summary"],
        "materials": [{
            "material": m["material"],
            "copies": [{
                "root": c["rootLabel"], "bytes": c["bytes"], "sha256": c["sha256"],
                "techniqueSet": c["techniqueSet"], "textureCount": c["textureCount"],
                "textureArrayStructuralSha256": c["textureArrayStructuralSha256"],
                "textures": [{"index": t["index"], "semantic": t["semantic"], "name": t["name"], "image": t["image"]} for t in c["textureRoleRows"]],
            } for c in m["copies"]],
            "byteIdentical": m["byteIdenticalAcrossCopies"],
            "techniqueSetIdentical": m["techniqueSetIdenticalAcrossCopies"],
            "textureRecordsStructurallyIdentical": m["textureRecordsStructurallyIdenticalAcrossCopies"],
            "topLevelFieldsDiffering": m["topLevelFieldsDifferingAcrossCopies"],
            "activeRetailClientOwnerResolved": m["activeRetailClientOwnerResolved"],
        } for m in result["materials"]],
    }
    print(json.dumps(compact, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
