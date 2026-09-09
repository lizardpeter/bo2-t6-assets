#!/usr/bin/env python3
"""Fail-closed recovery of copy-elided T6 layered component runtime textures.

Material_CreateLayered does not byte-copy standalone texture rows: it promotes
nearest->linear mip filtering for color/normal/specular maps, appends the layer
digit to texture argument identity on layers 1..3, and recomputes mature-content.
Missing standalone rows therefore cannot be inverted exactly. This tool recovers
only a layer-suffix-neutral *post-transform runtime* table and proves that exact
projection of all known/recovered components reproduces every generated table.
"""
from __future__ import annotations

import argparse, copy, hashlib, json
from collections import defaultdict
from pathlib import Path

from t6_layered_material_name_v1 import LayeredMaterialError, parse_layered_material_name
from t6_oat_material_manifest_v2 import _has_real_normal_map, _index_oat_materials
from t6_oat_material_manifest_v6 import _storage_identity

FORMAT = "t6-oat-layered-component-texture-recovery-v2"
LINEARIZE = {"colorMap", "normalMap", "specularMap"}
MATURE_FALSE = {"2D", "function", "waterMap"}
MOD = 1 << 32
INV33 = pow(33, -1, MOD)

class RecoveryError(RuntimeError):
    pass

def canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def sha(x):
    return hashlib.sha256(x).hexdigest()

def raw_textures(identity, source):
    rows = source["doc"].get("textures", [])
    if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
        raise RecoveryError(f"{identity!r}: invalid textures[]")
    return rows

def layer_char(i):
    if i == 0:
        return None
    if 1 <= i <= 3:
        return str(i)
    raise RecoveryError(f"layer index {i} outside source-closed 0..3")

def semantic(row):
    v = row.get("semantic")
    if not isinstance(v, str) or not v:
        raise RecoveryError(f"invalid texture semantic: {v!r}")
    return v

def mature(row):
    sem = semantic(row)
    if sem in MATURE_FALSE:
        return False
    image = row.get("image")
    if not isinstance(image, str):
        raise RecoveryError(f"{sem!r}: image unavailable for mature-content recomputation")
    return "_mature" in image

def project_row(source, layer_index):
    row = copy.deepcopy(source)
    sem = semantic(row)
    sampler = row.get("samplerState")
    if not isinstance(sampler, dict) or not isinstance(sampler.get("mipMap"), str):
        raise RecoveryError("invalid samplerState/mipMap")
    if sem in LINEARIZE and sampler["mipMap"] == "nearest":
        sampler["mipMap"] = "linear"
    ch = layer_char(layer_index)
    if ch is not None:
        if row.get("name") is not None:
            if not isinstance(row["name"], str) or not row["name"]:
                raise RecoveryError("invalid texture name")
            row["name"] += ch
        else:
            h = row.get("nameHash")
            if not isinstance(h, int) or not 0 <= h < MOD:
                raise RecoveryError("invalid fallback nameHash")
            if not isinstance(row.get("nameStart"), str) or len(row["nameStart"]) != 1:
                raise RecoveryError("invalid fallback nameStart")
            row["nameHash"] = (ord(ch) ^ (33 * h)) & 0xFFFFFFFF
            row["nameEnd"] = ch
    row["isMatureContent"] = mature(row)
    return row

def project(table, layer_index):
    return [project_row(x, layer_index) for x in table]

def unsuffix_row(source, layer_index):
    row = copy.deepcopy(source)
    ch = layer_char(layer_index)
    if ch is None:
        return row, False
    if row.get("name") is not None:
        name = row["name"]
        if not isinstance(name, str) or not name.endswith(ch) or len(name) == 1:
            raise RecoveryError(f"generated texture name {name!r} lacks layer suffix {ch!r}")
        row["name"] = name[:-1]
        return row, False
    h = row.get("nameHash")
    if not isinstance(h, int) or not 0 <= h < MOD:
        raise RecoveryError("invalid generated fallback nameHash")
    if not isinstance(row.get("nameStart"), str) or len(row["nameStart"]) != 1:
        raise RecoveryError("invalid generated fallback nameStart")
    if row.get("nameEnd") != ch:
        raise RecoveryError("generated fallback nameEnd does not match layer")
    row["nameHash"] = ((h ^ ord(ch)) * INV33) & 0xFFFFFFFF
    row.pop("nameEnd", None)  # overwritten pre-layer byte is not recoverable
    return row, True

def unsuffix_table(segment, layer_index):
    out, lost = [], False
    for x in segment:
        y, one_lost = unsuffix_row(x, layer_index)
        out.append(y); lost = lost or one_lost
    return out, lost

