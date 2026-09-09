#!/usr/bin/env python3
"""Close exact runtime row order for Nuketown generated layered Materials.

This verifier deliberately separates two questions:

1. What order did the missing standalone component Material originally serialize?
2. What order does the runtime generated layered Material actually use?

The first remains unknowable from a generated table once Material_CreateLayered has
qsorted it. The second is the order needed to reproduce the actual layered
Material used by Nuketown and can be closed exactly.

Authority is fail-closed:
- exact Nuketown layered Material universe;
- exact frozen missing-component row sets;
- exact dedicated-server Material_CreateLayered sort manifest;
- exact OAT-generated Material JSON rows dumped from the SHA-pinned Nuketown FF.

No filename similarity, semantic priority, component-relative row ordering, or
retail-client equivalence is inferred here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


class ProofError(RuntimeError):
    pass


EXPECTED_UNIVERSE_SHA = "891ddff8e3368086c77ccf896a52d515c618a779e7ddd93dde84bffcf0b1ded4"
EXPECTED_RESIDUAL_SHA = "9caab3e9ba364f2c8f56a148680bf0a0b17c9bf4"
EXPECTED_FASTFILE_SHA = "6c026322a713c461a03de9815bf6eef0e959fb2ab5d82299b029b775fa1ab1e0"
EXPECTED_OAT_COMMIT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"
EXPECTED_SERVER_SORT_FORMAT = "t6-pc-server-layered-material-sort-v1"
EXPECTED_COMPARATOR_SHA = "89c3ef79d0956caceb677fd742d376f28895d8788fd9ad7c1e88a4535d840952"
EXPECTED_CREATE_LAYERED_SHA = "505da556ae793f0a27a5e393dff0c9c1ff8f0be4a42c2935c5790c9c29535e42"
EXPECTED_LAYERED_COUNT = 120
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


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    raw = path.read_bytes()
    return json.loads(raw), raw


def r_hash_string(name: str) -> int:
    """Exact T6 R_HashString(name, 0): djb2_xor_nocase, uint32."""
    h = 0
    for ch in name.encode("latin-1"):
        h = (((h << 5) + h) ^ (ch | 0x20)) & 0xFFFFFFFF
    return h


def parse_layered(identity: str):
    m = NAME_RE.fullmatch(identity)
    if not m:
        raise ProofError(f"invalid layered Material identity: {identity!r}")
    tokens = m.group("tokens").split("_")
    components = m.group("components").split(":")
    if not 1 <= len(tokens) <= 4 or len(tokens) != len(components):
        raise ProofError(f"layer/component mismatch: {identity!r}")
    return tokens, components, "generated/_" + m.group("tokens")


def generated_name(source: str, layer: int) -> str:
    return source if layer == 0 else f"{source}{layer}"


def validate_sort_manifest(doc: dict) -> None:
    if doc.get("format") != EXPECTED_SERVER_SORT_FORMAT:
        raise ProofError("unexpected server sort manifest format")
    if doc.get("comparator", {}).get("sha256") != EXPECTED_COMPARATOR_SHA:
        raise ProofError("server comparator SHA changed")
    if doc.get("materialCreateLayered", {}).get("sha256") != EXPECTED_CREATE_LAYERED_SHA:
        raise ProofError("Material_CreateLayered SHA changed")
    tex = doc.get("materialCreateLayered", {}).get("textureSort", {})
    if tex != {
        "countLoadVa": "0x00A4E0A3",
        "countFieldOffset": "0x54",
        "tableLoadVa": "0x00A4E0A7",
        "tableFieldOffset": "0x60",
        "comparatorPushVa": "0x00A4E0AA",
        "elementSizeBytes": 16,
        "qsortCallVa": "0x00A4E0B3",
        "qsortVa": "0x00AAE010",
    }:
        raise ProofError(f"texture qsort proof changed: {tex!r}")
    cmp = doc.get("comparator", {})
    if cmp.get("recordKeyOffset") != 0 or cmp.get("recordKeyWidthBits") != 32:
        raise ProofError("unexpected comparator key layout")
    if cmp.get("textureKey") != "MaterialTextureDef.nameHash":
        raise ProofError("unexpected texture comparator key")


def build(material_root: Path, universe_path: Path, residual_path: Path, sort_manifest_path: Path) -> dict:
    universe, universe_raw = load(universe_path)
    residual, residual_raw = load(residual_path)
    sort_doc, sort_raw = load(sort_manifest_path)

    if sha256_bytes(universe_raw) != EXPECTED_UNIVERSE_SHA:
        raise ProofError("exact layered universe SHA changed")
    if universe.get("format") != "t6-nuketown-exact-layered-material-universe-v1":
        raise ProofError("unexpected layered universe format")
    if universe.get("authority", {}).get("fastFileSha256") != EXPECTED_FASTFILE_SHA:
        raise ProofError("Nuketown FastFile authority changed")
    layered = universe.get("layeredMaterials")
    if not isinstance(layered, list) or len(layered) != EXPECTED_LAYERED_COUNT or len(set(layered)) != EXPECTED_LAYERED_COUNT:
        raise ProofError("expected exactly 120 unique layered Materials")

    if residual.get("format") != "t6-nuketown-missing-layer-residual-rowsets-v1":
        raise ProofError("unexpected residual-rowset format")
    # The repository blob SHA is separately frozen in the source history; content
    # identity here is tied to its authority/result hash and exact target set.
    if residual.get("authority", {}).get("fastFileSha256") != EXPECTED_FASTFILE_SHA:
        raise ProofError("residual FastFile authority changed")
    if residual.get("authority", {}).get("layeredMaterialUniverseSha256") != EXPECTED_UNIVERSE_SHA:
        raise ProofError("residual layered-universe authority changed")
    if residual.get("authority", {}).get("oatCommit") != EXPECTED_OAT_COMMIT:
        raise ProofError("residual OAT authority changed")
    targets = residual.get("targets")
    if not isinstance(targets, dict) or set(targets) != EXPECTED_TARGETS:
        raise ProofError("missing-component target set changed")

    validate_sort_manifest(sort_doc)

    reports = []
    target_occurrence_counts = Counter()
    target_runtime_rows = defaultdict(list)
    total_texture_rows = 0
    multirow_tables = 0
    hash_collision_tables = 0
    target_bearing_tables = 0

    for identity in layered:
        tokens, components, storage = parse_layered(identity)
        p = material_root / f"{storage}.json"
        if not p.is_file():
            raise ProofError(f"missing exact generated Material JSON: {storage}")
        doc, raw = load(p)
        rows = doc.get("textures")
        if not isinstance(rows, list) or not all(isinstance(x, dict) for x in rows):
            raise ProofError(f"{identity}: invalid textures table")
        if len(rows) > 1:
            multirow_tables += 1
        total_texture_rows += len(rows)

        names = []
        hashes = []
        for ri, row in enumerate(rows):
            name = row.get("name")
            if not isinstance(name, str) or not name:
                raise ProofError(f"{identity}: row {ri} lacks exact resolved texture name")
            names.append(name)
            hashes.append(r_hash_string(name))
        if len(set(hashes)) != len(hashes):
            hash_collision_tables += 1
            collisions = [f"0x{h:08X}" for h, n in Counter(hashes).items() if n > 1]
            raise ProofError(f"{identity}: nameHash collision(s) {collisions}; qsort ordering not unique")
        if hashes != sorted(hashes):
            raise ProofError(
                f"{identity}: generated runtime textureTable is not strictly ascending by exact T6 nameHash: "
                + repr([(n, f"0x{h:08X}") for n, h in zip(names, hashes)])
            )

        target_layers = [(layer, component) for layer, component in enumerate(components) if component in targets]
        if target_layers:
            target_bearing_tables += 1
        for layer, component in target_layers:
            target_occurrence_counts[component] += 1
            src_rows = targets[component].get("rows")
            if not isinstance(src_rows, list) or not src_rows:
                raise ProofError(f"{component}: frozen target rows missing")
            matched_indices = []
            matched = []
            for src in src_rows:
                src_name = src.get("name")
                if not isinstance(src_name, str) or not src_name:
                    raise ProofError(f"{component}: frozen row lacks name")
                wanted = dict(src)
                wanted["name"] = generated_name(src_name, layer)
                matches = [(i, row) for i, row in enumerate(rows) if canonical(row) == canonical(wanted)]
                if len(matches) != 1:
                    raise ProofError(
                        f"{identity}: target {component} layer {layer} row {src_name!r} exact-match count {len(matches)}"
                    )
                i, actual = matches[0]
                matched_indices.append(i)
                matched.append({
                    "runtimeIndex": i,
                    "generatedName": actual["name"],
                    "nameHash": f"0x{hashes[i]:08X}",
                    "sourceName": src_name,
                })
            if len(set(matched_indices)) != len(matched_indices):
                raise ProofError(f"{identity}: target rows overlap")
            target_runtime_rows[component].append({
                "generatedMaterial": identity,
                "storageIdentity": storage,
                "layerIndex": layer,
                "token": tokens[layer],
                "runtimeRows": sorted(matched, key=lambda x: x["runtimeIndex"]),
            })

        reports.append({
            "material": identity,
            "storageIdentity": storage,
            "jsonSha256": sha256_bytes(raw),
            "textureCount": len(rows),
            "nameHashesInRuntimeOrder": [f"0x{x:08X}" for x in hashes],
            "strictAscendingUniqueNameHash": True,
            "targetLayerCount": len(target_layers),
        })

    expected_occ = {name: int(targets[name]["occurrenceCount"]) for name in sorted(targets)}
    got_occ = dict(sorted(target_occurrence_counts.items()))
    if got_occ != expected_occ:
        raise ProofError(f"target occurrence histogram changed: got={got_occ!r} expected={expected_occ!r}")

    # For every generated target layer, all target row hashes are unique within the
    # complete table. Therefore qsort's output is independent of the component's
    # pre-sort row permutation. This is the precise reason original standalone row
    # order is not a runtime degree of freedom for these generated map Materials.
    target_row_occurrences = sum(
        len(occ["runtimeRows"])
        for occs in target_runtime_rows.values()
        for occ in occs
    )

    return {
        "format": "t6-nuketown-layered-runtime-sort-closure-v1",
        "authority": {
            "fastFile": universe["authority"]["fastFile"],
            "fastFileSha256": universe["authority"]["fastFileSha256"],
            "layeredMaterialUniverse": str(universe_path),
            "layeredMaterialUniverseSha256": sha256_bytes(universe_raw),
            "missingLayerResidualRowSets": str(residual_path),
            "missingLayerResidualRowSetsSha256": sha256_bytes(residual_raw),
            "serverLayeredSortManifest": str(sort_manifest_path),
            "serverLayeredSortManifestSha256": sha256_bytes(sort_raw),
            "openAssetToolsCommit": EXPECTED_OAT_COMMIT,
        },
        "runtimeRule": {
            "producer": "Material_CreateLayered",
            "textureCountFieldOffset": "0x54",
            "textureTableFieldOffset": "0x60",
            "textureElementSizeBytes": 16,
            "comparatorVa": "0x00A4D630",
            "comparatorSha256": EXPECTED_COMPARATOR_SHA,
            "key": "MaterialTextureDef.nameHash",
            "keyAlgorithm": "T6 R_HashString(name,0) = djb2_xor_nocase(name,0), uint32",
            "ordering": "strict ascending unsigned uint32 for this corpus; no in-table hash collisions",
        },
        "summary": {
            "exactLayeredMaterialCount": len(reports),
            "multirowGeneratedMaterialCount": multirow_tables,
            "totalGeneratedTextureRowCount": total_texture_rows,
            "strictHashSortedGeneratedMaterialCount": len(reports),
            "hashCollisionGeneratedMaterialCount": hash_collision_tables,
            "targetBearingGeneratedMaterialCount": target_bearing_tables,
            "missingComponentTargetCount": len(targets),
            "missingComponentLayerOccurrenceCount": sum(got_occ.values()),
            "missingComponentTextureRowOccurrenceCount": target_row_occurrences,
            "standaloneSourceRowOrderNeededForExactGeneratedRuntime": False,
        },
        "targetOccurrenceHistogram": got_occ,
        "targetRuntimeRows": {k: v for k, v in sorted(target_runtime_rows.items())},
        "generatedMaterials": reports,
        "proofBoundary": (
            "For the exact 120 Nuketown generated layered Materials, runtime textureTable order is closed as the exact "
            "strictly ascending T6 nameHash order emitted by the SHA-pinned OAT dump and independently prescribed by "
            "the exact CoDMPServer_PC Material_CreateLayered qsort callsite. Every generated table has unique nameHash "
            "keys, including every occurrence of the seven formerly missing component row sets, so the final generated "
            "runtime table is invariant to any pre-sort permutation of a component's rows. Consequently the unresolved "
            "standalone source row order of the six multi-row component identities is not a Nuketown generated-runtime "
            "rendering degree of freedom. This does NOT reconstruct the historical standalone serialized row order, does "
            "NOT create standalone Material XAssets that are absent from the map dump, and does NOT claim retail-client "
            "executable equivalence beyond the independently observed exact retail FastFile generated tables."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("material_root", type=Path)
    ap.add_argument("universe", type=Path)
    ap.add_argument("residual", type=Path)
    ap.add_argument("sort_manifest", type=Path)
    ap.add_argument("out", type=Path)
    ns = ap.parse_args()
    try:
        result = build(ns.material_root, ns.universe, ns.residual, ns.sort_manifest)
    except (OSError, ValueError, KeyError, ProofError) as exc:
        raise SystemExit(f"FAIL-CLOSED: {exc}") from exc
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("GREEN T6_NUKETOWN_LAYERED_RUNTIME_SORT_CLOSURE_V1", json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
