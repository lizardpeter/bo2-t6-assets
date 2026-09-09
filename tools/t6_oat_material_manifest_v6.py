#!/usr/bin/env python3
"""T6 OAT material manifest v6: exact generated runtime texture authority.

v4/v5 remain historical render-state / ordinary-preview layers. v6 closes a
separate production gap: pinned OAT writes Treyarch generated Materials such as
``*22n_14(wpc/base:wpc/decal)`` under ``generated/_22n_14.json``. The exact
synthesized JSON ``textures[]`` table is the production dependency authority.

Parsed component names remain graph metadata. When every standalone component
JSON exists, v6 additionally requires exact equality between generated
``textures[]`` and the component ``textures[]`` arrays concatenated in layer
order and validates each normal marker. When standalone component evidence is
absent, v6 records that absence and never invents a component texture boundary.

The exact v4 decoded render-state archive and v5 ordinary shader-role preview
promotion are then applied to this corrected base representation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_layered_material_name_v1 import LayeredMaterialError, parse_layered_material_name
from t6_oat_image_filename_v1 import (
    OatImageFilenameError,
    oat_image_relative_path,
    oat_image_staging_basename,
)
from t6_oat_material_manifest_v2 import (
    CORE_PREVIEW_ROLES,
    OatMaterialManifestError,
    _has_real_normal_map,
    _index_oat_materials,
    _normalize_textures,
    _ordinary_material,
    _source_record,
)
from t6_oat_material_manifest_v4 import (
    _canonical,
    _load_oat_materials,
    _source_identity,
    _state_archive,
)
from t6_oat_material_manifest_v5 import _promote

PRODUCER = "t6_oat_material_manifest_v6.py"
OAT_MATERIAL_COMMIT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"
OAT_MATERIAL_COMMON_PATH = "src/ObjCommon/Material/MaterialCommon.cpp"
OAT_IMAGE_COMMIT = "7d027e8f89118196713e955b0e11f8404149c54d"
OAT_IMAGE_COMMON_PATH = "src/ObjCommon/Image/ImageCommon.cpp"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_compound(name: str) -> bool:
    return name.startswith("*") or "::" in name


def _storage_identity(name: str) -> str:
    if not name:
        raise OatMaterialManifestError("empty Material asset name")
    if not name.startswith("*"):
        return name
    sanitized = name.replace("*", "_")
    pos = sanitized.find("(")
    if pos >= 0:
        sanitized = sanitized[:pos]
    if not sanitized:
        raise OatMaterialManifestError(
            f"generated Material {name!r} maps to empty OAT storage identity"
        )
    return f"generated/{sanitized}"


def _raw_textures(name: str, source: dict) -> list[dict]:
    textures = source["doc"].get("textures", [])
    if not isinstance(textures, list):
        raise OatMaterialManifestError(f"{name!r}: textures is not a list")
    return textures


def _generated_material(
    *,
    material_index: int,
    name: str,
    catalog_entry: dict,
    indexed: dict[str, dict],
    source_texture_extension: str,
) -> tuple[dict, dict[str, int], dict]:
    try:
        identity = parse_layered_material_name(name)
    except LayeredMaterialError as exc:
        raise OatMaterialManifestError(f"{name!r}: {exc}") from exc

    storage_identity = _storage_identity(name)
    generated_source = indexed.get(storage_identity)
    if generated_source is None:
        raise OatMaterialManifestError(
            f"{name!r}: missing exact generated OAT Material JSON at {storage_identity!r}"
        )

    generated_raw = _raw_textures(name, generated_source)
    runtime = _normalize_textures(
        name,
        generated_source,
        source_texture_extension,
        first_texture_index=0,
    )
    role_counts: dict[str, int] = {}
    for dep in runtime:
        role = dep["role"]
        role_counts[role] = role_counts.get(role, 0) + 1

    layers: list[dict] = []
    source_components: list[dict] = []
    component_concat: list[dict] = []
    all_components_available = True
    missing_identities: set[str] = set()
    missing_occurrences = 0
    normal_validations = 0

    for layer_identity in identity["layers"]:
        component = str(layer_identity["componentMaterial"])
        component_source = indexed.get(component)
        expected_normal = bool(layer_identity["expectedNormalMap"])
        source_record = None
        validation = "standalone-component-not-available"
        if component_source is None:
            all_components_available = False
            missing_identities.add(component)
            missing_occurrences += 1
        else:
            source_record = _source_record(component_source)
            has_normal = _has_real_normal_map(component_source)
            if expected_normal != has_normal:
                raise OatMaterialManifestError(
                    f"{name!r} layer {layer_identity['layerIndex']} {component!r}: "
                    f"generated token expects real normal map={expected_normal}, "
                    f"but standalone OAT Material_HasNormalMap equivalent={has_normal}"
                )
            validation = "matched-standalone-component"
            normal_validations += 1
            component_concat.extend(_raw_textures(component, component_source))

        row = {
            "layerIndex": int(layer_identity["layerIndex"]),
            "layer": component,
            "token": layer_identity["token"],
            "bspMaterialIndex": int(layer_identity["bspMaterialIndex"]),
            "expectedNormalMap": expected_normal,
            "explicitNoNormalMarker": bool(layer_identity.get("explicitNoNormalMarker")),
            "standaloneOatMaterialAvailable": component_source is not None,
            "standaloneNormalValidation": validation,
            "sourceOatMaterial": source_record,
        }
        layers.append(row)
        source_components.append(
            {
                "layerIndex": row["layerIndex"],
                "token": row["token"],
                "bspMaterialIndex": row["bspMaterialIndex"],
                "expectedNormalMap": row["expectedNormalMap"],
                "componentMaterial": component,
                "standaloneOatMaterialAvailable": row["standaloneOatMaterialAvailable"],
                "standaloneNormalValidation": validation,
                "sourceOatMaterial": source_record,
            }
        )

    full_concat_validated = False
    if all_components_available:
        if generated_raw != component_concat:
            raise OatMaterialManifestError(
                f"{name!r}: exact generated OAT textures[] does not equal exact "
                "standalone component textures[] concatenated in layer order"
            )
        full_concat_validated = True

    blocked = [
        {
            "role": dep["role"],
            "reason": (
                "exact generated runtime Material dependency retained; layered "
                "technique/shader composition is not representable as core glTF preview"
            ),
            "texture": dep,
        }
        for dep in runtime
    ]
    missing_sorted = sorted(missing_identities)
    return (
        {
            "materialIndex": material_index,
            "material": name,
            "surfacePointerHex": catalog_entry.get("surfacePointerHex"),
            "layered": True,
            "compoundIdentity": True,
            "compoundIdentityDecoded": identity,
            "oatStorageIdentity": storage_identity,
            "compositors": [],
            "layers": layers,
            "runtimeTextureTable": runtime,
            "runtimeTextureTableAuthority": (
                "exact textures[] from exact synthesized generated OAT Material JSON"
            ),
            "standardPreview": {},
            "standardPreviewBlocked": blocked,
            "sourceOatMaterial": _source_record(generated_source),
            "sourceOatComponents": source_components,
            "reconstruction": {
                "method": "exact generated OAT runtime Material table",
                "textureTable": (
                    "direct generated Material JSON textures[]; no component texture boundary inferred"
                ),
                "textureCount": len(runtime),
                "allStandaloneComponentsAvailable": all_components_available,
                "componentConcatenationValidation": (
                    "exact-match"
                    if full_concat_validated
                    else "not-complete-because-standalone-component-evidence-is-missing"
                ),
                "missingStandaloneComponents": missing_sorted,
                "missingStandaloneLayerOccurrenceCount": missing_occurrences,
                "standaloneNormalValidationCount": normal_validations,
                "layeredTechniqueShader": "pending source closure; no preview blend invented",
            },
        },
        role_counts,
        {
            "fullConcat": full_concat_validated,
            "partial": bool(missing_sorted),
            "missingIdentities": missing_sorted,
            "missingOccurrences": missing_occurrences,
            "normalValidations": normal_validations,
            "runtimeDependencyCount": len(runtime),
        },
    )


def _remap_dependency(dep: dict, extension: str) -> bool:
    image = str(dep.get("imageAsset") or "")
    try:
        source = oat_image_staging_basename(image, extension)
        rel = oat_image_relative_path(image, extension)
    except OatImageFilenameError as exc:
        raise OatMaterialManifestError(str(exc)) from exc
    previous = str(dep.get("sourceTexture") or "")
    dep["sourceTexture"] = source
    dep["sourceOatImagePath"] = rel
    dep["sourceOatImageAsset"] = image
    return previous != source


def _authoritative_dependencies(material: dict) -> list[dict]:
    runtime = material.get("runtimeTextureTable")
    if isinstance(runtime, list):
        return runtime
    out: list[dict] = []
    for layer in material.get("layers", []):
        textures = layer.get("textures", [])
        if not isinstance(textures, list):
            raise OatMaterialManifestError(
                f"{material.get('material')!r}: layer textures is not a list"
            )
        out.extend(textures)
    return out


def _remap_images(materials: list[dict], extension: str) -> tuple[int, int, int]:
    dependency_count = 0
    remapped = 0
    by_source: dict[str, set[str]] = {}
    for material in materials:
        for dep in _authoritative_dependencies(material):
            dependency_count += 1
            remapped += int(_remap_dependency(dep, extension))
            by_source.setdefault(str(dep["sourceTexture"]), set()).add(str(dep["imageAsset"]))
        for binding in material.get("standardPreview", {}).values():
            _remap_dependency(binding, extension)
        for blocked in material.get("standardPreviewBlocked", []):
            texture = blocked.get("texture")
            if isinstance(texture, dict):
                _remap_dependency(texture, extension)

    collisions = {k: sorted(v) for k, v in by_source.items() if len(v) > 1}
    if collisions:
        source, assets = sorted(collisions.items())[0]
        raise OatMaterialManifestError(
            "distinct T6 GfxImage identities collide after OAT filename mapping: "
            f"{assets!r} -> {source!r}"
        )
    return dependency_count, remapped, len(by_source)


def _attach_render_state(doc: dict, material_root: Path) -> None:
    indexed = _load_oat_materials(material_root)
    cache: dict[str, dict] = {}

    def archive_for(identity: str) -> dict:
        if identity not in cache:
            source = indexed.get(identity)
            if source is None:
                raise OatMaterialManifestError(f"render-state source missing: {identity!r}")
            cache[identity] = _state_archive(identity, source)
        return cache[identity]

    material_state_count = 0
    component_state_count = 0
    exact_core_count = 0
    alpha_test_count = 0
    blend_count = 0
    stencil_count = 0
    polygon_offset_count = 0
    unique_signatures: set[str] = set()
    for material in doc.get("materials", []):
        identity = _source_identity(material.get("sourceOatMaterial"))
        material["renderState"] = archive_for(identity) if identity is not None else None
        state = material["renderState"]
        if state is not None:
            material_state_count += 1
            exact_core_count += int(state["coreGltfCompatibility"]["fullyRepresentable"])
            alpha_test_count += int(state["features"]["alphaTestUsed"])
            blend_count += int(state["features"]["blendUsed"])
            stencil_count += int(state["features"]["stencilUsed"])
            polygon_offset_count += int(state["features"]["polygonOffsetUsed"])
            unique_signatures.update(_canonical(x) for x in state["stateBits"])
        for layer in material.get("layers", []):
            layer_identity = _source_identity(layer.get("sourceOatMaterial"))
            if layer_identity is None:
                continue
            layer_state = archive_for(layer_identity)
            layer["renderState"] = layer_state
            component_state_count += 1
            unique_signatures.update(_canonical(x) for x in layer_state["stateBits"])

    doc.setdefault("policy", {})["renderState"] = (
        "retain exact OAT-decoded T6 stateBits/stateBitsEntry/constants/sortKey; "
        "do not approximate unsupported depth/blend/stencil/polygon-offset state into core glTF"
    )
    doc.setdefault("stats", {}).update(
        {
            "renderStateMaterialCount": material_state_count,
            "renderStateComponentLayerCount": component_state_count,
            "uniqueDecodedStateSignatureCount": len(unique_signatures),
            "coreGltfFullyRepresentableMaterialCount": exact_core_count,
            "alphaTestMaterialCount": alpha_test_count,
            "blendMaterialCount": blend_count,
            "stencilMaterialCount": stencil_count,
            "polygonOffsetMaterialCount": polygon_offset_count,
        }
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
    catalog = catalog_doc.get("materials", [])
    if not isinstance(catalog, list):
        raise OatMaterialManifestError("material catalog missing materials[]")

    materials: list[dict] = []
    missing: list[dict] = []
    role_counts: dict[str, int] = {}
    ordinary_count = compound_count = generated_success_count = 0
    full_concat_count = partial_count = missing_occurrences = normal_validations = 0
    generated_dependency_count = standard_binding_count = ambiguous_binding_count = 0
    missing_component_identities: set[str] = set()
    seen: set[str] = set()

    for entry in sorted(catalog, key=lambda item: int(item["index"])):
        index = int(entry["index"])
        name = str(entry.get("name") or "")
        if not name:
            raise OatMaterialManifestError(f"catalog material {index} has empty name")
        if name in seen:
            raise OatMaterialManifestError(f"duplicate catalog material name {name!r}")
        seen.add(name)
        try:
            if _is_compound(name):
                if not name.startswith("*"):
                    raise OatMaterialManifestError(
                        f"unsupported compound material identity {name!r}"
                    )
                compound_count += 1
                record, local_roles, local = _generated_material(
                    material_index=index,
                    name=name,
                    catalog_entry=entry,
                    indexed=indexed,
                    source_texture_extension=source_texture_extension,
                )
                generated_success_count += 1
                full_concat_count += int(local["fullConcat"])
                partial_count += int(local["partial"])
                missing_component_identities.update(local["missingIdentities"])
                missing_occurrences += int(local["missingOccurrences"])
                normal_validations += int(local["normalValidations"])
                generated_dependency_count += int(local["runtimeDependencyCount"])
            else:
                source = indexed.get(name)
                if source is None:
                    raise OatMaterialManifestError(
                        f"no exact OAT material JSON for catalog material {name!r}"
                    )
                ordinary_count += 1
                record, local_roles, bindings, ambiguous = _ordinary_material(
                    material_index=index,
                    name=name,
                    catalog_entry=entry,
                    source=source,
                    source_texture_extension=source_texture_extension,
                )
                standard_binding_count += bindings
                ambiguous_binding_count += ambiguous
        except OatMaterialManifestError as exc:
            missing.append(
                {
                    "materialIndex": index,
                    "material": name,
                    "surfacePointerHex": entry.get("surfacePointerHex"),
                    "reason": str(exc),
                }
            )
            if not allow_missing_materials:
                raise
            continue

        materials.append(record)
        for role, count in local_roles.items():
            role_counts[role] = role_counts.get(role, 0) + count

    dependency_count, remapped_count, unique_disk_count = _remap_images(
        materials, source_texture_extension
    )
    doc = {
        "format": "t6-material-texture-manifest-v1",
        "source": {
            "kind": "OpenAssetTools material.v1 JSON",
            "producer": PRODUCER,
            "materialRoot": str(material_root),
            "catalogMaterialCount": len(catalog),
            "indexedOatMaterialCount": len(indexed),
            "sourceTextureExtension": source_texture_extension,
            "oatGeneratedMaterialFilenameReference": {
                "repository": "Laupetin/OpenAssetTools",
                "commit": OAT_MATERIAL_COMMIT,
                "path": OAT_MATERIAL_COMMON_PATH,
                "rule": "ordinary name unchanged; generated '*' -> '_', truncate at '(', prefix generated/",
            },
            "oatImageFilenameReference": {
                "repository": "Laupetin/OpenAssetTools",
                "commit": OAT_IMAGE_COMMIT,
                "path": OAT_IMAGE_COMMON_PATH,
                "rule": "replace '*' with '_' then emit images/<cleanAssetName><extension>",
            },
        },
        "policy": {
            "ordinaryMaterialJoin": "exact catalog name == relative OAT material JSON path",
            "generatedMaterialJoin": "exact pinned OAT MaterialCommon generated storage transform",
            "generatedRuntimeTextureAuthority": "exact textures[] from exact generated OAT Material JSON",
            "generatedComponentBoundary": (
                "never inferred from generated table; validated only when every standalone component Material exists"
            ),
            "generatedComponentConcatenation": (
                "when all standalone components exist, generated textures[] must exactly equal their textures[] concatenation in layer order"
            ),
            "compoundNormalValidation": (
                "n marker validated only against available standalone component Material evidence; missing standalone evidence remains explicit"
            ),
            "roleSelection": "OAT textures[].semantic only; never filename/table order",
            "sourceTextureMapping": "exact OAT ImageDumper disk basename; original GfxImage identity preserved",
            "compoundMaterialPreview": "blocked until layered technique/shader composition is source-closed",
            "standardPreviewRoles": CORE_PREVIEW_ROLES,
            "samplerState": "preserved exactly in manifest; not silently approximated",
        },
        "stats": {
            "materialCount": len(materials),
            "missingMaterialCount": len(missing),
            "ordinaryMaterialCount": ordinary_count,
            "compoundMaterialCount": compound_count,
            "exactGeneratedCompoundJsonCount": generated_success_count,
            "exactFullComponentConcatenationValidationCount": full_concat_count,
            "generatedMaterialsWithComponentOnlyLayers": partial_count,
            "componentStandaloneMissingIdentityCount": len(missing_component_identities),
            "componentStandaloneMissingLayerOccurrenceCount": missing_occurrences,
            "componentStandaloneNormalValidationCount": normal_validations,
            "generatedRuntimeTextureDependencyCount": generated_dependency_count,
            "textureDependencyCount": dependency_count,
            "roleCounts": dict(sorted(role_counts.items())),
            "standardPreviewBindingCount": standard_binding_count,
            "ambiguousStandardPreviewBindings": ambiguous_binding_count,
            "oatImageMappedDependencyCount": dependency_count,
            "oatImageFilenameChangedDependencyCount": remapped_count,
            "oatImageUniqueDiskSourceCount": unique_disk_count,
            "skippedNonT6MaterialJsonCount": len(skipped),
        },
        "componentStandaloneMissingIdentities": sorted(missing_component_identities),
        "materials": materials,
        "missingMaterials": missing,
        "skippedFiles": skipped,
        "proofBoundary": (
            "Generated production texture dependencies come only from exact synthesized OAT Material textures[]. Component names/BSP indices remain graph metadata. Component texture boundaries and normal properties are promoted only from standalone component evidence; absent standalone evidence stays explicit. No layered shader/blend semantics are inferred."
        ),
    }

    _attach_render_state(doc, material_root)
    doc = _promote(doc)
    doc["source"]["producer"] = PRODUCER
    doc["source"]["baseRevision"] = (
        "v6 generated-runtime-table closure + v4 exact render-state archive + v5 ordinary exact-role preview promotion"
    )
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_root", type=Path)
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--source-texture-extension", required=True)
    parser.add_argument("--allow-missing-materials", action="store_true")
    args = parser.parse_args()
    doc = build_manifest(
        material_root=args.material_root,
        catalog_doc=json.loads(args.catalog_json.read_text(encoding="utf-8")),
        source_texture_extension=args.source_texture_extension,
        allow_missing_materials=args.allow_missing_materials,
    )
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_bytes(payload)
    print(
        json.dumps(
            {"out": str(args.output_json), "bytes": len(payload), "sha256": _sha256(payload), **doc["stats"]},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
