#!/usr/bin/env python3
"""Synthetic SM4/SM5 assembly regression for lightmap symbolic v2."""
from __future__ import annotations

from t6_lightmap_dxbc_symbolic_v2 import reconstruct_shader


def _deps(doc: dict) -> dict[str, list[str]]:
    return {row["output"]: row["lightmapDependencies"] for row in doc["outputs"]}


def main() -> int:
    shader = r'''
ps_4_0
sample_indexable(texture2d)(float,float,float,float) r0.xyzw, v0.xyxx, t4.xyzw, s0
sample_indexable(texture2d)(float,float,float,float) r1.xyzw, v0.xyxx, t5.xyzw, s1
mul r2.xyz, r0.xyzx, r1.xyzx
mad_sat r3.xyz, r2.xyzx, cb0[0].xxxx, r1.xyzx
mov o0.xyz, r3.xyzx
'''
    doc = reconstruct_shader(shader, primary_bind_points={4}, secondary_bind_points={5})
    assert doc["closureUsable"] is True, doc["blockers"]
    deps = _deps(doc)
    assert deps["o0.x"] == ["primary.x", "secondary.x"]
    assert deps["o0.y"] == ["primary.y", "secondary.y"]
    assert deps["o0.z"] == ["primary.z", "secondary.z"]
    assert any(node.get("op") == "saturate" for node in doc["nodes"])

    # Scalar destination still consumes xyz from both sources.
    dot = r'''
ps_4_0
sample_indexable(texture2d)(float,float,float,float) r0.xyzw, v0.xyxx, t4.xyzw, s0
sample_indexable(texture2d)(float,float,float,float) r1.xyzw, v0.xyxx, t5.xyzw, s1
dp3 r2.x, r0.xyzx, r1.xyzx
mov o0.x, r2.x
'''
    doc2 = reconstruct_shader(dot, primary_bind_points={4}, secondary_bind_points={5})
    assert doc2["closureUsable"] is True, doc2["blockers"]
    assert _deps(doc2)["o0.x"] == [
        "primary.x", "primary.y", "primary.z",
        "secondary.x", "secondary.y", "secondary.z",
    ]

    # Unknown opcode is permitted only when it is external to lightmap lineage.
    external = r'''
ps_4_0
sin r9.x, v0.x
sample_indexable(texture2d)(float,float,float,float) r0.x, v0.xyxx, t4.x, s0
mul o0.x, r0.x, r9.x
'''
    doc3 = reconstruct_shader(external, primary_bind_points={4}, secondary_bind_points=set())
    assert doc3["closureUsable"] is True, doc3["blockers"]
    assert _deps(doc3)["o0.x"] == ["primary.x"]

    bad_opcode = r'''
ps_4_0
sample_indexable(texture2d)(float,float,float,float) r0.x, v0.xyxx, t4.x, s0
sin o0.x, r0.x
'''
    doc4 = reconstruct_shader(bad_opcode, primary_bind_points={4}, secondary_bind_points=set())
    assert doc4["closureUsable"] is False
    assert any(x["reason"] == "unsupported-lightmap-consuming-opcode" for x in doc4["blockers"])

    branch = r'''
ps_4_0
sample_indexable(texture2d)(float,float,float,float) r0.x, v0.xyxx, t4.x, s0
if_nz r0.x
mov o0.x, r0.x
endif
'''
    doc5 = reconstruct_shader(branch, primary_bind_points={4}, secondary_bind_points=set())
    assert doc5["closureUsable"] is False
    assert any(x["reason"] == "control-flow" for x in doc5["blockers"])

    print("PASS t6_lightmap_dxbc_symbolic_v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
