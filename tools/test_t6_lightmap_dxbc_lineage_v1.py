#!/usr/bin/env python3
"""Regression for conservative T6 lightmap DXBC component-lineage tracing."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from t6_lightmap_dxbc_lineage_v1 import (
    LightmapLineageError,
    build_lineage_manifest,
    trace_shader,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expect_error(fn, needle: str) -> None:
    try:
        fn()
    except LightmapLineageError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r} in {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected LightmapLineageError containing {needle!r}")


def _deps(trace: dict) -> dict[str, list[str]]:
    return {
        item["output"]: item["dependencies"]
        for item in trace["outputsWithLightmapDependency"]
    }


def _dxbc_manifest() -> dict:
    return {
        "format": "t6-lightmap-shader-dxbc-manifest-v1",
        "provenance": [
            {
                "material": "mc/test",
                "techniqueSet": "test_techset",
                "technique": "test_lit",
                "techniqueTypes": ["lit"],
                "passIndex": 0,
                "pixelShader": "test_lightmap",
                "shaderModel": "4.0",
                "shaderPresent": True,
                "resolvedLightmapBindings": [
                    {
                        "codeSampler": "lightmapSamplerPrimary",
                        "shaderResource": "lmPrimaryTexture",
                        "bindPoint": 3,
                    },
                    {
                        "codeSampler": "lightmapSamplerSecondary",
                        "shaderResource": "lmSecondaryTexture",
                        "bindPoint": 7,
                    },
                ],
            }
        ],
    }


def main() -> int:
    # Straight-line primary + secondary flow. Arithmetic is intentionally a
    # conservative union, so every written component may inherit every sampled
    # component referenced by the arithmetic sources.
    straight = """\
ps_4_0
sample r0.xyzw, v0.xyxx, t3.xyzw, s0
sample r1.x, v0.xyxx, t7.w, s1
mul r2.xyz, r0.xyz, r1.xxx
mov o0.xyz, r2.xyz
"""
    traced = trace_shader(
        straight,
        primary_bind_points={3},
        secondary_bind_points={7},
    )
    assert traced["sampledLightmapInstructionCount"] == 2
    assert traced["controlFlowObserved"] is False
    assert traced["unsupportedWriteCount"] == 0
    assert traced["closureUsable"] is True
    assert _deps(traced) == {
        "o0.x": ["primary.x", "primary.y", "primary.z", "secondary.w"],
        "o0.y": ["primary.x", "primary.y", "primary.z", "secondary.w"],
        "o0.z": ["primary.x", "primary.y", "primary.z", "secondary.w"],
    }

    # mov must preserve component mapping exactly instead of unioning the whole
    # source register. Resource swizzles are source-channel identities.
    swizzle = """\
ps_4_0
sample r0.xy, v0.xyxx, t3.yx, s0
mov r1.xy, r0.yx
mov o0.xy, r1.xy
"""
    traced = trace_shader(
        swizzle,
        primary_bind_points={3},
        secondary_bind_points=set(),
    )
    assert _deps(traced) == {
        "o0.x": ["primary.x"],
        "o0.y": ["primary.y"],
    }
    first = traced["sampledLightmapInstructions"][0]
    assert first["taggedChannels"] == ["primary.y", "primary.x"]

    # A later write with no lightmap lineage must kill the old dependency for
    # exactly the overwritten destination component.
    overwrite = """\
ps_4_0
sample r0.xy, v0.xyxx, t3.xy, s0
mov r0.x, l(0.0)
mov o0.xy, r0.xy
"""
    traced = trace_shader(
        overwrite,
        primary_bind_points={3},
        secondary_bind_points=set(),
    )
    assert _deps(traced) == {"o0.y": ["primary.y"]}

    # Scalar source replication through mov is component-stable.
    scalar_mov = """\
ps_4_0
sample r4.x, v0.xyxx, t7.z, s1
mov r5.xyz, r4.x
mov o1.xyz, r5.xyz
"""
    traced = trace_shader(
        scalar_mov,
        primary_bind_points=set(),
        secondary_bind_points={7},
    )
    assert _deps(traced) == {
        "o1.x": ["secondary.z"],
        "o1.y": ["secondary.z"],
        "o1.z": ["secondary.z"],
    }

    # Control flow is recorded and deliberately prevents closure-grade use even
    # though a conservative output dependency can still be reported.
    control = """\
