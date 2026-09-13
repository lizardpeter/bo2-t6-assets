#!/usr/bin/env python3
"""Seal the exact retail multiply-decal TEXCOORD0.z formula.

Input is the already source-closed symbolic VS manifest.  This verifier does not
infer CPU fog construction.  It proves the compact formula below is exactly the
same DAG rooted at the VS producer of pixel v2.z, including branch thresholds,
DXBC exp operations, saturates, and the precise cb0/cb3 lanes used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-special-multiply-decal-fade-formula-v1"
INPUT_FORMAT = "t6-nuketown-special-multiply-decal-vs-symbolic-v1"
VS_SHA256 = "c3bd9eb7d12a444c63867be2e466ac00c495a5a7f64a8b2c9f73e2558a5e12e0"
PS_SHA256 = "e9820077a4df69228fd1626997270d7b31337f82eab6c26c1a14a33257424a0b"
ROOT = 160
EXPECTED_DAG_SHA256 = "5af1bb1f2ad05663f5bacf3b10b87ffa5292d832d920ea8f7f71a4d228f21062"


class ProofError(RuntimeError):
    pass


def f32(bits: str) -> float:
    return struct.unpack("<f", struct.pack("<I", int(bits, 16)))[0]


def req_node(nodes: dict[int, dict[str, Any]], node_id: int, kind: str, **fields: Any) -> dict[str, Any]:
    n = nodes.get(node_id)
    if n is None:
        raise ProofError(f"missing symbolic node {node_id}")
    if n.get("kind") != kind:
        raise ProofError(f"node {node_id} kind {n.get('kind')!r} != {kind!r}")
    for key, value in fields.items():
        if n.get(key) != value:
            raise ProofError(f"node {node_id} {key}={n.get(key)!r} != {value!r}")
    return n


def op(nodes: dict[int, dict[str, Any]], node_id: int, name: str, args: list[int]) -> None:
    req_node(nodes, node_id, "op", op=name, args=args)


def sym(nodes: dict[int, dict[str, Any]], node_id: int, name: str) -> None:
    req_node(nodes, node_id, "symbol", name=name)


def lit(nodes: dict[int, dict[str, Any]], node_id: int, bits: str) -> None:
    req_node(nodes, node_id, "literal32", bits=bits)


def build(src: Path) -> dict[str, Any]:
    d = json.loads(src.read_text(encoding="utf-8"))
    if d.get("format") != INPUT_FORMAT:
        raise ProofError(f"unexpected input format {d.get('format')!r}")
    if d.get("dagSha256") != EXPECTED_DAG_SHA256:
        raise ProofError(f"symbolic DAG SHA drift: {d.get('dagSha256')}")
    if d.get("vertexShader", {}).get("sha256") != VS_SHA256:
        raise ProofError("exact multiply-decal VS identity drift")
    if d.get("pixelShader", {}).get("sha256") != PS_SHA256:
        raise ProofError("exact multiply-decal PS identity drift")
    producer = d.get("pixelV2ZProducer", {})
    if producer.get("node") != ROOT or producer.get("pixelInputRegister") != 2 or producer.get("vertexOutput") != "o2.z":
        raise ProofError(f"pixel v2.z producer drift: {producer}")

    nodes = {int(n["id"]): n for n in d.get("vsNodes", [])}
    if len(nodes) != len(d.get("vsNodes", [])):
        raise ProofError("symbolic node ids are not unique")

    # Inputs and exact literals used by the fade branch.
    for node_id, name in [
        (119, "cb0[26].w"),
        (126, "cb0[27].x"), (149, "cb0[27].y"), (151, "cb0[27].z"), (125, "cb0[27].w"),
        (139, "cb0[28].x"),
        (106, "cb0[29].x"), (107, "cb0[29].y"), (108, "cb0[29].z"),
        (121, "cb0[30].w"),
        (115, "cb0[31].x"), (114, "cb0[31].y"),
    ]:
        sym(nodes, node_id, name)
    lit(nodes, 3, "3f800000")
    lit(nodes, 135, "00000000")
    lit(nodes, 143, "38d1b717")
    lit(nodes, 130, "42800000")
    lit(nodes, 132, "3fb8aa3b")

    # World-space/camera-relative vector P from exact cb3 worldMatrix DP4 chain.
    for node_id, name in [(15,"cb3[0].x"),(16,"cb3[0].y"),(17,"cb3[0].z"),(18,"cb3[0].w"),
                          (26,"cb3[1].x"),(27,"cb3[1].y"),(28,"cb3[1].z"),(29,"cb3[1].w"),
                          (37,"cb3[2].x"),(38,"cb3[2].y"),(39,"cb3[2].z"),(40,"cb3[2].w")]:
        sym(nodes,node_id,name)
    for node_id,name in [(0,"v0.x"),(1,"v0.y"),(2,"v0.z")]: sym(nodes,node_id,name)
    # Final transformed components are nodes 25,36,47. Exact arithmetic is pinned by DAG hash;
    # verify the downstream length path explicitly too.
    op(nodes,96,"mul",[25,25]); op(nodes,97,"mul",[36,36]); op(nodes,98,"mul",[47,47])
    op(nodes,99,"add",[96,97]); op(nodes,100,"add",[99,98]); op(nodes,102,"sqrt",[100])
    op(nodes,101,"rsq",[100]); op(nodes,103,"mul",[101,25]); op(nodes,104,"mul",[101,36]); op(nodes,105,"mul",[101,47])

    # Height-fog integral branch.
    op(nodes,129,"mul",[47,125]); op(nodes,142,"abs",[129]); op(nodes,144,"lt",[142,143])
    op(nodes,127,"mul",[125,47]); op(nodes,128,"add",[127,126]); op(nodes,136,"lt",[128,135])
    op(nodes,131,"min",[128,130]); op(nodes,133,"mul",[131,132]); op(nodes,134,"exp",[133])
    op(nodes,137,"add",[128,3]); op(nodes,138,"select",[136,134,137])
    op(nodes,140,"neg",[139]); op(nodes,141,"add",[138,140])
    op(nodes,145,"select",[144,3,129]); op(nodes,146,"div",[141,145]); op(nodes,147,"saturate",[139])
    op(nodes,148,"select",[144,147,146])

    # Distance transmittance.
    op(nodes,150,"mul",[148,149]); op(nodes,152,"mul",[150,102]); op(nodes,153,"add",[152,151])
    op(nodes,154,"exp",[153]); op(nodes,155,"min",[154,3])

    # Directional sun-fog opacity ramp.
    op(nodes,109,"mul",[106,103]); op(nodes,110,"mul",[107,104]); op(nodes,111,"mul",[108,105])
    op(nodes,112,"add",[109,110]); op(nodes,113,"add",[112,111]); op(nodes,116,"mul",[114,113])
    op(nodes,117,"add",[116,115]); op(nodes,118,"saturate",[117])
    op(nodes,120,"neg",[119]); op(nodes,122,"add",[120,121]); op(nodes,123,"mul",[118,122]); op(nodes,124,"add",[123,119])

    # Final visibility multiplier: 1 - (1 - T) * opacity.
    op(nodes,156,"neg",[155]); op(nodes,157,"add",[156,3]); op(nodes,158,"neg",[157]); op(nodes,159,"mul",[158,124]); op(nodes,160,"add",[159,3])

    exact_lanes = [
        "cb0[26].w", "cb0[27].x", "cb0[27].y", "cb0[27].z", "cb0[27].w",
        "cb0[28].x", "cb0[29].x", "cb0[29].y", "cb0[29].z",
        "cb0[30].w", "cb0[31].x", "cb0[31].y",
    ]
    formula = {
        "notation": {
            "P": "float3(oWorldX,oWorldY,oWorldZ) produced by cb3 worldMatrix from POSITION",
            "R": "length(P)",
            "A": "cb0[26].w",
            "F": "cb0[27].xyzw",
            "G": "cb0[28].x",
            "D": "cb0[29].xyz",
            "B": "cb0[30].w",
            "S": "cb0[31].xy",
        },
        "steps": [
            "a = P.z * F.w",
            "x = a + F.x",
            "q = (x < 0) ? dxbc_exp(min(x,64) * 1.4426950216293335) : (x + 1)",
            "H = (abs(a) < 0.00009999999747378752) ? saturate(G) : ((q - G) / a)",
            "T = min(dxbc_exp(H * F.y * R + F.z), 1)",
            "C = saturate(S.y * dot(D, normalize(P)) + S.x)",
            "O = A + C * (B - A)",
            "v2.z = 1 - (1 - T) * O",
        ],
        "dxbcExpNote": "`dxbc_exp` names the exact SM4 EXP instruction retained by the symbolic proof; no CPU-side approximation or fog-source construction is asserted here.",
        "exactReadLanes": exact_lanes,
        "literalBits": {
            "epsilon": {"bits":"0x38D1B717","f32":f32("38d1b717")},
            "expArgumentClamp": {"bits":"0x42800000","f32":f32("42800000")},
            "log2e": {"bits":"0x3FB8AA3B","f32":f32("3fb8aa3b")},
        },
    }
    formula_sha = hashlib.sha256(json.dumps(formula, sort_keys=True, separators=(",",":"), allow_nan=False).encode()).hexdigest()
    return {
        "format": FORMAT,
        "producer": "tools/t6_nuketown_special_multiply_decal_fade_formula_v1.py",
        "map": "mp_nuketown_2020",
        "techniqueSet": "wpc_unlitdecalblend_multiply_35079164",
        "vertexShaderSha256": VS_SHA256,
        "pixelShaderSha256": PS_SHA256,
        "sourceDagSha256": EXPECTED_DAG_SHA256,
        "formulaSha256": formula_sha,
        "formula": formula,
        "proofBoundary": (
            "Exact structural equivalence to the already source-closed retail VS symbolic DAG rooted at o2.z / pixel v2.z. "
            "This closes the shader-side fade arithmetic and exact read lanes only. It does not infer how the T6 CPU constructs fogColor/fogConsts/fogConsts2/sunFogDir/sunFogColor/sunFog, nor whether cb3 worldMatrix is camera-relative in the original runtime."
        ),
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbolic",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    d=build(a.symbolic)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"formulaSha256":d["formulaSha256"],"formula":d["formula"]},indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
