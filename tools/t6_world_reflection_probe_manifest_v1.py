#!/usr/bin/env python3
"""Join normalized T6 GfxWorld surfaces to exact reflection-probe assets.

The input catalog is deliberately structural. It archives the loaded retail
GfxReflectionProbe[] records by dense index: origin, lighting SH, reflection
GfxImage identity, volume planes/count and mipLodBias. This tool then joins each
normalized GfxSurface by its exact reflectionProbeIndex.

No nearest-probe search, box blending, PBR roughness conversion or environment
sampling semantics are inferred here. Surface index 0 is treated as an ordinary
valid probe index when present; there is no guessed "no probe" sentinel.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path


class ReflectionProbeManifestError(RuntimeError):
    pass


def _finite_vector(value, width: int, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != width:
        raise ReflectionProbeManifestError(f"{label} must contain exactly {width} values")
    out = [float(v) for v in value]
    if not all(math.isfinite(v) for v in out):
        raise ReflectionProbeManifestError(f"{label} contains non-finite values")
    return out


def _texture_name(image_asset: str, extension: str) -> str:
    if not image_asset:
        raise ReflectionProbeManifestError("empty reflection probe image asset")
    if "/" in image_asset or "\\" in image_asset or "\0" in image_asset:
        raise ReflectionProbeManifestError(
            f"reflection image asset must be an exact basename for staging: {image_asset!r}"
        )
    if extension and not extension.startswith("."):
        raise ReflectionProbeManifestError(
            f"source texture extension must be empty or begin with '.': {extension!r}"
        )
    return image_asset + extension


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
    if not isinstance(volumes, list) or len(volumes) != count:
        raise ReflectionProbeManifestError(
            f"probe {probe_index}: probe volume array/count mismatch"
        )
    out: list[dict] = []
    for volume_index, volume in enumerate(volumes):
        if not isinstance(volume, dict):
            raise ReflectionProbeManifestError(
                f"probe {probe_index} volume {volume_index}: expected object"
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

    if probe_catalog.get("format") != "t6-gfxworld-reflection-probe-catalog-v1":
        raise ReflectionProbeManifestError(
            f"unsupported reflection probe catalog {probe_catalog.get('format')!r}"
        )
    if world.get("map") and probe_catalog.get("map") and world["map"] != probe_catalog["map"]:
        raise ReflectionProbeManifestError(
            f"map mismatch: world={world['map']!r}, catalog={probe_catalog['map']!r}"
        )

    probes = probe_catalog.get("reflectionProbes", [])
    probe_count = int(probe_catalog.get("reflectionProbeCount", len(probes)))
    if probe_count < 0:
        raise ReflectionProbeManifestError("negative reflectionProbeCount")
    if not isinstance(probes, list) or len(probes) != probe_count:
        raise ReflectionProbeManifestError("reflection probe array/count mismatch")

    normalized_probes: list[dict] = []
    for expected_index, entry in enumerate(probes):
        if not isinstance(entry, dict):
            raise ReflectionProbeManifestError(f"probe {expected_index}: expected object")
        index = int(entry.get("index", expected_index))
        if index != expected_index:
            raise ReflectionProbeManifestError(
                f"reflection probes must be dense/in-order: expected {expected_index}, got {index}"
            )
        image = str(entry.get("reflectionImage") or "")
        mip_lod_bias = float(entry.get("mipLodBias"))
        if not math.isfinite(mip_lod_bias):
            raise ReflectionProbeManifestError(f"probe {index}: non-finite mipLodBias")
        normalized_probes.append(
            {
                "index": index,
                "origin": _finite_vector(entry.get("origin"), 3, f"probe {index} origin"),
                "lightingSH": _normalize_sh(entry, index),
                "reflectionImage": image,
                "reflectionSourceTexture": _texture_name(image, source_texture_extension),
                "mipLodBias": mip_lod_bias,
                "probeVolumeCount": int(entry.get("probeVolumeCount", len(entry.get("probeVolumes", [])))),
                "probeVolumes": _normalize_volumes(entry, index),
                "source": entry.get("source"),
            }
        )

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
                f"surface {surface_index}: reflectionProbeIndex {probe_index} outside 0..{probe_count - 1}"
            )
        usage[probe_index] += 1
        probe = normalized_probes[probe_index]
        bindings.append(
            {
                "surfaceIndex": surface_index,
                "reflectionProbeIndex": probe_index,
                "reflectionImage": probe["reflectionImage"],
                "reflectionSourceTexture": probe["reflectionSourceTexture"],
                "probeOrigin": probe["origin"],
                "mipLodBias": probe["mipLodBias"],
                "probeVolumeCount": probe["probeVolumeCount"],
            }
        )

    referenced = sorted(usage)
    unreferenced = [i for i in range(probe_count) if i not in usage]
    return {
        "format": "t6-world-reflection-probe-manifest-v1",
        "map": world.get("map") or probe_catalog.get("map"),
        "source": {
            "worldFormat": world.get("format"),
            "probeCatalogFormat": probe_catalog.get("format"),
            "sourceTextureExtension": source_texture_extension,
        },
        "policy": {
            "surfaceJoin": "exact GfxSurface.reflectionProbeIndex",
            "probeIndexZero": "ordinary valid dense probe index; no no-probe sentinel inferred",
            "imageJoin": "exact GfxReflectionProbe.reflectionImage GfxImage identity",
            "resourcePayload": (
                "origin + lightingSH + reflectionImage + probeVolumes + mipLodBias preserved; "
                "runtime GfxTexture pointer values are not archival identities"
            ),
            "shading": (
                "probe sampling/factor semantics are separate in t6_reflection_probe_semantics_v1.py; "
                "no PBR or nearest-probe substitution"
            ),
        },
        "stats": {
            "surfaceCount": len(surfaces),
            "reflectionProbeCount": probe_count,
            "referencedReflectionProbeCount": len(referenced),
            "unreferencedReflectionProbeCount": len(unreferenced),
            "surfaceUseCountByReflectionProbe": {
                str(index): usage[index] for index in referenced
            },
        },
        "reflectionProbes": normalized_probes,
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
