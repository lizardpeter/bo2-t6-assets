#!/usr/bin/env python3
"""Regression for T6 OAT material render-state archival v4."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from t6_oat_material_manifest_v4 import _state_archive
from t6_oat_material_manifest_v3 import OatMaterialManifestError


def _source(root: Path, doc: dict, name: str = "material.json") -> dict:
    path = root / name
    raw = (json.dumps(doc, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return {"path": path, "raw": raw, "doc": doc}


def _state(**overrides) -> dict:
    row = {
        "alphaTest": "disabled",
        "blendOpAlpha": "disabled",
        "blendOpRgb": "disabled",
        "colorWriteAlpha": True,
        "colorWriteRgb": True,
        "cullFace": "back",
        "depthTest": "less_equal",
        "depthWrite": True,
        "dstBlendAlpha": "zero",
        "dstBlendRgb": "zero",
        "polygonOffset": "offset0",
        "polymodeLine": False,
        "srcBlendAlpha": "one",
        "srcBlendRgb": "one",
    }
    row.update(overrides)
    return row


def _doc(states, routing) -> dict:
    return {
        "_game": "t6",
        "_type": "material",
        "_version": 1,
        "cameraRegion": "none",
        "constants": [{"name": "testConstant", "literal": [1.0, 2.0, 3.0, 4.0]}],
        "contents": 1,
        "gameFlags": [],
        "layeredSurfaceTypes": 0,
        "sortKey": 4,
        "stateBits": states,
        "stateBitsEntry": routing,
        "stateFlags": 0,
        "surfaceFlags": 0,
        "surfaceTypeBits": 0,
        "techniqueSet": "test_techset",
        "textureAtlas": {"columns": 1, "rows": 1},
        "textures": [],
    }


def _must_fail(root: Path, doc: dict, contains: str) -> None:
    try:
        _state_archive("bad", _source(root, doc, "bad.json"))
    except OatMaterialManifestError as exc:
        assert contains in str(exc), str(exc)
    else:
        raise AssertionError("expected OatMaterialManifestError")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # Matches the pinned OAT T6 schema shape: optional stencil keys omitted.
        ordinary = _state_archive(
            "ordinary",
            _source(root, _doc([_state()], [-1, -1, 0] + [-1] * 33)),
        )
        assert ordinary["referencedStateIndices"] == [0]
        assert ordinary["stateBits"][0]["stencilFront"] is None
        assert ordinary["stateBits"][0]["stencilBack"] is None
        assert ordinary["features"]["alphaTestUsed"] is False
        assert ordinary["features"]["blendUsed"] is False
        assert ordinary["coreGltfCompatibility"]["doubleSided"] is False
        assert ordinary["coreGltfCompatibility"]["alphaMode"] == "OPAQUE"
        # Depth is preserved, but core glTF has no normative depth-state control.
        assert ordinary["coreGltfCompatibility"]["fullyRepresentable"] is False
        assert "depth-test-write-not-core-gltf-state" in ordinary["coreGltfCompatibility"]["blockers"]

        special = _state_archive(
            "special",
            _source(
                root,
                _doc(
                    [
                        _state(
                            alphaTest="ge128",
                            cullFace="none",
                            blendOpRgb="add",
                            srcBlendRgb="srcalpha",
                            dstBlendRgb="invsrcalpha",
                            depthWrite=False,
                            polygonOffset="offset1",
                            stencilFront={"pass":"keep","fail":"keep","zfail":"keep","func":"always"},
                        )
                    ],
                    [0] + [-1] * 35,
                ),
                "special.json",
            ),
        )
        assert special["features"]["alphaTestUsed"] is True
        assert special["features"]["blendUsed"] is True
        assert special["features"]["polygonOffsetUsed"] is True
        assert special["features"]["stencilUsed"] is True
        assert special["coreGltfCompatibility"]["doubleSided"] is True
        assert special["coreGltfCompatibility"]["alphaMode"] is None
        blockers = special["coreGltfCompatibility"]["blockers"]
        assert "alpha-test-or-blend-requires-t6-aware-render-state" in blockers
        assert "polygon-offset-not-core-gltf" in blockers
        assert "stencil-not-core-gltf" in blockers

        # Mixed technique routing must remain visible rather than being collapsed.
        mixed = _state_archive(
            "mixed",
            _source(
                root,
                _doc(
                    [_state(cullFace="back"), _state(cullFace="front", depthWrite=False)],
                    [0, 1] + [-1] * 34,
                ),
                "mixed.json",
            ),
        )
        assert mixed["features"]["cullFaces"] == ["back", "front"]
        assert mixed["coreGltfCompatibility"]["doubleSided"] is None
        assert "cull-state-not-uniformly-core-gltf-representable" in mixed["coreGltfCompatibility"]["blockers"]
        assert "depth-write-varies-by-technique-state" in mixed["coreGltfCompatibility"]["blockers"]

        bad_route = _doc([_state()], [1] + [-1] * 35)
        _must_fail(root, bad_route, "outside -1..0")

        missing_required = _doc([_state()], [0] + [-1] * 35)
        del missing_required["stateBits"][0]["alphaTest"]
        _must_fail(root, missing_required, "missing fields ['alphaTest']")

    print("PASS t6_oat_material_manifest_v4 exact render-state regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
