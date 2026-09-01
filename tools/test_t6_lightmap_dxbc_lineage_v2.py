#!/usr/bin/env python3
"""Regression for dumpbin-faithful T6 lightmap DXBC lineage v2."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from t6_lightmap_dxbc_lineage_v1 import LightmapLineageError
from t6_lightmap_dxbc_lineage_v2 import build_lineage_manifest, trace_shader


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _deps(trace: dict) -> dict[str, list[str]]:
    return {x["output"]: x["dependencies"] for x in trace["outputsWithLightmapDependency"]}


def _expect_error(fn, needle: str) -> None:
    try:
        fn()
    except LightmapLineageError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected LightmapLineageError containing {needle!r}")


def main() -> int:
    # Real fxc-style decorated opcode plus numeric instruction labels.
    text = """\
// ps_4_0
0: dcl_sampler s0, mode_default
1: dcl_sampler s1, mode_default
2: dcl_resource_texture2d (float,float,float,float) t3
3: dcl_resource_texture2d (float,float,float,float) t7
4: sample_indexable(texture2d)(float,float,float,float) r0.xyzw, v0.xyxx, t3.xyzw, s0
5: sample_l_indexable(texture2d)(float,float,float,float) r1.w, v0.xyxx, t7.w, s1, l(0.000000)
6: mul r0.xyz, |r0.xyzx|, cb0[0].xyzx
7: mad r2.xyz, -|r0.xyzx|, r1.wwww, r0.xyzx
8: mov o0.xyz, r2.xyz
9: ret
"""
    traced = trace_shader(text, primary_bind_points={3}, secondary_bind_points={7})
    assert traced["sampledLightmapInstructionCount"] == 2
    assert traced["unparsedInstructionCandidateCount"] == 0
    assert traced["closureUsable"] is True
    assert traced["sampledLightmapInstructions"][0]["opcode"] == "sample_indexable"
    assert traced["sampledLightmapInstructions"][0]["opcodeDecorations"] == "(texture2d)(float,float,float,float)"
    assert traced["sampledLightmapInstructions"][0]["displayIndex"] == 4
    expected = ["primary.x", "primary.y", "primary.z", "secondary.w"]
    assert _deps(traced) == {"o0.x": expected, "o0.y": expected, "o0.z": expected}

    # Absolute-value syntax must preserve lineage instead of dropping it.
    abs_text = """\
ps_5_0
sample_indexable(texture2d)(float,float,float,float) r3.x, v0.xyxx, t3.z, s0
mul r4.x, -|r3.x|, l(2.000000)
mov o0.x, r4.x
"""
    traced = trace_shader(abs_text, primary_bind_points={3}, secondary_bind_points=set())
    assert _deps(traced) == {"o0.x": ["primary.z"]}

    # Discard changes coverage/control semantics, so v2 refuses closure-grade use.
    discard = """\
ps_5_0
sample_indexable(texture2d)(float,float,float,float) r0.x, v0.xyxx, t3.x, s0
discard_nz r0.x
mov o0.x, r0.x
"""
    traced = trace_shader(discard, primary_bind_points={3}, secondary_bind_points=set())
    assert traced["controlFlowObserved"] is True
    assert traced["closureUsable"] is False
    assert traced["controlFlow"][0]["opcode"] == "discard_nz"

    # A relevant line that fails instruction parsing is retained as an explicit blocker.
    malformed = """\
ps_4_0
sample_indexable(texture2d)(float,float,float,float) r0.x, v0.xyxx, t3.x, s0
??? r0.x, t3.x
mov o0.x, r0.x
"""
    traced = trace_shader(malformed, primary_bind_points={3}, secondary_bind_points=set())
    assert traced["unparsedInstructionCandidateCount"] == 1
    assert traced["closureUsable"] is False
    assert "??? r0.x, t3.x" in traced["unparsedInstructionCandidates"][0]["line"]

    _expect_error(
        lambda: trace_shader(
            "sample_indexable(texture2d)(float,float,float,float) r0.x, v0.xyxx, t3.x, s0\n",
            primary_bind_points={3},
            secondary_bind_points={3},
        ),
        "overlap texture bind points",
    )

    # Full archive path retains the v2 format and stats deterministically.
    raw = text.encode("utf-8")
    dxbc = {
        "format": "t6-lightmap-shader-dxbc-manifest-v1",
        "provenance": [
            {
                "material": "mc/test",
                "techniqueSet": "test",
                "technique": "test_lit",
                "techniqueTypes": ["lit"],
                "passIndex": 0,
                "pixelShader": "world_lm",
                "shaderModel": "4.0",
                "shaderPresent": True,
                "resolvedLightmapBindings": [
                    {"codeSampler": "lightmapSamplerPrimary", "bindPoint": 3},
                    {"codeSampler": "lightmapSamplerSecondary", "bindPoint": 7},
                ],
            }
        ],
    }
    archive = {
        "format": "t6-dxbc-disassembly-archive-v1",
        "shaders": [
            {
                "pixelShader": "world_lm",
                "disassemblyFile": "ps_world_lm.fxc.dumpbin.txt",
                "disassemblyBytes": len(raw),
                "disassemblySha256": _sha256(raw),
            }
        ],
    }
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "ps_world_lm.fxc.dumpbin.txt").write_bytes(raw)
        a = build_lineage_manifest(dxbc, archive, disassembly_root=root)
        b = build_lineage_manifest(copy.deepcopy(dxbc), copy.deepcopy(archive), disassembly_root=root)
        assert json.dumps(a, sort_keys=True, separators=(",", ":")) == json.dumps(
            b, sort_keys=True, separators=(",", ":")
        )
        assert a["format"] == "t6-lightmap-dxbc-lineage-v2"
        assert a["source"]["producer"] == "t6_lightmap_dxbc_lineage_v2.py"
        assert a["stats"] == {
            "provenanceTraceCount": 1,
            "closureUsableStraightLineTraceCount": 1,
            "controlFlowTraceCount": 0,
            "unsupportedWriteCount": 0,
            "unparsedInstructionCandidateCount": 0,
            "sampledLightmapInstructionCount": 2,
            "outputComponentDependencyCount": 3,
        }

        changed = bytearray(raw)
        changed[-2] ^= 1
        (root / "ps_world_lm.fxc.dumpbin.txt").write_bytes(bytes(changed))
        _expect_error(
            lambda: build_lineage_manifest(dxbc, archive, disassembly_root=root),
            "disassembly artifact changed",
        )

    print("PASS t6_lightmap_dxbc_lineage_v2 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
