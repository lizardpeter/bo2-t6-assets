#!/usr/bin/env python3
"""Diagnose exact row-order transforms in Nuketown layered Materials.

This probe is deliberately non-promotional. It uses only the pinned exact layered
Material universe and exact OAT Material JSONs. It records how each standalone-
known component's texture rows map into the generated layered table and reports
only cases where source-relative order changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


class ProofError(RuntimeError):
    pass


EXPECTED_TARGETS = {
    "wpc/asphalt_road_dark_dec",
    "wpc/decal_concrete_clean_line",
    "wpc/decal_damage_asphalt_crack01",
    "wpc/decal_grunge_glue",
    "wpc/decal_grunge_mold01",
    "wpc/decal_signage_const_marking01",
    "wpc/decal_signage_const_marking02",
}
NAME_RE = re.compile(r"^\*(?P<tokens>[^()]+)\((?P<components>[^()]*)\)$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    raw = path.read_bytes()
    return json.loads(raw), raw


def load_rows(path: Path) -> list[dict]:
    doc, _ = load_json(path)
    rows = doc.get("textures")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ProofError(f"{path}: invalid textures table")
    return rows


def parse_compound(name: str):
    m = NAME_RE.fullmatch(name)
    if not m:
        raise ProofError(f"invalid compound identity {name!r}")
    tokens = m.group("tokens").split("_")
    components = m.group("components").split(":")
    if len(tokens) != len(components):
        raise ProofError(f"layer/component mismatch {name!r}")
    return tokens, components, "generated/_" + m.group("tokens")


def expected_generated_name(name: str, layer_index: int) -> str:
    return name if layer_index == 0 else f"{name}{layer_index}"


def build_probe(material_root: Path, universe_path: Path) -> dict:
    universe, universe_raw = load_json(universe_path)
    if universe.get("format") != "t6-nuketown-exact-layered-material-universe-v1":
        raise ProofError("unexpected universe format")
    names = universe.get("layeredMaterials")
    if not isinstance(names, list) or len(names) != 120 or len(set(names)) != 120:
        raise ProofError("expected 120 unique layered identities")

    parsed = []
    referenced = set()
    for name in names:
        tokens, components, storage = parse_compound(name)
        parsed.append((name, tokens, components, storage))
        referenced.update(components)
    if len(referenced) != 83:
        raise ProofError(f"expected 83 referenced components, got {len(referenced)}")

    component_rows: dict[str, list[dict] | None] = {}
    for identity in referenced:
        path = material_root / f"{identity}.json"
        component_rows[identity] = load_rows(path) if path.is_file() else None
    missing = {k for k, v in component_rows.items() if v is None}
    if missing != EXPECTED_TARGETS:
        raise ProofError(f"standalone-missing set changed: {sorted(missing)!r}")

    failures = []
    known_occurrences = 0
    known_texture_occurrences = 0
    for full_name, tokens, components, storage in parsed:
        generated_path = material_root / f"{storage}.json"
        if not generated_path.is_file():
            raise ProofError(f"missing generated Material {storage}")
        generated_rows = load_rows(generated_path)
        by_name: dict[str, list[int]] = {}
        for gi, row in enumerate(generated_rows):
            name = row.get("name")
            if not isinstance(name, str) or not name:
                raise ProofError(f"{storage}: row {gi} lacks name")
            by_name.setdefault(name, []).append(gi)

        for layer_index, identity in enumerate(components):
            rows = component_rows[identity]
            if rows is None:
                continue
            known_occurrences += 1
            known_texture_occurrences += len(rows)
            mapping = []
            for si, row in enumerate(rows):
                source_name = row.get("name")
                if not isinstance(source_name, str) or not source_name:
                    raise ProofError(f"{identity}: source row {si} lacks name")
                expected_name = expected_generated_name(source_name, layer_index)
                matches = by_name.get(expected_name, [])
                if len(matches) != 1:
                    raise ProofError(
                        f"{full_name}: {identity} row {si} expected {expected_name!r} match count {len(matches)}"
                    )
                gi = matches[0]
                mapping.append(
                    {
                        "sourceTextureIndex": si,
                        "sourceName": source_name,
                        "sourceRow": row,
                        "expectedGeneratedName": expected_name,
                        "generatedTextureIndex": gi,
                        "generatedRow": generated_rows[gi],
                    }
                )
            indices = [row["generatedTextureIndex"] for row in mapping]
            if indices != sorted(indices):
                failures.append(
                    {
                        "generatedMaterial": full_name,
                        "storageIdentity": storage,
                        "tokens": tokens,
                        "components": components,
                        "component": identity,
                        "layerIndex": layer_index,
                        "sourceTextureCount": len(rows),
                        "sourceRows": rows,
                        "generatedTextureCount": len(generated_rows),
                        "generatedRows": generated_rows,
                        "generatedIndicesInSourceOrder": indices,
                        "generatedIndicesSorted": sorted(indices),
                        "mapping": mapping,
                    }
                )

    if len(failures) != 6:
        raise ProofError(f"order-failure census changed: expected 6, got {len(failures)}")

    return {
        "format": "t6-nuketown-layered-texture-order-probe-v1",
        "authority": {
            "materialUniverse": str(universe_path),
            "materialUniverseSha256": sha256_bytes(universe_raw),
            "fastFile": universe["authority"]["fastFile"],
            "fastFileSha256": universe["authority"]["fastFileSha256"],
            "oatCommit": "9dca965366541504b71fa8cfb7ac049cb9b717e1",
        },
        "summary": {
            "exactLayeredMaterialCount": len(parsed),
            "referencedComponentCount": len(referenced),
            "knownComponentOccurrenceCount": known_occurrences,
            "knownTextureOccurrenceCount": known_texture_occurrences,
            "relativeOrderFailureCount": len(failures),
        },
        "relativeOrderFailures": failures,
        "proofBoundary": (
            "Diagnostic only. This records exact source-to-generated row permutations and exact row fields for known component tables. "
            "It does not infer a universal ordering rule and does not promote missing component tables."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_root", type=Path)
    parser.add_argument("universe_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    doc = build_probe(args.material_root, args.universe_json)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.output_json.write_text(payload, encoding="utf-8")
    print(json.dumps(doc["summary"], sort_keys=True))
    for failure in doc["relativeOrderFailures"]:
        print(
            "ORDER_FAILURE",
            failure["generatedMaterial"],
            failure["component"],
            f"layer={failure['layerIndex']}",
            f"indices={failure['generatedIndicesInSourceOrder']}",
        )
        print(
            "  SOURCE",
            [(r.get("name"), r.get("semantic"), r.get("samplerState")) for r in failure["sourceRows"]],
        )
        print(
            "  GENERATED",
            [(r.get("name"), r.get("semantic"), r.get("samplerState")) for r in failure["generatedRows"]],
        )
    print(f"output_sha256={sha256_bytes(payload.encode())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
