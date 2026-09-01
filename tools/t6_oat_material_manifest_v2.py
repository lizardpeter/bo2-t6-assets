#!/usr/bin/env python3
"""Build a T6 material texture manifest directly from OAT material JSON dumps.

Ordinary Material identities join by exact relative OAT path. Treyarch generated
layered identities such as ``*22n_14(wpc/base:wpc/decal)`` are source-closed
far enough to reconstruct their component dependency graph without requiring a
standalone generated JSON:

- decimal tokens are BSP material indices;
- ``n`` means that component must have a real normal map;
- at most four components are allowed;
- Material_CreateLayered concatenates the component texture tables.

The adapter reconstructs that exact dependency ordering from the component OAT
Material JSONs, while still refusing to invent the layered technique/shader
blend math. Therefore generated materials keep ``standardPreview`` empty and
all component dependencies remain explicit reconstruction metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_layered_material_name_v1 import LayeredMaterialError, parse_layered_material_name


class OatMaterialManifestError(RuntimeError):
    pass


CORE_PREVIEW_ROLES = {
    "colorMap": "baseColorTexture",
    "normalMap": "normalTexture",
}

IDENTITY_NORMAL_IMAGE = "$identitynormalmap"


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


def _source_record(source: dict) -> dict:
    doc = source["doc"]
    return {
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
        "layeredSurfaceTypes": doc.get("layeredSurfaceTypes"),
        "contents": doc.get("contents"),
        "textureAtlas": doc.get("textureAtlas"),
    }


def _normalize_textures(
    material_name: str,
    source: dict,
    source_texture_extension: str,
    *,
    first_texture_index: int = 0,
) -> list[dict]:
    textures = source["doc"].get("textures", [])
    if not isinstance(textures, list):
        raise OatMaterialManifestError(f"{material_name!r}: textures is not a list")

    normalized: list[dict] = []
    for local_index, texture in enumerate(textures):
        image = str(texture.get("image") or "")
        semantic = str(texture.get("semantic") or "")
        role_name = str(texture.get("name") or "")
        role = semantic or role_name
        if not role:
            raise OatMaterialManifestError(
                f"{material_name!r} texture {local_index} has no semantic/name"
            )
        normalized.append(
            {
                "role": role,
                "semantic": semantic or None,
                "name": role_name or None,
                "textureIndex": first_texture_index + local_index,
                "sourceTextureIndex": local_index,
                "imageAsset": image,
                "sourceTexture": _source_texture_name(image, source_texture_extension),
                "samplerState": texture.get("samplerState"),
                "isMatureContent": texture.get("isMatureContent"),
                "compositors": [],
            }
        )
    return normalized


def _has_real_normal_map(source: dict) -> bool:
    textures = source["doc"].get("textures", [])
    if not isinstance(textures, list):
        return False
    return any(
        str(texture.get("semantic") or "") == "normalMap"
        and str(texture.get("image") or "") != IDENTITY_NORMAL_IMAGE
        for texture in textures
    )


def _ordinary_material(
    *,
    material_index: int,
    name: str,
    catalog_entry: dict,
    source: dict,
    source_texture_extension: str,
) -> tuple[dict, dict[str, int], int, int]:
    textures = _normalize_textures(name, source, source_texture_extension)
    role_counts: dict[str, int] = {}
    candidates: dict[str, list[dict]] = {
        target: [] for target in CORE_PREVIEW_ROLES.values()
    }
    for dependency in textures:
        role = dependency["role"]
        role_counts[role] = role_counts.get(role, 0) + 1
        semantic = dependency.get("semantic") or ""
        target = CORE_PREVIEW_ROLES.get(semantic)
        if target is not None:
            candidates[target].append(dependency)

    preview: dict[str, dict] = {}
    blocked: list[dict] = []
    ambiguous = 0
    for target in CORE_PREVIEW_ROLES.values():
        options = candidates[target]
        if not options:
            continue
        if len(options) != 1:
            ambiguous += 1
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

    for dependency in textures:
        semantic = dependency.get("semantic")
        if semantic in CORE_PREVIEW_ROLES:
            target = CORE_PREVIEW_ROLES[semantic]
            if (
                target in preview
                and preview[target]["textureIndex"] == dependency["textureIndex"]
            ):
                continue
        if not any(
            item.get("texture", {}).get("textureIndex") == dependency["textureIndex"]
            for item in blocked
        ):
            blocked.append(
                {
                    "role": dependency["role"],
                    "reason": (
                        "exact OAT semantic retained; no standard preview conversion policy"
                    ),
                    "texture": dependency,
                }
            )

    return (
        {
            "materialIndex": material_index,
            "material": name,
            "surfacePointerHex": catalog_entry.get("surfacePointerHex"),
            "layered": False,
            "compoundIdentity": False,
            "compositors": [],
            "layers": [
                {
                    "layerIndex": 0,
                    "layer": name,
                    "textures": textures,
                    "sourceOatMaterial": _source_record(source),
                }
            ],
            "standardPreview": preview,
            "standardPreviewBlocked": blocked,
            "sourceOatMaterial": _source_record(source),
        },
        role_counts,
        len(preview),
        ambiguous,
    )


def _compound_material(
    *,
    material_index: int,
    name: str,
    catalog_entry: dict,
    indexed: dict[str, dict],
    source_texture_extension: str,
) -> tuple[dict, dict[str, int], int, bool]:
    try:
        identity = parse_layered_material_name(name)
    except LayeredMaterialError as exc:
        raise OatMaterialManifestError(f"{name!r}: {exc}") from exc

    layers: list[dict] = []
    all_textures: list[dict] = []
    role_counts: dict[str, int] = {}
    source_components: list[dict] = []
    next_texture_index = 0

    for layer_identity in identity["layers"]:
        component = layer_identity["componentMaterial"]
        component_source = indexed.get(component)
        if component_source is None:
            raise OatMaterialManifestError(
                f"{name!r}: missing exact OAT component material {component!r}"
            )

        has_normal = _has_real_normal_map(component_source)
        expected_normal = bool(layer_identity["expectedNormalMap"])
        if expected_normal != has_normal:
            raise OatMaterialManifestError(
                f"{name!r} layer {layer_identity['layerIndex']} {component!r}: "
                f"generated token expects real normal map={expected_normal}, "
                f"but OAT component Material_HasNormalMap equivalent={has_normal}"
            )

        textures = _normalize_textures(
            component,
            component_source,
            source_texture_extension,
            first_texture_index=next_texture_index,
        )
        next_texture_index += len(textures)
        for dependency in textures:
            role = dependency["role"]
            role_counts[role] = role_counts.get(role, 0) + 1
        all_textures.extend(textures)

        source_record = _source_record(component_source)
        source_components.append(
            {
                "layerIndex": int(layer_identity["layerIndex"]),
                "token": layer_identity["token"],
                "bspMaterialIndex": int(layer_identity["bspMaterialIndex"]),
                "expectedNormalMap": expected_normal,
                "componentMaterial": component,
                "sourceOatMaterial": source_record,
            }
        )
        layers.append(
            {
                "layerIndex": int(layer_identity["layerIndex"]),
                "layer": component,
                "token": layer_identity["token"],
                "bspMaterialIndex": int(layer_identity["bspMaterialIndex"]),
                "expectedNormalMap": expected_normal,
                "explicitNoNormalMarker": bool(
                    layer_identity.get("explicitNoNormalMarker")
                ),
                "textures": textures,
                "sourceOatMaterial": source_record,
            }
        )

    # If an exact generated JSON happens to exist, archive it and verify the
    # source-closed invariant that its texture count equals the concatenated
    # component texture counts. Windows OAT output normally cannot use the
    # generated name as a path, so this is optional rather than required.
    generated_source = indexed.get(name)
    generated_record = _source_record(generated_source) if generated_source else None
    if generated_source is not None:
        generated_textures = generated_source["doc"].get("textures", [])
        if not isinstance(generated_textures, list):
            raise OatMaterialManifestError(f"{name!r}: generated textures is not a list")
        if len(generated_textures) != len(all_textures):
            raise OatMaterialManifestError(
                f"{name!r}: exact generated OAT texture count {len(generated_textures)} "
                f"!= component concatenation {len(all_textures)}"
            )

    blocked = [
        {
            "role": dependency["role"],
            "reason": (
                "layered Material_CreateLayered dependency retained; exact layered "
                "technique/shader composition is not representable as core glTF preview"
            ),
            "texture": dependency,
        }
        for dependency in all_textures
    ]

    return (
        {
            "materialIndex": material_index,
            "material": name,
            "surfacePointerHex": catalog_entry.get("surfacePointerHex"),
            "layered": True,
            "compoundIdentity": True,
            "compoundIdentityDecoded": identity,
            "compositors": [],
            "layers": layers,
            "standardPreview": {},
            "standardPreviewBlocked": blocked,
            "sourceOatMaterial": generated_record,
            "sourceOatComponents": source_components,
            "reconstruction": {
                "method": "source-closed Material_LoadLayered component grammar",
                "textureTable": "component texture tables concatenated in layer order",
                "textureCount": len(all_textures),
                "normalExpectationValidation": "all layers matched",
                "layeredTechniqueShader": "pending source closure; no preview blend invented",
            },
        },
        role_counts,
        len(identity["layers"]),
        generated_source is not None,
    )


def build_manifest(
    *,
    material_root: Path,
    catalog_doc: dict,
    source_texture_extension: str,
    allow_missing_materials: bool = False,
) -> dict:
    if source_texture_extension and not source_texture_extension.startswith("."):
        raise OatMaterialManifestError(
            f"source texture extension must be empty or start with '.': {source_texture_extension!r}"
        )
    indexed, skipped = _index_oat_materials(material_root)

    catalog_entries = catalog_doc.get("materials", [])
    if not isinstance(catalog_entries, list):
        raise OatMaterialManifestError("material catalog missing materials[]")

    materials: list[dict] = []
    missing: list[dict] = []
    role_counts: dict[str, int] = {}
    standard_binding_count = 0
    compound_count = 0
    reconstructed_compound_count = 0
    exact_generated_compound_json_count = 0
    compound_layer_validation_count = 0
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

        is_compound = _is_compound_material_name(name)
        if is_compound and name.startswith("*"):
            compound_count += 1
            try:
                record, local_roles, validated_layers, has_exact_generated = _compound_material(
                    material_index=material_index,
                    name=name,
                    catalog_entry=catalog_entry,
                    indexed=indexed,
                    source_texture_extension=source_texture_extension,
                )
            except OatMaterialManifestError as exc:
                missing_record = {
                    "materialIndex": material_index,
                    "material": name,
                    "surfacePointerHex": catalog_entry.get("surfacePointerHex"),
                    "reason": str(exc),
                }
                missing.append(missing_record)
                if not allow_missing_materials:
                    raise
                continue
            reconstructed_compound_count += 1
            exact_generated_compound_json_count += int(has_exact_generated)
            compound_layer_validation_count += validated_layers
            materials.append(record)
            for role, count in local_roles.items():
                role_counts[role] = role_counts.get(role, 0) + count
            continue

        if is_compound:
            missing_record = {
                "materialIndex": material_index,
                "material": name,
                "surfacePointerHex": catalog_entry.get("surfacePointerHex"),
                "reason": "unsupported compound identity syntax",
            }
            missing.append(missing_record)
            if not allow_missing_materials:
                raise OatMaterialManifestError(
                    f"unsupported compound material identity {name!r}"
                )
            continue

        source = indexed.get(name)
        if source is None:
            record = {
                "materialIndex": material_index,
                "material": name,
                "surfacePointerHex": catalog_entry.get("surfacePointerHex"),
                "reason": "no exact OAT material JSON",
            }
            missing.append(record)
            if not allow_missing_materials:
                raise OatMaterialManifestError(
                    f"no exact OAT material JSON for catalog material {name!r}"
                )
            continue

        record, local_roles, bindings, ambiguous = _ordinary_material(
            material_index=material_index,
            name=name,
            catalog_entry=catalog_entry,
            source=source,
            source_texture_extension=source_texture_extension,
        )
        materials.append(record)
        standard_binding_count += bindings
        ambiguous_binding_count += ambiguous
        for role, count in local_roles.items():
            role_counts[role] = role_counts.get(role, 0) + count

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
            "compoundMaterialDependencies": (
                "source-closed *index[n]_... grammar resolves exact component OAT "
                "materials; component texture tables concatenate in layer order"
            ),
            "compoundNormalValidation": (
                "n marker must equal Material_HasNormalMap equivalent; "
                "$identitynormalmap does not count as a real normal map"
            ),
            "compoundMaterialPreview": (
                "blocked until layered technique/shader composition is source-closed"
            ),
            "standardPreviewRoles": CORE_PREVIEW_ROLES,
            "samplerState": "preserved exactly in manifest; not silently approximated",
        },
        "stats": {
            "materialCount": len(materials),
            "missingMaterialCount": len(missing),
            "compoundMaterialCount": compound_count,
            "reconstructedCompoundMaterialCount": reconstructed_compound_count,
            "exactGeneratedCompoundJsonCount": exact_generated_compound_json_count,
            "compoundLayerNormalValidationCount": compound_layer_validation_count,
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
