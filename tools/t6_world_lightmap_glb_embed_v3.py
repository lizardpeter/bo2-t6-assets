#!/usr/bin/env python3
"""Lossless T6 world-lightmap DDS GLB archival embedding v3.

v3 consumes `t6-world-lightmap-manifest-v3` and preserves nullable retail
GfxLightmapArray roles exactly. Present primary/secondary GfxImage roles are
archived as raw DDS bufferViews. Absent roles remain explicit null metadata and
create no file dependency, no missing-file record, and no invented fallback.

No standard glTF lightmap texture/material binding is created. The T6 shader
combine equation remains a separate reverse-engineering target.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_lightmap_glb_embed_v1 import (
    LightmapGlbEmbedError,
    _append_buffer_view,
    _sha256,
)


MANIFEST_FORMAT = "t6-world-lightmap-manifest-v3"
ARCHIVE_FORMAT = "t6-world-lightmap-glb-archive-v3"


def _safe_basename(value: str) -> str:
    if not value or value in (".", ".."):
        raise LightmapGlbEmbedError(f"invalid lightmap sourceTexture {value!r}")
    if "/" in value or "\\" in value or "\0" in value:
        raise LightmapGlbEmbedError(
            f"lightmap sourceTexture must be an exact flat basename: {value!r}"
        )
    return value


def _role_metadata(lightmap: dict, role: str) -> dict:
    present_key = f"{role}Present"
    if present_key not in lightmap:
        raise LightmapGlbEmbedError(
            f"lightmap {lightmap.get('index')} {role}: missing explicit {present_key}"
        )
    present = bool(lightmap[present_key])
    asset = lightmap.get(f"{role}OatImageAsset")
    if asset is None:
        asset = lightmap.get(f"{role}Image")
    source = lightmap.get(f"{role}SourceTexture")
    oat_path = lightmap.get(f"{role}OatImagePath")

    if present:
        asset = str(asset or "")
        source = _safe_basename(str(source or ""))
        if not asset:
            raise LightmapGlbEmbedError(
                f"lightmap {lightmap.get('index')} {role}: present role lacks GfxImage identity"
            )
        return {
            "present": True,
            "gfxImageAsset": asset,
            "sourceTexture": source,
            "oatImagePath": oat_path,
            "codeTextureSource": int(lightmap[f"{role}CodeTextureSource"]),
            "samplerAccessor": str(lightmap[f"{role}SamplerAccessor"]),
        }

    if asset not in (None, "") or source not in (None, "") or oat_path not in (None, ""):
        raise LightmapGlbEmbedError(
            f"lightmap {lightmap.get('index')} {role}: absent role carries image/disk identity"
        )
    return {
        "present": False,
        "gfxImageAsset": None,
        "sourceTexture": None,
        "oatImagePath": None,
        "codeTextureSource": int(lightmap[f"{role}CodeTextureSource"]),
        "samplerAccessor": str(lightmap[f"{role}SamplerAccessor"]),
    }


def _dependency_records(lightmap_manifest: dict) -> list[dict]:
    if lightmap_manifest.get("format") != MANIFEST_FORMAT:
        raise LightmapGlbEmbedError(
            f"unsupported lightmap manifest {lightmap_manifest.get('format')!r}"
        )

    records: list[dict] = []
    for expected_index, lightmap in enumerate(lightmap_manifest.get("lightmaps", [])):
        index = int(lightmap["index"])
        if index != expected_index:
            raise LightmapGlbEmbedError(
                f"lightmaps must be dense/in-order: expected {expected_index}, got {index}"
            )
        for role in ("primary", "secondary"):
            item = _role_metadata(lightmap, role)
            if not item["present"]:
                continue
            records.append(
                {
                    "lightmapIndex": index,
                    "role": role,
                    **item,
                }
            )
    return records


def validate_identity_disk_bijection(lightmap_manifest: dict) -> bool:
    records = _dependency_records(lightmap_manifest)
    sources_by_asset: dict[str, set[str]] = {}
    assets_by_source: dict[str, set[str]] = {}
    for record in records:
        asset = record["gfxImageAsset"]
        source = record["sourceTexture"]
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


def embed_lightmap_dds(
    gltf: dict,
    raw: bytes,
    lightmap_manifest: dict,
    *,
    dds_root: Path,
    allow_missing: bool = False,
) -> tuple[dict, bytes]:
    validate_identity_disk_bijection(lightmap_manifest)

    document = copy.deepcopy(gltf)
    if len(document.get("buffers", [])) != 1:
        raise LightmapGlbEmbedError(
            f"expected exactly one glTF buffer, found {len(document.get('buffers', []))}"
        )
    if int(document["buffers"][0].get("byteLength", -1)) != len(raw):
        raise LightmapGlbEmbedError(
            "input raw buffer length does not match glTF buffers[0].byteLength"
        )

    records = _dependency_records(lightmap_manifest)
    embedded_by_asset: dict[str, dict] = {}
    missing_by_asset: dict[str, dict] = {}

    for record in records:
        asset = record["gfxImageAsset"]
        source = record["sourceTexture"]
        existing = embedded_by_asset.get(asset)
        if existing is not None:
            if existing["sourceTexture"] != source:
                raise LightmapGlbEmbedError(
                    f"T6 GfxImage {asset!r} maps to multiple disk sources"
                )
            continue
        missing_existing = missing_by_asset.get(asset)
        if missing_existing is not None:
            if missing_existing["sourceTexture"] != source:
                raise LightmapGlbEmbedError(
                    f"T6 GfxImage {asset!r} has inconsistent missing disk sources"
                )
            continue

        path = dds_root / source
        if not path.is_file():
            item = {
                "gfxImageAsset": asset,
                "sourceTexture": source,
                "path": str(path),
            }
            missing_by_asset[asset] = item
            if not allow_missing:
                raise LightmapGlbEmbedError(f"missing exact lightmap DDS {path}")
            continue

        payload = path.read_bytes()
        if len(payload) < 4 or payload[:4] != b"DDS ":
            raise LightmapGlbEmbedError(
                f"lightmap source is not a DDS file: {path}"
            )
        view_index, raw = _append_buffer_view(
            document,
            raw,
            payload,
            name=f"T6 lightmap DDS:{asset}",
        )
        embedded_by_asset[asset] = {
            "gfxImageAsset": asset,
            "sourceTexture": source,
            "bytes": len(payload),
            "sha256": _sha256(payload),
            "bufferView": view_index,
            "mimeType": "image/vnd-ms.dds",
            "storage": "raw DDS bytes in untyped GLB bufferView",
        }

    archived_lightmaps: list[dict] = []
    for lightmap in lightmap_manifest.get("lightmaps", []):
        index = int(lightmap["index"])
        archive = {"index": index, "source": copy.deepcopy(lightmap.get("source"))}
        for role in ("primary", "secondary"):
            role_meta = _role_metadata(lightmap, role)
            item = {
                "present": bool(role_meta["present"]),
                "gfxImageAsset": role_meta["gfxImageAsset"],
                "sourceTexture": role_meta["sourceTexture"],
                "oatImagePath": role_meta["oatImagePath"],
                "codeTextureSource": role_meta["codeTextureSource"],
                "samplerAccessor": role_meta["samplerAccessor"],
                "embedded": False,
            }
            if role_meta["present"]:
                embedded = embedded_by_asset.get(role_meta["gfxImageAsset"])
                if embedded is not None:
                    item.update(
                        {
                            "embedded": True,
                            "bufferView": embedded["bufferView"],
                            "bytes": embedded["bytes"],
                            "sha256": embedded["sha256"],
                            "mimeType": embedded["mimeType"],
                        }
                    )
            archive[role] = item
        archived_lightmaps.append(archive)

    unique_assets = {record["gfxImageAsset"] for record in records}
    missing = list(missing_by_asset.values())
    archive_root = document.setdefault("extras", {}).setdefault("T6", {})
    archive_root["lightmapArchive"] = {
        "format": ARCHIVE_FORMAT,
        "sourceManifestFormat": lightmap_manifest.get("format"),
        "map": lightmap_manifest.get("map"),
        "policy": {
            "storage": "raw DDS payloads in untyped bufferViews",
            "standardGltfImagesCreated": False,
            "standardGltfTexturesCreated": False,
            "materialBindingsCreated": False,
            "shaderComposition": "not guessed",
            "assetIdentity": "exact T6 GfxImage identity for present roles only",
            "diskJoin": "exact OAT ImageDumper basename from manifest v3",
            "rolePresence": (
                "retail null primary/secondary GfxImage roles remain explicit null "
                "archive entries and create no DDS dependency or fallback"
            ),
            "missingAccounting": "unique present T6 GfxImage identity",
        },
        "codeSamplerContract": copy.deepcopy(
            lightmap_manifest.get("t6CodeSamplerContract", {})
        ),
        "stats": {
            "lightmapCount": len(archived_lightmaps),
            "declaredRoleCount": 2 * len(archived_lightmaps),
            "presentDependencyUseCount": len(records),
            "absentRoleCount": 2 * len(archived_lightmaps) - len(records),
            "uniqueGfxImageCount": len(unique_assets),
            "embeddedGfxImageCount": len(embedded_by_asset),
            "missingGfxImageCount": len(missing),
            "accountedGfxImageCount": len(embedded_by_asset) + len(missing),
            "surfaceBindingCount": len(
                lightmap_manifest.get("surfaceBindings", [])
            ),
        },
        "lightmaps": archived_lightmaps,
        "surfaceBindings": copy.deepcopy(
            lightmap_manifest.get("surfaceBindings", [])
        ),
        "missing": missing,
    }

    validate_lightmap_archive(document, raw)
    return document, raw


def validate_lightmap_archive(gltf: dict, raw: bytes) -> bool:
    if len(gltf.get("buffers", [])) != 1:
        raise LightmapGlbEmbedError("lightmap archive requires exactly one buffer")
    if int(gltf["buffers"][0].get("byteLength", -1)) != len(raw):
        raise LightmapGlbEmbedError("archived raw buffer length mismatch")

    archive = gltf.get("extras", {}).get("T6", {}).get("lightmapArchive")
    if not isinstance(archive, dict):
        raise LightmapGlbEmbedError("missing extras.T6.lightmapArchive")
    if archive.get("format") != ARCHIVE_FORMAT:
        raise LightmapGlbEmbedError(
            f"unsupported nullable lightmap archive {archive.get('format')!r}"
        )
    if archive.get("sourceManifestFormat") != MANIFEST_FORMAT:
        raise LightmapGlbEmbedError("nullable lightmap archive source manifest mismatch")

    views = gltf.get("bufferViews", [])
    seen_payloads: dict[int, tuple[str, int]] = {}
    present_use_count = 0
    present_assets: set[str] = set()
    source_by_asset: dict[str, str] = {}
    asset_by_source: dict[str, str] = {}

    for expected_index, lightmap in enumerate(archive.get("lightmaps", [])):
        if int(lightmap.get("index", -1)) != expected_index:
            raise LightmapGlbEmbedError("archived lightmap indices are not dense/in-order")
        for role in ("primary", "secondary"):
            item = lightmap.get(role)
            if not isinstance(item, dict):
                raise LightmapGlbEmbedError(
                    f"lightmap {expected_index} {role}: missing archive role"
                )
            present = bool(item.get("present"))
            asset = item.get("gfxImageAsset")
            source = item.get("sourceTexture")
            if not present:
                if item.get("embedded"):
                    raise LightmapGlbEmbedError(
                        f"lightmap {expected_index} {role}: absent role cannot be embedded"
                    )
                if asset not in (None, "") or source not in (None, ""):
                    raise LightmapGlbEmbedError(
                        f"lightmap {expected_index} {role}: absent role carries image identity"
                    )
                continue

            present_use_count += 1
            asset = str(asset or "")
            source = str(source or "")
            if not asset or not source:
                raise LightmapGlbEmbedError(
                    f"lightmap {expected_index} {role}: present role lost identity"
                )
            prior_source = source_by_asset.setdefault(asset, source)
            if prior_source != source:
                raise LightmapGlbEmbedError(
                    f"T6 GfxImage {asset!r} maps to multiple archived disk sources"
                )
            prior_asset = asset_by_source.setdefault(source, asset)
            if prior_asset != asset:
                raise LightmapGlbEmbedError(
                    f"archived disk source {source!r} aliases distinct GfxImages"
                )
            present_assets.add(asset)

            if not item.get("embedded"):
                continue
            view_index = int(item["bufferView"])
            if view_index < 0 or view_index >= len(views):
                raise LightmapGlbEmbedError(
                    f"lightmap {expected_index} {role}: bad bufferView {view_index}"
                )
            view = views[view_index]
            start = int(view.get("byteOffset", 0))
            length = int(view["byteLength"])
            end = start + length
            if start < 0 or length < 4 or end > len(raw):
                raise LightmapGlbEmbedError(
                    f"lightmap {expected_index} {role}: bufferView outside raw buffer"
                )
            payload = raw[start:end]
            if payload[:4] != b"DDS ":
                raise LightmapGlbEmbedError(
                    f"lightmap {expected_index} {role}: embedded payload lost DDS magic"
                )
            if _sha256(payload) != item.get("sha256"):
                raise LightmapGlbEmbedError(
                    f"lightmap {expected_index} {role}: SHA-256 mismatch"
                )
            if length != int(item.get("bytes", -1)):
                raise LightmapGlbEmbedError(
                    f"lightmap {expected_index} {role}: byte count mismatch"
                )
            prior = seen_payloads.get(view_index)
            identity = (asset, length)
            if prior is not None and prior != identity:
                raise LightmapGlbEmbedError(
                    f"bufferView {view_index} is aliased by inconsistent GfxImage metadata"
                )
            seen_payloads[view_index] = identity

    missing = archive.get("missing", [])
    if not isinstance(missing, list):
        raise LightmapGlbEmbedError("missing lightmap dependency table is not a list")
    missing_assets = [str(item.get("gfxImageAsset") or "") for item in missing]
    if not all(missing_assets) or len(missing_assets) != len(set(missing_assets)):
        raise LightmapGlbEmbedError(
            "missing lightmap dependencies are not unique by present GfxImage"
        )
    if not set(missing_assets).issubset(present_assets):
        raise LightmapGlbEmbedError(
            "missing table references an absent/nonexistent lightmap role identity"
        )

    embedded_assets = {
        str(item.get("gfxImageAsset"))
        for lightmap in archive.get("lightmaps", [])
        for item in (lightmap["primary"], lightmap["secondary"])
        if item.get("present") and item.get("embedded")
    }
    overlap = embedded_assets.intersection(missing_assets)
    if overlap:
        raise LightmapGlbEmbedError(
            f"lightmap assets cannot be both embedded and missing: {sorted(overlap)!r}"
        )

    stats = archive.get("stats", {})
    declared_roles = 2 * len(archive.get("lightmaps", []))
    if int(stats.get("declaredRoleCount", -1)) != declared_roles:
        raise LightmapGlbEmbedError("declared lightmap role stats are inconsistent")
    if int(stats.get("presentDependencyUseCount", -1)) != present_use_count:
        raise LightmapGlbEmbedError("present lightmap dependency-use stats are inconsistent")
    if int(stats.get("absentRoleCount", -1)) != declared_roles - present_use_count:
        raise LightmapGlbEmbedError("absent lightmap role stats are inconsistent")
    if int(stats.get("uniqueGfxImageCount", -1)) != len(present_assets):
        raise LightmapGlbEmbedError("unique present GfxImage stats are inconsistent")
    if int(stats.get("embeddedGfxImageCount", -1)) != len(embedded_assets):
        raise LightmapGlbEmbedError("embedded GfxImage stats are inconsistent")
    if int(stats.get("missingGfxImageCount", -1)) != len(missing_assets):
        raise LightmapGlbEmbedError("missing GfxImage stats are inconsistent")
    accounted = len(embedded_assets) + len(missing_assets)
    if int(stats.get("accountedGfxImageCount", -1)) != accounted:
        raise LightmapGlbEmbedError("accounted GfxImage stats are inconsistent")
    if accounted != len(present_assets):
        raise LightmapGlbEmbedError(
            "embedded + missing present GfxImages do not cover archive dependencies"
        )
    if len(seen_payloads) != len(embedded_assets):
        raise LightmapGlbEmbedError(
            "embedded lightmap bufferView count does not match unique embedded GfxImages"
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
    parser.add_argument(
        "--gltf", action="store_true", help="write embedded-buffer .gltf instead of GLB"
    )
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
