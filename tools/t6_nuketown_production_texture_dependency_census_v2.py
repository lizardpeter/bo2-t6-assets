#!/usr/bin/env python3
"""Nuketown production texture dependency census v2.

v1 reads ordinary ``layers[].textures[]``. v2 additionally understands the v6
Material manifest's exact generated ``runtimeTextureTable``. For a generated
Material that table is the sole production dependency authority; component layer
metadata is never re-counted and missing standalone component boundaries are not
inferred.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from t6_nuketown_production_texture_dependency_census_v1 import (
    FORMAT,
    CensusError,
    bridge_images,
    lightmap_uses,
    load,
    reflection_uses,
    rows_for,
    sha256,
)

FORMAT_V2 = "t6-nuketown-production-texture-dependency-census-v2"


def material_uses(doc: dict) -> dict[str, list[dict]]:
    materials = doc.get("materials")
    if not isinstance(materials, list):
        raise CensusError("material manifest lacks materials[]")
    uses: dict[str, list[dict]] = defaultdict(list)
    seen = set()
    for mi, material in enumerate(materials):
        if not isinstance(material, dict):
            raise CensusError(f"material row {mi} is not an object")
        name = str(material.get("material") or "")
        if not name or name in seen:
            raise CensusError(f"material row {mi}: empty/duplicate identity {name!r}")
        seen.add(name)

        runtime = material.get("runtimeTextureTable")
        if runtime is not None:
            if not (material.get("layered") and material.get("compoundIdentity")):
                raise CensusError(
                    f"{name!r}: runtimeTextureTable is only admitted for generated/compound Materials"
                )
            if not isinstance(runtime, list):
                raise CensusError(f"{name!r}: runtimeTextureTable is not a list")
            dependencies = [
                (
                    tex,
                    {
                        "layerIndex": None,
                        "layer": "$generated-runtime-texture-table",
                        "dependencyAuthority": "exact-generated-runtime-texture-table",
                        "componentBoundaryAuthoritative": False,
                    },
                )
                for tex in runtime
            ]
        else:
            layers = material.get("layers") or []
            if not isinstance(layers, list):
                raise CensusError(f"{name!r}: layers is not a list")
            dependencies = []
            for li, layer in enumerate(layers):
                textures = layer.get("textures") or []
                if not isinstance(textures, list):
                    raise CensusError(f"{name!r} layer {li}: textures is not a list")
                for tex in textures:
                    dependencies.append(
                        (
                            tex,
                            {
                                "layerIndex": layer.get("layerIndex", li),
                                "layer": layer.get("layer"),
                                "dependencyAuthority": "exact-ordinary-oat-material-texture-table",
                                "componentBoundaryAuthoritative": True,
                            },
                        )
                    )

        for ti, (tex, authority) in enumerate(dependencies):
            if not isinstance(tex, dict):
                raise CensusError(f"{name!r} dependency {ti}: not an object")
            image = str(tex.get("imageAsset") or "")
            source = str(tex.get("sourceTexture") or "")
            role = str(tex.get("role") or tex.get("semantic") or tex.get("name") or "")
            if not image:
                raise CensusError(f"{name!r} dependency {ti}: empty imageAsset")
            uses[image].append(
                {
                    "material": name,
                    "materialIndex": material.get("materialIndex"),
                    **authority,
                    "textureIndex": tex.get("textureIndex"),
                    "sourceTextureIndex": tex.get("sourceTextureIndex"),
                    "role": role,
                    "semantic": tex.get("semantic"),
                    "name": tex.get("name"),
                    "sourceTexture": source,
                    "samplerState": tex.get("samplerState"),
                }
            )
    return dict(uses)


def build(material_doc: dict, bridge_doc: dict, lightmap_doc: dict | None, reflection_doc: dict | None) -> dict:
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
        "format": FORMAT_V2,
        "previousFormat": FORMAT,
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
            {
                "image": image,
                "output": b[image].get("output"),
                "ddsSha256": b[image].get("ddsSha256"),
            }
            for image in sorted(bridge_unused)
        ],
        "proofBoundary": (
            "Coverage is exact GfxImage identity intersection only. Generated Materials contribute only their exact runtimeTextureTable; parsed component layers are never used to infer missing standalone component boundaries. Missing dependencies remain missing and no filename similarity, adjacency, dimensions, or image substitution is admitted."
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
