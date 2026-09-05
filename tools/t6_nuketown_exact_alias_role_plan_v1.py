#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import collections
import hashlib
import json
import zlib
from pathlib import Path

ROLE_SPECS = (
    ("colorMap", "baseColorTexture", 2),
    ("normalMap", "normalTexture", 5),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    raw = path.read_bytes()
    try:
        return json.loads(raw)
    except Exception:
        return json.loads(zlib.decompress(base64.b64decode(raw)).decode())


def retained_materials(proof: dict) -> set[str]:
    names = {m for model in proof["models"] for m in model["materials"]}
    return names


def load_oat_material(root: Path, name: str) -> tuple[Path, dict] | None:
    path = root / (name + ".json")
    if not path.is_file():
        return None
    doc = json.loads(path.read_text())
    if doc.get("_game") != "t6" or doc.get("_type") != "material":
        raise ValueError(f"{path}: expected OAT T6 material JSON")
    return path, doc


def first_semantic(textures: list[dict], semantic: str):
    return next(((i, row) for i, row in enumerate(textures) if str(row.get("semantic") or "") == semantic), None)


def count_roles(rows: list[dict]) -> dict:
    counts = collections.Counter(r["gltfRole"] for r in rows)
    return {
        "bindings": len(rows),
        "baseColorTexture": counts["baseColorTexture"],
        "normalTexture": counts["normalTexture"],
        "uniqueImages": len({r["image"] for r in rows}),
        "uniqueMaterials": len({r["material"] for r in rows}),
    }


def build(
    material_root: Path,
    proof_path: Path,
    alias_bank_path: Path,
    exact43_path: Path,
    out_path: Path,
    expected_materials: int = 344,
    expected_bindings: int = 78,
    expected_colors: int = 52,
    expected_normals: int = 26,
    expected_exact43_bindings: int = 41,
    expected_exact43_colors: int = 28,
    expected_exact43_normals: int = 13,
) -> dict:
    proof = load_json(proof_path)
    bank = load_json(alias_bank_path)
    exact43 = load_json(exact43_path)

    materials = retained_materials(proof)
    if len(materials) != expected_materials:
        raise ValueError(f"retained material count {len(materials)} != {expected_materials}")
    aliases = {row["name"]: row for row in bank["aliases"]}
    if len(aliases) != 81 or int(bank.get("conflictCount", -1)) != 0:
        raise ValueError("alias bank must contain 81 conflict-free identities")
    exact_names = {row["name"] for row in exact43["rows"]}
    if len(exact_names) != 43:
        raise ValueError(f"exact payload identity count {len(exact_names)} != 43")
    if not exact_names <= aliases.keys():
        raise ValueError("exact43 proof contains image identities outside alias bank")

    bindings: list[dict] = []
    first_semantic_rows: list[dict] = []
    non_alias_first: list[dict] = []
    unresolved: list[str] = []

    for material in sorted(materials):
        loaded = load_oat_material(material_root, material)
        if loaded is None:
            unresolved.append(material)
            continue
        path, doc = loaded
        textures = doc.get("textures", [])
        if not isinstance(textures, list):
            raise ValueError(f"{material}: textures is not a list")

        for oat_semantic, gltf_role, raw_semantic in ROLE_SPECS:
            hit = first_semantic(textures, oat_semantic)
            if hit is None:
                continue
            texture_index, texture = hit
            image = str(texture.get("image") or "")
            base = {
                "material": material,
                "materialJson": str(path),
                "textureIndex": texture_index,
                "oatSemantic": oat_semantic,
                "rawSemantic": raw_semantic,
                "gltfRole": gltf_role,
                "image": image,
                "samplerState": texture.get("samplerState"),
            }
            first_semantic_rows.append(base)

            alias = aliases.get(image)
            if alias is None:
                non_alias_first.append(base)
                continue

            # Independent fail-closed cross-check: the archived raw retail alias
            # record must agree with the OAT texture-table slot and semantic.
            if int(alias["semantic"]) != raw_semantic:
                raise ValueError(
                    f"{material} {gltf_role}: alias semantic {alias['semantic']} != {raw_semantic}"
                )
            if int(alias["slot"]) != texture_index:
                raise ValueError(
                    f"{material} {gltf_role}: alias slot {alias['slot']} != OAT texture index {texture_index}"
                )

            row = dict(base)
            row.update(
                {
                    "aliasHash": alias["hash"],
                    "aliasDataHash": alias["dataHash"],
                    "aliasBlock": alias["block"],
                    "aliasVirtualOffset": alias["virtualOffset"],
                    "aliasSuffix": alias["suffix"],
                    "baseIpakExact43": image in exact_names,
                    "aliasEvidence": alias.get("evidence", []),
                }
            )
            bindings.append(row)

    if unresolved:
        raise ValueError(f"missing exact OAT Material JSON for {len(unresolved)} retained materials: {unresolved}")

    exact_rows = [r for r in bindings if r["baseIpakExact43"]]
    remaining_rows = [r for r in bindings if not r["baseIpakExact43"]]
    all_counts = count_roles(bindings)
    exact_counts = count_roles(exact_rows)

    expected = {
        "bindings": expected_bindings,
        "baseColorTexture": expected_colors,
        "normalTexture": expected_normals,
    }
    for key, value in expected.items():
        if all_counts[key] != value:
            raise ValueError(f"alias-backed {key} {all_counts[key]} != {value}")
    expected43 = {
        "bindings": expected_exact43_bindings,
        "baseColorTexture": expected_exact43_colors,
        "normalTexture": expected_exact43_normals,
    }
    for key, value in expected43.items():
        if exact_counts[key] != value:
            raise ValueError(f"base.ipak exact43 {key} {exact_counts[key]} != {value}")

    report = {
        "format": "t6-nuketown-exact-alias-role-plan-v1",
        "source": {
            "materialProof": {"file": proof_path.name, "sha256": sha256_file(proof_path)},
            "aliasBank": {"file": alias_bank_path.name, "sha256": sha256_file(alias_bank_path)},
            "baseIpakExact43Proof": {"file": exact43_path.name, "sha256": sha256_file(exact43_path)},
            "materialRoot": str(material_root),
        },
        "retainedMaterialCount": len(materials),
        "resolvedRetainedMaterialCount": len(materials),
        "firstSemanticRoleCount": count_roles(first_semantic_rows),
        "aliasBackedFirstSemanticRoleCount": all_counts,
        "baseIpakExact43FirstSemanticRoleCount": exact_counts,
        "aliasBackedButNotBaseExact43Count": count_roles(remaining_rows),
        "aliasBankAvailabilityAtArchiveTime": bank.get("availability"),
        "bindings": bindings,
        "baseIpakExact43Bindings": exact_rows,
        "nonAliasFirstSemanticRoles": non_alias_first,
        "validation": {
            "all344RetainedMaterialsResolvedExactly": True,
            "firstSemanticOnly": True,
            "aliasSemanticMatchesRetailRole": True,
            "aliasSlotMatchesRetailTextureIndex": True,
            "sameNameFallbacks": 0,
            "filenameRoleInference": 0,
            "laterSlotSubstitutions": 0,
            "aliasConflicts": 0,
        },
        "proofBoundary": (
            "For every exact retained Material identity, select only the first retail OAT texture-table "
            "colorMap (raw semantic 2) and first normalMap (raw semantic 5), mirroring the historical v8 "
            "static applicator. A binding is emitted only when that exact first image is one of the 81 "
            "conflict-free packed-image aliases and the alias raw semantic and slot independently equal "
            "the selected retail role and texture index. Exact43 marks only identities independently "
            "validated from base.ipak by exact nameHash+dataHash, CRC29, IWI27 parse and dimensions."
        ),
    }
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--material-root", type=Path, required=True)
    ap.add_argument("--proof", type=Path, required=True)
    ap.add_argument("--alias-bank", type=Path, required=True)
    ap.add_argument("--exact43-proof", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expected-materials", type=int, default=344)
    ap.add_argument("--expected-bindings", type=int, default=78)
    ap.add_argument("--expected-colors", type=int, default=52)
    ap.add_argument("--expected-normals", type=int, default=26)
    ap.add_argument("--expected-exact43-bindings", type=int, default=41)
    ap.add_argument("--expected-exact43-colors", type=int, default=28)
    ap.add_argument("--expected-exact43-normals", type=int, default=13)
    args = ap.parse_args()
    report = build(
        args.material_root,
        args.proof,
        args.alias_bank,
        args.exact43_proof,
        args.out,
        args.expected_materials,
        args.expected_bindings,
        args.expected_colors,
        args.expected_normals,
        args.expected_exact43_bindings,
        args.expected_exact43_colors,
        args.expected_exact43_normals,
    )
    print(json.dumps({
        "retainedMaterialCount": report["retainedMaterialCount"],
        "aliasBackedFirstSemanticRoleCount": report["aliasBackedFirstSemanticRoleCount"],
        "baseIpakExact43FirstSemanticRoleCount": report["baseIpakExact43FirstSemanticRoleCount"],
        "validation": report["validation"],
    }, indent=2))


if __name__ == "__main__":
    main()
