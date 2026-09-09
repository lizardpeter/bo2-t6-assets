#!/usr/bin/env python3
"""Recover copy-elided T6 layered component texture tables exactly.

Treyarch layered Materials serialize a generated ``textures[]`` table that is the
ordered concatenation of the component Material texture tables. Some component
Materials are not retained as standalone XAssets in the map FastFile. This tool
recovers only those missing ``textures[]`` arrays when the concatenation equation
has a unique exact solution and every independent occurrence agrees.

It deliberately does not reconstruct the missing component's TechniqueSet,
constants, render state, or retail override owner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from t6_layered_material_name_v1 import LayeredMaterialError, parse_layered_material_name
from t6_oat_material_manifest_v2 import _has_real_normal_map, _index_oat_materials
from t6_oat_material_manifest_v6 import _storage_identity

FORMAT = "t6-oat-layered-component-texture-recovery-v1"
PRODUCER = "t6_oat_layered_component_texture_recovery_v1.py"


class RecoveryError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _raw_textures(identity: str, source: dict) -> list[dict]:
    textures = source["doc"].get("textures", [])
    if not isinstance(textures, list):
        raise RecoveryError(f"{identity!r}: textures is not a list")
    if any(not isinstance(row, dict) for row in textures):
        raise RecoveryError(f"{identity!r}: textures contains a non-object row")
    return textures


def _solve_one(
    generated: list[dict],
    components: list[str],
    tables: dict[str, list[dict]],
    unknown: str,
) -> tuple[list[dict], list[int]] | None:
    positions = [i for i, name in enumerate(components) if name == unknown]
    if not positions:
        return None
    unresolved = {name for name in components if name not in tables}
    if unresolved != {unknown}:
        return None
    known_len = sum(len(tables[name]) for name in components if name != unknown)
    residual = len(generated) - known_len
    copies = len(positions)
    if residual < 0 or residual % copies:
        raise RecoveryError(
            f"{unknown!r}: generated table length {len(generated)} cannot satisfy "
            f"{copies} repeated unknown layer(s) after {known_len} known entries"
        )
    width = residual // copies
    cursor = 0
    candidate: list[dict] | None = None
    for name in components:
        if name == unknown:
            segment = generated[cursor:cursor + width]
            if len(segment) != width:
                raise RecoveryError(f"{unknown!r}: truncated generated table while solving")
            if candidate is None:
                candidate = segment
            elif _canonical(segment) != _canonical(candidate):
                raise RecoveryError(
                    f"{unknown!r}: repeated unknown layers are not byte-equivalent JSON tables"
                )
            cursor += width
        else:
            expected = tables[name]
            actual = generated[cursor:cursor + len(expected)]
            if _canonical(actual) != _canonical(expected):
                raise RecoveryError(
                    f"generated concatenation disagrees with standalone component {name!r}"
                )
            cursor += len(expected)
    if cursor != len(generated) or candidate is None:
        raise RecoveryError(f"{unknown!r}: internal concatenation accounting failure")
    return candidate, positions


def build_recovery(*, material_root: Path, catalog_doc: dict, targets: list[str]) -> dict:
    indexed, skipped = _index_oat_materials(material_root)
    catalog = catalog_doc.get("materials")
    if not isinstance(catalog, list):
        raise RecoveryError("catalog missing materials[]")
    if not targets:
        raise RecoveryError("no target component identities supplied")
    if len(set(targets)) != len(targets):
        raise RecoveryError("duplicate target component identity")
    target_set = set(targets)
    present_targets = sorted(target_set & set(indexed))
    if present_targets:
        raise RecoveryError(
            f"targets unexpectedly have standalone OAT Materials: {present_targets}"
        )

    generated_rows: list[dict] = []
    referenced_components: set[str] = set()
    occurrence_tokens: dict[str, set[str]] = defaultdict(set)
    occurrence_indices: dict[str, set[int]] = defaultdict(set)
    occurrence_normals: dict[str, set[bool]] = defaultdict(set)
    occurrence_names: dict[str, list[str]] = defaultdict(list)

    for row in catalog:
        name = str(row.get("name") or "")
        if not name.startswith("*"):
            continue
        try:
            parsed = parse_layered_material_name(name)
        except LayeredMaterialError as exc:
            raise RecoveryError(str(exc)) from exc
        storage = _storage_identity(name)
        source = indexed.get(storage)
        if source is None:
            raise RecoveryError(
                f"{name!r}: missing generated OAT Material JSON {storage!r}"
            )
        textures = _raw_textures(name, source)
        components = [
            str(layer["componentMaterial"]) for layer in parsed["layers"]
        ]
        referenced_components.update(components)
        for layer in parsed["layers"]:
            component = str(layer["componentMaterial"])
            occurrence_tokens[component].add(str(layer["token"]))
            occurrence_indices[component].add(int(layer["bspMaterialIndex"]))
            occurrence_normals[component].add(bool(layer["expectedNormalMap"]))
            occurrence_names[component].append(name)
        generated_rows.append(
            {
                "material": name,
                "storageIdentity": storage,
                "source": source,
                "textures": textures,
                "components": components,
            }
        )

    missing_referenced = sorted(
        name for name in referenced_components if name not in indexed
    )
    if missing_referenced != sorted(target_set):
        raise RecoveryError(
            "target set is not the exact standalone-missing component set: "
            f"observed={missing_referenced!r} supplied={sorted(target_set)!r}"
        )

    tables: dict[str, list[dict]] = {
        name: _raw_textures(name, indexed[name])
        for name in referenced_components
        if name in indexed
    }
    recovered: dict[str, list[dict]] = {}
    evidence: dict[str, list[dict]] = defaultdict(list)

    while True:
        candidates: dict[str, list[tuple[list[dict], dict]]] = defaultdict(list)
        combined = {**tables, **recovered}
        for row in generated_rows:
            unresolved = sorted(
                {name for name in row["components"] if name not in combined}
            )
            if len(unresolved) != 1:
                continue
            unknown = unresolved[0]
            if unknown not in target_set:
                continue
            solved = _solve_one(
                row["textures"], row["components"], combined, unknown
            )
            if solved is None:
                continue
            candidate, positions = solved
            rec = {
                "generatedMaterial": row["material"],
                "generatedStorageIdentity": row["storageIdentity"],
                "generatedSourceFile": row["source"]["relative"],
                "generatedSourceBytes": len(row["source"]["raw"]),
                "generatedSourceSha256": _sha256(row["source"]["raw"]),
                "unknownLayerPositions": positions,
                "unknownLayerMultiplicity": len(positions),
                "candidateTextureCount": len(candidate),
                "candidateTextureTableSha256": _sha256(_canonical(candidate)),
            }
            candidates[unknown].append((candidate, rec))

        promotions = 0
        for identity, rows in sorted(candidates.items()):
            if identity in recovered:
                continue
            hashes = {_sha256(_canonical(table)) for table, _ in rows}
            if len(hashes) != 1:
                raise RecoveryError(
                    f"{identity!r}: {len(hashes)} distinct texture-table candidates "
                    "across generated occurrences"
                )
            recovered[identity] = rows[0][0]
            evidence[identity].extend(rec for _, rec in rows)
            promotions += 1
        if not promotions:
            break

    unresolved_targets = sorted(target_set - set(recovered))
    if unresolved_targets:
        raise RecoveryError(f"could not uniquely recover targets {unresolved_targets}")

    # Re-evaluate the complete generated population after the fixed point.
    # First require exact full-table reconstruction for every generated catalog
    # Material. Then, for every target-bearing generated Material, hide one target
    # identity at a time and independently solve it again. This makes the final
    # evidence census cover every occurrence, including rows that were not
    # solvable during the first fixed-point iteration because another target was
    # still unknown.
    combined = {**tables, **recovered}
    target_generated_count = 0
    all_generated_reconstruction_count = 0
    final_evidence: dict[str, list[dict]] = defaultdict(list)
    for row in generated_rows:
        reconstructed: list[dict] = []
        for component in row["components"]:
            if component not in combined:
                raise RecoveryError(
                    f"{row['material']!r}: unresolved component {component!r}"
                )
            reconstructed.extend(combined[component])
        if _canonical(reconstructed) != _canonical(row["textures"]):
            raise RecoveryError(
                f"{row['material']!r}: full recovered concatenation does not "
                "reproduce generated textures[]"
            )
        all_generated_reconstruction_count += 1

        row_targets = sorted(set(row["components"]) & target_set)
        if row_targets:
            target_generated_count += 1
        for identity in row_targets:
            other_tables = {k: v for k, v in combined.items() if k != identity}
            solved = _solve_one(
                row["textures"], row["components"], other_tables, identity
            )
            if solved is None:
                raise RecoveryError(
                    f"{row['material']!r}: target {identity!r} did not "
                    "independently re-solve"
                )
            candidate, positions = solved
            if _canonical(candidate) != _canonical(recovered[identity]):
                raise RecoveryError(
                    f"{row['material']!r}: independent candidate for {identity!r} "
                    "disagrees with recovered table"
                )
            final_evidence[identity].append(
                {
                    "generatedMaterial": row["material"],
                    "generatedStorageIdentity": row["storageIdentity"],
                    "generatedSourceFile": row["source"]["relative"],
                    "generatedSourceBytes": len(row["source"]["raw"]),
                    "generatedSourceSha256": _sha256(row["source"]["raw"]),
                    "unknownLayerPositions": positions,
                    "unknownLayerMultiplicity": len(positions),
                    "candidateTextureCount": len(candidate),
                    "candidateTextureTableSha256": _sha256(_canonical(candidate)),
                    "independentFinalResolve": True,
                }
            )

    output_rows: list[dict] = []
    for identity in targets:
        normal_values = occurrence_normals[identity]
        token_values = occurrence_tokens[identity]
        index_values = occurrence_indices[identity]
        if len(normal_values) != 1:
            raise RecoveryError(
                f"{identity!r}: conflicting expected-normal markers "
                f"{sorted(normal_values)}"
            )
        if len(index_values) != 1:
            raise RecoveryError(
                f"{identity!r}: conflicting BSP material indices {sorted(index_values)}"
            )
        expected_normal = next(iter(normal_values))
        pseudo_source = {"doc": {"textures": recovered[identity]}}
        has_normal = _has_real_normal_map(pseudo_source)
        if has_normal != expected_normal:
            raise RecoveryError(
                f"{identity!r}: recovered texture table real-normal={has_normal} "
                f"does not match generated token expectation {expected_normal}"
            )
        output_rows.append(
            {
                "identity": identity,
                "standaloneOatMaterialAvailable": False,
                "bspMaterialIndex": next(iter(index_values)),
                "tokens": sorted(token_values),
                "expectedNormalMap": expected_normal,
                "recoveredHasRealNormalMap": has_normal,
                "textureCount": len(recovered[identity]),
                "textureTableSha256": _sha256(_canonical(recovered[identity])),
                "textures": recovered[identity],
                "generatedMaterialCount": len(set(occurrence_names[identity])),
                "generatedLayerOccurrenceCount": len(occurrence_names[identity]),
                "generatedMaterials": sorted(set(occurrence_names[identity])),
                "fixedPointAdmissionEvidence": evidence[identity],
                "recoveryEvidence": final_evidence[identity],
            }
        )

    return {
        "format": FORMAT,
        "source": {
            "producer": PRODUCER,
            "materialRoot": str(material_root),
            "catalogFormat": catalog_doc.get("format"),
            "catalogMap": catalog_doc.get("map"),
            "indexedOatMaterialCount": len(indexed),
            "generatedCatalogMaterialCount": len(generated_rows),
            "skippedNonT6MaterialJsonCount": len(skipped),
        },
        "policy": {
            "recoveryEquation": (
                "generated textures[] == component textures[] concatenated in "
                "serialized layer order"
            ),
            "admission": (
                "target must be absent as a standalone OAT Material, be the exact "
                "complete standalone-missing component set, have a unique "
                "length/alignment solution, and agree across every generated occurrence"
            ),
            "normalValidation": (
                "recovered real normal-map presence must exactly equal every "
                "serialized n-marker expectation"
            ),
        },
        "summary": {
            "targetCount": len(targets),
            "recoveredTargetCount": len(output_rows),
            "standaloneMissingComponentCount": len(missing_referenced),
            "generatedCatalogMaterialCount": len(generated_rows),
            "allGeneratedExactReconstructionCount": all_generated_reconstruction_count,
            "targetBearingGeneratedMaterialCount": target_generated_count,
            "targetGeneratedLayerOccurrenceCount": sum(
                len(occurrence_names[x]) for x in targets
            ),
        },
        "components": output_rows,
        "proofBoundary": (
            "This proof recovers only exact raw OAT textures[] tables for copy-elided "
            "layered components. It does not recover or infer a standalone component "
            "TechniqueSet, constants, render state, asset owner, retail duplicate "
            "precedence, or layered shader/blend math."
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
    print(
        json.dumps(
            {
                "out": str(args.output_json),
                "bytes": len(payload),
                "sha256": _sha256(payload),
                **doc["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
