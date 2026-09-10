#!/usr/bin/env python3
"""T6 OAT material manifest v7: source-correct generated texture validation.

v6 correctly made each generated Material's own exact OAT ``textures[]`` table
the runtime dependency authority, but added an over-strong auxiliary assertion:
it required that table to equal standalone component ``textures[]`` arrays by
literal concatenation.  Retail Nuketown disproves that representation-level
claim: generated tables rewrite binding names and may reorder entries.

v7 keeps the generated table as the sole runtime authority.  When all standalone
components exist it additionally requires exact component payload conservation:
a generated texture entry may differ from a component entry only in the binding
name representation (``name`` or unresolved name-hash fragment fields) and in
array position.  Image identity, semantic, sampler state, mature-content flag,
and every other serialized JSON field must match as an exact multiset.  Any
payload difference still fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import t6_oat_material_manifest_v6 as v6
from t6_layered_material_name_v1 import LayeredMaterialError, parse_layered_material_name
from t6_oat_material_manifest_v2 import (
    OatMaterialManifestError,
    _has_real_normal_map,
    _normalize_textures,
    _source_record,
)

PRODUCER = "t6_oat_material_manifest_v7.py"
BINDING_NAME_FIELDS = frozenset({"name", "nameHash", "nameStart", "nameEnd"})


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _payload_signature(texture: dict) -> str:
    """Exact texture payload identity with only binding-name representation removed."""
    if not isinstance(texture, dict):
        raise OatMaterialManifestError("generated/component texture entry is not an object")
    payload = {k: texture[k] for k in sorted(texture) if k not in BINDING_NAME_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_multiset(rows: list[dict]) -> Counter[str]:
    return Counter(_payload_signature(row) for row in rows)


def _generated_material_v7(
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

    storage_identity = v6._storage_identity(name)
    generated_source = indexed.get(storage_identity)
    if generated_source is None:
        raise OatMaterialManifestError(
            f"{name!r}: missing exact generated OAT Material JSON at {storage_identity!r}"
        )

    generated_raw = v6._raw_textures(name, generated_source)
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
            component_concat.extend(v6._raw_textures(component, component_source))

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

    exact_concat = False
    payload_multiset_validated = False
    binding_rewritten = False
    relation = "not-complete-because-standalone-component-evidence-is-missing"
    if all_components_available:
        if len(generated_raw) != len(component_concat):
            raise OatMaterialManifestError(
                f"{name!r}: generated/component texture counts differ "
                f"({len(generated_raw)} != {len(component_concat)})"
            )
        if generated_raw == component_concat:
            exact_concat = True
            payload_multiset_validated = True
            relation = "exact-concatenation"
        elif _payload_multiset(generated_raw) == _payload_multiset(component_concat):
            payload_multiset_validated = True
            binding_rewritten = True
            relation = "exact-payload-multiset-with-runtime-binding-rewrite"
        else:
            generated_payloads = _payload_multiset(generated_raw)
            component_payloads = _payload_multiset(component_concat)
            only_generated = list((generated_payloads - component_payloads).elements())
            only_components = list((component_payloads - generated_payloads).elements())
            raise OatMaterialManifestError(
                f"{name!r}: generated OAT texture payload multiset differs from exact "
                f"standalone component payload multiset; generatedOnly={only_generated[:2]!r} "
                f"componentOnly={only_components[:2]!r}"
            )

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
                "exact ordered/named textures[] from exact synthesized generated OAT Material JSON"
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
                "componentConcatenationValidation": relation,
                "componentTexturePayloadMultisetValidation": (
                    "exact-match" if payload_multiset_validated else "not-complete"
                ),
                "runtimeBindingRewriteObserved": binding_rewritten,
                "bindingNameFieldsExcludedFromAuxiliaryPayloadComparison": sorted(BINDING_NAME_FIELDS),
                "missingStandaloneComponents": missing_sorted,
                "missingStandaloneLayerOccurrenceCount": missing_occurrences,
                "standaloneNormalValidationCount": normal_validations,
                "layeredTechniqueShader": "pending source closure; no preview blend invented",
            },
        },
        role_counts,
        {
            "fullConcat": exact_concat,
            "payloadMultiset": payload_multiset_validated,
            "bindingRewrite": binding_rewritten,
            "partial": bool(missing_sorted),
            "missingIdentities": missing_sorted,
            "missingOccurrences": missing_occurrences,
            "normalValidations": normal_validations,
            "runtimeDependencyCount": len(runtime),
        },
    )


def build_manifest(*, material_root: Path, catalog_doc: dict, source_texture_extension: str, allow_missing_materials: bool = False) -> dict:
    original = v6._generated_material
    v6._generated_material = _generated_material_v7
    try:
        doc = v6.build_manifest(
            material_root=material_root,
            catalog_doc=catalog_doc,
            source_texture_extension=source_texture_extension,
            allow_missing_materials=allow_missing_materials,
        )
    finally:
        v6._generated_material = original

    complete = [
        m for m in doc.get("materials", [])
        if m.get("layered") and m.get("reconstruction", {}).get("allStandaloneComponentsAvailable")
    ]
    exact_concat = sum(
        1 for m in complete
        if m["reconstruction"].get("componentConcatenationValidation") == "exact-concatenation"
    )
    payload_exact = sum(
        1 for m in complete
        if m["reconstruction"].get("componentTexturePayloadMultisetValidation") == "exact-match"
    )
    binding_rewrite = sum(
        1 for m in complete if m["reconstruction"].get("runtimeBindingRewriteObserved") is True
    )
    if payload_exact != len(complete):
        raise OatMaterialManifestError(
            f"component payload multiset closure incomplete: {payload_exact}/{len(complete)}"
        )

    doc["source"]["producer"] = PRODUCER
    doc["source"]["baseRevision"] = (
        "v7 generated runtime-table authority + exact component payload-multiset validation; "
        "v4 render-state archive + v5 ordinary exact-role preview promotion"
    )
    doc["policy"]["generatedComponentConcatenation"] = (
        "literal concatenation is observed but not required; when every standalone component exists, "
        "generated/component texture payloads must match as an exact multiset after removing only "
        "binding-name representation fields. The generated table remains the ordered/named runtime authority."
    )
    doc["stats"]["exactFullComponentConcatenationValidationCount"] = exact_concat
    doc["stats"]["exactComponentTexturePayloadMultisetValidationCount"] = payload_exact
    doc["stats"]["generatedComponentRuntimeBindingRewriteCount"] = binding_rewrite
    doc["proofBoundary"] = (
        "Generated production texture dependencies come only from the exact synthesized OAT Material textures[]. "
        "Standalone component evidence is auxiliary: when complete, all non-binding texture payload fields must "
        "match the generated table as an exact multiset. Binding names/order are never reconstructed from components. "
        "Missing standalone component evidence remains explicit. No layered shader/blend semantics are inferred."
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
    print(json.dumps({
        "out": str(args.output_json),
        "bytes": len(payload),
        "sha256": _sha256(payload),
        **doc["stats"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
