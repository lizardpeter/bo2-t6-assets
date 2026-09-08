#!/usr/bin/env python3
"""Count exact Nuketown production image dependencies against the 81-IWI DDS closure.

This is an accounting tool, not a permissive resolver. It consumes only explicit
source-owned identities from:

- the exact OAT material manifest used by the production world pipeline;
- the lossless 81-payload IWI27 -> DDS bridge manifest;
- optional exact GfxWorld lightmap ownership catalog;
- optional exact GfxWorld reflection-probe ownership catalog.

Missing images are reported with their exact owners/roles. They are never
resolved by filename similarity, material order, dimensions, or nearby hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

FORMAT = "t6-nuketown-production-texture-dependency-census-v1"
MAP = "mp_nuketown_2020"
BRIDGE_FORMAT = "t6-iwi27-dds-bridge-v1"
LIGHTMAP_FORMAT = "t6-gfxworld-lightmap-catalog-v1"
REFLECTION_FORMAT = "t6-gfxworld-reflection-probe-catalog-v1"


class CensusError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise CensusError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise CensusError(f"{path}: top level is not an object")
    return doc, raw


def material_uses(doc: dict) -> dict[str, list[dict]]:
    materials = doc.get("materials")
    if not isinstance(materials, list):
        raise CensusError("material manifest lacks materials[]")
    uses: dict[str, list[dict]] = defaultdict(list)
    seen_materials = set()
    for mi, material in enumerate(materials):
        if not isinstance(material, dict):
            raise CensusError(f"material row {mi} is not an object")
        name = str(material.get("material") or "")
        if not name or name in seen_materials:
            raise CensusError(f"material row {mi}: empty/duplicate identity {name!r}")
        seen_materials.add(name)
        layers = material.get("layers") or []
        if not isinstance(layers, list):
            raise CensusError(f"{name!r}: layers is not a list")
        for li, layer in enumerate(layers):
            textures = layer.get("textures") or []
            if not isinstance(textures, list):
                raise CensusError(f"{name!r} layer {li}: textures is not a list")
            for ti, tex in enumerate(textures):
                if not isinstance(tex, dict):
                    raise CensusError(f"{name!r} layer {li} texture {ti}: not an object")
                image = str(tex.get("imageAsset") or "")
                source = str(tex.get("sourceTexture") or "")
                role = str(tex.get("role") or tex.get("semantic") or tex.get("name") or "")
                if not image:
                    raise CensusError(f"{name!r} layer {li} texture {ti}: empty imageAsset")
                uses[image].append({
                    "material": name,
                    "materialIndex": material.get("materialIndex"),
                    "layerIndex": layer.get("layerIndex", li),
                    "layer": layer.get("layer"),
                    "textureIndex": tex.get("textureIndex"),
                    "sourceTextureIndex": tex.get("sourceTextureIndex"),
                    "role": role,
                    "semantic": tex.get("semantic"),
                    "name": tex.get("name"),
                    "sourceTexture": source,
                    "samplerState": tex.get("samplerState"),
                })
    return dict(uses)


def bridge_images(doc: dict) -> dict[str, dict]:
    if doc.get("format") != BRIDGE_FORMAT:
        raise CensusError(f"bridge format {doc.get('format')!r} != {BRIDGE_FORMAT!r}")
    summary = doc.get("summary") or {}
    if not (
        int(summary.get("sourceAliasCount", -1)) == 81
        and int(summary.get("sourcePayloadCount", -1)) == 81
        and int(summary.get("outputImageNameCount", -1)) == 81
        and int(summary.get("unresolvedCount", -1)) == 0
        and int(summary.get("conflictCount", -1)) == 0
        and summary.get("allCompressedMipBytesPreserved") is True
    ):
        raise CensusError(f"DDS bridge is not exact green 81/81: {summary}")
    out = {}
    for row in doc.get("outputs") or []:
        image = str(row.get("image") or "")
        if not image or image in out:
            raise CensusError(f"empty/duplicate DDS bridge image identity {image!r}")
        out[image] = row
    if len(out) != 81:
        raise CensusError(f"DDS bridge output image population {len(out)} != 81")
    return out


def lightmap_uses(doc: dict | None) -> dict[str, list[dict]]:
    if doc is None:
        return {}
    if doc.get("format") != LIGHTMAP_FORMAT:
        raise CensusError(f"lightmap format {doc.get('format')!r} != {LIGHTMAP_FORMAT!r}")
    rows = doc.get("lightmaps")
    if not isinstance(rows, list) or int(doc.get("lightmapCount", -1)) != len(rows):
        raise CensusError("lightmap count mismatch")
    out: dict[str, list[dict]] = defaultdict(list)
    for ordinal, row in enumerate(rows):
        if int(row.get("index", -1)) != ordinal:
            raise CensusError(f"lightmap index {row.get('index')} != ordinal {ordinal}")
        for role, key in (("lightmapPrimary", "primaryImage"), ("lightmapSecondary", "secondaryImage")):
            value = row.get(key)
            if value is None:
                continue
            image = str(value)
            if not image:
                raise CensusError(f"lightmap {ordinal} has empty non-null {key}")
            out[image].append({"lightmapIndex": ordinal, "role": role})
    return dict(out)


def reflection_uses(doc: dict | None) -> dict[str, list[dict]]:
    if doc is None:
        return {}
    if doc.get("format") != REFLECTION_FORMAT:
        raise CensusError(f"reflection format {doc.get('format')!r} != {REFLECTION_FORMAT!r}")
    rows = doc.get("reflectionProbes")
    if not isinstance(rows, list) or int(doc.get("reflectionProbeCount", -1)) != len(rows):
        raise CensusError("reflection-probe count mismatch")
    out: dict[str, list[dict]] = defaultdict(list)
    for ordinal, row in enumerate(rows):
        if int(row.get("index", -1)) != ordinal:
            raise CensusError(f"reflection probe index {row.get('index')} != ordinal {ordinal}")
        value = row.get("reflectionImage")
        if value is None:
            continue
        image = str(value)
        if not image:
            raise CensusError(f"reflection probe {ordinal} has empty non-null image")
        out[image].append({"reflectionProbeIndex": ordinal, "role": "reflectionProbe"})
    return dict(out)


def rows_for(kind: str, uses: dict[str, list[dict]], bridge: dict[str, dict]) -> list[dict]:
    rows = []
    for image in sorted(uses):
        b = bridge.get(image)
        rows.append({
            "kind": kind,
            "image": image,
            "coveredByExact81DdsBridge": b is not None,
            "bridgeDds": None if b is None else {
                "output": b.get("output"),
                "ddsSha256": b.get("ddsSha256"),
                "ddsFormat": b.get("ddsFormat"),
                "width": b.get("width"),
                "height": b.get("height"),
                "mipCount": b.get("mipCount"),
            },
            "uses": uses[image],
        })
    return rows


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

    kind_rows = {
        "material": rows_for("material", m, b),
        "lightmap": rows_for("lightmap", l, b),
        "reflectionProbe": rows_for("reflectionProbe", r, b),
    }

    return {
        "format": FORMAT,
        "map": MAP,
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
        "material": kind_rows["material"],
        "lightmaps": kind_rows["lightmap"],
        "reflectionProbes": kind_rows["reflectionProbe"],
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
            "Coverage is exact identity set intersection only. Missing dependencies remain missing; "
            "no filename similarity, hash proximity, material adjacency, dimension matching, or image substitution is admitted. "
            "Lightmap/reflection counts are included only when their exact ownership catalogs are supplied."
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