ps_4_0
sample r0.x, v0.xyxx, t3.x, s0
if_nz r8.x
mov o0.x, r0.x
endif
"""
    traced = trace_shader(
        control,
        primary_bind_points={3},
        secondary_bind_points=set(),
    )
    assert traced["controlFlowObserved"] is True
    assert traced["closureUsable"] is False
    assert {x["opcode"] for x in traced["controlFlow"]} == {"if_nz", "endif"}
    assert _deps(traced) == {"o0.x": ["primary.x"]}

    # Writes to a destination class v1 does not model are explicit blockers,
    # never silently treated as proven lineage.
    unsupported = """\
ps_5_0
sample r0.x, v0.xyxx, t3.x, s0
store_uav_typed u0.x, r0.x
"""
    traced = trace_shader(
        unsupported,
        primary_bind_points={3},
        secondary_bind_points=set(),
    )
    assert traced["unsupportedWriteCount"] == 1
    assert traced["closureUsable"] is False

    _expect_error(
        lambda: trace_shader(
            "sample r0.x, v0.xyxx, t3.x, s0\n",
            primary_bind_points={3},
            secondary_bind_points={3},
        ),
        "overlap texture bind points",
    )
    _expect_error(
        lambda: trace_shader(
            "sample r0.xyz, v0.xyxx, t3.xy, s0\n",
            primary_bind_points={3},
            secondary_bind_points=set(),
        ),
        "cannot map 3 destination components",
    )
    _expect_error(
        lambda: trace_shader(
            "sample r0.x, v0.xyxx, t3.x, t7.x\n",
            primary_bind_points={3},
            secondary_bind_points={7},
        ),
        "references multiple mapped lightmap textures",
    )

    # Full manifest path: exact disassembly size/hash must be revalidated before
    # tracing, and deterministic regeneration must yield byte-identical JSON.
    disassembly = straight.encode("utf-8")
    archive = {
        "format": "t6-dxbc-disassembly-archive-v1",
        "shaders": [
            {
                "pixelShader": "test_lightmap",
                "disassemblyFile": "ps_test_lightmap.txt",
                "disassemblyBytes": len(disassembly),
                "disassemblySha256": _sha256(disassembly),
            }
        ],
    }
    dxbc = _dxbc_manifest()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "ps_test_lightmap.txt").write_bytes(disassembly)
        manifest1 = build_lineage_manifest(dxbc, archive, disassembly_root=root)
        manifest2 = build_lineage_manifest(
            copy.deepcopy(dxbc), copy.deepcopy(archive), disassembly_root=root
        )
        payload1 = json.dumps(manifest1, sort_keys=True, separators=(",", ":"))
        payload2 = json.dumps(manifest2, sort_keys=True, separators=(",", ":"))
        assert payload1 == payload2
        assert manifest1["format"] == "t6-lightmap-dxbc-lineage-v1"
        assert len(manifest1["results"]) == 1
        result = manifest1["results"][0]
        assert result["pixelShader"] == "test_lightmap"
        assert result["primaryTextureBindPoints"] == [3]
        assert result["secondaryTextureBindPoints"] == [7]
        assert result["trace"]["closureUsable"] is True

        changed = bytearray(disassembly)
        changed[-2] ^= 1
        (root / "ps_test_lightmap.txt").write_bytes(bytes(changed))
        _expect_error(
            lambda: build_lineage_manifest(dxbc, archive, disassembly_root=root),
            "disassembly artifact changed",
        )

        (root / "ps_test_lightmap.txt").write_bytes(disassembly)
        bad_archive = copy.deepcopy(archive)
        bad_archive["shaders"] = []
        _expect_error(
            lambda: build_lineage_manifest(dxbc, bad_archive, disassembly_root=root),
            "no disassembly archive entry",
        )

        unsafe_archive = copy.deepcopy(archive)
        unsafe_archive["shaders"][0]["disassemblyFile"] = "../escape.txt"
        _expect_error(
            lambda: build_lineage_manifest(dxbc, unsafe_archive, disassembly_root=root),
            "unsafe disassembly filename",
        )

    print("PASS t6_lightmap_dxbc_lineage_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
