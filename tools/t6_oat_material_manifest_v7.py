#!/usr/bin/env python3
"""T6 OAT material manifest v7: exact layered projection + recovered boundaries.

v6 correctly retained each generated Material's exact OAT ``textures[]`` table as
runtime authority, but its optional component validation used the now-disproven
raw-concatenation model. Retail Nuketown instead proves that T6 layered creation
preserves component texture rows, appends the decimal layer index to texture
argument names for layers 1..3, then globally orders the generated table by the
Treyarch 32-bit argument-name hash.

v7 keeps the generated table as the only runtime dependency authority. It uses an
independently green ``t6-oat-layered-component-texture-recovery-v3`` proof only to
restore exact component texture boundaries for the seven standalone-missing
Nuketown components. Every layered Material must reconstruct exactly from its
component tables under the proven suffix+hash-sort projection. No missing
TechniqueSet, constants, render state, ownership, or shader/blend semantics are
inferred for a recovered component.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path

from t6_layered_material_name_v1 import LayeredMaterialError, parse_layered_material_name
from t6_oat_material_manifest_v2 import (
    CORE_PREVIEW_ROLES,
    OatMaterialManifestError,
    _has_real_normal_map,
    _index_oat_materials,
    _normalize_textures,
    _ordinary_material,
    _source_record,
)
from t6_oat_material_manifest_v4 import _canonical
from t6_oat_material_manifest_v5 import _promote
from t6_oat_material_manifest_v6 import (
    OAT_IMAGE_COMMIT,
    OAT_IMAGE_COMMON_PATH,
    OAT_MATERIAL_COMMIT,
    OAT_MATERIAL_COMMON_PATH,
    _attach_render_state,
    _is_compound,
    _remap_images,
    _storage_identity,
)
from t6_oat_layered_component_texture_recovery_v3 import (
    FORMAT as RECOVERY_FORMAT,
    _canonical as _recovery_canonical,
    _project,
    _row_hash,
    _suffix_row,
)

PRODUCER = "t6_oat_material_manifest_v7.py"
FORMAT = "t6-material-texture-manifest-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _raw_textures(name: str, source: dict) -> list[dict]:
    textures = source["doc"].get("textures", [])
    if not isinstance(textures, list) or any(not isinstance(row, dict) for row in textures):
        raise OatMaterialManifestError(f"{name!r}: textures is not a list of objects")
    return textures


def _load_recovery(doc: dict, catalog_doc: dict) -> dict[str, dict]:
    if doc.get("format") != RECOVERY_FORMAT:
        raise OatMaterialManifestError(
            f"unsupported layered component recovery format {doc.get('format')!r}"
        )
    source = doc.get("source") or {}
    catalog_map = catalog_doc.get("map")
    recovery_map = source.get("catalogMap")
    if catalog_map is not None and recovery_map is not None and catalog_map != recovery_map:
        raise OatMaterialManifestError(
            f"layered recovery map mismatch: catalog={catalog_map!r} recovery={recovery_map!r}"
        )
    rows = doc.get("components")
    if not isinstance(rows, list) or not rows:
        raise OatMaterialManifestError("layered recovery missing components[]")
    indexed: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise OatMaterialManifestError("layered recovery contains non-object component")
        identity = str(row.get("identity") or "")
        if not identity:
            raise OatMaterialManifestError("layered recovery component has empty identity")
        if identity in indexed:
            raise OatMaterialManifestError(f"duplicate layered recovery identity {identity!r}")
        if row.get("standaloneOatMaterialAvailable") is not False:
            raise OatMaterialManifestError(
                f"{identity!r}: recovery row is not explicitly standalone-missing"
            )
        textures = row.get("textures")
        if not isinstance(textures, list) or any(not isinstance(x, dict) for x in textures):
            raise OatMaterialManifestError(f"{identity!r}: recovery textures[] invalid")
        digest = _sha256(_recovery_canonical(textures))
        if digest != row.get("textureTableSha256"):
            raise OatMaterialManifestError(
                f"{identity!r}: recovery texture-table SHA mismatch {digest} != {row.get('textureTableSha256')}"
            )
        if int(row.get("textureCount", -1)) != len(textures):
            raise OatMaterialManifestError(f"{identity!r}: recovery textureCount mismatch")
        indexed[identity] = row
    summary = doc.get("summary") or {}
    if int(summary.get("recoveredTargetCount", -1)) != len(indexed):
        raise OatMaterialManifestError("layered recovery summary/component count mismatch")
    if int(summary.get("targetCount", -1)) != len(indexed):
        raise OatMaterialManifestError("layered recovery target/component count mismatch")
    return indexed


def _component_table(
    component: str,
    indexed_materials: dict[str, dict],
    recovered: dict[str, dict],
) -> tuple[list[dict], dict | None, str, dict | None]:
    source = indexed_materials.get(component)
    if source is not None:
        return _raw_textures(component, source), _source_record(source), "standalone-oat-material", None
    recovery = recovered.get(component)
    if recovery is None:
        raise OatMaterialManifestError(
            f"layered component {component!r} has neither standalone OAT Material nor exact v3 recovery"
        )
    return list(recovery["textures"]), None, "exact-layered-component-recovery-v3", recovery


def _runtime_bindings(
    generated_raw: list[dict],
    component_tables: list[tuple[int, str, list[dict]]],
) -> dict[int, list[dict]]:
    by_row: dict[bytes, deque[int]] = defaultdict(deque)
    for index, row in enumerate(generated_raw):
        by_row[_recovery_canonical(row)].append(index)

    result: dict[int, list[dict]] = {}
    used: set[int] = set()
    for layer_index, component, table in component_tables:
        bindings: list[dict] = []
        for source_index, source_row in enumerate(table):
            projected = _suffix_row(source_row, layer_index)
            key = _recovery_canonical(projected)
            queue = by_row.get(key)
            if not queue:
                raise OatMaterialManifestError(
                    f"layer {layer_index} {component!r}: projected texture row absent from generated runtime table"
                )
            runtime_index = queue.popleft()
            if runtime_index in used:
                raise OatMaterialManifestError("generated runtime texture index assigned more than once")
            used.add(runtime_index)
            bindings.append(
                {
                    "sourceTextureIndex": source_index,
                    "runtimeTextureIndex": runtime_index,
                    "sourceArgumentName": source_row.get("name"),
                    "runtimeArgumentName": projected.get("name"),
                    "argumentHash": _row_hash(projected),
                }
            )
        result[layer_index] = bindings
    if len(used) != len(generated_raw):
        raise OatMaterialManifestError(
            f"component/runtime binding coverage {len(used)}/{len(generated_raw)}"
        )
    return result


def _generated_material_v7(
    *,
    material_index: int,
    name: str,
    catalog_entry: dict,
    indexed: dict[str, dict],
    recovered: dict[str, dict],
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
    if any(_row_hash(a) > _row_hash(b) for a, b in zip(generated_raw, generated_raw[1:])):
        raise OatMaterialManifestError(f"{name!r}: generated texture argument hashes are not nondecreasing")

    runtime = _normalize_textures(
        name, generated_source, source_texture_extension, first_texture_index=0
    )
    role_counts: dict[str, int] = {}
    for dep in runtime:
        role = dep["role"]
        role_counts[role] = role_counts.get(role, 0) + 1

    layers: list[dict] = []
    source_components: list[dict] = []
    component_tables: list[tuple[int, str, list[dict]]] = []
    standalone_missing: set[str] = set()
    recovered_identities: set[str] = set()
    recovered_occurrences = 0
    standalone_occurrences = 0
    normal_validations = 0

    for layer_identity in identity["layers"]:
        layer_index = int(layer_identity["layerIndex"])
        component = str(layer_identity["componentMaterial"])
        expected_normal = bool(layer_identity["expectedNormalMap"])
        table, source_record, boundary_authority, recovery_row = _component_table(
            component, indexed, recovered
        )
        component_tables.append((layer_index, component, table))
        if source_record is None:
            standalone_missing.add(component)
            recovered_identities.add(component)
            recovered_occurrences += 1
            standalone_available = False
        else:
            standalone_occurrences += 1
            standalone_available = True

        pseudo = {"doc": {"textures": table}}
        has_normal = _has_real_normal_map(pseudo)
        if has_normal != expected_normal:
            raise OatMaterialManifestError(
                f"{name!r} layer {layer_index} {component!r}: expected real normal={expected_normal}, "
                f"component table has real normal={has_normal}"
            )
        normal_validations += 1
        table_sha = _sha256(_recovery_canonical(table))
        if recovery_row is not None and table_sha != recovery_row.get("textureTableSha256"):
            raise OatMaterialManifestError(f"{component!r}: recovery table SHA changed during manifest build")

        row = {
            "layerIndex": layer_index,
            "layer": component,
            "token": layer_identity["token"],
            "bspMaterialIndex": int(layer_identity["bspMaterialIndex"]),
            "expectedNormalMap": expected_normal,
            "explicitNoNormalMarker": bool(layer_identity.get("explicitNoNormalMarker")),
            "standaloneOatMaterialAvailable": standalone_available,
            "sourceOatMaterial": source_record,
            "componentTextureBoundaryAvailable": True,
            "componentTextureBoundaryAuthority": boundary_authority,
            "componentTextureCount": len(table),
            "componentTextureTableSha256": table_sha,
            "componentTextureTable": table,
            "componentNormalValidation": "exact-match",
        }
        if recovery_row is not None:
            row["componentTextureRecoveryEvidence"] = {
                "format": RECOVERY_FORMAT,
                "textureTableSha256": recovery_row["textureTableSha256"],
                "generatedMaterialCount": recovery_row.get("generatedMaterialCount"),
                "generatedLayerOccurrenceCount": recovery_row.get("generatedLayerOccurrenceCount"),
            }
        layers.append(row)
        source_components.append(
            {
                "layerIndex": layer_index,
                "token": row["token"],
                "bspMaterialIndex": row["bspMaterialIndex"],
                "expectedNormalMap": expected_normal,
                "componentMaterial": component,
                "standaloneOatMaterialAvailable": standalone_available,
                "componentTextureBoundaryAvailable": True,
                "componentTextureBoundaryAuthority": boundary_authority,
                "componentTextureTableSha256": table_sha,
                "sourceOatMaterial": source_record,
            }
        )

    tables = {component: table for _, component, table in component_tables}
    reconstructed = _project(
        [str(layer["componentMaterial"]) for layer in identity["layers"]], tables
    )
    if _recovery_canonical(reconstructed) != _recovery_canonical(generated_raw):
        raise OatMaterialManifestError(
            f"{name!r}: exact component suffix+hash-sort projection does not reproduce generated textures[]"
        )
    bindings = _runtime_bindings(generated_raw, component_tables)
    for layer in layers:
        layer["projectedRuntimeTextureBindings"] = bindings[int(layer["layerIndex"])]

    blocked = [
        {
            "role": dep["role"],
            "reason": (
                "exact generated runtime Material dependency retained; layered technique/shader "
                "composition is outside this manifest's portable core-glTF preview boundary"
            ),
            "texture": dep,
        }
        for dep in runtime
    ]
    missing_sorted = sorted(standalone_missing)
    recovered_sorted = sorted(recovered_identities)
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
            "runtimeTextureTableAuthority": "exact textures[] from exact synthesized generated OAT Material JSON",
            "standardPreview": {},
            "standardPreviewBlocked": blocked,
            "sourceOatMaterial": _source_record(generated_source),
            "sourceOatComponents": source_components,
            "reconstruction": {
                "method": "exact generated runtime table + exact component projection validation",
                "textureTable": "generated Material JSON textures[] remains runtime authority",
                "textureCount": len(runtime),
                "allComponentTextureBoundariesAvailable": True,
                "componentProjectionValidation": "exact-layer-suffix-plus-global-argument-hash-sort",
                "missingStandaloneComponents": missing_sorted,
                "recoveredStandaloneMissingComponents": recovered_sorted,
                "recoveredStandaloneMissingLayerOccurrenceCount": recovered_occurrences,
                "standaloneComponentLayerOccurrenceCount": standalone_occurrences,
                "componentNormalValidationCount": normal_validations,
                "layeredTechniqueShader": "not inferred by this manifest; consume independent shader-semantic proof",
            },
        },
        role_counts,
        {
            "projectionExact": True,
            "recovered": bool(recovered_sorted),
            "missingStandaloneIdentities": missing_sorted,
            "recoveredIdentities": recovered_sorted,
            "recoveredOccurrences": recovered_occurrences,
            "standaloneOccurrences": standalone_occurrences,
            "normalValidations": normal_validations,
            "runtimeDependencyCount": len(runtime),
            "componentLayerCount": len(layers),
        },
    )


def build_manifest(
    *,
    material_root: Path,
    catalog_doc: dict,
    layered_component_recovery_doc: dict,
    source_texture_extension: str,
    allow_missing_materials: bool = False,
) -> dict:
    if source_texture_extension and not source_texture_extension.startswith("."):
        raise OatMaterialManifestError(
            f"source texture extension must be empty or start with '.': {source_texture_extension!r}"
        )
    indexed, skipped = _index_oat_materials(material_root)
    recovered = _load_recovery(layered_component_recovery_doc, catalog_doc)
    catalog = catalog_doc.get("materials", [])
    if not isinstance(catalog, list):
        raise OatMaterialManifestError("material catalog missing materials[]")

    materials: list[dict] = []
    missing: list[dict] = []
    role_counts: dict[str, int] = {}
    ordinary_count = compound_count = generated_success_count = 0
    projection_exact_count = recovered_material_count = 0
    recovered_occurrences = standalone_occurrences = normal_validations = 0
    component_layer_count = generated_dependency_count = 0
    standard_binding_count = ambiguous_binding_count = 0
    observed_missing_identities: set[str] = set()
    observed_recovered_identities: set[str] = set()
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
                    raise OatMaterialManifestError(f"unsupported compound material identity {name!r}")
                compound_count += 1
                record, local_roles, local = _generated_material_v7(
                    material_index=index,
                    name=name,
                    catalog_entry=entry,
                    indexed=indexed,
                    recovered=recovered,
                    source_texture_extension=source_texture_extension,
                )
                generated_success_count += 1
                projection_exact_count += int(local["projectionExact"])
                recovered_material_count += int(local["recovered"])
                observed_missing_identities.update(local["missingStandaloneIdentities"])
                observed_recovered_identities.update(local["recoveredIdentities"])
                recovered_occurrences += int(local["recoveredOccurrences"])
                standalone_occurrences += int(local["standaloneOccurrences"])
                normal_validations += int(local["normalValidations"])
                generated_dependency_count += int(local["runtimeDependencyCount"])
                component_layer_count += int(local["componentLayerCount"])
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

    expected_recovered = set(recovered)
    if observed_missing_identities != expected_recovered:
        raise OatMaterialManifestError(
            "exact recovery identity set does not equal observed standalone-missing layered identity set: "
            f"observed={sorted(observed_missing_identities)!r} recovery={sorted(expected_recovered)!r}"
        )
    if observed_recovered_identities != expected_recovered:
        raise OatMaterialManifestError(
            "not every recovery identity was consumed by layered projection: "
            f"observed={sorted(observed_recovered_identities)!r} recovery={sorted(expected_recovered)!r}"
        )

    dependency_count, remapped_count, unique_disk_count = _remap_images(
        materials, source_texture_extension
    )
    doc = {
        "format": FORMAT,
        "source": {
            "kind": "OpenAssetTools material.v1 JSON + exact layered component recovery v3",
            "producer": PRODUCER,
            "materialRoot": str(material_root),
            "catalogMaterialCount": len(catalog),
            "indexedOatMaterialCount": len(indexed),
            "sourceTextureExtension": source_texture_extension,
            "layeredComponentRecoveryFormat": layered_component_recovery_doc.get("format"),
            "layeredComponentRecoverySummary": layered_component_recovery_doc.get("summary"),
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
                "standalone OAT component table when present; otherwise exact v3 residual recovery only"
            ),
            "generatedComponentProjection": (
                "preserve component texture rows; suffix argument names by decimal layer index for layers 1..3; "
                "global nondecreasing Treyarch 32-bit argument-name hash order; exact reconstruction required"
            ),
            "compoundNormalValidation": "every component table, standalone or v3-recovered, must match serialized n-marker expectation",
            "roleSelection": "OAT textures[].semantic only; never filename/table order",
            "sourceTextureMapping": "exact OAT ImageDumper disk basename; original GfxImage identity preserved",
            "compoundMaterialPreview": "portable core-glTF preview remains blocked here; layered shader semantics come from independent proof",
            "standardPreviewRoles": CORE_PREVIEW_ROLES,
            "samplerState": "preserved exactly in manifest; no BO1-style mip mutation",
        },
        "stats": {
            "materialCount": len(materials),
            "missingMaterialCount": len(missing),
            "ordinaryMaterialCount": ordinary_count,
            "compoundMaterialCount": compound_count,
            "exactGeneratedCompoundJsonCount": generated_success_count,
            "exactComponentProjectionValidationCount": projection_exact_count,
            "generatedMaterialsWithRecoveredComponentLayers": recovered_material_count,
            "componentLayerCount": component_layer_count,
            "componentStandaloneMissingIdentityCount": len(observed_missing_identities),
            "componentRecoveredIdentityCount": len(observed_recovered_identities),
            "componentRecoveredLayerOccurrenceCount": recovered_occurrences,
            "componentStandaloneLayerOccurrenceCount": standalone_occurrences,
            "componentNormalValidationCount": normal_validations,
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
        "componentStandaloneMissingIdentities": sorted(observed_missing_identities),
        "componentRecoveredIdentities": sorted(observed_recovered_identities),
        "materials": materials,
        "missingMaterials": missing,
        "skippedFiles": skipped,
        "proofBoundary": (
            "Generated runtime texture dependencies remain direct generated OAT Material textures[]. v7 closes exact component "
            "texture boundaries through standalone evidence or v3 residual recovery and proves the T6 suffix+hash-sort projection. "
            "Recovered components do not gain a fabricated TechniqueSet, constants, render state, asset owner, duplicate precedence, "
            "or shader/blend semantics."
        ),
    }
    _attach_render_state(doc, material_root)

    # v6's historical helper calls its all-layer total
    # renderStateComponentLayerCount, even though ordinary records also carry a
    # one-layer self description. v7 separates those accounting domains without
    # changing any attached render-state data.
    render_state_layer_count = 0
    render_state_ordinary_layer_count = 0
    render_state_component_layer_count = 0
    render_state_recovered_component_layer_count = 0
    for material in doc["materials"]:
        is_compound = bool(material.get("compoundIdentityDecoded"))
        for layer in material.get("layers", []):
            if "renderState" not in layer:
                continue
            render_state_layer_count += 1
            if is_compound:
                if layer.get("standaloneOatMaterialAvailable") is False:
                    render_state_recovered_component_layer_count += 1
                else:
                    render_state_component_layer_count += 1
            else:
                render_state_ordinary_layer_count += 1

    stats = doc["stats"]
    inherited_all_layer_count = int(stats.get("renderStateComponentLayerCount", -1))
    if inherited_all_layer_count != render_state_layer_count:
        raise OatMaterialManifestError(
            "v6 render-state helper all-layer count disagrees with v7 record census: "
            f"helper={inherited_all_layer_count} census={render_state_layer_count}"
        )
    if int(stats.get("renderStateMaterialCount", -1)) != len(doc["materials"]):
        raise OatMaterialManifestError(
            "not every resolved v7 Material received exact top-level render state"
        )
    if render_state_ordinary_layer_count != int(stats["ordinaryMaterialCount"]):
        raise OatMaterialManifestError(
            "ordinary self-layer render-state census disagrees with ordinary Material count"
        )
    if render_state_component_layer_count != int(stats["componentStandaloneLayerOccurrenceCount"]):
        raise OatMaterialManifestError(
            "standalone compound-component render-state census disagrees with component occurrence count"
        )
    if render_state_recovered_component_layer_count != 0:
        raise OatMaterialManifestError(
            "a v3-recovered standalone-missing component unexpectedly received fabricated render state"
        )

    stats["renderStateLayerCount"] = render_state_layer_count
    stats["renderStateOrdinaryLayerCount"] = render_state_ordinary_layer_count
    stats["renderStateComponentLayerCount"] = render_state_component_layer_count
    stats["renderStateRecoveredComponentLayerCount"] = render_state_recovered_component_layer_count

    doc = _promote(doc)
    doc["source"]["producer"] = PRODUCER
    doc["source"]["baseRevision"] = (
        "v7 exact layered component projection/recovery + v6 generated runtime authority + "
        "v4 exact render-state archive + v5 ordinary exact-role preview promotion"
    )
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_root", type=Path)
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--layered-component-recovery", type=Path, required=True)
    parser.add_argument("--source-texture-extension", required=True)
    parser.add_argument("--allow-missing-materials", action="store_true")
    args = parser.parse_args()
    doc = build_manifest(
        material_root=args.material_root,
        catalog_doc=json.loads(args.catalog_json.read_text(encoding="utf-8")),
        layered_component_recovery_doc=json.loads(args.layered_component_recovery.read_text(encoding="utf-8")),
        source_texture_extension=args.source_texture_extension,
        allow_missing_materials=args.allow_missing_materials,
    )
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_bytes(payload)
    print(json.dumps({"out": str(args.output_json), "bytes": len(payload), "sha256": _sha256(payload), **doc["stats"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