def solve_one(generated, components, tables, unknown):
    positions = [i for i, x in enumerate(components) if x == unknown]
    if not positions:
        return None
    if {x for x in components if x not in tables} != {unknown}:
        return None
    known_len = sum(len(tables[x]) for x in components if x != unknown)
    residual = len(generated) - known_len
    if residual < 0 or residual % len(positions):
        raise RecoveryError(f"{unknown!r}: no exact repeated-layer width solution")
    width, cursor, candidate, lost0 = residual // len(positions), 0, None, None
    for layer_index, component in enumerate(components):
        if component == unknown:
            seg = generated[cursor:cursor + width]
            if len(seg) != width:
                raise RecoveryError(f"{unknown!r}: truncated candidate slice")
            normalized, lost = unsuffix_table(seg, layer_index)
            if candidate is None:
                candidate, lost0 = normalized, lost
            elif canon(candidate) != canon(normalized) or lost0 != lost:
                raise RecoveryError(f"{unknown!r}: generated occurrences disagree after exact canonicalization")
            cursor += width
        else:
            expected = project(tables[component], layer_index)
            actual = generated[cursor:cursor + len(expected)]
            if canon(actual) != canon(expected):
                raise RecoveryError(
                    f"generated layer {layer_index} disagrees with exact Material_CreateLayered projection of {component!r}"
                )
            cursor += len(expected)
    if cursor != len(generated) or candidate is None:
        raise RecoveryError(f"{unknown!r}: concatenation accounting failure")
    return candidate, positions, bool(lost0)

