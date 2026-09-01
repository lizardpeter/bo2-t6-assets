#!/usr/bin/env python3
"""Exact OpenAssetTools GfxImage output-name mapping used by T6 staging.

Pinned OAT behavior at commit 7d027e8f89118196713e955b0e11f8404149c54d:

    cleanAssetName = assetName
    replace(cleanAssetName, '*', '_')
    return "images/" + cleanAssetName + extension

The T6 asset identity itself must remain unchanged in manifests. This module is
only for deriving the on-disk filename emitted by OAT's ImageDumper.
"""
from __future__ import annotations


class OatImageFilenameError(RuntimeError):
    pass


def _validate(asset_name: str, extension: str) -> None:
    if not asset_name:
        raise OatImageFilenameError("empty GfxImage asset name")
    if "\0" in asset_name:
        raise OatImageFilenameError("GfxImage asset name contains NUL")
    if extension and not extension.startswith("."):
        raise OatImageFilenameError(
            f"image extension must be empty or begin with '.': {extension!r}"
        )


def oat_image_relative_path(asset_name: str, extension: str) -> str:
    """Return OAT's exact relative ImageDumper path, including `images/`."""
    _validate(asset_name, extension)
    clean = asset_name.replace("*", "_")
    return f"images/{clean}{extension}"


def oat_image_staging_basename(asset_name: str, extension: str) -> str:
    """Return the flat basename used by this repo's current DDS staging roots.

    The current staging API intentionally accepts a flat exact basename. If a
    future retail T6 GfxImage identity contains a path separator, fail closed
    here instead of flattening it differently from OpenAssetTools.
    """
    _validate(asset_name, extension)
    clean = asset_name.replace("*", "_")
    if "/" in clean or "\\" in clean:
        raise OatImageFilenameError(
            "current flat DDS staging cannot represent OAT image subpaths: "
            f"asset={asset_name!r}, oatPath={oat_image_relative_path(asset_name, extension)!r}"
        )
    return clean + extension


if __name__ == "__main__":
    raise SystemExit("library module; import oat_image_relative_path/staging_basename")
