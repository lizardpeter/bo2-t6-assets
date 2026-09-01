#!/usr/bin/env python3
"""T6 OAT material manifest v3: preserve exact asset identity + exact OAT image filename.

v2 source-closes generated/layered component reconstruction. v3 keeps that
material graph unchanged and fixes the disk-image mapping to match OAT's actual
ImageDumper rule at the pinned upstream revision:

    GfxImage asset name '*' -> '_' for the output filename

The manifest schema intentionally remains ``t6-material-texture-manifest-v1``
so the already-validated DDS/portable-GLB consumers remain compatible. Tool
revision and filename policy are recorded under source/policy instead.
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
from t6_oat_material_manifest_v2 import (
    OatMaterialManifestError,
    build_manifest as build_manifest_v2,
)


def _mapped(image_asset: str, extension: str) -> tuple[str, str]:
    try:
        return (
            oat_image_staging_basename(image_asset, extension),
            oat_image_relative_path(image_asset, extension),
        )
    except OatImageFilenameError as exc:
        raise OatMaterialManifestError(str(exc)) from exc


def _update_dependency(dependency: dict, extension: str) -> bool:
    image_asset = str(dependency.get("imageAsset") or "")
    source_texture, relative_path = _mapped(image_asset, extension)
    previous = str(dependency.get("sourceTexture") or "")
    dependency["sourceTexture"] = source_texture
    dependency["sourceOatImagePath"] = relative_path
    dependency["sourceOatImageAsset"] = image_asset
    return source_texture != previous


def build_manifest(
    *,
    material_root: Path,
    catalog_doc: dict,
    source_texture_extension: str,
    allow_missing_materials: bool = False,
) -> dict:
    doc = build_manifest_v2(
        material_root=material_root,
        catalog_doc=catalog_doc,
        source_texture_extension=source_texture_extension,
        allow_missing_materials=allow_missing_materials,
    )

    remapped = 0
    dependency_count = 0
    for material in doc.get("materials", []):
        for layer in material.get("layers", []):
            for dependency in layer.get("textures", []):
                dependency_count += 1
                remapped += int(_update_dependency(dependency, source_texture_extension))

        for binding in material.get("standardPreview", {}).values():
            # Preview entries repeat the exact image identity but are not always
            # the same Python dict as layers[].textures[]. Keep them synchronized.
            image_asset = str(binding.get("imageAsset") or "")
            source_texture, relative_path = _mapped(
                image_asset, source_texture_extension
            )
            binding["sourceTexture"] = source_texture
            binding["sourceOatImagePath"] = relative_path
            binding["sourceOatImageAsset"] = image_asset

        for blocked in material.get("standardPreviewBlocked", []):
            texture = blocked.get("texture")
            if isinstance(texture, dict):
                _update_dependency(texture, source_texture_extension)

    source = doc.setdefault("source", {})
    source["producer"] = "t6_oat_material_manifest_v3.py"
    source["oatImageFilenameReference"] = {
        "repository": "Laupetin/OpenAssetTools",
        "commit": "7d027e8f89118196713e955b0e11f8404149c54d",
        "path": "src/ObjCommon/Image/ImageCommon.cpp",
        "rule": "replace '*' with '_' then emit images/<cleanAssetName><extension>",
    }
    policy = doc.setdefault("policy", {})
    policy["sourceTextureMapping"] = (
        "exact OAT ImageDumper disk basename; preserve original GfxImage asset identity separately"
    )
    policy["oatImagePathMapping"] = (
        "images/<GfxImage.name with '*' replaced by '_'><configured extension>"
    )
    stats = doc.setdefault("stats", {})
    stats["oatImageMappedDependencyCount"] = dependency_count
    stats["oatImageFilenameChangedDependencyCount"] = remapped
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_root", type=Path)
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--source-texture-extension", required=True)
    parser.add_argument("--allow-missing-materials", action="store_true")
    args = parser.parse_args()

    catalog_doc = json.loads(args.catalog_json.read_text(encoding="utf-8"))
    doc = build_manifest(
        material_root=args.material_root,
        catalog_doc=catalog_doc,
        source_texture_extension=args.source_texture_extension,
        allow_missing_materials=args.allow_missing_materials,
    )
    args.output_json.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.output_json), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
