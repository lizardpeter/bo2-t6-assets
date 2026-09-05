#!/usr/bin/env python3
"""Losslessly archive exact T6 reflection-probe DDS payloads inside a GLB.

This stage consumes `t6-world-reflection-probe-manifest-v2` and appends each
unique present reflection GfxImage DDS payload as an untyped GLB bufferView.
DDS bytes are preserved verbatim so cubemap faces, mip chains and native pixel
format survive even though generic glTF has no core cubemap material binding.

Deliberately NOT created:
- standard glTF images/textures for the DDS payloads;
- Blender/PBR environment bindings;
- nearest-probe selection or probe blending;
- guessed cubemap face extraction;
- a replacement image for nullable retail reflectionImage roles.

The archive keeps the exact dense probe records and surfaceBindings alongside
payload SHA-256/bufferView identity for a later source-closed renderer.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_lightmap_glb_embed_v1 import _append_buffer_view


MANIFEST_FORMAT = "t6-world-reflection-probe-manifest-v2"
ARCHIVE_FORMAT = "t6-world-reflection-probe-glb-archive-v1"


class ReflectionProbeGlbEmbedError(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_basename(value: str) -> str:
    if not value or value in (".", ".."):
        raise ReflectionProbeGlbEmbedError(
            f"invalid reflection probe sourceTexture {value!r}"
        )
    if "/" in value or "\\" in value or "\0" in value:
        raise ReflectionProbeGlbEmbedError(
            f"reflection probe sourceTexture must be an exact flat basename: {value!r}"
        )
    return value


def _probe_records(manifest: dict) -> list[dict]:
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ReflectionProbeGlbEmbedError(
            f"unsupported reflection probe manifest {manifest.get('format')!r}"
        )

    probes = manifest.get("reflectionProbes")
    if not isinstance(probes, list):
        raise ReflectionProbeGlbEmbedError("reflection probe manifest lacks reflectionProbes[]")

    records: list[dict] = []
    source_by_asset: dict[str, str] = {}
    asset_by_source: dict[str, str] = {}
    for expected_index, probe in enumerate(probes):
        index = int(probe.get("index", -1))
        if index != expected_index:
            raise ReflectionProbeGlbEmbedError(
                f"reflection probes must be dense/in-order: expected {expected_index}, got {index}"
            )
        present = bool(probe.get("reflectionImagePresent"))
        asset = probe.get("reflectionOatImageAsset")
        source = probe.get("reflectionSourceTexture")
        oat_path = probe.get("reflectionOatImagePath")

        if not present:
            if asset not in (None, "") or source not in (None, "") or oat_path not in (None, ""):
                raise ReflectionProbeGlbEmbedError(
                    f"probe {index}: absent reflection image carries asset/disk identity"
                )
            continue

        asset = str(asset or "")
        source = _safe_basename(str(source or ""))
        if not asset:
            raise ReflectionProbeGlbEmbedError(
                f"probe {index}: present reflection image lacks exact GfxImage identity"
            )

        prior_source = source_by_asset.setdefault(asset, source)
        if prior_source != source:
            raise ReflectionProbeGlbEmbedError(
                f"T6 reflection GfxImage {asset!r} maps to multiple disk sources: "
                f"{prior_source!r}, {source!r}"
            )
        prior_asset = asset_by_source.setdefault(source, asset)
        if prior_asset != asset:
            raise ReflectionProbeGlbEmbedError(
                "distinct T6 reflection GfxImage identities share one disk source: "
                f"{prior_asset!r}, {asset!r} -> {source!r}"
            )

        records.append(
            {
                "reflectionProbeIndex": index,
                "gfxImageAsset": asset,
                "sourceTexture": source,
                "oatImagePath": oat_path,
            }
        )
    return records


def _validate_surface_bindings(manifest: dict, probe_count: int) -> None:
    bindings = manifest.get("surfaceBindings")
    if not isinstance(bindings, list):
        raise ReflectionProbeGlbEmbedError("reflection probe manifest lacks surfaceBindings[]")
    seen_surfaces: set[int] = set()
    probes = manifest["reflectionProbes"]
    for binding in bindings:
        surface = int(binding.get("surfaceIndex", -1))
        if surface < 0 or surface in seen_surfaces:
            raise ReflectionProbeGlbEmbedError(
                f"invalid/duplicate reflection surface binding {surface}"
            )
        seen_surfaces.add(surface)
        probe_index = int(binding.get("reflectionProbeIndex", -1))
        if probe_index < 0 or probe_index >= probe_count:
            raise ReflectionProbeGlbEmbedError(
                f"surface {surface}: reflectionProbeIndex {probe_index} outside 0..{probe_count - 1}"
            )
        expected_present = bool(probes[probe_index]["reflectionImagePresent"])
        if bool(binding.get("reflectionImagePresent")) != expected_present:
            raise ReflectionProbeGlbEmbedError(
                f"surface {surface}: reflection image presence disagrees with probe {probe_index}"
            )


def embed_reflection_probe_dds(
    gltf: dict,
    raw: bytes,
    reflection_manifest: dict,
    *,
    dds_root: Path,
    allow_missing: bool = False,
) -> tuple[dict, bytes]:
    document = copy.deepcopy(gltf)
    if len(document.get("buffers", [])) != 1:
        raise ReflectionProbeGlbEmbedError(
            f"expected exactly one glTF buffer, found {len(document.get('buffers', []))}"
        )
    if int(document["buffers"][0].get("byteLength", -1)) != len(raw):
        raise ReflectionProbeGlbEmbedError(
            "input raw buffer length does not match glTF buffers[0].byteLength"
        )

    records = _probe_records(reflection_manifest)
    probe_count = len(reflection_manifest.get("reflectionProbes", []))
    _validate_surface_bindings(reflection_manifest, probe_count)

    image_count_before = len(document.get("images", []))
    texture_count_before = len(document.get("textures", []))
    material_count_before = len(document.get("materials", []))

    embedded_by_asset: dict[str, dict] = {}
    missing_by_asset: dict[str, dict] = {}

    for record in records:
        asset = record["gfxImageAsset"]
        source = record["sourceTexture"]
        if asset in embedded_by_asset or asset in missing_by_asset:
            continue

        path = dds_root / source
        if not path.is_file():
            missing_by_asset[asset] = {
                "gfxImageAsset": asset,
                "sourceTexture": source,
                "path": str(path),
            }
            if not allow_missing:
                raise ReflectionProbeGlbEmbedError(
                    f"missing exact reflection probe DDS {path}"
                )
            continue

        payload = path.read_bytes()
        if len(payload) < 4 or payload[:4] != b"DDS ":
            raise ReflectionProbeGlbEmbedError(
                f"reflection probe source is not a DDS file: {path}"
            )
        view_index, raw = _append_buffer_view(
            document,
            raw,
            payload,
            name=f"T6 reflection probe DDS:{asset}",
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

    archived_probes: list[dict] = []
    for probe in reflection_manifest["reflectionProbes"]:
        index = int(probe["index"])
        present = bool(probe["reflectionImagePresent"])
        archive = {
            "index": index,
            "origin": copy.deepcopy(probe["origin"]),
            "lightingSH": copy.deepcopy(probe["lightingSH"]),
            "reflectionImagePresent": present,
            "reflectionOatImageAsset": probe.get("reflectionOatImageAsset"),
            "reflectionSourceTexture": probe.get("reflectionSourceTexture"),
            "reflectionOatImagePath": probe.get("reflectionOatImagePath"),
            "probeVolumeCount": int(probe["probeVolumeCount"]),
            "probeVolumes": copy.deepcopy(probe["probeVolumes"]),
            "mipLodBias": float(probe["mipLodBias"]),
            "embedded": False,
        }
        if present:
            asset = str(probe["reflectionOatImageAsset"])
            embedded = embedded_by_asset.get(asset)
            if embedded is not None:
                archive.update(
                    {
                        "embedded": True,
                        "bufferView": embedded["bufferView"],
                        "bytes": embedded["bytes"],
                        "sha256": embedded["sha256"],
                        "mimeType": embedded["mimeType"],
                    }
                )
        archived_probes.append(archive)

    unique_assets = {record["gfxImageAsset"] for record in records}
    missing = list(missing_by_asset.values())
    root = document.setdefault("extras", {}).setdefault("T6", {})
    if "reflectionProbeArchive" in root:
        raise ReflectionProbeGlbEmbedError(
            "input glTF already contains extras.T6.reflectionProbeArchive; refusing overwrite"
        )
    root["reflectionProbeArchive"] = {
        "format": ARCHIVE_FORMAT,
        "sourceManifestFormat": reflection_manifest.get("format"),
        "map": reflection_manifest.get("map"),
        "policy": {
            "storage": "verbatim raw DDS payloads in untyped GLB bufferViews",
            "ddsSemantics": (
                "faces/mips/pixel format remain inside original DDS; no cubemap flattening or face extraction"
            ),
            "standardGltfImagesCreated": False,
            "standardGltfTexturesCreated": False,
            "materialBindingsCreated": False,
            "surfaceJoin": "exact preserved GfxSurface.reflectionProbeIndex",
            "nullableReflectionImage": "null retail role remains null and creates no DDS dependency",
            "rendererSemantics": (
                "separate t6_reflection_probe_semantics_v1 contract; no generic PBR/environment substitution"
            ),
            "missingAccounting": "unique present T6 GfxImage identity",
        },
        "stats": {
            "reflectionProbeCount": probe_count,
            "surfaceBindingCount": len(reflection_manifest.get("surfaceBindings", [])),
            "presentDependencyUseCount": len(records),
            "uniquePresentGfxImageCount": len(unique_assets),
            "embeddedGfxImageCount": len(embedded_by_asset),
            "missingGfxImageCount": len(missing_by_asset),
            "accountedGfxImageCount": len(embedded_by_asset) + len(missing_by_asset),
            "absentReflectionImageProbeCount": sum(
                int(not probe["reflectionImagePresent"])
                for probe in reflection_manifest["reflectionProbes"]
            ),
        },
        "reflectionProbes": archived_probes,
        "surfaceBindings": copy.deepcopy(reflection_manifest.get("surfaceBindings", [])),
        "referencedReflectionProbeIndices": copy.deepcopy(
            reflection_manifest.get("referencedReflectionProbeIndices", [])
        ),
        "unreferencedReflectionProbeIndices": copy.deepcopy(
            reflection_manifest.get("unreferencedReflectionProbeIndices", [])
        ),
        "missing": missing,
    }

    if len(document.get("images", [])) != image_count_before:
        raise ReflectionProbeGlbEmbedError("reflection archive unexpectedly modified glTF images[]")
    if len(document.get("textures", [])) != texture_count_before:
        raise ReflectionProbeGlbEmbedError("reflection archive unexpectedly modified glTF textures[]")
    if len(document.get("materials", [])) != material_count_before:
        raise ReflectionProbeGlbEmbedError("reflection archive unexpectedly modified glTF materials[]")

    validate_reflection_probe_archive(document, raw)
    return document, raw


def validate_reflection_probe_archive(gltf: dict, raw: bytes) -> bool:
    if len(gltf.get("buffers", [])) != 1:
        raise ReflectionProbeGlbEmbedError("reflection archive requires exactly one glTF buffer")
    if int(gltf["buffers"][0].get("byteLength", -1)) != len(raw):
        raise ReflectionProbeGlbEmbedError("reflection archive raw buffer length mismatch")

    archive = gltf.get("extras", {}).get("T6", {}).get("reflectionProbeArchive")
    if not isinstance(archive, dict) or archive.get("format") != ARCHIVE_FORMAT:
        raise ReflectionProbeGlbEmbedError("missing/invalid extras.T6.reflectionProbeArchive")
    if archive.get("sourceManifestFormat") != MANIFEST_FORMAT:
        raise ReflectionProbeGlbEmbedError("reflection archive source manifest mismatch")

    views = gltf.get("bufferViews", [])
    payload_by_asset: dict[str, tuple[int, str, int, str]] = {}
    source_by_asset: dict[str, str] = {}
    asset_by_source: dict[str, str] = {}
    present_assets: set[str] = set()
    absent_count = 0

    for expected_index, probe in enumerate(archive.get("reflectionProbes", [])):
        if int(probe.get("index", -1)) != expected_index:
            raise ReflectionProbeGlbEmbedError("archived reflection probe indices are not dense/in-order")
        present = bool(probe.get("reflectionImagePresent"))
        asset = probe.get("reflectionOatImageAsset")
        source = probe.get("reflectionSourceTexture")
        embedded = bool(probe.get("embedded"))

        if not present:
            absent_count += 1
            if asset not in (None, "") or source not in (None, "") or embedded:
                raise ReflectionProbeGlbEmbedError(
                    f"probe {expected_index}: absent archived image carries identity/payload"
                )
            continue

        asset = str(asset or "")
        source = str(source or "")
        if not asset or not source:
            raise ReflectionProbeGlbEmbedError(
                f"probe {expected_index}: present archived image lost identity"
            )
        present_assets.add(asset)
        if source_by_asset.setdefault(asset, source) != source:
            raise ReflectionProbeGlbEmbedError(
                f"archived T6 reflection GfxImage {asset!r} maps to multiple sources"
            )
        if asset_by_source.setdefault(source, asset) != asset:
            raise ReflectionProbeGlbEmbedError(
                f"archived reflection source {source!r} aliases distinct GfxImages"
            )

        if not embedded:
            continue
        view_index = int(probe.get("bufferView", -1))
        if view_index < 0 or view_index >= len(views):
            raise ReflectionProbeGlbEmbedError(
                f"probe {expected_index}: invalid archived DDS bufferView {view_index}"
            )
        view = views[view_index]
        offset = int(view.get("byteOffset", 0))
        length = int(view.get("byteLength", -1))
        if offset < 0 or length < 4 or offset + length > len(raw):
            raise ReflectionProbeGlbEmbedError(
                f"probe {expected_index}: archived DDS bufferView outside raw buffer"
            )
        payload = raw[offset:offset + length]
        if payload[:4] != b"DDS ":
            raise ReflectionProbeGlbEmbedError(
                f"probe {expected_index}: archived payload is not DDS"
            )
        sha = _sha256(payload)
        if int(probe.get("bytes", -1)) != len(payload) or probe.get("sha256") != sha:
            raise ReflectionProbeGlbEmbedError(
                f"probe {expected_index}: archived DDS size/hash mismatch"
            )
        identity = (view_index, sha, len(payload), source)
        prior = payload_by_asset.setdefault(asset, identity)
        if prior != identity:
            raise ReflectionProbeGlbEmbedError(
                f"T6 reflection GfxImage {asset!r} is duplicated with inconsistent payload identity"
            )

    missing = archive.get("missing", [])
    if not isinstance(missing, list):
        raise ReflectionProbeGlbEmbedError("reflection archive missing[] is not a list")
    missing_assets = {str(item.get("gfxImageAsset") or "") for item in missing}
    if "" in missing_assets:
        raise ReflectionProbeGlbEmbedError("reflection archive has missing entry without GfxImage identity")
    embedded_assets = set(payload_by_asset)
    if embedded_assets & missing_assets:
        raise ReflectionProbeGlbEmbedError("reflection GfxImage is both embedded and missing")
    if embedded_assets | missing_assets != present_assets:
        raise ReflectionProbeGlbEmbedError(
            "reflection archive does not account for every unique present GfxImage"
        )

    stats = archive.get("stats", {})
    if int(stats.get("reflectionProbeCount", -1)) != len(archive.get("reflectionProbes", [])):
        raise ReflectionProbeGlbEmbedError("reflection archive probe count mismatch")
    if int(stats.get("uniquePresentGfxImageCount", -1)) != len(present_assets):
        raise ReflectionProbeGlbEmbedError("reflection archive unique GfxImage count mismatch")
    if int(stats.get("embeddedGfxImageCount", -1)) != len(embedded_assets):
        raise ReflectionProbeGlbEmbedError("reflection archive embedded GfxImage count mismatch")
    if int(stats.get("missingGfxImageCount", -1)) != len(missing_assets):
        raise ReflectionProbeGlbEmbedError("reflection archive missing GfxImage count mismatch")
    if int(stats.get("accountedGfxImageCount", -1)) != len(present_assets):
        raise ReflectionProbeGlbEmbedError("reflection archive accounted GfxImage count mismatch")
    if int(stats.get("absentReflectionImageProbeCount", -1)) != absent_count:
        raise ReflectionProbeGlbEmbedError("reflection archive absent image count mismatch")
    if int(stats.get("surfaceBindingCount", -1)) != len(archive.get("surfaceBindings", [])):
        raise ReflectionProbeGlbEmbedError("reflection archive surface binding count mismatch")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gltf_json", type=Path)
    parser.add_argument("raw_bin", type=Path)
    parser.add_argument("reflection_manifest_json", type=Path)
    parser.add_argument("dds_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    gltf = json.loads(args.gltf_json.read_text(encoding="utf-8"))
    raw = args.raw_bin.read_bytes()
    manifest = json.loads(args.reflection_manifest_json.read_text(encoding="utf-8"))
    document, out_raw = embed_reflection_probe_dds(
        gltf,
        raw,
        manifest,
        dds_root=args.dds_root,
        allow_missing=args.allow_missing,
    )

    if args.output.suffix.lower() == ".glb":
        args.output.write_bytes(glb_bytes(document, out_raw))
    elif args.output.suffix.lower() == ".gltf":
        args.output.write_bytes(gltf_bytes(document, out_raw))
    else:
        raise SystemExit("output must end in .glb or .gltf")

    stats = document["extras"]["T6"]["reflectionProbeArchive"]["stats"]
    print(json.dumps({"out": str(args.output), **stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
