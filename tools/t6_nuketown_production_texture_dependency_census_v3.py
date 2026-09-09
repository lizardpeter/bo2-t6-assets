#!/usr/bin/env python3
"""Nuketown production texture dependency census v3.

v3 preserves the v2 dependency rule: ordinary Materials contribute their exact
OAT layer texture tables and generated Materials contribute only their exact
runtimeTextureTable. It additionally requires the input Material manifest to be
an exact v7 layered-projection proof before any image dependency is admitted.
Recovered component boundaries are proof metadata, not extra runtime image uses.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from t6_nuketown_production_texture_dependency_census_v1 import (
    bridge_images,
    lightmap_uses,
    load,
    reflection_uses,
    rows_for,
    sha256,
)
from t6_nuketown_production_texture_dependency_census_v2 import (
    CensusError,
    material_uses,
)

FORMAT = "t6-nuketown-production-texture-dependency-census-v3"
EXPECTED_RECOVERED = [
    "wpc/asphalt_road_dark_dec",
    "wpc/decal_concrete_clean_line",
    "wpc/decal_damage_asphalt_crack01",
    "wpc/decal_grunge_glue",
    "wpc/decal_grunge_mold01",
    "wpc/decal_signage_const_marking01",
    "wpc/decal_signage_const_marking02",
]


def require_v7_material_proof(doc: dict) -> None:
    if doc.get("format") != "t6-material-texture-manifest-v1":
        raise CensusError(f"unsupported Material manifest format {doc.get('format')!r}")
    source = doc.get("source") or {}
    if source.get("producer") != "t6_oat_material_manifest_v7.py":
        raise CensusError(f"Material manifest is not v7: producer={source.get('producer')!r}")
    stats = doc.get("stats") or {}
    exact = {
        "materialCount": 327,
        "missingMaterialCount": 0,
        "ordinaryMaterialCount": 207,
        "compoundMaterialCount": 120,
        "exactGeneratedCompoundJsonCount": 120,
        "exactComponentProjectionValidationCount": 120,
        "generatedMaterialsWithRecoveredComponentLayers": 14,
        "componentStandaloneMissingIdentityCount": 7,
        "componentRecoveredIdentityCount": 7,
        "componentRecoveredLayerOccurrenceCount": 15,
        "componentStandaloneLayerOccurrenceCount": 244,
        "componentLayerCount": 259,
        "componentNormalValidationCount": 259,
        "renderStateMaterialCount": 327,
        "renderStateLayerCount": 451,
        "renderStateOrdinaryLayerCount": 207,
        "renderStateComponentLayerCount": 244,
        "renderStateRecoveredComponentLayerCount": 0,
        "generatedRuntimeTextureDependencyCount": 460,
    }
    for key, value in exact.items():
        if stats.get(key) != value:
            raise CensusError(f"v7 Material proof statistic {key}={stats.get(key)!r}, expected {value!r}")
    if doc.get("componentStandaloneMissingIdentities") != EXPECTED_RECOVERED:
        raise CensusError("v7 standalone-missing identity set changed")
    if doc.get("componentRecoveredIdentities") != EXPECTED_RECOVERED:
        raise CensusError("v7 recovered identity set changed")

    compounds = [m for m in doc.get("materials", []) if m.get("compoundIdentityDecoded")]
    if len(compounds) != 120:
        raise CensusError(f"v7 compound record count {len(compounds)}, expected 120")
    recovered_occurrences = 0
    runtime_rows = 0
    for material in compounds:
        if material.get("runtimeTextureTableAuthority") != (
            "exact textures[] from exact synthesized generated OAT Material JSON"
        ):
            raise CensusError(f"{material.get('material')!r}: generated runtime authority changed")
        reconstruction = material.get("reconstruction") or {}
        if reconstruction.get("componentProjectionValidation") != (
            "exact-layer-suffix-plus-global-argument-hash-sort"
        ):
            raise CensusError(f"{material.get('material')!r}: v7 projection proof missing")
        runtime = material.get("runtimeTextureTable")
        if not isinstance(runtime, list):
            raise CensusError(f"{material.get('material')!r}: runtimeTextureTable missing")
        runtime_rows += len(runtime)
        bound: list[int] = []
        for layer in material.get("layers", []):
            bindings = layer.get("projectedRuntimeTextureBindings")
            if not isinstance(bindings, list) or len(bindings) != layer.get("componentTextureCount"):
                raise CensusError(f"{material.get('material')!r}: incomplete component/runtime bindings")
            bound.extend(int(row["runtimeTextureIndex"]) for row in bindings)
            if layer.get("standaloneOatMaterialAvailable") is False:
                recovered_occurrences += 1
                if "renderState" in layer:
                    raise CensusError(
                        f"{material.get('material')!r}: recovered component gained render state"
                    )
        if sorted(bound) != list(range(len(runtime))):
            raise CensusError(f"{material.get('material')!r}: runtime texture binding coverage is not exact")
    if runtime_rows != 460:
        raise CensusError(f"v7 generated runtime dependency count {runtime_rows}, expected 460")
    if recovered_occurrences != 15:
        raise CensusError(f"v7 recovered layer occurrence count {recovered_occurrences}, expected 15")


def build(material_doc: dict, bridge_doc: dict, lightmap_doc: dict | None, reflection_doc: dict | None) -> dict:
    require_v7_material_proof(material_doc)
    m = material_uses(material_doc)
    b = bridge_images(bridge_doc)
    l = lightmap_uses(lightmap_doc)
    r = reflection_uses(reflection_doc)

    material_set = set(m)
    lightmap_set = set(l)
    reflection_set = set(r)
    required = material_set | lightmap_set | reflection_set
    bridge_set = set(b)
    covered = required & bridge_set
    missing = required - bridge_set
    bridge_unused = bridge_set - required

    return {
        "format": FORMAT,
        "map": "mp_nuketown_2020",
        "summary": {
            "materialUniqueImageCount": len(material_set),
            "materialCoveredByExact81Count": len(material_set & bridge_set),
            "materialMissingFromExact81Count": len(material_set - bridge_set),
            "lightmapUniqueImageCount": len(lightmap_set),
            "lightmapCoveredByExact81Count": len(lightmap_set & bridge_set),
            "lightmapMissingFromExact81Count": len(lightmap_set - bridge_set),
            "reflectionUniqueImageCount": len(reflection_set),
            "reflectionCoveredByExact81Count": len(reflection_set & bridge_set),
            "reflectionMissingFromExact81Count": len(reflection_set - bridge_set),
            "productionUniqueImageCount": len(required),
            "productionCoveredByExact81Count": len(covered),
            "productionMissingFromExact81Count": len(missing),
            "exact81BridgeImageCount": len(bridge_set),
            "exact81BridgeImageUnusedByCurrentProductionGraphCount": len(bridge_unused),
            "productionCoverageRatio": 1.0 if not required else len(covered) / len(required),
        },
        "material": rows_for("material", m, b),
        "lightmaps": rows_for("lightmap", l, b),
        "reflectionProbes": rows_for("reflectionProbe", r, b),
        "missingProductionImages": [
            {
                "image": image,
                "materialUses": m.get(image, []),
                "lightmapUses": l.get(image, []),
                "reflectionProbeUses": r.get(image, []),
            }
            for image in sorted(missing)
        ],
        "bridgeImagesNotRequiredByCurrentProductionGraph": [
            {"image": image, "output": b[image].get("output"), "ddsSha256": b[image].get("ddsSha256")}
            for image in sorted(bridge_unused)
        ],
        "proofBoundary": (
            "Material admission requires the exact v7 327-Material layered-projection proof. Generated Materials contribute only "
            "their exact generated runtimeTextureTable to the production image graph; recovered component boundaries are used only "
            "to prove that table and are never counted as extra dependencies. Coverage remains exact GfxImage identity intersection "
            "only. Missing images remain missing; no filename similarity, adjacency, dimensions, or substitution is admitted."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--material-manifest", type=Path, required=True)
    ap.add_argument("--dds-bridge", type=Path, required=True)
    ap.add_argument("--lightmap-catalog", type=Path)
    ap.add_argument("--reflection-catalog", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    material_doc, material_raw = load(args.material_manifest)
    bridge_doc, bridge_raw = load(args.dds_bridge)
    lightmap_doc = lightmap_raw = None
    reflection_doc = reflection_raw = None
    if args.lightmap_catalog:
        lightmap_doc, lightmap_raw = load(args.lightmap_catalog)
    if args.reflection_catalog:
        reflection_doc, reflection_raw = load(args.reflection_catalog)

    doc = build(material_doc, bridge_doc, lightmap_doc, reflection_doc)
    doc["inputs"] = {
        "materialManifest": {"path": str(args.material_manifest), "bytes": len(material_raw), "sha256": sha256(material_raw)},
        "ddsBridge": {"path": str(args.dds_bridge), "bytes": len(bridge_raw), "sha256": sha256(bridge_raw)},
        "lightmapCatalog": None if lightmap_raw is None else {"path": str(args.lightmap_catalog), "bytes": len(lightmap_raw), "sha256": sha256(lightmap_raw)},
        "reflectionCatalog": None if reflection_raw is None else {"path": str(args.reflection_catalog), "bytes": len(reflection_raw), "sha256": sha256(reflection_raw)},
    }
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({"out": str(args.out), "bytes": len(payload), "sha256": sha256(payload), **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
