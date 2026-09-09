#!/usr/bin/env python3
"""Recover copy-elided T6 layered component texture tables exactly (v3).

Retail Nuketown proves the T6 layered texture projection used here:
  * component texture rows are preserved field-for-field;
  * layer index 0 keeps the texture argument name;
  * layer indices 1..3 append the decimal layer index to the argument name;
  * the generated texture table is globally sorted by the resulting 32-bit
    Treyarch argument-name hash.

This tool first re-proves that projection against every source-complete generated
Material in the exact OAT root, then recovers only standalone-missing component
``textures[]`` arrays by exact multiset subtraction. Recovered candidates must
agree across every independent layer occurrence, and the final recovered universe
must reproduce every generated Material byte-equivalent at canonical JSON level.

It deliberately does not recover TechniqueSets, constants, render state, shader
math, ownership, or retail duplicate precedence for a missing standalone Material.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from t6_layered_material_name_v1 import LayeredMaterialError, parse_layered_material_name
from t6_oat_material_manifest_v2 import _has_real_normal_map, _index_oat_materials
from t6_oat_material_manifest_v6 import _storage_identity

FORMAT = "t6-oat-layered-component-texture-recovery-v3"
PRODUCER = "t6_oat_layered_component_texture_recovery_v3.py"
MOD = 1 << 32


class RecoveryError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _name_hash(name: str) -> int:
    h = 0
    for ch in name:
        h = (ord(ch) ^ (33 * h)) & 0xFFFFFFFF
    return h


def _row_hash(row: dict) -> int:
    name = row.get("name")
    if isinstance(name, str) and name:
        return _name_hash(name)
    h = row.get("nameHash")
    if isinstance(h, int) and 0 <= h < MOD:
        return h
    raise RecoveryError(f"texture row lacks usable argument identity: {row!r}")


def _textures(identity: str, source: dict) -> list[dict]:
    rows = source["doc"].get("textures", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RecoveryError(f"{identity!r}: textures[] is not a list of objects")
    return rows


def _suffix_row(source: dict, layer_index: int) -> dict:
    if not 0 <= layer_index <= 3:
        raise RecoveryError(f"layer index {layer_index} outside 0..3")
    row = copy.deepcopy(source)
    if layer_index:
        digit = str(layer_index)
        name = row.get("name")
        if isinstance(name, str) and name:
            row["name"] = name + digit
            if "nameHash" in row:
                row["nameHash"] = _name_hash(row["name"])
            if "nameEnd" in row:
                row["nameEnd"] = digit
        else:
            h = row.get("nameHash")
            if not isinstance(h, int) or not 0 <= h < MOD:
                raise RecoveryError(f"cannot suffix anonymous texture row: {row!r}")
            row["nameHash"] = (ord(digit) ^ (33 * h)) & 0xFFFFFFFF
            if "nameEnd" in row:
                row["nameEnd"] = digit
    return row


def _unsuffix_row(source: dict, layer_index: int) -> dict:
    if not 0 <= layer_index <= 3:
        raise RecoveryError(f"layer index {layer_index} outside 0..3")
    row = copy.deepcopy(source)
    if not layer_index:
        return row
    digit = str(layer_index)
    name = row.get("name")
    if not isinstance(name, str) or not name:
        raise RecoveryError(
            "retail Nuketown recovery requires explicit generated argument names; "
            f"cannot invert anonymous row {row!r}"
        )
    if not name.endswith(digit):
        raise RecoveryError(
            f"generated argument {name!r} does not carry expected layer suffix {digit!r}"
        )
    base = name[:-1]
    if not base:
        raise RecoveryError(f"generated argument {name!r} becomes empty after suffix removal")
    row["name"] = base
    if "nameHash" in row:
        row["nameHash"] = _name_hash(base)
    if "nameEnd" in row:
        # OAT JSON in the retail corpus uses explicit names and normally omits
        # nameEnd. If present, the exact pre-suffix byte is derivable from name.
        row["nameEnd"] = base[-1]
    return row


def _project(components: list[str], tables: dict[str, list[dict]]) -> list[dict]:
    out: list[dict] = []
    for layer_index, component in enumerate(components):
        try:
            table = tables[component]
        except KeyError as exc:
            raise RecoveryError(f"missing component table {component!r}") from exc
        for row in table:
            out.append(_suffix_row(row, layer_index))
    return sorted(out, key=_row_hash)


def _subtract_exact(generated: list[dict], known_rows: list[dict]) -> list[dict]:
    pool = Counter(_canonical(row) for row in generated)
    for row in known_rows:
        key = _canonical(row)
        if pool[key] <= 0:
            raise RecoveryError(f"known projected row is absent from generated table: {row!r}")
        pool[key] -= 1
    remaining = Counter(pool)
    residual: list[dict] = []
    for row in generated:
        key = _canonical(row)
        if remaining[key] > 0:
            residual.append(row)
            remaining[key] -= 1
    if any(remaining.values()):
        raise RecoveryError("internal exact-subtraction accounting failure")
    return residual


def _candidate_for_position(residual: list[dict], positions: list[int], position: int) -> list[dict]:
    if position == 0:
        if len(positions) != 1:
            raise RecoveryError("cannot disambiguate repeated missing layer including layer 0")
        selected = residual
    else:
        digit = str(position)
        selected = []
        for row in residual:
            name = row.get("name")
            if not isinstance(name, str) or not name:
                raise RecoveryError("target residual row lacks explicit argument name")
            if name.endswith(digit):
                selected.append(row)
    if not selected:
        raise RecoveryError(f"no residual rows assigned to missing layer position {position}")
    return sorted((_unsuffix_row(row, position) for row in selected), key=_row_hash)


def build_recovery(*, material_root: Path, catalog_doc: dict, targets: list[str]) -> dict:
    indexed, skipped = _index_oat_materials(material_root)
    catalog = catalog_doc.get("materials")
    if not isinstance(catalog, list):
        raise RecoveryError("catalog missing materials[]")
    if not targets or len(set(targets)) != len(targets):
        raise RecoveryError("targets must be a non-empty unique identity list")
    target_set = set(targets)
    unexpected_present = sorted(target_set & set(indexed))
    if unexpected_present:
        raise RecoveryError(f"targets unexpectedly have standalone OAT Materials: {unexpected_present}")

    generated_rows: list[dict] = []
    referenced: set[str] = set()
    occurrences: dict[str, list[dict]] = defaultdict(list)
    occurrence_normals: dict[str, set[bool]] = defaultdict(set)
    occurrence_tokens: dict[str, set[str]] = defaultdict(set)
    occurrence_indices: dict[str, set[int]] = defaultdict(set)

    for cat in catalog:
        material = str(cat.get("name") or "")
        if not material.startswith("*"):
            continue
        try:
            parsed = parse_layered_material_name(material)
        except LayeredMaterialError as exc:
            raise RecoveryError(str(exc)) from exc
        components = [str(layer["componentMaterial"]) for layer in parsed["layers"]]
        referenced.update(components)
        source = indexed.get(_storage_identity(material))
        if source is None:
            raise RecoveryError(f"{material!r}: exact generated OAT Material unavailable")
        generated = _textures(material, source)
        if any(_row_hash(a) > _row_hash(b) for a, b in zip(generated, generated[1:])):
            raise RecoveryError(f"{material!r}: generated texture hashes are not nondecreasing")
        for layer in parsed["layers"]:
            component = str(layer["componentMaterial"])
            if component in target_set:
                rec = {
                    "generatedMaterial": material,
                    "layerIndex": int(layer["layerIndex"]),
                    "token": str(layer["token"]),
                    "bspMaterialIndex": int(layer["bspMaterialIndex"]),
                    "expectedNormalMap": bool(layer["expectedNormalMap"]),
                }
                occurrences[component].append(rec)
                occurrence_normals[component].add(rec["expectedNormalMap"])
                occurrence_tokens[component].add(rec["token"])
                occurrence_indices[component].add(rec["bspMaterialIndex"])
        generated_rows.append({
            "material": material,
            "components": components,
            "source": source,
            "textures": generated,
        })

    observed_missing = sorted(name for name in referenced if name not in indexed)
    if observed_missing != sorted(target_set):
        raise RecoveryError(
            "target set is not the exact standalone-missing component set: "
            f"observed={observed_missing!r} supplied={sorted(target_set)!r}"
        )

    standalone_tables = {
        name: _textures(name, indexed[name])
        for name in referenced
        if name in indexed
    }

    # First re-prove the exact projection against every source-complete generated Material.
    source_complete_count = 0
    for row in generated_rows:
        if all(component in standalone_tables for component in row["components"]):
            expected = _project(row["components"], standalone_tables)
            if _canonical(expected) != _canonical(row["textures"]):
                raise RecoveryError(
                    f"{row['material']!r}: suffix+hash-sort projection disagrees with exact generated table"
                )
            source_complete_count += 1

    evidence: dict[str, list[dict]] = defaultdict(list)
    candidates: dict[str, list[list[dict]]] = defaultdict(list)
    target_bearing_count = 0

    for row in generated_rows:
        missing = sorted({component for component in row["components"] if component not in standalone_tables})
        if not missing:
            continue
        target_bearing_count += 1
        if len(missing) != 1:
            raise RecoveryError(
                f"{row['material']!r}: expected exactly one standalone-missing identity, got {missing!r}"
            )
        target = missing[0]
        if target not in target_set:
            raise RecoveryError(f"{row['material']!r}: unexpected missing identity {target!r}")
        positions = [i for i, component in enumerate(row["components"]) if component == target]
        known_rows: list[dict] = []
        for layer_index, component in enumerate(row["components"]):
            if component == target:
                continue
            for source_row in standalone_tables[component]:
                known_rows.append(_suffix_row(source_row, layer_index))
        residual = _subtract_exact(row["textures"], known_rows)

        position_candidates: list[list[dict]] = []
        consumed = 0
        for position in positions:
            candidate = _candidate_for_position(residual, positions, position)
            position_candidates.append(candidate)
            consumed += len(candidate)
        if consumed != len(residual):
            raise RecoveryError(
                f"{row['material']!r}: residual partition consumed {consumed}/{len(residual)} rows"
            )
        hashes = {_sha256(_canonical(candidate)) for candidate in position_candidates}
        if len(hashes) != 1:
            raise RecoveryError(
                f"{row['material']!r}: repeated missing-layer positions disagree after suffix reversal"
            )
        candidate = position_candidates[0]
        candidates[target].append(candidate)
        evidence[target].append({
            "generatedMaterial": row["material"],
            "generatedStorageIdentity": _storage_identity(row["material"]),
            "generatedSourceFile": row["source"]["relative"],
            "generatedSourceBytes": len(row["source"]["raw"]),
            "generatedSourceSha256": _sha256(row["source"]["raw"]),
            "missingLayerPositions": positions,
            "missingLayerMultiplicity": len(positions),
            "residualGeneratedTextureCount": len(residual),
            "candidateTextureCount": len(candidate),
            "candidateTextureTableSha256": _sha256(_canonical(candidate)),
            "exactKnownRowSubtraction": True,
            "exactLayerSuffixReversal": True,
        })

    recovered: dict[str, list[dict]] = {}
    for target in targets:
        rows = candidates.get(target, [])
        if not rows:
            raise RecoveryError(f"{target!r}: no exact recovery candidate")
        hashes = {_sha256(_canonical(table)) for table in rows}
        if len(hashes) != 1:
            raise RecoveryError(
                f"{target!r}: {len(hashes)} distinct recovered tables across independent occurrences"
            )
        recovered[target] = rows[0]

    # The recovered table itself must be in the same hash order observed in standalone tables.
    for target, table in recovered.items():
        if any(_row_hash(a) > _row_hash(b) for a, b in zip(table, table[1:])):
            raise RecoveryError(f"{target!r}: recovered standalone table is not hash-ordered")

    combined = {**standalone_tables, **recovered}
    final_reconstruction_count = 0
    for row in generated_rows:
        expected = _project(row["components"], combined)
        if _canonical(expected) != _canonical(row["textures"]):
            raise RecoveryError(
                f"{row['material']!r}: final recovered projection does not reproduce generated textures[]"
            )
        final_reconstruction_count += 1

    output_rows: list[dict] = []
    for target in targets:
        normals = occurrence_normals[target]
        indices = occurrence_indices[target]
        if len(normals) != 1:
            raise RecoveryError(f"{target!r}: conflicting normal expectations {sorted(normals)!r}")
        if len(indices) != 1:
            raise RecoveryError(f"{target!r}: conflicting BSP indices {sorted(indices)!r}")
        expected_normal = next(iter(normals))
        pseudo = {"doc": {"textures": recovered[target]}}
        has_normal = _has_real_normal_map(pseudo)
        if has_normal != expected_normal:
            raise RecoveryError(
                f"{target!r}: recovered real-normal={has_normal} != token expectation={expected_normal}"
            )
        target_evidence = evidence[target]
        output_rows.append({
            "identity": target,
            "standaloneOatMaterialAvailable": False,
            "bspMaterialIndex": next(iter(indices)),
            "tokens": sorted(occurrence_tokens[target]),
            "expectedNormalMap": expected_normal,
            "recoveredHasRealNormalMap": has_normal,
            "textureCount": len(recovered[target]),
            "textureTableSha256": _sha256(_canonical(recovered[target])),
            "textures": recovered[target],
            "generatedMaterialCount": len(target_evidence),
            "generatedLayerOccurrenceCount": sum(int(e["missingLayerMultiplicity"]) for e in target_evidence),
            "recoveryEvidence": target_evidence,
        })

    summary = {
        "targetCount": len(targets),
        "recoveredTargetCount": len(output_rows),
        "standaloneMissingComponentCount": len(observed_missing),
        "generatedCatalogMaterialCount": len(generated_rows),
        "sourceCompleteProjectionProofCount": source_complete_count,
        "targetBearingGeneratedMaterialCount": target_bearing_count,
        "targetGeneratedLayerOccurrenceCount": sum(len(occurrences[target]) for target in targets),
        "allGeneratedExactReconstructionCount": final_reconstruction_count,
    }
    return {
        "format": FORMAT,
        "source": {
            "producer": PRODUCER,
            "materialRoot": str(material_root),
            "catalogFormat": catalog_doc.get("format"),
            "catalogMap": catalog_doc.get("map"),
            "indexedOatMaterialCount": len(indexed),
            "skippedNonT6MaterialJsonCount": len(skipped),
        },
        "projection": {
            "rowMutation": "preserve all fields; append decimal layer index to argument name for layers 1..3",
            "ordering": "global nondecreasing Treyarch 32-bit argument-name hash",
            "hashRecurrence": "h = (ord(ch) XOR (33*h)) mod 2^32 from h=0",
            "recovery": "exact known-row multiset subtraction followed by exact layer-suffix reversal",
        },
        "summary": summary,
        "components": output_rows,
        "proofBoundary": (
            "This proof recovers only exact raw OAT textures[] tables for standalone-missing layered components. "
            "It does not recover or infer a standalone TechniqueSet, constants, render state, asset owner, "
            "retail duplicate precedence, or layered shader/blend math."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("material_root", type=Path)
    ap.add_argument("catalog_json", type=Path)
    ap.add_argument("output_json", type=Path)
    ap.add_argument("--target", action="append", default=[])
    args = ap.parse_args()
    doc = build_recovery(
        material_root=args.material_root,
        catalog_doc=json.loads(args.catalog_json.read_text(encoding="utf-8")),
        targets=args.target,
    )
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_bytes(payload)
    print(json.dumps({"out": str(args.output_json), "bytes": len(payload), "sha256": _sha256(payload), **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
