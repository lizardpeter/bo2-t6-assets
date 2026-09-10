#!/usr/bin/env python3
"""Classify exact T6 generated-Material texture tables against component tables.

This is a diagnostic/proof tool, not a reconstruction heuristic.  The generated
Material's own OAT textures[] array remains authoritative.  Component arrays are
compared only to learn which relations are actually present in retail data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from t6_layered_material_name_v1 import LayeredMaterialError, parse_layered_material_name

FORMAT = "t6-generated-material-texture-table-relation-v1"


class RelationError(RuntimeError):
    pass


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def storage_identity(name: str) -> str:
    if not name.startswith("*"):
        return name
    s = name.replace("*", "_")
    p = s.find("(")
    if p >= 0:
        s = s[:p]
    return f"generated/{s}"


def load_json(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RelationError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(d, dict):
        raise RelationError(f"{path}: root is not an object")
    return d


def textures(doc: dict, identity: str) -> list[dict]:
    rows = doc.get("textures", [])
    if not isinstance(rows, list):
        raise RelationError(f"{identity!r}: textures is not a list")
    if any(not isinstance(x, dict) for x in rows):
        raise RelationError(f"{identity!r}: non-object texture entry")
    return rows


def compact(row: dict) -> dict:
    return {
        k: row.get(k)
        for k in ("name", "nameHash", "nameStart", "nameEnd", "semantic", "image", "samplerState")
        if k in row
    }


def stable_dedupe(rows: list[dict], *, keep_last: bool) -> list[dict]:
    # Exact full-record identity only.  This does not infer runtime texture keys.
    if keep_last:
        seen = set()
        out_rev = []
        for row in reversed(rows):
            h = sha(row)
            if h not in seen:
                seen.add(h)
                out_rev.append(row)
        return list(reversed(out_rev))
    seen = set()
    out = []
    for row in rows:
        h = sha(row)
        if h not in seen:
            seen.add(h)
            out.append(row)
    return out


def first_difference(a: list[dict], b: list[dict]) -> int | None:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else n


def build(catalog: dict, root: Path) -> dict:
    mats = catalog.get("materials")
    if not isinstance(mats, list) or not mats:
        raise RelationError("catalog lacks materials[]")

    rows = []
    counts = Counter()
    for ordinal, cat in enumerate(mats):
        name = str(cat.get("name") or "")
        if not name.startswith("*"):
            continue
        try:
            parsed = parse_layered_material_name(name)
        except LayeredMaterialError as exc:
            raise RelationError(f"{name!r}: {exc}") from exc

        gid = storage_identity(name)
        gp = root / f"{gid}.json"
        if not gp.is_file():
            raise RelationError(f"{name!r}: missing generated dump {gp}")
        gd = load_json(gp)
        gr = textures(gd, gid)

        component_rows: list[dict] = []
        component_info = []
        all_available = True
        for layer in parsed["layers"]:
            cid = str(layer["componentMaterial"])
            cp = root / f"{cid}.json"
            if not cp.is_file():
                all_available = False
                component_info.append({
                    "layerIndex": int(layer["layerIndex"]),
                    "identity": cid,
                    "available": False,
                })
                continue
            cd = load_json(cp)
            cr = textures(cd, cid)
            component_rows.extend(cr)
            component_info.append({
                "layerIndex": int(layer["layerIndex"]),
                "identity": cid,
                "available": True,
                "textureCount": len(cr),
                "texturesSha256": sha(cr),
            })

        relation = "components-incomplete"
        details: dict = {}
        if all_available:
            ghashes = [sha(x) for x in gr]
            chashes = [sha(x) for x in component_rows]
            if gr == component_rows:
                relation = "exact-concatenation"
            elif Counter(ghashes) == Counter(chashes):
                relation = "same-full-record-multiset-different-order"
            elif gr == stable_dedupe(component_rows, keep_last=False):
                relation = "exact-full-record-dedupe-first"
            elif gr == stable_dedupe(component_rows, keep_last=True):
                relation = "exact-full-record-dedupe-last"
            else:
                relation = "structurally-different"
                i = first_difference(gr, component_rows)
                details = {
                    "firstConcatDifferenceIndex": i,
                    "generatedAtDifference": None if i is None or i >= len(gr) else compact(gr[i]),
                    "concatAtDifference": None if i is None or i >= len(component_rows) else compact(component_rows[i]),
                    "generatedSequence": [compact(x) for x in gr],
                    "componentConcatSequence": [compact(x) for x in component_rows],
                }
        counts[relation] += 1
        rows.append({
            "catalogOrdinal": ordinal,
            "material": name,
            "generatedStorageIdentity": gid,
            "generatedTextureCount": len(gr),
            "generatedTexturesSha256": sha(gr),
            "allStandaloneComponentsAvailable": all_available,
            "componentConcatTextureCount": len(component_rows),
            "componentConcatTexturesSha256": sha(component_rows),
            "relation": relation,
            "components": component_info,
            **details,
        })

    if len(rows) != 120:
        raise RelationError(f"expected 120 generated Nuketown Materials, got {len(rows)}")
    return {
        "format": FORMAT,
        "map": "mp_nuketown_2020",
        "generatedMaterialCount": len(rows),
        "relationCounts": dict(sorted(counts.items())),
        "materials": rows,
        "proofBoundary": (
            "The generated Material's own exact OAT textures[] table is authoritative. "
            "Relations to standalone component tables are observations only; no inferred "
            "component boundary, merge key, precedence, or substitution is promoted."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--material-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(load_json(args.catalog), args.material_root)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "out": str(args.out),
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "generatedMaterialCount": doc["generatedMaterialCount"],
        "relationCounts": doc["relationCounts"],
    }, sort_keys=True))
    for row in doc["materials"]:
        if row["relation"] == "structurally-different":
            print("GENERATED_TEXTURE_RELATION_DIFFERENCE " + json.dumps({
                "material": row["material"],
                "generatedTextureCount": row["generatedTextureCount"],
                "componentConcatTextureCount": row["componentConcatTextureCount"],
                "firstConcatDifferenceIndex": row.get("firstConcatDifferenceIndex"),
                "generatedAtDifference": row.get("generatedAtDifference"),
                "concatAtDifference": row.get("concatAtDifference"),
            }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
