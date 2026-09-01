#!/usr/bin/env python3
"""Join normalized T6 GfxWorld surfaces to exact primary/secondary lightmap assets.

Source-closed structure:
- GfxWorld.lightmapCount + GfxLightmapArray[lightmapCount]
- each GfxLightmapArray contains GfxImage* primary and GfxImage* secondary
- each GfxSurface carries lightmapIndex
- inherited renderer uses lightmapIndex == 31 as the no-lightmap sentinel
- world lightmap UV is already decoded from vd0 and exported at
  TEXCOORD_<native uvCount> for each vertex group.

This tool does not infer how primary/secondary are combined in the shader. It
only validates exact indexing and produces a portable dependency manifest.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


class LightmapManifestError(RuntimeError):
    pass


NO_LIGHTMAP_INDEX = 31


def _texture_name(image_asset: str, extension: str) -> str:
    if not image_asset:
        raise LightmapManifestError("empty lightmap image asset")
    if "/" in image_asset or "\\" in image_asset or "\0" in image_asset:
        raise LightmapManifestError(
            f"lightmap image asset must be an exact basename for staging: {image_asset!r}"
        )
    if extension and not extension.startswith("."):
        raise LightmapManifestError(
            f"source texture extension must be empty or begin with '.': {extension!r}"
        )
    return image_asset + extension


def build_manifest(
    world: dict,
    lightmap_catalog: dict,
    *,
    source_texture_extension: str = ".dds",
) -> dict:
    if world.get("format") != "t6-world-mesh-normalized-v1":
        raise LightmapManifestError(f"unsupported world format {world.get('format')!r}")
    groups = world.get("groups", [])
    surfaces = world.get("surfaces", [])
    if not isinstance(groups, list) or not isinstance(surfaces, list):
        raise LightmapManifestError("world must contain groups[] and surfaces[]")

    if lightmap_catalog.get("format") != "t6-gfxworld-lightmap-catalog-v1":
        raise LightmapManifestError(
            f"unsupported lightmap catalog {lightmap_catalog.get('format')!r}"
        )
    if (
        world.get("map")
        and lightmap_catalog.get("map")
        and world["map"] != lightmap_catalog["map"]
    ):
        raise LightmapManifestError(
            f"map mismatch: world={world['map']!r}, catalog={lightmap_catalog['map']!r}"
        )

    lightmaps = lightmap_catalog.get("lightmaps", [])
    lightmap_count = int(lightmap_catalog.get("lightmapCount", len(lightmaps)))
    if not isinstance(lightmaps, list) or len(lightmaps) != lightmap_count:
        raise LightmapManifestError(
            f"lightmap array/count mismatch {len(lightmaps) if isinstance(lightmaps, list) else 'not-list'} != {lightmap_count}"
        )

    normalized_lightmaps: list[dict] = []
    for expected_index, entry in enumerate(lightmaps):
        index = int(entry.get("index", expected_index))
        if index != expected_index:
            raise LightmapManifestError(
                f"lightmaps must be dense/in-order: expected {expected_index}, got {index}"
            )
        primary = str(entry.get("primaryImage") or "")
        secondary = str(entry.get("secondaryImage") or "")
        normalized_lightmaps.append(
            {
                "index": index,
                "primaryImage": primary,
                "primarySourceTexture": _texture_name(primary, source_texture_extension),
                "secondaryImage": secondary,
                "secondarySourceTexture": _texture_name(secondary, source_texture_extension),
                "source": entry.get("source"),
            }
        )

    group_by_index = {int(group["groupIndex"]): group for group in groups}
    usage = Counter()
    no_lightmap_surfaces = 0
    bindings: list[dict] = []
    for surface in surfaces:
        surface_index = int(surface["index"])
        lightmap_index = surface.get("lightmapIndex")
        if lightmap_index is None:
            raise LightmapManifestError(f"surface {surface_index}: missing lightmapIndex")
        lightmap_index = int(lightmap_index)
        group_index = int(surface["groupIndex"])
        group = group_by_index.get(group_index)
        if group is None:
            raise LightmapManifestError(
                f"surface {surface_index}: groupIndex {group_index} is unavailable"
            )
        uv_count = int(group.get("uvCount", 0))
        if uv_count < 1 or uv_count > 4:
            raise LightmapManifestError(
                f"surface {surface_index}: invalid group uvCount {uv_count}"
            )

        if lightmap_index == NO_LIGHTMAP_INDEX:
            no_lightmap_surfaces += 1
            bindings.append(
                {
                    "surfaceIndex": surface_index,
                    "groupIndex": group_index,
                    "lightmapIndex": NO_LIGHTMAP_INDEX,
                    "hasLightmap": False,
                    "lightmapTexCoord": uv_count,
                }
            )
            continue
        if lightmap_index < 0 or lightmap_index >= lightmap_count:
            raise LightmapManifestError(
                f"surface {surface_index}: lightmapIndex {lightmap_index} outside 0..{lightmap_count - 1} or sentinel {NO_LIGHTMAP_INDEX}"
            )

        usage[lightmap_index] += 1
        binding = normalized_lightmaps[lightmap_index]
        bindings.append(
            {
                "surfaceIndex": surface_index,
                "groupIndex": group_index,
                "lightmapIndex": lightmap_index,
                "hasLightmap": True,
                "lightmapTexCoord": uv_count,
                "primarySourceTexture": binding["primarySourceTexture"],
                "secondarySourceTexture": binding["secondarySourceTexture"],
            }
        )

    referenced_indices = sorted(usage)
    unreferenced_indices = [
        index for index in range(lightmap_count) if index not in usage
    ]
    return {
        "format": "t6-world-lightmap-manifest-v1",
        "map": world.get("map") or lightmap_catalog.get("map"),
        "source": {
            "worldFormat": world.get("format"),
            "lightmapCatalogFormat": lightmap_catalog.get("format"),
            "sourceTextureExtension": source_texture_extension,
        },
        "policy": {
            "surfaceJoin": "exact GfxSurface.lightmapIndex",
            "noLightmapSentinel": NO_LIGHTMAP_INDEX,
            "imageJoin": "exact GfxLightmapArray primary/secondary GfxImage identities",
            "lightmapUv": "TEXCOORD_<group native uvCount>",
            "shading": (
                "primary/secondary preserved as separate dependencies; shader combination not guessed"
            ),
        },
        "stats": {
            "surfaceCount": len(surfaces),
            "lightmapCount": lightmap_count,
            "surfacesWithLightmap": sum(usage.values()),
            "surfacesWithoutLightmap": no_lightmap_surfaces,
            "referencedLightmapCount": len(referenced_indices),
            "unreferencedLightmapCount": len(unreferenced_indices),
            "surfaceUseCountByLightmap": {
                str(index): usage[index] for index in referenced_indices
            },
        },
        "lightmaps": normalized_lightmaps,
        "surfaceBindings": bindings,
        "referencedLightmapIndices": referenced_indices,
        "unreferencedLightmapIndices": unreferenced_indices,
    }


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
