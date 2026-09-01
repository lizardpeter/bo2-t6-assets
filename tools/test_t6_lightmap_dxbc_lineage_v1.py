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
        assert needle in str(exc), (needle, str(exc))
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
    straight = """\
ps_4_0
sample r0.xyzw, v0.xyxx, t3.xyzw, s0
sample r1.x, v0.xyxx, t7.w, s1
mul r2.xyz, r0.xyz, r1.xxx
mov o0.xyz, r2.xyz
"""
    traced = trace_shader(straight, primary_bind_points={3}, secondary_bind_points={7})
    assert traced["sampledLightmapInstructionCount"] == 2
    assert traced["controlFlowObserved"] is False
    assert traced["unsupportedWriteCount"] == 0
    assert traced["closureUsable"] is True
    expected_union = ["primary.x", "primary.y", "primary.z", "secondary.w"]
    assert _deps(traced) == {
        "o0.x": expected_union,
        "o0.y": expected_union,
        "o0.z": expected_union,
    }

    # Resource swizzles name source channels; mov preserves component routing.
    swizzle = """\
ps_4_0
sample r0.xy, v0.xyxx, t3.yx, s0
mov r1.xy, r0.yx
mov o0.xy, r1.xy
"""
    traced = trace_shader(swizzle, primary_bind_points={3}, secondary_bind_points=set())
    assert traced["sampledLightmapInstructions"][0]["taggedChannels"] == [
        "primary.y", "primary.x"
    ]
    assert _deps(traced) == {"o0.x": ["primary.x"], "o0.y": ["primary.y"]}

    # A later constant write kills only the overwritten component lineage.
    overwrite = """\
ps_4_0
sample r0.xy, v0.xyxx, t3.xy, s0
mov r0.x, l(0.0)
mov o0.xy, r0.xy
"""
    traced = trace_shader(overwrite, primary_bind_points={3}, secondary_bind_points=set())
    assert _deps(traced) == {"o0.y": ["primary.y"]}

    # Scalar source replication stays component-stable through mov.
    scalar_mov = """\
ps_4_0
sample r4.x, v0.xyxx, t7.z, s1
mov r5.xyz, r4.x
mov o1.xyz, r5.xyz
"""
    traced = trace_shader(scalar_mov, primary_bind_points=set(), secondary_bind_points={7})
    assert _deps(traced) == {
        "o1.x": ["secondary.z"],
        "o1.y": ["secondary.z"],
        "o1.z": ["secondary.z"],
    }

    # V1 reports useful conservative lineage through branches but refuses to
    # call it closure-usable until CFG/SSA merging exists.
    control = """\
ps_4_0
sample r0.x, v0.xyxx, t3.x, s0
if_nz r8.x
mov o0.x, r0.x
endif
"""
    traced = trace_shader(control, primary_bind_points={3}, secondary_bind_points=set())
    assert traced["controlFlowObserved"] is True
    assert traced["closureUsable"] is False
    assert {x["opcode"] for x in traced["controlFlow"]} == {"if_nz", "endif"}
    assert _deps(traced) == {"o0.x": ["primary.x"]}

    # Unsupported destination classes are explicit blockers, never guessed.
    unsupported = """\
ps_5_0
sample r0.x, v0.xyxx, t3.x, s0
store_uav_typed u0.x, r0.x
"""
    traced = trace_shader(unsupported, primary_bind_points={3}, secondary_bind_points=set())
    assert traced["unsupportedWriteCount"] == 1
    assert traced["closureUsable"] is False

    _expect_error(
        lambda: trace_shader(
            "sample r0.x, v0.xyxx, t3.x, s0\n",
            primary_bind_points={3}, secondary_bind_points={3},
        ),
        "overlap texture bind points",
    )
    _expect_error(
        lambda: trace_shader(
            "sample r0.xyz, v0.xyxx, t3.xy, s0\n",
            primary_bind_points={3}, secondary_bind_points=set(),
        ),
        "cannot map 3 destination components",
    )
    _expect_error(
        lambda: trace_shader(
            "sample r0.x, v0.xyxx, t3.x, t7.x\n",
            primary_bind_points={3}, secondary_bind_points={7},
        ),
        "references multiple mapped lightmap textures",
    )

    # Full manifest path revalidates exact archived disassembly bytes/hash.
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
        path = root / "ps_test_lightmap.txt"
        path.write_bytes(disassembly)
        manifest1 = build_lineage_manifest(dxbc, archive, disassembly_root=root)
        manifest2 = build_lineage_manifest(
            copy.deepcopy(dxbc), copy.deepcopy(archive), disassembly_root=root
        )
        assert json.dumps(manifest1, sort_keys=True, separators=(",", ":")) == json.dumps(
            manifest2, sort_keys=True, separators=(",", ":")
        )
        assert manifest1["format"] == "t6-lightmap-dxbc-lineage-v1"
        assert manifest1["stats"] == {
            "provenanceTraceCount": 1,
            "closureUsableStraightLineTraceCount": 1,
            "controlFlowTraceCount": 0,
            "sampledLightmapInstructionCount": 2,
            "outputComponentDependencyCount": 3,
        }
        assert len(manifest1["provenance"]) == 1
        result = manifest1["provenance"][0]
        assert result["pixelShader"] == "test_lightmap"
        assert result["primaryTextureBindPoints"] == [3]
        assert result["secondaryTextureBindPoints"] == [7]
        assert result["trace"]["closureUsable"] is True

        changed = bytearray(disassembly)
        changed[-2] ^= 1
        path.write_bytes(bytes(changed))
        _expect_error(
            lambda: build_lineage_manifest(dxbc, archive, disassembly_root=root),
            "disassembly artifact changed",
        )
        path.write_bytes(disassembly)

        missing = copy.deepcopy(archive)
        missing["shaders"] = []
        _expect_error(
            lambda: build_lineage_manifest(dxbc, missing, disassembly_root=root),
            "no disassembly archive entry",
        )
        unsafe = copy.deepcopy(archive)
        unsafe["shaders"][0]["disassemblyFile"] = "../escape.txt"
        _expect_error(
            lambda: build_lineage_manifest(dxbc, unsafe, disassembly_root=root),
            "unsafe disassembly filename",
        )

    print("PASS t6_lightmap_dxbc_lineage_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
