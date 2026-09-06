#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import io
import tempfile
from pathlib import Path

from PIL import Image

import t6_world_lightmap_preview_embed_v1 as preview
from t6_world_lightmap_glb_embed_v3 import embed_lightmap_dds, validate_lightmap_archive
from t6_world_lightmap_manifest_v3 import build_manifest


def _dds_rgba(color: tuple[int, int, int, int]) -> bytes:
    image = Image.new("RGBA", (2, 2), color)
    out = io.BytesIO()
    image.save(out, format="DDS")
    payload = out.getvalue()
    assert payload[:4] == b"DDS "
    return payload


def _world() -> dict:
    return {
        "format": "t6-world-mesh-normalized-v1",
        "map": "mp_lightmap_preview_test",
        "groups": [{"groupIndex": 0, "uvCount": 1}],
        "surfaces": [
            {"index": 0, "groupIndex": 0, "lightmapIndex": 0},
            {"index": 1, "groupIndex": 0, "lightmapIndex": 1},
            {"index": 2, "groupIndex": 0, "lightmapIndex": 2},
        ],
    }


def _catalog() -> dict:
    return {
        "format": "t6-gfxworld-lightmap-catalog-v1",
        "map": "mp_lightmap_preview_test",
        "lightmapCount": 3,
        "lightmaps": [
            {"index": 0, "primaryImage": "lm_primary", "secondaryImage": "lm_secondary"},
            # Reuse the exact same secondary GfxImage to prove preview dedupe.
            {"index": 1, "primaryImage": None, "secondaryImage": "lm_secondary"},
            {"index": 2, "primaryImage": None, "secondaryImage": None},
        ],
    }


def main() -> int:
    manifest = build_manifest(_world(), _catalog())
    base_raw = b"\x10\x20\x30\x40"
    base_doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(base_raw)}],
        "bufferViews": [],
        # Existing unrelated glTF image/texture state must remain untouched.
        "images": [{"name": "ordinary"}],
        "textures": [{"name": "ordinary"}],
        "samplers": [{"name": "ordinary"}],
    }

    with tempfile.TemporaryDirectory(prefix="t6_lm_preview_") as td:
        root = Path(td)
        primary_dds = _dds_rgba((10, 20, 30, 40))
        secondary_dds = _dds_rgba((120, 80, 40, 255))
        (root / "lm_primary.dds").write_bytes(primary_dds)
        (root / "lm_secondary.dds").write_bytes(secondary_dds)

        archived_doc, archived_raw = embed_lightmap_dds(
            copy.deepcopy(base_doc),
            base_raw,
            manifest,
            dds_root=root,
        )
        assert validate_lightmap_archive(archived_doc, archived_raw)
        source_sha = hashlib.sha256(archived_raw).hexdigest()

        out, raw, stats = preview.embed_lightmap_previews(archived_doc, archived_raw)
        assert raw[:len(archived_raw)] == archived_raw
        assert hashlib.sha256(raw[:len(archived_raw)]).hexdigest() == source_sha
        assert stats["lightmapCount"] == 3
        assert stats["presentRoleCount"] == 3
        assert stats["embeddedRoleCount"] == 3
        assert stats["absentRoleCount"] == 3
        assert stats["uniquePreviewImageCount"] == 2
        assert stats["sourceBinExactPrefix"] is True
        assert stats["appendedPreviewBytes"] > 0

        contract = out["extras"]["T6"][preview.ROOT_KEY]
        assert contract["format"] == preview.FORMAT
        assert contract["sourceArchiveFormat"] == "t6-world-lightmap-glb-archive-v3"
        assert contract["policy"]["materialBindingsCreated"] is False
        assert contract["policy"]["colorSpace"].startswith("data/non-color")
        assert len(contract["previews"]) == 2

        archive = out["extras"]["T6"]["lightmapArchive"]
        p0 = archive["lightmaps"][0]["primary"]
        s0 = archive["lightmaps"][0]["secondary"]
        s1 = archive["lightmaps"][1]["secondary"]
        neither = archive["lightmaps"][2]
        assert p0["preview"]["sourceDdsSha256"] == hashlib.sha256(primary_dds).hexdigest()
        assert s0["preview"]["sourceDdsSha256"] == hashlib.sha256(secondary_dds).hexdigest()
        assert s0["preview"]["previewTextureIndex"] == s1["preview"]["previewTextureIndex"]
        assert s0["preview"]["previewImageIndex"] == s1["preview"]["previewImageIndex"]
        assert "preview" not in neither["primary"]
        assert "preview" not in neither["secondary"]

        for role in (p0, s0):
            item = role["preview"]
            assert item["width"] == 2 and item["height"] == 2
            image = out["images"][item["previewImageIndex"]]
            assert image["mimeType"] == "image/png"
            assert image["extras"]["T6"]["previewOnly"] is True
            assert image["extras"]["T6"]["dataTexture"] is True
            view = out["bufferViews"][item["previewBufferView"]]
            start = int(view["byteOffset"])
            payload = raw[start:start + int(view["byteLength"])]
            assert payload[:8] == b"\x89PNG\r\n\x1a\n"
            assert hashlib.sha256(payload).hexdigest() == item["previewPngSha256"]

        # Canonical DDS archive remains independently valid after preview append.
        assert validate_lightmap_archive(out, raw)

        out2, raw2, stats2 = preview.embed_lightmap_previews(
            copy.deepcopy(archived_doc), archived_raw
        )
        assert raw2 == raw
        assert out2 == out
        assert stats2 == stats

        try:
            preview.embed_lightmap_previews(out, raw)
        except preview.LightmapPreviewEmbedError as exc:
            assert "already attached" in str(exc)
        else:
            raise AssertionError("duplicate lightmap preview attachment was accepted")

        # Canonical archive SHA is an exact trust boundary.
        corrupt = copy.deepcopy(archived_doc)
        corrupt["extras"]["T6"]["lightmapArchive"]["lightmaps"][0]["primary"]["sha256"] = "0" * 64
        try:
            preview.embed_lightmap_previews(corrupt, archived_raw)
        except preview.LightmapPreviewEmbedError as exc:
            assert "invalid canonical lightmap archive" in str(exc)
        else:
            raise AssertionError("corrupted canonical lightmap DDS SHA was accepted")

    print("PASS: derived PNG previews for exact T6 lightmap DDS archive v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
