#!/usr/bin/env python3
"""T6 world reflection-probe manifest v2 with exact OAT image mapping.

v1 established the exact dense surface -> reflectionProbeIndex join but treated
`reflectionImage` as mandatory and derived a flat DDS name directly. v2 aligns
probe resources with the stronger nullable/OAT-aware lightmap pipeline:

- `GfxReflectionProbe::reflectionImage` may be null and remains explicitly null;
- present GfxImage identities are preserved unchanged;
- present disk dependencies use the pinned OpenAssetTools ImageDumper filename
  rule (`*` -> `_`, `images/<clean><extension>`);
- distinct GfxImage identities are forbidden from colliding onto one staging
  basename;
- surface ownership is exact `GfxSurface.reflectionProbeIndex` only;
- index 0 is a normal dense probe index. No no-probe sentinel is inferred.

This is a resource/ownership manifest. Reflection coordinate, mip, decode and
factor equations remain separate in `t6_reflection_probe_semantics_v1.py`.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from t6_oat_image_filename_v1 import (
    OatImageFilenameError,
    oat_image_relative_path,
    oat_image_staging_basename,
)


CATALOG_FORMAT = "t6-gfxworld-reflection-probe-catalog-v1"
FORMAT = "t6-world-reflection-probe-manifest-v2"


class ReflectionProbeManifestError(RuntimeError):
    pass


def _finite_vector(value, width: int, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != width:
        raise ReflectionProbeManifestError(f"{label} must contain exactly {width} values")
    out = [float(v) for v in value]
    if not all(math.isfinite(v) for v in out):
        raise ReflectionProbeManifestError(f"{label} contains non-finite values")
    return out


def _normalize_sh(entry: dict, probe_index: int) -> dict:
    sh = entry.get("lightingSH")
    if not isinstance(sh, dict):
        raise ReflectionProbeManifestError(f"probe {probe_index}: missing lightingSH object")
    return {
        "V0": _finite_vector(sh.get("V0"), 4, f"probe {probe_index} lightingSH.V0"),
        "V1": _finite_vector(sh.get("V1"), 4, f"probe {probe_index} lightingSH.V1"),
        "V2": _finite_vector(sh.get("V2"), 4, f"probe {probe_index} lightingSH.V2"),
    }


def _normalize_volumes(entry: dict, probe_index: int) -> list[dict]:
    volumes = entry.get("probeVolumes", [])
    count = int(entry.get("probeVolumeCount", len(volumes)))
    if count < 0:
        raise ReflectionProbeManifestError(f"probe {probe_index}: negative probeVolumeCount")
    if not isinstance(volumes, list) or len(volumes) != count:
        raise ReflectionProbeManifestError(
            f"probe {probe_index}: probe volume array/count mismatch"
        )
    out: list[dict] = []
    for expected_volume_index, volume in enumerate(volumes):
        if not isinstance(volume, dict):
            raise ReflectionProbeManifestError(
                f"probe {probe_index} volume {expected_volume_index}: expected object"
            )
        volume_index = int(volume.get("volumeIndex", expected_volume_index))
        if volume_index != expected_volume_index:
            raise ReflectionProbeManifestError(
                f"probe {probe_index}: volume indices must be dense/in-order; "
                f"expected {expected_volume_index}, got {volume_index}"
            )
        planes = volume.get("volumePlanes")
        if not isinstance(planes, list) or len(planes) != 6:
            raise ReflectionProbeManifestError(
                f"probe {probe_index} volume {volume_index}: expected six volume planes"
            )
        out.append(
            {
                "volumeIndex": volume_index,
                "volumePlanes": [
                    _finite_vector(
                        plane,
                        4,
                        f"probe {probe_index} volume {volume_index} plane {plane_index}",
                    )
                    for plane_index, plane in enumerate(planes)
                ],
            }
        )
    return out


def _mapped_image(asset: str, extension: str) -> tuple[str, str]:
    try:
        return (
            oat_image_staging_basename(asset, extension),
            oat_image_relative_path(asset, extension),
        )
    except OatImageFilenameError as exc:
        raise ReflectionProbeManifestError(str(exc)) from exc


def _normalize_probe(entry: dict, expected_index: int, extension: str) -> dict:
    if not isinstance(entry, dict):
        raise ReflectionProbeManifestError(f"probe {expected_index}: expected object")
    index = int(entry.get("index", expected_index))
    if index != expected_index:
        raise ReflectionProbeManifestError(
            f"reflection probes must be dense/in-order: expected {expected_index}, got {index}"
        )

    origin = _finite_vector(entry.get("origin"), 3, f"probe {index} origin")
    sh = _normalize_sh(entry, index)
    volumes = _normalize_volumes(entry, index)
    mip_lod_bias = float(entry.get("mipLodBias"))
    if not math.isfinite(mip_lod_bias):
        raise ReflectionProbeManifestError(f"probe {index}: non-finite mipLodBias")

    raw_image = entry.get("reflectionImage")
    if raw_image is None:
        asset = None
    else:
        asset = str(raw_image)
        if not asset:
            raise ReflectionProbeManifestError(
                f"probe {index}: reflectionImage must be null or a non-empty GfxImage identity"
            )

    present = asset is not None
    source = None
    oat_path = None
    if present:
        source, oat_path = _mapped_image(asset, extension)

    return {
        "index": index,
        "origin": origin,
        "lightingSH": sh,
        "reflectionImagePresent": present,
        "reflectionImage": asset,
        "reflectionOatImageAsset": asset,
        "reflectionSourceTexture": source,
        "reflectionOatImagePath": oat_path,
        "mipLodBias": mip_lod_bias,
        "probeVolumeCount": len(volumes),
        "probeVolumes": volumes,
        "source": entry.get("source"),
    }


def _validate_image_bijection(probes: list[dict]) -> tuple[int, int]:
    source_by_asset: dict[str, str] = {}
    asset_by_source: dict[str, str] = {}
    present_uses = 0

    for probe in probes:
        if not probe["reflectionImagePresent"]:
            if any(
                probe.get(key) is not None
                for key in (
                    "reflectionImage",
                    "reflectionOatImageAsset",
                    "reflectionSourceTexture",
                    "reflectionOatImagePath",
                )
            ):
                raise ReflectionProbeManifestError(
                    f"probe {probe['index']}: absent reflection image carries disk/asset identity"
                )
            continue

        present_uses += 1
        asset = str(probe["reflectionOatImageAsset"])
        source = str(probe["reflectionSourceTexture"])
        if not asset or not source:
            raise ReflectionProbeManifestError(
                f"probe {probe['index']}: present reflection image lacks asset/source"
            )

        prior_source = source_by_asset.setdefault(asset, source)
        if prior_source != source:
            raise ReflectionProbeManifestError(
                f"T6 reflection GfxImage {asset!r} maps to multiple disk sources: "
                f"{prior_source!r}, {source!r}"
            )
        prior_asset = asset_by_source.setdefault(source, asset)
        if prior_asset != asset:
            raise ReflectionProbeManifestError(
                "distinct T6 reflection GfxImage identities collide after OAT filename mapping: "
                f"{prior_asset!r}, {asset!r} -> {source!r}"
            )

    return present_uses, len(asset_by_source)


def build_manifest(
    world: dict,
    probe_catalog: dict,
    *,
    source_texture_extension: str = ".dds",
) -> dict:
    if world.get("format") != "t6-world-mesh-normalized-v1":
        raise ReflectionProbeManifestError(f"unsupported world format {world.get('format')!r}")
    surfaces = world.get("surfaces")
    if not isinstance(surfaces, list):
        raise ReflectionProbeManifestError("world must contain surfaces[]")

    if probe_catalog.get("format") != CATALOG_FORMAT:
        raise ReflectionProbeManifestError(
            f"unsupported reflection probe catalog {probe_catalog.get('format')!r}"
        )
    if world.get("map") and probe_catalog.get("map") and world["map"] != probe_catalog["map"]:
        raise ReflectionProbeManifestError(
            f"map mismatch: world={world['map']!r}, catalog={probe_catalog['map']!r}"
        )

    entries = probe_catalog.get("reflectionProbes", [])
    probe_count = int(probe_catalog.get("reflectionProbeCount", len(entries)))
    if probe_count < 0:
        raise ReflectionProbeManifestError("negative reflectionProbeCount")
    if not isinstance(entries, list) or len(entries) != probe_count:
        raise ReflectionProbeManifestError(
            f"reflection probe array/count mismatch "
            f"{len(entries) if isinstance(entries, list) else 'not-list'} != {probe_count}"
        )

    probes = [
        _normalize_probe(entry, index, source_texture_extension)
        for index, entry in enumerate(entries)
    ]
    present_image_uses, unique_disk_sources = _validate_image_bijection(probes)

    usage = Counter()
    bindings: list[dict] = []
    for surface in surfaces:
        surface_index = int(surface["index"])
        if "reflectionProbeIndex" not in surface or surface["reflectionProbeIndex"] is None:
            raise ReflectionProbeManifestError(
                f"surface {surface_index}: missing reflectionProbeIndex"
            )
        probe_index = int(surface["reflectionProbeIndex"])
        if probe_index < 0 or probe_index >= probe_count:
            raise ReflectionProbeManifestError(
                f"surface {surface_index}: reflectionProbeIndex {probe_index} outside "
                f"0..{probe_count - 1}; no no-probe sentinel is inferred"
            )

        usage[probe_index] += 1
        probe = probes[probe_index]
        bindings.append(
            {
                "surfaceIndex": surface_index,
                "reflectionProbeIndex": probe_index,
                "reflectionImagePresent": bool(probe["reflectionImagePresent"]),
                "reflectionOatImageAsset": probe["reflectionOatImageAsset"],
                "reflectionSourceTexture": probe["reflectionSourceTexture"],
                "reflectionOatImagePath": probe["reflectionOatImagePath"],
                "probeOrigin": probe["origin"],
                "lightingSH": probe["lightingSH"],
                "mipLodBias": probe["mipLodBias"],
                "probeVolumeCount": probe["probeVolumeCount"],
                "probeVolumes": probe["probeVolumes"],
            }
        )

    referenced = sorted(usage)
    unreferenced = [index for index in range(probe_count) if index not in usage]
    present_probe_count = sum(int(row["reflectionImagePresent"]) for row in probes)
    filename_changed = sum(
        int(
            row["reflectionImagePresent"]
            and row["reflectionSourceTexture"]
            != str(row["reflectionOatImageAsset"]) + source_texture_extension
        )
        for row in probes
    )

    return {
        "format": FORMAT,
        "map": world.get("map") or probe_catalog.get("map"),
        "source": {
            "producer": "t6_world_reflection_probe_manifest_v2.py",
            "worldFormat": world.get("format"),
            "probeCatalogFormat": probe_catalog.get("format"),
            "sourceTextureExtension": source_texture_extension,
            "oatImageFilenameReference": {
                "repository": "Laupetin/OpenAssetTools",
                "commit": "7d027e8f89118196713e955b0e11f8404149c54d",
                "path": "src/ObjCommon/Image/ImageCommon.cpp",
                "rule": "replace '*' with '_' then emit images/<cleanAssetName><extension>",
            },
            "gfxWorldStructure": (
                "GfxWorld.draw.reflectionProbeCount / reflectionProbes[]; "
                "GfxReflectionProbe.reflectionImage is nullable"
            ),
        },
        "policy": {
            "surfaceJoin": "exact GfxSurface.reflectionProbeIndex",
            "probeIndexZero": "ordinary valid dense index; no no-probe sentinel inferred",
            "imageJoin": (
                "exact GfxReflectionProbe.reflectionImage GfxImage identity when present; "
                "null pointer preserved as absent"
            ),
            "sourceTextureMapping": (
                "exact pinned OAT ImageDumper path/basename for present images only; "
                "T6 GfxImage identity retained separately"
            ),
            "oatImageFilenameCollision": (
                "fail closed if distinct present T6 GfxImage identities map to one flat staging basename"
            ),
            "probePayload": (
                "origin + lightingSH + reflectionImage + probeVolumes + mipLodBias preserved exactly; "
                "runtime GfxTexture pointer values omitted"
            ),
            "shading": (
                "resource ownership only; reflection equations are separate and no generic PBR mapping is inferred"
            ),
        },
        "stats": {
            "surfaceCount": len(surfaces),
            "reflectionProbeCount": probe_count,
            "presentReflectionImageProbeCount": present_probe_count,
            "absentReflectionImageProbeCount": probe_count - present_probe_count,
            "presentReflectionImageDependencyUseCount": present_image_uses,
            "oatImageUniqueDiskSourceCount": unique_disk_sources,
            "oatImageFilenameChangedDependencyCount": filename_changed,
            "referencedReflectionProbeCount": len(referenced),
            "unreferencedReflectionProbeCount": len(unreferenced),
            "surfaceUseCountByReflectionProbe": {
                str(index): usage[index] for index in referenced
            },
        },
        "reflectionProbes": probes,
        "surfaceBindings": bindings,
        "referencedReflectionProbeIndices": referenced,
        "unreferencedReflectionProbeIndices": unreferenced,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("world_json", type=Path)
    parser.add_argument("probe_catalog_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--source-texture-extension", default=".dds")
    args = parser.parse_args()

    world = json.loads(args.world_json.read_text(encoding="utf-8"))
    catalog = json.loads(args.probe_catalog_json.read_text(encoding="utf-8"))
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
