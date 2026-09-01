#!/usr/bin/env python3
"""Hardened lossless T6 world-lightmap DDS GLB archival embedding v2.

v1 established renderer-neutral raw-DDS storage in untyped GLB bufferViews.
v2 closes two provenance/accounting edge cases without changing that storage:

- the T6 GfxImage identity <-> OAT disk basename relationship must be one-to-one
  within one archive (both directions are checked before touching files);
- allow-missing accounting is by unique GfxImage identity, so a shared missing
  primary/secondary image is reported once rather than once per lightmap use.

No standard glTF image/texture/material lightmap binding is created. The T6
primary/secondary combine shader remains deliberately unsolved here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_lightmap_glb_embed_v1 import (
    LightmapGlbEmbedError,
    embed_lightmap_dds as embed_lightmap_dds_v1,
    validate_lightmap_archive as validate_lightmap_archive_v1,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity_pairs(lightmap_manifest: dict) -> list[tuple[str, str]]:
    if lightmap_manifest.get("format") != "t6-world-lightmap-manifest-v2":
        raise LightmapGlbEmbedError(
            f"unsupported lightmap manifest {lightmap_manifest.get('format')!r}"
        )
    pairs: list[tuple[str, str]] = []
    for lightmap in lightmap_manifest.get("lightmaps", []):
        for role in ("primary", "secondary"):
            asset = str(
                lightmap.get(f"{role}OatImageAsset")
                or lightmap.get(f"{role}Image")
                or ""
            )
            source = str(lightmap.get(f"{role}SourceTexture") or "")
            if not asset or not source:
                raise LightmapGlbEmbedError(
                    f"lightmap {lightmap.get('index')} {role}: missing asset/source identity"
                )
            pairs.append((asset, source))
    return pairs


def validate_identity_disk_bijection(lightmap_manifest: dict) -> bool:
    pairs = _identity_pairs(lightmap_manifest)
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
        raise LightmapGlbEmbedError(
            f"T6 GfxImage {asset!r} maps to multiple disk sources: {sources!r}"
        )

    collisions = {
        source: sorted(assets)
        for source, assets in assets_by_source.items()
        if len(assets) > 1
    }
    if collisions:
        source, assets = sorted(collisions.items())[0]
        raise LightmapGlbEmbedError(
            "distinct T6 GfxImage identities share one lightmap disk source: "
            f"{assets!r} -> {source!r}"
        )
    return True


def _dedupe_missing(archive: dict) -> None:
    unique: dict[str, dict] = {}
    for item in archive.get("missing", []):
        asset = str(item.get("gfxImageAsset") or "")
        source = str(item.get("sourceTexture") or "")
        if not asset or not source:
            raise LightmapGlbEmbedError("malformed missing lightmap dependency record")
        previous = unique.get(asset)
        if previous is not None and previous.get("sourceTexture") != source:
            raise LightmapGlbEmbedError(
                f"T6 GfxImage {asset!r} has inconsistent missing disk sources"
            )
        unique.setdefault(asset, item)
    archive["missing"] = list(unique.values())
    archive.setdefault("stats", {})["missingGfxImageCount"] = len(unique)


def embed_lightmap_dds(
    gltf: dict,
    raw: bytes,
    lightmap_manifest: dict,
    *,
    dds_root: Path,
    allow_missing: bool = False,
) -> tuple[dict, bytes]:
    validate_identity_disk_bijection(lightmap_manifest)
    document, out_raw = embed_lightmap_dds_v1(
        gltf,
        raw,
        lightmap_manifest,
        dds_root=dds_root,
        allow_missing=allow_missing,
    )
    archive = document.get("extras", {}).get("T6", {}).get("lightmapArchive")
    if not isinstance(archive, dict):
        raise LightmapGlbEmbedError("v1 embedding did not create lightmapArchive")
    _dedupe_missing(archive)
    archive["format"] = "t6-world-lightmap-glb-archive-v2"
    archive.setdefault("policy", {})["identityDiskMapping"] = (
        "bijective within archive: one T6 GfxImage identity per OAT disk basename and vice versa"
    )
    archive["policy"]["missingAccounting"] = (
        "unique GfxImage identities, not dependency-use count"
    )
    stats = archive.setdefault("stats", {})
    stats["accountedGfxImageCount"] = int(stats.get("embeddedGfxImageCount", 0)) + int(
        stats.get("missingGfxImageCount", 0)
    )
    validate_lightmap_archive(document, out_raw)
    return document, out_raw


def validate_lightmap_archive(gltf: dict, raw: bytes) -> bool:
    validate_lightmap_archive_v1(gltf, raw)
    archive = gltf.get("extras", {}).get("T6", {}).get("lightmapArchive")
    if archive.get("format") != "t6-world-lightmap-glb-archive-v2":
        raise LightmapGlbEmbedError(
            f"unsupported hardened lightmap archive {archive.get('format')!r}"
        )

    # Re-check the bijection from archived metadata, independent of the input
    # manifest used to create it.
    manifest_like = {
        "format": "t6-world-lightmap-manifest-v2",
        "lightmaps": [],
    }
    embedded_assets: set[str] = set()
    for lightmap in archive.get("lightmaps", []):
        reconstructed = {"index": lightmap.get("index")}
        for role in ("primary", "secondary"):
            item = lightmap[role]
            reconstructed[f"{role}OatImageAsset"] = item.get("gfxImageAsset")
            reconstructed[f"{role}SourceTexture"] = item.get("sourceTexture")
            if item.get("embedded"):
                embedded_assets.add(str(item.get("gfxImageAsset") or ""))
        manifest_like["lightmaps"].append(reconstructed)
    validate_identity_disk_bijection(manifest_like)

    missing = archive.get("missing", [])
    missing_assets = [str(item.get("gfxImageAsset") or "") for item in missing]
    if not all(missing_assets) or len(missing_assets) != len(set(missing_assets)):
        raise LightmapGlbEmbedError("missing lightmap dependencies are not unique by GfxImage")
    overlap = embedded_assets.intersection(missing_assets)
    if overlap:
        raise LightmapGlbEmbedError(
            f"lightmap assets cannot be both embedded and missing: {sorted(overlap)!r}"
        )

    stats = archive.get("stats", {})
    embedded_count = int(stats.get("embeddedGfxImageCount", -1))
    missing_count = int(stats.get("missingGfxImageCount", -1))
    unique_count = int(stats.get("uniqueGfxImageCount", -1))
    accounted_count = int(stats.get("accountedGfxImageCount", -1))
    if missing_count != len(missing_assets):
        raise LightmapGlbEmbedError("missing GfxImage stats do not match unique missing records")
    if accounted_count != embedded_count + missing_count:
        raise LightmapGlbEmbedError("accounted GfxImage stats are inconsistent")
    if accounted_count != unique_count:
        raise LightmapGlbEmbedError(
            "embedded + unique missing GfxImages do not cover the archive dependency identities"
        )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gltf_json", type=Path)
    parser.add_argument("raw_bin", type=Path)
    parser.add_argument("lightmap_manifest_json", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dds-root", type=Path, required=True)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--gltf", action="store_true", help="write embedded-buffer .gltf instead of GLB")
    args = parser.parse_args()

    gltf = json.loads(args.gltf_json.read_text(encoding="utf-8"))
    raw = args.raw_bin.read_bytes()
    manifest = json.loads(args.lightmap_manifest_json.read_text(encoding="utf-8"))
    out_gltf, out_raw = embed_lightmap_dds(
        gltf,
        raw,
        manifest,
        dds_root=args.dds_root,
        allow_missing=args.allow_missing,
    )
    payload = gltf_bytes(out_gltf, out_raw) if args.gltf else glb_bytes(out_gltf, out_raw)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "out": str(args.output),
                "bytes": len(payload),
                "sha256": _sha256(payload),
                "archiveStats": out_gltf["extras"]["T6"]["lightmapArchive"]["stats"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
