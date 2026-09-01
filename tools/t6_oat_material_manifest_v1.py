#!/usr/bin/env python3
"""Build a T6 material texture manifest directly from OAT material JSON dumps.

Material identity is joined against the GfxWorld material catalog by exact
material name. OAT material names are derived from their relative path under the
materials root (e.g. materials/wpc/foo.json -> wpc/foo).

The OAT T6 material schema already exposes exact texture semantic, image asset,
and sampler state. This tool therefore does not infer roles from filenames or
table order. An explicit source texture extension maps an OAT image asset to
the staging basename (for example image `foo_n` + `.dds` -> `foo_n.dds`).

Generated/compound material identities are preserved but not auto-bound to a
standard preview until their compositor semantics are independently proven.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class OatMaterialManifestError(RuntimeError):
    pass


CORE_PREVIEW_ROLES = {
    "colorMap": "baseColorTexture",
    "normalMap": "normalTexture",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_compound_material_name(name: str) -> bool:
    return name.startswith("*") or "::" in name


def _source_texture_name(image: str, extension: str) -> str:
    if not image:
        raise OatMaterialManifestError("empty OAT image asset name")
    if "/" in image or "\\" in image or "\0" in image:
        raise OatMaterialManifestError(
            f"OAT image asset must be a basename for current texture staging: {image!r}"
        )
    if extension and not extension.startswith("."):
        raise OatMaterialManifestError(
            f"source texture extension must be empty or start with '.': {extension!r}"
        )
    return image + extension


def _index_oat_materials(material_root: Path) -> tuple[dict[str, dict], list[dict]]:
    if not material_root.is_dir():
        raise OatMaterialManifestError(f"material root is not a directory: {material_root}")

    indexed: dict[str, dict] = {}
    skipped: list[dict] = []
    for path in sorted(material_root.rglob("*.json")):
        relative = path.relative_to(material_root)
        name = relative.with_suffix("").as_posix()
        raw = path.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise OatMaterialManifestError(f"invalid JSON {path}: {exc}") from exc

        if doc.get("_game") != "t6" or doc.get("_type") != "material":
            skipped.append(
                {
                    "file": str(path),
                    "relative": relative.as_posix(),
                    "game": doc.get("_game"),
                    "type": doc.get("_type"),
                    "reason": "not a T6 material JSON",
                }
            )
            continue
        if name in indexed:
            raise OatMaterialManifestError(f"duplicate OAT material identity {name!r}")
        indexed[name] = {
            "path": path,
            "relative": relative.as_posix(),
            "raw": raw,
            "doc": doc,
        }
    return indexed, skipped


def build_manifest(
    *,
    material_root: Path,
    catalog_doc: dict,
    source_texture_extension: str,
    allow_missing_materials: bool = False,
) -> dict:
    indexed, skipped = _index_oat_materials(material_root)

    catalog_entries = catalog_doc.get("materials", [])
    if not isinstance(catalog_entries, list):
        raise OatMaterialManifestError("material catalog missing materials[]")

    materials: list[dict] = []
    missing: list[dict] = []
    role_counts: dict[str, int] = {}
    standard_binding_count = 0
    compound_count = 0
    ambiguous_binding_count = 0

    seen_catalog_names: set[str] = set()
    for catalog_entry in sorted(catalog_entries, key=lambda item: int(item["index"])):
        material_index = int(catalog_entry["index"])
        name = str(catalog_entry.get("name") or "")
        if not name:
            raise OatMaterialManifestError(
                f"catalog material {material_index} has empty name"
            )
        if name in seen_catalog_names:
            raise OatMaterialManifestError(f"duplicate catalog material name {name!r}")
        seen_catalog_names.add(name)

        source = indexed.get(name)
        if source is None:
            record = {
                "materialIndex": material_index,
                "material": name,
                "surfacePointerHex": catalog_entry.get("surfacePointerHex"),
            }
            missing.append(record)
            if not allow_missing_materials:
                raise OatMaterialManifestError(
                    f"no exact OAT material JSON for catalog material {name!r}"
                )
            continue

        doc = source["doc"]
        textures = doc.get("textures", [])
        if not isinstance(textures, list):
            raise OatMaterialManifestError(f"{name!r}: textures is not a list")

        normalized_textures: list[dict] = []
        candidates: dict[str, list[dict]] = {
            target: [] for target in CORE_PREVIEW_ROLES.values()
        }
        for texture_index, texture in enumerate(textures):
            image = str(texture.get("image") or "")
            semantic = str(texture.get("semantic") or "")
            role_name = str(texture.get("name") or "")
            role = semantic or role_name
            if not role:
                raise OatMaterialManifestError(
                    f"{name!r} texture {texture_index} has no semantic/name"
                )
            source_texture = _source_texture_name(image, source_texture_extension)
            dependency = {
                "role": role,
                "semantic": semantic or None,
                "name": role_name or None,
                "textureIndex": texture_index,
                "imageAsset": image,
                "sourceTexture": source_texture,
                "samplerState": texture.get("samplerState"),
                "isMatureContent": texture.get("isMatureContent"),
                "compositors": [],
            }
            normalized_textures.append(dependency)
            role_counts[role] = role_counts.get(role, 0) + 1
            target = CORE_PREVIEW_ROLES.get(semantic)
            if target is not None:
                candidates[target].append(dependency)

        is_compound = _is_compound_material_name(name)
        if is_compound:
            compound_count += 1

        preview: dict[str, dict] = {}
        blocked: list[dict] = []
        for target in CORE_PREVIEW_ROLES.values():
            options = candidates[target]
            if not options:
                continue
            if is_compound:
                for option in options:
                    blocked.append(
                        {
                            "role": option["role"],
                            "reason": (
                                "generated/compound material identity; compositor "
                                "semantics are not source-closed"
                            ),
                            "texture": option,
                        }
                    )
                continue
            if len(options) != 1:
                ambiguous_binding_count += 1
                for option in options:
                    blocked.append(
                        {
                            "role": option["role"],
                            "reason": (
                                "multiple exact OAT semantic candidates for one "
                                "standard preview binding"
                            ),
                            "texture": option,
                        }
                    )
                continue
            option = options[0]
            preview[target] = {
                "role": option["role"],
                "semantic": option["semantic"],
                "textureIndex": option["textureIndex"],
                "imageAsset": option["imageAsset"],
                "sourceTexture": option["sourceTexture"],
                "samplerState": option["samplerState"],
            }

        for dependency in normalized_textures:
            semantic = dependency.get("semantic")
            if semantic in CORE_PREVIEW_ROLES:
                target = CORE_PREVIEW_ROLES[semantic]
                if (
                    target in preview
                    and preview[target]["textureIndex"] == dependency["textureIndex"]
                ):
                    continue
            if not any(
                item.get("texture", {}).get("textureIndex")
                == dependency["textureIndex"]
                for item in blocked
            ):
                blocked.append(
                    {
                        "role": dependency["role"],
                        "reason": (
                            "exact OAT semantic retained; no standard preview "
                            "conversion policy"
                        ),
                        "texture": dependency,
                    }
                )

        standard_binding_count += len(preview)
        materials.append(
            {
                "materialIndex": material_index,
                "material": name,
                "layered": None,
                "compoundIdentity": is_compound,
                "compositors": [],
                "layers": [
                    {
                        "layerIndex": 0,
                        "layer": name,
                        "textures": normalized_textures,
                    }
                ],
                "standardPreview": preview,
                "standardPreviewBlocked": blocked,
                "sourceOatMaterial": {
                    "file": source["relative"],
                    "bytes": len(source["raw"]),
                    "sha256": _sha256(source["raw"]),
                    "schema": doc.get("$schema"),
                    "version": doc.get("_version"),
                    "techniqueSet": doc.get("techniqueSet"),
                    "cameraRegion": doc.get("cameraRegion"),
                    "gameFlags": doc.get("gameFlags"),
                    "stateFlags": doc.get("stateFlags"),
                    "surfaceFlags": doc.get("surfaceFlags"),
                    "surfaceTypeBits": doc.get("surfaceTypeBits"),
                    "contents": doc.get("contents"),
                    "textureAtlas": doc.get("textureAtlas"),
                },
            }
        )

    return {
        "format": "t6-material-texture-manifest-v1",
        "source": {
            "kind": "OpenAssetTools material.v1 JSON",
            "materialRoot": str(material_root),
            "catalogMaterialCount": len(catalog_entries),
            "indexedOatMaterialCount": len(indexed),
            "sourceTextureExtension": source_texture_extension,
        },
        "policy": {
            "materialJoin": "exact catalog name == relative OAT material JSON path",
            "roleSelection": "OAT textures[].semantic only; never filename/table order",
            "sourceTextureMapping": (
                "sourceTexture = OAT image asset + explicitly configured extension"
            ),
            "compoundMaterialPreview": (
                "blocked for names beginning '*' or containing '::' until compositor "
                "semantics are source-closed"
            ),
            "standardPreviewRoles": CORE_PREVIEW_ROLES,
            "samplerState": "preserved exactly in manifest; not silently approximated",
        },
        "stats": {
            "materialCount": len(materials),
            "missingMaterialCount": len(missing),
            "compoundMaterialCount": compound_count,
            "textureDependencyCount": sum(role_counts.values()),
            "roleCounts": dict(sorted(role_counts.items())),
            "standardPreviewBindingCount": standard_binding_count,
            "ambiguousStandardPreviewBindings": ambiguous_binding_count,
            "skippedNonT6MaterialJsonCount": len(skipped),
        },
        "materials": materials,
        "missingMaterials": missing,
        "skippedFiles": skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_root", type=Path)
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--source-texture-extension", required=True)
    parser.add_argument("--allow-missing-materials", action="store_true")
    args = parser.parse_args()

    catalog_doc = json.loads(args.catalog_json.read_text(encoding="utf-8"))
    doc = build_manifest(
        material_root=args.material_root,
        catalog_doc=catalog_doc,
        source_texture_extension=args.source_texture_extension,
        allow_missing_materials=args.allow_missing_materials,
    )
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output_json.write_bytes(payload)
    print(
        json.dumps(
            {
                "out": str(args.output_json),
                "bytes": len(payload),
                "sha256": _sha256(payload),
                **doc["stats"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
