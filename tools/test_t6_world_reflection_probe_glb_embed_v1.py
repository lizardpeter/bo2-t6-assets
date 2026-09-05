#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path
import tempfile

from t6_world_reflection_probe_glb_embed_v1 import (
    ReflectionProbeGlbEmbedError,
    embed_reflection_probe_dds,
    validate_reflection_probe_archive,
)


def _probe(index: int, image, source, *, present: bool, bias: float = 0.0) -> dict:
    return {
        "index": index,
        "origin": [float(index), 2.0, 3.0],
        "lightingSH": {
            "V0": [0.1, 0.2, 0.3, 0.4],
            "V1": [0.5, 0.6, 0.7, 0.8],
            "V2": [0.9, 1.0, 1.1, 1.2],
        },
        "reflectionImagePresent": present,
        "reflectionImage": image if present else None,
        "reflectionOatImageAsset": image if present else None,
        "reflectionSourceTexture": source if present else None,
        "reflectionOatImagePath": f"images/{source}" if present else None,
        "mipLodBias": bias,
        "probeVolumeCount": 0,
        "probeVolumes": [],
    }


def _manifest() -> dict:
    probes = [
        _probe(0, "probe*shared", "probe_shared.dds", present=True, bias=0.25),
        _probe(1, None, None, present=False),
        _probe(2, "probe*shared", "probe_shared.dds", present=True, bias=-0.5),
    ]
    return {
        "format": "t6-world-reflection-probe-manifest-v2",
        "map": "mp_fixture",
        "reflectionProbes": probes,
        "surfaceBindings": [
            {
                "surfaceIndex": 10,
                "reflectionProbeIndex": 0,
                "reflectionImagePresent": True,
            },
            {
                "surfaceIndex": 11,
                "reflectionProbeIndex": 1,
                "reflectionImagePresent": False,
            },
        ],
        "referencedReflectionProbeIndices": [0, 1],
        "unreferencedReflectionProbeIndices": [2],
    }


def _gltf(raw: bytes) -> dict:
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(raw)}],
        "bufferViews": [],
        "images": [{"name": "existing"}],
        "textures": [{"source": 0}],
        "materials": [{"name": "existing_material"}],
        "extras": {"T6": {"sentinel": "preserved"}},
    }


def expect_error(fn, needle: str) -> None:
    try:
        fn()
    except ReflectionProbeGlbEmbedError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected ReflectionProbeGlbEmbedError containing {needle!r}")


def main() -> int:
    raw = b"BASE"
    gltf = _gltf(raw)
    manifest = _manifest()
    dds = b"DDS " + bytes(range(64))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "probe_shared.dds").write_bytes(dds)

        original_gltf = copy.deepcopy(gltf)
        document, out_raw = embed_reflection_probe_dds(
            gltf,
            raw,
            manifest,
            dds_root=root,
        )
        assert gltf == original_gltf  # transformer must not mutate caller document
        assert out_raw.startswith(raw)
        assert out_raw[4:] == dds
        assert validate_reflection_probe_archive(document, out_raw)

        archive = document["extras"]["T6"]["reflectionProbeArchive"]
        stats = archive["stats"]
        assert stats["reflectionProbeCount"] == 3
        assert stats["surfaceBindingCount"] == 2
        assert stats["presentDependencyUseCount"] == 2
        assert stats["uniquePresentGfxImageCount"] == 1
        assert stats["embeddedGfxImageCount"] == 1
        assert stats["missingGfxImageCount"] == 0
        assert stats["accountedGfxImageCount"] == 1
        assert stats["absentReflectionImageProbeCount"] == 1
        assert archive["missing"] == []

        p0, p1, p2 = archive["reflectionProbes"]
        assert p0["embedded"] is True
        assert p2["embedded"] is True
        assert p0["bufferView"] == p2["bufferView"]
        assert p0["sha256"] == p2["sha256"]
        assert p0["bytes"] == len(dds)
        assert p1["embedded"] is False
        assert p1["reflectionImagePresent"] is False
        assert p1["reflectionOatImageAsset"] is None
        assert p1["reflectionSourceTexture"] is None

        assert len(document["images"]) == len(gltf["images"])
        assert len(document["textures"]) == len(gltf["textures"])
        assert len(document["materials"]) == len(gltf["materials"])
        assert document["extras"]["T6"]["sentinel"] == "preserved"
        assert len(document["bufferViews"]) == 1

        # Missing dependency may be archived only when explicitly allowed.
        missing_root = root / "empty"
        missing_root.mkdir()
        missing_doc, missing_raw = embed_reflection_probe_dds(
            gltf,
            raw,
            manifest,
            dds_root=missing_root,
            allow_missing=True,
        )
        assert missing_raw == raw
        assert validate_reflection_probe_archive(missing_doc, missing_raw)
        missing_archive = missing_doc["extras"]["T6"]["reflectionProbeArchive"]
        assert missing_archive["stats"]["embeddedGfxImageCount"] == 0
        assert missing_archive["stats"]["missingGfxImageCount"] == 1
        assert len(missing_archive["missing"]) == 1

        expect_error(
            lambda: embed_reflection_probe_dds(
                gltf,
                raw,
                manifest,
                dds_root=missing_root,
                allow_missing=False,
            ),
            "missing exact reflection probe DDS",
        )

        bad_root = root / "bad"
        bad_root.mkdir()
        (bad_root / "probe_shared.dds").write_bytes(b"NOTDDS")
        expect_error(
            lambda: embed_reflection_probe_dds(
                gltf,
                raw,
                manifest,
                dds_root=bad_root,
            ),
            "not a DDS file",
        )

    bad = copy.deepcopy(manifest)
    bad["reflectionProbes"][2]["reflectionSourceTexture"] = "other.dds"
    expect_error(
        lambda: embed_reflection_probe_dds(gltf, raw, bad, dds_root=Path("."), allow_missing=True),
        "multiple disk sources",
    )

    bad = copy.deepcopy(manifest)
    bad["reflectionProbes"][2]["reflectionOatImageAsset"] = "different_asset"
    expect_error(
        lambda: embed_reflection_probe_dds(gltf, raw, bad, dds_root=Path("."), allow_missing=True),
        "distinct T6 reflection GfxImage identities share one disk source",
    )

    bad = copy.deepcopy(manifest)
    bad["reflectionProbes"][1]["reflectionSourceTexture"] = "invented.dds"
    expect_error(
        lambda: embed_reflection_probe_dds(gltf, raw, bad, dds_root=Path("."), allow_missing=True),
        "absent reflection image carries asset/disk identity",
    )

    bad = copy.deepcopy(manifest)
    bad["surfaceBindings"][0]["reflectionImagePresent"] = False
    expect_error(
        lambda: embed_reflection_probe_dds(gltf, raw, bad, dds_root=Path("."), allow_missing=True),
        "presence disagrees",
    )

    bad_gltf = _gltf(raw)
    bad_gltf["extras"]["T6"]["reflectionProbeArchive"] = {"format": "old"}
    expect_error(
        lambda: embed_reflection_probe_dds(
            bad_gltf,
            raw,
            manifest,
            dds_root=Path("."),
            allow_missing=True,
        ),
        "refusing overwrite",
    )

    expect_error(
        lambda: embed_reflection_probe_dds(
            {"buffers": [{"byteLength": 99}]},
            raw,
            manifest,
            dds_root=Path("."),
            allow_missing=True,
        ),
        "raw buffer length",
    )

    print("PASS: T6 reflection probe DDS GLB archive v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
