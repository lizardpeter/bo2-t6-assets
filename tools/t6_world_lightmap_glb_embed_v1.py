#!/usr/bin/env python3
"""Embed exact T6 world-lightmap DDS payloads into a GLB binary buffer losslessly.

This is an archival/provenance layer, not a guessed renderer conversion.

Input:
- an already-built internal glTF document + raw binary buffer;
- `t6-world-lightmap-manifest-v2`;
- a flat directory containing the exact OAT-dumped DDS files named by the
  manifest's `primarySourceTexture` / `secondarySourceTexture` fields.

Output:
- the same glTF scene/material representation;
- exact DDS payloads appended as untyped bufferViews;
- `extras.T6.lightmapArchive` describing every primary/secondary asset,
  code-sampler identity, SHA-256, bufferView, lightmap index, UV set, and
  surface binding.

Deliberately NOT created:
- glTF `image` objects for the DDS payloads;
- glTF `texture` objects for the DDS payloads;
- material/PBR lightmap bindings;
- any primary/secondary combine equation.

The raw bytes remain available inside one GLB so a future source-closed T6
renderer can consume them without needing the original extraction directory.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes


class LightmapGlbEmbedError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_basename(value: str) -> str:
    if not value or value in (".", ".."):
        raise LightmapGlbEmbedError(f"invalid lightmap sourceTexture {value!r}")
    if "/" in value or "\\" in value or "\0" in value:
        raise LightmapGlbEmbedError(
            f"lightmap sourceTexture must be an exact flat basename: {value!r}"
        )
    return value


def _append_buffer_view(
    gltf: dict,
    raw: bytes,
    payload: bytes,
    *,
    name: str,
) -> tuple[int, bytes]:
    mutable = bytearray(raw)
    while len(mutable) % 4:
        mutable.append(0)
    offset = len(mutable)
    mutable.extend(payload)
    view_index = len(gltf.setdefault("bufferViews", []))
    gltf["bufferViews"].append(
        {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(payload),
            "name": name,
        }
    )
    out = bytes(mutable)
    buffers = gltf.setdefault("buffers", [])
    if len(buffers) != 1:
        raise LightmapGlbEmbedError(
            f"expected exactly one glTF buffer, found {len(buffers)}"
        )
    buffers[0]["byteLength"] = len(out)
    return view_index, out


def _dependency_records(lightmap_manifest: dict) -> list[dict]:
    if lightmap_manifest.get("format") != "t6-world-lightmap-manifest-v2":
        raise LightmapGlbEmbedError(
            f"unsupported lightmap manifest {lightmap_manifest.get('format')!r}"
        )

    records: list[dict] = []
    expected_index = 0
    for lightmap in lightmap_manifest.get("lightmaps", []):
        index = int(lightmap["index"])
        if index != expected_index:
            raise LightmapGlbEmbedError(
                f"lightmaps must be dense/in-order: expected {expected_index}, got {index}"
            )
        expected_index += 1
        for role in ("primary", "secondary"):
            source = _safe_basename(str(lightmap.get(f"{role}SourceTexture") or ""))
            asset = str(
                lightmap.get(f"{role}OatImageAsset")
                or lightmap.get(f"{role}Image")
                or ""
            )
            if not asset:
                raise LightmapGlbEmbedError(
                    f"lightmap {index} {role}: empty T6 GfxImage identity"
                )
            records.append(
                {
                    "lightmapIndex": index,
                    "role": role,
                    "sourceTexture": source,
                    "oatImagePath": lightmap.get(f"{role}OatImagePath"),
                    "gfxImageAsset": asset,
                    "codeTextureSource": int(lightmap[f"{role}CodeTextureSource"]),
                    "samplerAccessor": str(lightmap[f"{role}SamplerAccessor"]),
                }
            )

    by_source: dict[str, set[str]] = {}
    for record in records:
        by_source.setdefault(record["sourceTexture"], set()).add(
            record["gfxImageAsset"]
        )
    collisions = {
        source: sorted(assets)
        for source, assets in by_source.items()
        if len(assets) > 1
    }
    if collisions:
        source, assets = sorted(collisions.items())[0]
        raise LightmapGlbEmbedError(
            "distinct T6 GfxImage identities share one lightmap disk source: "
            f"{assets!r} -> {source!r}"
        )
    return records


def embed_lightmap_dds(
    gltf: dict,
    raw: bytes,
    lightmap_manifest: dict,
    *,
    dds_root: Path,
    allow_missing: bool = False,
) -> tuple[dict, bytes]:
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
    missing: list[dict] = []

    for record in records:
        asset = record["gfxImageAsset"]
        source = record["sourceTexture"]
        existing = embedded_by_asset.get(asset)
        if existing is not None:
            if existing["sourceTexture"] != source:
                raise LightmapGlbEmbedError(
                    f"T6 GfxImage {asset!r} maps to multiple disk sources: "
                    f"{existing['sourceTexture']!r}, {source!r}"
                )
            continue

        path = dds_root / source
        if not path.is_file():
            item = {
                "gfxImageAsset": asset,
                "sourceTexture": source,
                "path": str(path),
            }
            missing.append(item)
            if not allow_missing:
                raise LightmapGlbEmbedError(f"missing exact lightmap DDS {path}")
            continue

        payload = path.read_bytes()
        if len(payload) < 4 or payload[:4] != b"DDS ":
            raise LightmapGlbEmbedError(
                f"lightmap source is not a DDS file: {path}"
            )
        sha = _sha256(payload)
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
            "sha256": sha,
            "bufferView": view_index,
            "mimeType": "image/vnd-ms.dds",
            "storage": "raw DDS bytes in untyped GLB bufferView",
        }

    archived_lightmaps: list[dict] = []
    for lightmap in lightmap_manifest.get("lightmaps", []):
        index = int(lightmap["index"])
        archive = {"index": index}
        for role in ("primary", "secondary"):
            asset = str(
                lightmap.get(f"{role}OatImageAsset")
                or lightmap.get(f"{role}Image")
                or ""
            )
            source = str(lightmap.get(f"{role}SourceTexture") or "")
            embedded = embedded_by_asset.get(asset)
            archive[role] = {
                "gfxImageAsset": asset,
                "sourceTexture": source,
                "oatImagePath": lightmap.get(f"{role}OatImagePath"),
                "codeTextureSource": int(lightmap[f"{role}CodeTextureSource"]),
                "samplerAccessor": str(lightmap[f"{role}SamplerAccessor"]),
                "embedded": embedded is not None,
                **(
                    {
                        "bufferView": embedded["bufferView"],
                        "bytes": embedded["bytes"],
                        "sha256": embedded["sha256"],
                        "mimeType": embedded["mimeType"],
                    }
                    if embedded is not None
                    else {}
                ),
            }
        archived_lightmaps.append(archive)

    archive_root = document.setdefault("extras", {}).setdefault("T6", {})
    archive_root["lightmapArchive"] = {
        "format": "t6-world-lightmap-glb-archive-v1",
        "sourceManifestFormat": lightmap_manifest.get("format"),
        "map": lightmap_manifest.get("map"),
        "policy": {
            "storage": "raw DDS payloads in untyped bufferViews",
            "standardGltfImagesCreated": False,
            "standardGltfTexturesCreated": False,
            "materialBindingsCreated": False,
            "shaderComposition": "not guessed",
            "assetIdentity": "exact T6 GfxImage identity",
            "diskJoin": "exact OAT ImageDumper basename from manifest v2",
        },
        "codeSamplerContract": copy.deepcopy(
            lightmap_manifest.get("t6CodeSamplerContract", {})
        ),
        "stats": {
            "lightmapCount": len(archived_lightmaps),
            "dependencyUseCount": len(records),
            "uniqueGfxImageCount": len({r["gfxImageAsset"] for r in records}),
            "embeddedGfxImageCount": len(embedded_by_asset),
            "missingGfxImageCount": len(missing),
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
    views = gltf.get("bufferViews", [])
    archive = gltf.get("extras", {}).get("T6", {}).get("lightmapArchive")
    if not isinstance(archive, dict):
        raise LightmapGlbEmbedError("missing extras.T6.lightmapArchive")

    seen_payloads: dict[int, tuple[str, int]] = {}
    for lightmap in archive.get("lightmaps", []):
        for role in ("primary", "secondary"):
            item = lightmap[role]
            if not item.get("embedded"):
                continue
            view_index = int(item["bufferView"])
            if view_index < 0 or view_index >= len(views):
                raise LightmapGlbEmbedError(
                    f"lightmap {lightmap['index']} {role}: bad bufferView {view_index}"
                )
            view = views[view_index]
            start = int(view.get("byteOffset", 0))
            length = int(view["byteLength"])
            end = start + length
            if start < 0 or length < 4 or end > len(raw):
                raise LightmapGlbEmbedError(
                    f"lightmap {lightmap['index']} {role}: bufferView outside raw buffer"
                )
            payload = raw[start:end]
            if payload[:4] != b"DDS ":
                raise LightmapGlbEmbedError(
                    f"lightmap {lightmap['index']} {role}: embedded payload lost DDS magic"
                )
            actual = _sha256(payload)
            if actual != item["sha256"]:
                raise LightmapGlbEmbedError(
                    f"lightmap {lightmap['index']} {role}: SHA-256 mismatch"
                )
            if length != int(item["bytes"]):
                raise LightmapGlbEmbedError(
                    f"lightmap {lightmap['index']} {role}: byte count mismatch"
                )
            prior = seen_payloads.get(view_index)
            identity = (str(item["gfxImageAsset"]), length)
            if prior is not None and prior != identity:
                raise LightmapGlbEmbedError(
                    f"bufferView {view_index} is aliased by inconsistent GfxImage metadata"
                )
            seen_payloads[view_index] = identity

    stats = archive.get("stats", {})
    if len(seen_payloads) != int(stats.get("embeddedGfxImageCount", -1)):
        raise LightmapGlbEmbedError(
            "embedded lightmap bufferView count does not match archive stats"
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
