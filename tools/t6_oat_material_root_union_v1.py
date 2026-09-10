#!/usr/bin/env python3
"""Build a fail-closed union of exact OAT Material JSON roots.

This is intentionally not an XAsset precedence resolver. For every required
OAT Material dump identity:

- one physical owner -> admit it;
- multiple owners with byte-identical JSON -> admit one and record all owners;
- multiple owners with byte-different JSON -> fail closed;
- no physical owner -> fail closed.

When a Nuketown world catalog is supplied, required identities are source-derived
from every catalog Material. Ordinary asset names map directly to OAT relative
Material paths. Treyarch generated ``*...(...)`` Materials use the exact pinned
OpenAssetTools MaterialCommon::GetFileNameForAssetName transform:

- replace ``*`` with ``_``;
- truncate at the first ``(``;
- prefix ``generated/``.

Layer component names remain explicit graph metadata, but are not required to be
standalone XAssets. This matters for component-only BSP Materials whose texture
tables are already present in the exact synthesized generated Material dump.

Unrelated dependency-zone Material duplicates are deliberately ignored. This
avoids inventing retail client precedence where no current production dependency
requires it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from t6_layered_material_name_v1 import LayeredMaterialError, parse_layered_material_name

FORMAT = "t6-oat-material-root-union-v1"
OAT_COMMIT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"
OAT_MATERIAL_COMMON_PATH = "src/ObjCommon/Material/MaterialCommon.cpp"


class UnionError(RuntimeError):
    def __init__(self, message: str, diagnostic: dict | None = None):
        super().__init__(message)
        self.diagnostic = diagnostic


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity_from_relative(rel: str) -> str:
    path = Path(rel)
    if path.suffix != ".json":
        raise UnionError(f"Material path is not JSON: {rel!r}")
    return path.with_suffix("").as_posix()


def oat_dump_identity(asset_name: str) -> str:
    """Return the exact Material-root-relative identity used by pinned OAT."""
    if not asset_name:
        raise UnionError("empty Material asset name")
    if not asset_name.startswith("*"):
        return asset_name
    sanitized = asset_name.replace("*", "_")
    parenthesis = sanitized.find("(")
    if parenthesis >= 0:
        sanitized = sanitized[:parenthesis]
    if not sanitized:
        raise UnionError(f"generated Material {asset_name!r} maps to empty OAT identity")
    return f"generated/{sanitized}"


def index_root(label: str, root: Path) -> dict[str, dict]:
    if not root.is_dir():
        raise UnionError(f"root {label!r} is not a directory: {root}")
    out = {}
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise UnionError(f"{label}:{rel}: invalid JSON: {exc}") from exc
        if doc.get("_game") != "t6" or doc.get("_type") != "material":
            continue
        identity = identity_from_relative(rel)
        if identity in out:
            raise UnionError(f"{label}: duplicate Material identity {identity!r}")
        out[identity] = {
            "label": label,
            "path": path,
            "relative": rel,
            "identity": identity,
            "bytes": len(raw),
            "sha256": sha256(raw),
            "raw": raw,
        }
    return out


def required_from_catalog(path: Path) -> tuple[set[str], dict]:
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise UnionError(f"cannot parse required catalog {path}: {exc}") from exc
    rows = doc.get("materials")
    if not isinstance(rows, list) or not rows:
        raise UnionError("required catalog lacks materials[]")

    required: set[str] = set()
    catalog_names: set[str] = set()
    ordinary: set[str] = set()
    generated: set[str] = set()
    generated_storage: set[str] = set()
    components: set[str] = set()
    component_only: set[str] = set()
    storage_to_catalog: dict[str, str] = {}

    for ordinal, row in enumerate(rows):
        name = str(row.get("name") or "")
        if not name:
            raise UnionError(f"catalog row {ordinal} has empty Material name")
        if name in catalog_names:
            raise UnionError(f"duplicate catalog Material identity {name!r}")
        catalog_names.add(name)

        storage_identity = oat_dump_identity(name)
        previous = storage_to_catalog.get(storage_identity)
        if previous is not None and previous != name:
            raise UnionError(
                "distinct catalog Materials collide under pinned OAT filename transform: "
                f"{previous!r}, {name!r} -> {storage_identity!r}"
            )
        storage_to_catalog[storage_identity] = name
        required.add(storage_identity)

        if name.startswith("*"):
            generated.add(name)
            generated_storage.add(storage_identity)
            try:
                parsed = parse_layered_material_name(name)
            except LayeredMaterialError as exc:
                raise UnionError(f"catalog generated Material {name!r}: {exc}") from exc
            for layer in parsed["layers"]:
                components.add(str(layer["componentMaterial"]))
        else:
            ordinary.add(name)

    component_only = components - ordinary
    return required, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": sha256(raw),
        "catalogMaterialCount": len(rows),
        "ordinaryCatalogMaterialCount": len(ordinary),
        "generatedCatalogMaterialCount": len(generated),
        "generatedOatStorageIdentityCount": len(generated_storage),
        "generatedComponentMaterialCount": len(components),
        "componentOnlyMaterialIdentityCount": len(component_only),
        "componentOnlyMaterialIdentities": sorted(component_only),
        "requiredPhysicalMaterialIdentityCount": len(required),
        "oatMaterialFilenameReference": {
            "repository": "Laupetin/OpenAssetTools",
            "commit": OAT_COMMIT,
            "path": OAT_MATERIAL_COMMON_PATH,
            "rule": "ordinary name unchanged; generated '*' -> '_', truncate at '(', prefix generated/",
        },
    }


def build(
    roots: list[tuple[str, Path]],
    out_root: Path,
    required: set[str] | None = None,
    required_source: dict | None = None,
) -> dict:
    if not roots:
        raise UnionError("no Material roots supplied")
    indexed = {label: index_root(label, root) for label, root in roots}
    all_identities = set().union(*(set(root) for root in indexed.values()))
    target = set(all_identities if required is None else required)
    if not target:
        raise UnionError("required Material identity set is empty")

    missing = []
    divergent = []
    rows = []
    out_root.mkdir(parents=True, exist_ok=True)
    byte_identical_duplicate_count = 0
    single_owner_count = 0
    for identity in sorted(target):
        copies = [indexed[label][identity] for label in sorted(indexed) if identity in indexed[label]]
        if not copies:
            missing.append(identity)
            continue
        shas = {row["sha256"] for row in copies}
        owners = [row["label"] for row in copies]
        if len(shas) != 1:
            divergent.append({
                "identity": identity,
                "owners": owners,
                "copies": [
                    {"owner": row["label"], "bytes": row["bytes"], "sha256": row["sha256"]}
                    for row in copies
                ],
            })
            continue
        selected = copies[0]
        dst = out_root / selected["relative"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(selected["raw"])
        if dst.read_bytes() != selected["raw"]:
            raise UnionError(f"write/readback mismatch for {identity}")
        if len(copies) > 1:
            byte_identical_duplicate_count += 1
        else:
            single_owner_count += 1
        rows.append({
            "identity": identity,
            "relative": selected["relative"],
            "owners": owners,
            "ownerCount": len(copies),
            "bytes": selected["bytes"],
            "sha256": selected["sha256"],
            "byteIdenticalAcrossOwners": True,
        })

    summary = {
        "rootCount": len(roots),
        "physicalMaterialJsonCount": sum(len(x) for x in indexed.values()),
        "allAvailableUniqueMaterialIdentityCount": len(all_identities),
        "requiredMaterialIdentityCount": len(target),
        "admittedRequiredMaterialIdentityCount": len(rows),
        "missingRequiredMaterialIdentityCount": len(missing),
        "singleOwnerRequiredIdentityCount": single_owner_count,
        "multipleOwnerRequiredIdentityCount": sum(1 for row in rows if row["ownerCount"] > 1) + len(divergent),
        "byteIdenticalMultipleOwnerRequiredIdentityCount": byte_identical_duplicate_count,
        "divergentMultipleOwnerRequiredIdentityCount": len(divergent),
    }
    doc = {
        "format": FORMAT,
        "authoritative": not missing and not divergent,
        "summary": summary,
        "requiredSource": required_source,
        "roots": [
            {"label": label, "path": str(root), "materialJsonCount": len(indexed[label])}
            for label, root in roots
        ],
        "materials": rows,
        "missing": missing,
        "divergent": divergent,
        "proofBoundary": (
            "No runtime owner priority is inferred. Only source-derived required OAT storage identities are considered when a catalog is supplied. Ordinary catalog names map directly; generated catalog names map through the exact pinned OpenAssetTools MaterialCommon filename transform. A required identity is admitted only when it has one physical owner or every supplied owner is byte-identical. Missing or byte-divergent required identities are hard blockers; component names are graph metadata and are not assumed to be standalone XAssets."
        ),
    }
    if missing or divergent:
        detail = []
        if missing:
            detail.append(f"missing={len(missing)} first={missing[0]!r}")
        if divergent:
            first = divergent[0]
            detail.append(f"divergent={len(divergent)} first={first['identity']!r} owners={first['owners']}")
        raise UnionError("required Material union failed: " + "; ".join(detail), diagnostic=doc)
    return doc


def write_manifest(path: Path, doc: dict) -> bytes:
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", required=True, help="LABEL=PATH")
    ap.add_argument("--required-catalog", type=Path)
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    args = ap.parse_args()
    roots = []
    labels = set()
    for spec in args.root:
        if "=" not in spec:
            raise UnionError(f"invalid --root {spec!r}; expected LABEL=PATH")
        label, raw_path = spec.split("=", 1)
        if not label or label in labels:
            raise UnionError(f"empty/duplicate root label {label!r}")
        labels.add(label)
        roots.append((label, Path(raw_path)))

    required = None
    required_source = None
    if args.required_catalog:
        required, required_source = required_from_catalog(args.required_catalog)

    try:
        doc = build(roots, args.out_root, required, required_source)
    except UnionError as exc:
        if exc.diagnostic is not None:
            payload = write_manifest(args.manifest, exc.diagnostic)
            summary = exc.diagnostic["summary"]
            print("MATERIAL_UNION_FAILURE_SUMMARY " + json.dumps(summary, sort_keys=True))
            for identity in exc.diagnostic["missing"]:
                print("MATERIAL_UNION_MISSING " + json.dumps({"identity": identity}, sort_keys=True))
            for row in exc.diagnostic["divergent"]:
                print("MATERIAL_UNION_DIVERGENT " + json.dumps(row, sort_keys=True))
            failure = {
                "manifest": str(args.manifest),
                "bytes": len(payload),
                "sha256": sha256(payload),
                **summary,
                "missing": exc.diagnostic["missing"],
                "divergent": exc.diagnostic["divergent"],
            }
            print("MATERIAL_UNION_FAILURE " + json.dumps(failure, sort_keys=True))
        if args.out_root.exists():
            shutil.rmtree(args.out_root)
        raise
    payload = write_manifest(args.manifest, doc)
    print(json.dumps({"manifest": str(args.manifest), "bytes": len(payload), "sha256": sha256(payload), **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