def build_recovery(*, material_root: Path, catalog_doc: dict, targets: list[str]):
    indexed, skipped = _index_oat_materials(material_root)
    catalog = catalog_doc.get("materials")
    if not isinstance(catalog, list) or not targets or len(set(targets)) != len(targets):
        raise RecoveryError("invalid catalog/target set")
    target_set = set(targets)
    present = sorted(target_set & set(indexed))
    if present:
        raise RecoveryError(f"targets unexpectedly have standalone OAT Materials: {present}")

    generated_rows, referenced = [], set()
    tokens, indices, normals, names, positions = (defaultdict(set), defaultdict(set), defaultdict(set), defaultdict(list), defaultdict(list))
    for catalog_row in catalog:
        name = str(catalog_row.get("name") or "")
        if not name.startswith("*"):
            continue
        try:
            parsed = parse_layered_material_name(name)
        except LayeredMaterialError as exc:
            raise RecoveryError(str(exc)) from exc
        storage = _storage_identity(name)
        source = indexed.get(storage)
        if source is None:
            raise RecoveryError(f"{name!r}: missing generated OAT Material {storage!r}")
        comps = [str(x["componentMaterial"]) for x in parsed["layers"]]
        referenced.update(comps)
        for layer in parsed["layers"]:
            c, li = str(layer["componentMaterial"]), int(layer["layerIndex"])
            tokens[c].add(str(layer["token"])); indices[c].add(int(layer["bspMaterialIndex"]))
            normals[c].add(bool(layer["expectedNormalMap"])); names[c].append(name); positions[c].append(li)
        generated_rows.append({"material": name, "storage": storage, "source": source, "textures": raw_textures(name, source), "components": comps})

    missing = sorted(x for x in referenced if x not in indexed)
    if missing != sorted(target_set):
        raise RecoveryError(f"target set is not exact standalone-missing set: observed={missing!r} supplied={sorted(target_set)!r}")
    tables = {x: raw_textures(x, indexed[x]) for x in referenced if x in indexed}
    recovered, lost_name_end, admission = {}, {}, defaultdict(list)

    while True:
        candidates = defaultdict(list); combined = {**tables, **recovered}
        for row in generated_rows:
            unresolved = sorted({x for x in row["components"] if x not in combined})
            if len(unresolved) != 1 or unresolved[0] not in target_set:
                continue
            u = unresolved[0]; solved = solve_one(row["textures"], row["components"], combined, u)
            if solved is None:
                continue
            table, pos, lost = solved
            candidates[u].append((table, lost, {
                "generatedMaterial": row["material"], "generatedStorageIdentity": row["storage"],
                "generatedSourceFile": row["source"]["relative"], "generatedSourceSha256": sha(row["source"]["raw"]),
                "unknownLayerPositions": pos, "candidateTextureTableSha256": sha(canon(table))}))
        promotions = 0
        for identity, rows in sorted(candidates.items()):
            if identity in recovered:
                continue
            if len({sha(canon(x[0])) for x in rows}) != 1 or len({x[1] for x in rows}) != 1:
                raise RecoveryError(f"{identity!r}: non-unique runtime-canonical candidate")
            recovered[identity], lost_name_end[identity] = rows[0][0], rows[0][1]
            admission[identity].extend(x[2] for x in rows); promotions += 1
        if not promotions:
            break
    unresolved = sorted(target_set - set(recovered))
    if unresolved:
        raise RecoveryError(f"could not uniquely recover targets {unresolved}")

    combined, final = {**tables, **recovered}, defaultdict(list)
    target_generated = exact_count = 0
    for row in generated_rows:
        rebuilt = []
        for li, component in enumerate(row["components"]):
            rebuilt.extend(project(combined[component], li))
        if canon(rebuilt) != canon(row["textures"]):
            raise RecoveryError(f"{row['material']!r}: full exact layered projection mismatch")
        exact_count += 1
        row_targets = sorted(set(row["components"]) & target_set)
        target_generated += bool(row_targets)
        for identity in row_targets:
            solved = solve_one(row["textures"], row["components"], {k:v for k,v in combined.items() if k != identity}, identity)
            if solved is None:
                raise RecoveryError(f"{row['material']!r}: target {identity!r} did not independently re-solve")
            candidate, pos, lost = solved
            if canon(candidate) != canon(recovered[identity]) or lost != lost_name_end[identity]:
                raise RecoveryError(f"{row['material']!r}: target {identity!r} independent candidate disagrees")
            final[identity].append({"generatedMaterial": row["material"], "unknownLayerPositions": pos,
                                    "candidateTextureTableSha256": sha(canon(candidate)), "independentFinalResolve": True})

    components = []
    for identity in targets:
        if len(normals[identity]) != 1 or len(indices[identity]) != 1:
            raise RecoveryError(f"{identity!r}: conflicting serialized component identity")
        expected_normal = next(iter(normals[identity]))
        has_normal = _has_real_normal_map({"doc": {"textures": recovered[identity]}})
        if has_normal != expected_normal:
            raise RecoveryError(f"{identity!r}: normal-map presence disagrees with n-marker")
        components.append({
            "identity": identity, "standaloneOatMaterialAvailable": False, "sourceStandaloneTextureTableRecovered": False,
            "recoveredTableKind": "layer-suffix-neutral post-Material_CreateLayered runtime component texture table",
            "fallbackSourceNameEndNotRecoverable": lost_name_end[identity], "bspMaterialIndex": next(iter(indices[identity])),
            "tokens": sorted(tokens[identity]), "layerPositions": sorted(positions[identity]), "expectedNormalMap": expected_normal,
            "recoveredHasRealNormalMap": has_normal, "textureCount": len(recovered[identity]),
            "textureTableSha256": sha(canon(recovered[identity])), "textures": recovered[identity],
            "generatedMaterialCount": len(set(names[identity])), "generatedLayerOccurrenceCount": len(names[identity]),
            "generatedMaterials": sorted(set(names[identity])), "fixedPointAdmissionEvidence": admission[identity],
            "recoveryEvidence": final[identity]})

    return {
        "format": FORMAT,
        "source": {"producer": Path(__file__).name, "materialRoot": str(material_root), "catalogFormat": catalog_doc.get("format"),
                   "catalogMap": catalog_doc.get("map"), "indexedOatMaterialCount": len(indexed),
                   "generatedCatalogMaterialCount": len(generated_rows), "skippedNonT6MaterialJsonCount": len(skipped)},
        "policy": {
            "recoveryEquation": "generated textures[] equals ordered exact Material_CreateLayered projection of component tables",
            "mipmapTransform": "nearest->linear only for colorMap/normalMap/specularMap",
            "argumentIdentityTransform": "layers 1..3 append ASCII layer digit to texture name/hash",
            "matureTransform": "isMatureContent recomputed from semantic/image; 2D/function/waterMap forced false",
            "copyElidedCanonicalization": "reverse only layer name suffix/hash; retain post-transform sampler/mature state"},
        "summary": {"targetCount": len(targets), "recoveredTargetCount": len(components), "standaloneMissingComponentCount": len(missing),
                    "generatedCatalogMaterialCount": len(generated_rows), "allGeneratedExactReconstructionCount": exact_count,
                    "targetBearingGeneratedMaterialCount": target_generated,
                    "targetGeneratedLayerOccurrenceCount": sum(len(names[x]) for x in targets)},
        "components": components,
        "proofBoundary": "Runtime-exact generated-layer texture dependencies only. No claim of missing standalone pre-layer samplerState/overwritten fallback nameEnd, TechniqueSet, constants, render state, owner, duplicate precedence, or layered shader/blend math."
    }

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("material_root", type=Path); ap.add_argument("catalog_json", type=Path); ap.add_argument("output_json", type=Path); ap.add_argument("--target", action="append", default=[])
    a = ap.parse_args(); doc = build_recovery(material_root=a.material_root, catalog_doc=json.loads(a.catalog_json.read_text()), targets=a.target)
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode(); a.output_json.parent.mkdir(parents=True, exist_ok=True); a.output_json.write_bytes(payload)
    print(json.dumps({"out": str(a.output_json), "bytes": len(payload), "sha256": sha(payload), **doc["summary"]}, indent=2, sort_keys=True)); return 0

if __name__ == "__main__":
    raise SystemExit(main())
