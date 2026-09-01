#!/usr/bin/env python3
"""T6 world lightmap manifest v3 with nullable retail image roles.

Retail GfxLightmapArray entries contain two GfxImage* fields, primary and
secondary. Either pointer may be null. v1/v2 incorrectly required both roles
to resolve to non-empty image identities. v3 makes pointer/image presence
explicit and only creates disk dependencies for roles that actually exist.

The T6 code-sampler contract remains global and exact:
  0x4 -> lightmapSamplerPrimary
  0x5 -> lightmapSamplerSecondary
An absent image role does not erase that renderer contract; it only means that
this specific GfxLightmapArray entry has no GfxImage dependency for the role.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from t6_oat_image_filename_v1 import (
    OatImageFilenameError,
    oat_image_relative_path,
    oat_image_staging_basename,
)
from t6_world_lightmap_manifest_v1 import (
    LIGHTMAP_PRIMARY_CODE_TEXTURE_SOURCE,
    LIGHTMAP_PRIMARY_SAMPLER_ACCESSOR,
    LIGHTMAP_SECONDARY_CODE_TEXTURE_SOURCE,
    LIGHTMAP_SECONDARY_SAMPLER_ACCESSOR,
    LightmapManifestError,
    NO_LIGHTMAP_INDEX,
)


ROLE_CONTRACT = {
    "primary": {
        "codeTextureSource": LIGHTMAP_PRIMARY_CODE_TEXTURE_SOURCE,
        "samplerAccessor": LIGHTMAP_PRIMARY_SAMPLER_ACCESSOR,
    },
    "secondary": {
        "codeTextureSource": LIGHTMAP_SECONDARY_CODE_TEXTURE_SOURCE,
        "samplerAccessor": LIGHTMAP_SECONDARY_SAMPLER_ACCESSOR,
    },
}


def _mapped(asset_name: str, extension: str) -> tuple[str, str]:
    try:
        return (
            oat_image_staging_basename(asset_name, extension),
            oat_image_relative_path(asset_name, extension),
        )
    except OatImageFilenameError as exc:
        raise LightmapManifestError(str(exc)) from exc


def _role(entry: dict, role: str, extension: str) -> dict:
    asset = str(entry.get(f"{role}Image") or "")
    present = bool(asset)
    contract = ROLE_CONTRACT[role]
    out = {
        f"{role}Present": present,
        f"{role}Image": asset if present else None,
        f"{role}OatImageAsset": asset if present else None,
        f"{role}SourceTexture": None,
        f"{role}OatImagePath": None,
        f"{role}CodeTextureSource": int(contract["codeTextureSource"]),
        f"{role}SamplerAccessor": str(contract["samplerAccessor"]),
    }
    if present:
        source, oat_path = _mapped(asset, extension)
        out[f"{role}SourceTexture"] = source
        out[f"{role}OatImagePath"] = oat_path
    return out


def _present_identity_pairs(lightmaps: list[dict]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for lightmap in lightmaps:
        for role in ("primary", "secondary"):
            if not bool(lightmap[f"{role}Present"]):
                continue
            asset = str(lightmap[f"{role}OatImageAsset"])
            source = str(lightmap[f"{role}SourceTexture"])
            if not asset or not source:
                raise LightmapManifestError(
                    f"lightmap {lightmap['index']} {role}: present role lacks asset/source"
                )
            pairs.append((asset, source))
    return pairs


def _validate_bijection(lightmaps: list[dict]) -> tuple[int, int]:
    pairs = _present_identity_pairs(lightmaps)
    sources_by_asset: dict[str, set[str]] = {}
    assets_by_source: dict[str, set[str]] = {}
    for asset, source in pairs:
        sources_by_asset.setdefault(asset, set()).add(source)
        assets_by_source.setdefault(source, set()).add(asset)

    split = {
        asset: sorted(sources)
        for asset, sources in sources_by_asset.items()
        if len(sources) > 1
    }
    if split:
        asset, sources = sorted(split.items())[0]
        raise LightmapManifestError(
            f"T6 lightmap GfxImage {asset!r} maps to multiple disk sources: {sources!r}"
        )

    collisions = {
        source: sorted(assets)
        for source, assets in assets_by_source.items()
        if len(assets) > 1
    }
    if collisions:
        source, assets = sorted(collisions.items())[0]
        raise LightmapManifestError(
            "distinct T6 lightmap GfxImage identities collide after OAT filename mapping: "
            f"{assets!r} -> {source!r}"
        )
    return len(pairs), len(assets_by_source)


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

    entries = lightmap_catalog.get("lightmaps", [])
    lightmap_count = int(lightmap_catalog.get("lightmapCount", len(entries)))
    if not isinstance(entries, list) or len(entries) != lightmap_count:
        raise LightmapManifestError(
            f"lightmap array/count mismatch "
            f"{len(entries) if isinstance(entries, list) else 'not-list'} != {lightmap_count}"
        )

    normalized_lightmaps: list[dict] = []
    filename_changed = 0
    present_primary = 0
    present_secondary = 0
    for expected_index, entry in enumerate(entries):
        index = int(entry.get("index", expected_index))
        if index != expected_index:
            raise LightmapManifestError(
                f"lightmaps must be dense/in-order: expected {expected_index}, got {index}"
            )
        row = {
            "index": index,
            **_role(entry, "primary", source_texture_extension),
            **_role(entry, "secondary", source_texture_extension),
            "source": entry.get("source"),
        }
        for role in ("primary", "secondary"):
            if row[f"{role}Present"]:
                asset = str(row[f"{role}OatImageAsset"])
                source = str(row[f"{role}SourceTexture"])
                filename_changed += int(source != asset + source_texture_extension)
        present_primary += int(row["primaryPresent"])
        present_secondary += int(row["secondaryPresent"])
        normalized_lightmaps.append(row)

    dependency_use_count, unique_disk_source_count = _validate_bijection(
        normalized_lightmaps
    )

    group_by_index = {int(group["groupIndex"]): group for group in groups}
    usage = Counter()
    no_lightmap_surfaces = 0
    bindings: list[dict] = []
    by_index = {int(row["index"]): row for row in normalized_lightmaps}

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
                f"surface {surface_index}: lightmapIndex {lightmap_index} outside "
                f"0..{lightmap_count - 1} or sentinel {NO_LIGHTMAP_INDEX}"
            )

        usage[lightmap_index] += 1
        lightmap = by_index[lightmap_index]
        binding = {
            "surfaceIndex": surface_index,
            "groupIndex": group_index,
            "lightmapIndex": lightmap_index,
            "hasLightmap": True,
            "lightmapTexCoord": uv_count,
        }
        for role in ("primary", "secondary"):
            binding[f"{role}Present"] = bool(lightmap[f"{role}Present"])
            binding[f"{role}CodeTextureSource"] = int(
                lightmap[f"{role}CodeTextureSource"]
            )
            binding[f"{role}SamplerAccessor"] = str(
                lightmap[f"{role}SamplerAccessor"]
            )
            if lightmap[f"{role}Present"]:
                binding[f"{role}SourceTexture"] = lightmap[
                    f"{role}SourceTexture"
                ]
                binding[f"{role}OatImagePath"] = lightmap[f"{role}OatImagePath"]
                binding[f"{role}OatImageAsset"] = lightmap[
                    f"{role}OatImageAsset"
                ]
            else:
                binding[f"{role}SourceTexture"] = None
                binding[f"{role}OatImagePath"] = None
                binding[f"{role}OatImageAsset"] = None
        bindings.append(binding)

    referenced_indices = sorted(usage)
    unreferenced_indices = [
        index for index in range(lightmap_count) if index not in usage
    ]

    return {
        "format": "t6-world-lightmap-manifest-v3",
        "map": world.get("map") or lightmap_catalog.get("map"),
        "source": {
            "producer": "t6_world_lightmap_manifest_v3.py",
            "worldFormat": world.get("format"),
            "lightmapCatalogFormat": lightmap_catalog.get("format"),
            "sourceTextureExtension": source_texture_extension,
            "oatImageFilenameReference": {
                "repository": "Laupetin/OpenAssetTools",
                "commit": "7d027e8f89118196713e955b0e11f8404149c54d",
                "path": "src/ObjCommon/Image/ImageCommon.cpp",
                "rule": "replace '*' with '_' then emit images/<cleanAssetName><extension>",
            },
        },
        "t6CodeSamplerContract": {
            "primary": {
                "materialTextureSource": LIGHTMAP_PRIMARY_CODE_TEXTURE_SOURCE,
                "materialTextureSourceHex": "0x4",
                "enum": "TEXTURE_SRC_CODE_LIGHTMAP_PRIMARY",
                "accessor": LIGHTMAP_PRIMARY_SAMPLER_ACCESSOR,
            },
            "secondary": {
                "materialTextureSource": LIGHTMAP_SECONDARY_CODE_TEXTURE_SOURCE,
                "materialTextureSourceHex": "0x5",
                "enum": "TEXTURE_SRC_CODE_LIGHTMAP_SECONDARY",
                "accessor": LIGHTMAP_SECONDARY_SAMPLER_ACCESSOR,
            },
        },
        "policy": {
            "surfaceJoin": "exact GfxSurface.lightmapIndex",
            "noLightmapSentinel": NO_LIGHTMAP_INDEX,
            "imageJoin": (
                "exact GfxLightmapArray primary/secondary GfxImage identity when "
                "that pointer is present; null pointer is preserved as absent"
            ),
            "rolePresence": (
                "per-lightmap role presence is explicit; absent roles create no "
                "OAT/DDS dependency and no fallback image is invented"
            ),
            "lightmapUv": "TEXCOORD_<group native uvCount>",
            "codeSamplerIdentity": (
                "global T6 MaterialTextureSource/accessor contract retained for "
                "both roles even when an individual GfxImage pointer is null"
            ),
            "sourceTextureMapping": (
                "exact OAT ImageDumper disk basename for present roles only; "
                "exact T6 GfxImage identity retained separately"
            ),
            "oatImageFilenameCollision": (
                "fail closed if distinct present T6 GfxImage identities map to "
                "one OAT disk filename"
            ),
            "shading": (
                "present primary/secondary dependencies remain separate; null "
                "roles remain null; channel encoding and shader combination not guessed"
            ),
        },
        "stats": {
            "surfaceCount": len(surfaces),
            "lightmapCount": lightmap_count,
            "declaredRoleCount": 2 * lightmap_count,
            "presentRoleDependencyUseCount": dependency_use_count,
            "presentPrimaryImageCount": present_primary,
            "absentPrimaryImageCount": lightmap_count - present_primary,
            "presentSecondaryImageCount": present_secondary,
            "absentSecondaryImageCount": lightmap_count - present_secondary,
            "oatImageFilenameChangedDependencyCount": filename_changed,
            "oatImageUniqueDiskSourceCount": unique_disk_source_count,
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
