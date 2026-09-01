#!/usr/bin/env python3
"""T6 world lightmap manifest v2 with exact OpenAssetTools image filename mapping.

v1 source-closes surface/lightmap indexing and T6 code-sampler identities. v2
keeps those semantics and distinguishes the exact T6 GfxImage identity from the
filename emitted by OAT's ImageDumper (`*` is replaced by `_`).

Because that transform is not injective, distinct T6 lightmap image identities
that collapse to the same OAT disk filename fail closed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from t6_oat_image_filename_v1 import (
    OatImageFilenameError,
    oat_image_relative_path,
    oat_image_staging_basename,
)
from t6_world_lightmap_manifest_v1 import (
    LightmapManifestError,
    build_manifest as build_manifest_v1,
)


def _mapped(asset_name: str, extension: str) -> tuple[str, str]:
    try:
        return (
            oat_image_staging_basename(asset_name, extension),
            oat_image_relative_path(asset_name, extension),
        )
    except OatImageFilenameError as exc:
        raise LightmapManifestError(str(exc)) from exc


def _validate_no_filename_collisions(lightmaps: list[dict]) -> int:
    by_source: dict[str, set[str]] = {}
    for lightmap in lightmaps:
        for prefix in ("primary", "secondary"):
            source = str(lightmap.get(f"{prefix}SourceTexture") or "")
            asset = str(lightmap.get(f"{prefix}OatImageAsset") or "")
            by_source.setdefault(source, set()).add(asset)
    collisions = {
        source: sorted(assets)
        for source, assets in by_source.items()
        if len(assets) > 1
    }
    if collisions:
        source, assets = sorted(collisions.items())[0]
        raise LightmapManifestError(
            "distinct T6 lightmap GfxImage identities collide after OAT filename mapping: "
            f"{assets!r} -> {source!r}"
        )
    return len(by_source)


def build_manifest(
    world: dict,
    lightmap_catalog: dict,
    *,
    source_texture_extension: str = ".dds",
) -> dict:
    doc = build_manifest_v1(
        world,
        lightmap_catalog,
        source_texture_extension=source_texture_extension,
    )

    remapped = 0
    by_index: dict[int, dict] = {}
    lightmaps = doc.get("lightmaps", [])
    for lightmap in lightmaps:
        index = int(lightmap["index"])
        primary_asset = str(lightmap.get("primaryImage") or "")
        secondary_asset = str(lightmap.get("secondaryImage") or "")
        primary_source, primary_path = _mapped(
            primary_asset, source_texture_extension
        )
        secondary_source, secondary_path = _mapped(
            secondary_asset, source_texture_extension
        )
        remapped += int(primary_source != lightmap.get("primarySourceTexture"))
        remapped += int(secondary_source != lightmap.get("secondarySourceTexture"))
        lightmap["primarySourceTexture"] = primary_source
        lightmap["primaryOatImagePath"] = primary_path
        lightmap["primaryOatImageAsset"] = primary_asset
        lightmap["secondarySourceTexture"] = secondary_source
        lightmap["secondaryOatImagePath"] = secondary_path
        lightmap["secondaryOatImageAsset"] = secondary_asset
        by_index[index] = lightmap

    unique_disk_source_count = _validate_no_filename_collisions(lightmaps)

    for binding in doc.get("surfaceBindings", []):
        if not binding.get("hasLightmap"):
            continue
        lightmap = by_index[int(binding["lightmapIndex"])]
        binding["primarySourceTexture"] = lightmap["primarySourceTexture"]
        binding["primaryOatImagePath"] = lightmap["primaryOatImagePath"]
        binding["primaryOatImageAsset"] = lightmap["primaryOatImageAsset"]
        binding["secondarySourceTexture"] = lightmap["secondarySourceTexture"]
        binding["secondaryOatImagePath"] = lightmap["secondaryOatImagePath"]
        binding["secondaryOatImageAsset"] = lightmap["secondaryOatImageAsset"]

    doc["format"] = "t6-world-lightmap-manifest-v2"
    source = doc.setdefault("source", {})
    source["producer"] = "t6_world_lightmap_manifest_v2.py"
    source["oatImageFilenameReference"] = {
        "repository": "Laupetin/OpenAssetTools",
        "commit": "7d027e8f89118196713e955b0e11f8404149c54d",
        "path": "src/ObjCommon/Image/ImageCommon.cpp",
        "rule": "replace '*' with '_' then emit images/<cleanAssetName><extension>",
    }
    policy = doc.setdefault("policy", {})
    policy["sourceTextureMapping"] = (
        "exact OAT ImageDumper disk basename; exact T6 GfxImage identity retained separately"
    )
    policy["oatImageFilenameCollision"] = (
        "fail closed if distinct T6 GfxImage identities map to one OAT disk filename"
    )
    stats = doc.setdefault("stats", {})
    stats["oatImageDependencyCount"] = 2 * len(lightmaps)
    stats["oatImageFilenameChangedDependencyCount"] = remapped
    stats["oatImageUniqueDiskSourceCount"] = unique_disk_source_count
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("world_json", type=Path)
    parser.add_argument("lightmap_catalog_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--source-texture-extension", default=".dds")
    args = parser.parse_args()
    world = json.loads(args.world_json.read_text(encoding="utf-8"))
    catalog = json.loads(args.lightmap_catalog_json.read_text(encoding="utf-8"))
    doc = build_manifest(
        world,
        catalog,
        source_texture_extension=args.source_texture_extension,
    )
    args.output_json.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.output_json), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
