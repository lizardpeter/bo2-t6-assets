#!/usr/bin/env python3
"""Build an exact local-vs-import T6 Material dependency graph.

Inputs are an expanded retail zone plus an independently proven Material handle
ledger.  The ledger proves Material identity and a retained serialized-record
start; it does not by itself prove that the record is a full local definition.

At every retained start this tool replays the source-closed 112-byte Material
serializer.  A record is classified as an external import stub only if it is a
strict zero body: texture/constant/state counts are zero, TechniqueSet/texture/
constant/state/thermal pointers are all null, and the exact inline serialized
name matches the proven Material identity.  Everything else must be a valid
local definition with a packed VIRTUAL TechniqueSet pointer.

A missing direct-inline start may be supplied by a retained full-player proof,
but its complete serialized interval is SHA-256 verified against current retail
bytes before use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_material_techset_top_level_walk_v1 import Cursor, parse_front


FORMAT = "t6-material-dependency-graph-v1"
OWNER_FORMAT = "t6-seal6-smg-material-handle-proof-v1"
FULL_FORMAT = "t6-seal6-smg-full-player-retail-proof-v1"


class GraphError(RuntimeError):
    pass


def canonical(name: str) -> str:
    return name[1:] if name.startswith(",") else name


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_name(node: dict[str, Any]) -> str:
    raw = node.get("name")
    if isinstance(raw, dict):
        raw = raw.get("value")
    if not isinstance(raw, str) or not raw:
        raise GraphError(f"Material parser did not recover exact inline name: {raw!r}")
    return raw


def parse_direct_start(row: dict[str, Any]) -> int:
    if isinstance(row.get("serializedStart"), int):
        return int(row["serializedStart"])
    raw = row.get("serializedStartHex")
    if isinstance(raw, str) and raw:
        return int(raw, 0)
    raise GraphError(f"direct-inline row lacks serialized start: {row.get('name')!r}")


def is_null_pointer(p: Any) -> bool:
    return isinstance(p, dict) and p.get("kind") == "null"


def strict_import_stub(node: dict[str, Any]) -> bool:
    return (
        int(node.get("textureCount", -1)) == 0
        and int(node.get("constantCount", -1)) == 0
        and int(node.get("stateBitsCount", -1)) == 0
        and is_null_pointer(node.get("techniqueSetPointer"))
        and not node.get("textures")
        and is_null_pointer(node.get("thermalPointer"))
    )


def parse_at(data: bytes, blocks: tuple[int, ...], start: int, expected_name: str) -> dict[str, Any]:
    if start < 0 or start + 112 > len(data):
        raise GraphError(f"{expected_name}: Material start out of range: {start}")
    c = Cursor(data, start, blocks)
    node = c.material()
    got = canonical(exact_name(node))
    expected = canonical(expected_name)
    if got != expected:
        raise GraphError(f"{expected}: serialized identity mismatch at {start}: {got!r}")
    return {
        "name": expected,
        "serializedName": exact_name(node),
        "start": start,
        "end": c.p,
        "serializedBytes": c.p - start,
        "serializedSha256": sha256(data[start:c.p]),
        "textureCount": int(node.get("textureCount", 0)),
        "constantCount": int(node.get("constantCount", 0)),
        "stateBitsCount": int(node.get("stateBitsCount", 0)),
        "techniqueSetPointer": node.get("techniqueSetPointer"),
        "thermalPointer": node.get("thermalPointer"),
        "node": node,
    }


def build(expanded: Path, owner_ledger: Path, direct_proof: Path | None, zone: str) -> dict[str, Any]:
    data = expanded.read_bytes()
    blocks, _assets, _body = parse_front(data)
    ledger = json.loads(owner_ledger.read_text(encoding="utf-8-sig"))
    if ledger.get("format") != OWNER_FORMAT:
        raise GraphError(f"expected {OWNER_FORMAT}, got {ledger.get('format')!r}")
    if (ledger.get("summary") or {}).get("targetAllHandlesExact") is not True:
        raise GraphError("Material handle ledger is not exact")
    src = ledger.get("source") or {}
    if int(src.get("expandedBytes", -1)) != len(data) or str(src.get("expandedSha256") or "").lower() != sha256(data):
        raise GraphError("Material handle ledger does not identify current expanded retail zone")

    target_names: list[str] = []
    for raw in ledger.get("surfaceMaterialSequence") or []:
        name = canonical(str(raw))
        if name and name not in target_names:
            target_names.append(name)

    starts: dict[str, dict[str, Any]] = {}
    for row in ledger.get("uniqueHandleOwners") or []:
        name = canonical(str(row.get("materialName") or ""))
        start = row.get("ownerMaterialRawStart")
        if not name or start is None:
            continue
        value = int(start)
        prev = starts.get(name)
        if prev is not None and int(prev["start"]) != value:
            raise GraphError(f"conflicting retained starts for {name}: {prev['start']} != {value}")
        starts[name] = {
            "start": value,
            "source": "exact-xmodel-material-handle-owner-ledger",
            "ownerEvidence": row.get("evidence"),
        }

    direct_rows: dict[str, dict[str, Any]] = {}
    if direct_proof is not None:
        full = json.loads(direct_proof.read_text(encoding="utf-8-sig"))
        if full.get("format") != FULL_FORMAT:
            raise GraphError(f"expected {FULL_FORMAT}, got {full.get('format')!r}")
        stream = full.get("expandedStream") or {}
        if int(stream.get("bytes", -1)) != len(data) or str(stream.get("sha256") or "").lower() != sha256(data):
            raise GraphError("direct-inline proof does not identify current expanded retail zone")
        for row in (full.get("bodyMaterials") or {}).get("directInline") or []:
            if isinstance(row, dict) and row.get("name"):
                direct_rows[canonical(str(row["name"]))] = row

    missing = [n for n in target_names if n not in starts]
    supplements: list[dict[str, Any]] = []
    for name in missing:
        row = direct_rows.get(name)
        if row is None:
            raise GraphError(f"{name}: no retained exact start and no direct-inline proof")
        start = parse_direct_start(row)
        size = int(row.get("serializedBytes", 0))
        expected_sha = str(row.get("serializedSha256") or "").lower()
        if size <= 0 or start < 0 or start + size > len(data) or len(expected_sha) != 64:
            raise GraphError(f"{name}: invalid retained direct-inline interval")
        actual = sha256(data[start:start + size])
        if actual != expected_sha:
            raise GraphError(f"{name}: direct-inline serialized SHA mismatch: {actual} != {expected_sha}")
        starts[name] = {"start": start, "source": "sha256-gated-direct-inline-interval"}
        supplements.append({"material": name, "start": start, "bytes": size, "sha256": expected_sha})

    if set(starts) != set(target_names):
        raise GraphError(f"start coverage mismatch: have={sorted(starts)} target={sorted(target_names)}")

    rows: list[dict[str, Any]] = []
    for name in target_names:
        proof = starts[name]
        parsed = parse_at(data, blocks, int(proof["start"]), name)
        stub = strict_import_stub(parsed["node"])
        tech = parsed["techniqueSetPointer"]
        if stub:
            classification = "import_stub"
        else:
            if not isinstance(tech, dict) or tech.get("kind") != "packed" or int(tech.get("block", -1)) != 5:
                raise GraphError(
                    f"{name}: non-stub Material lacks packed VIRTUAL TechniqueSet: {tech!r}"
                )
            classification = "local_definition"
        rows.append({
            "material": name,
            "classification": classification,
            "start": parsed["start"],
            "end": parsed["end"],
            "serializedBytes": parsed["serializedBytes"],
            "serializedSha256": parsed["serializedSha256"],
            "serializedName": parsed["serializedName"],
            "textureCount": parsed["textureCount"],
            "constantCount": parsed["constantCount"],
            "stateBitsCount": parsed["stateBitsCount"],
            "techniqueSetPointer": tech,
            "startEvidence": proof["source"],
        })

    local = [x for x in rows if x["classification"] == "local_definition"]
    imports = [x for x in rows if x["classification"] == "import_stub"]
    return {
        "format": FORMAT,
        "zone": zone,
        "source": {"expandedBytes": len(data), "expandedSha256": sha256(data)},
        "materials": rows,
        "directInlineSupplements": supplements,
        "summary": {
            "targetMaterials": len(rows),
            "localDefinitions": len(local),
            "importStubs": len(imports),
            "allTargetMaterialRecordsExact": len(rows) == len(target_names),
            "allImportStubsStrictZeroBody": all(x["textureCount"] == x["constantCount"] == x["stateBitsCount"] == 0 for x in imports),
        },
        "proofBoundary": (
            "Material identity/start originates in the exact XModel handle ledger or a complete SHA-256-gated direct-inline interval. "
            "The current retail bytes are replayed with the source-closed 112-byte Material serializer. Only an exact zero-count, "
            "all-null-child record is classified as an import stub; it is never promoted to a local definition."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("owner_ledger", type=Path)
    ap.add_argument("--direct-proof", type=Path)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = build(a.expanded, a.owner_ledger, a.direct_proof, a.zone)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
