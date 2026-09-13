#!/usr/bin/env python3
"""Exact-lane refinement of the Nuketown multiply-decal VS binding proof.

The symbolic VS DAG reads only specific components from cb0 rows 26..31. RDEF
may contain legal padding in the surrounding register span, so v2 proves the
actual 4-byte lanes instead of requiring padding bytes to be owned variables.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).with_name("t6_nuketown_special_multiply_decal_vs_bindings_v1.py")
_spec = importlib.util.spec_from_file_location("multiply_decal_bindings_v1", BASE)
base = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(base)

FORMAT = "t6-nuketown-special-multiply-decal-vs-bindings-v2"
# Exact cb0 components reached by the proved o2.z DAG.
FADE_COMPONENTS = [
    (26, "w"),
    (27, "x"), (27, "y"), (27, "z"), (27, "w"),
    (28, "x"),
    (29, "x"), (29, "y"), (29, "z"),
    (30, "w"),
    (31, "x"), (31, "y"),
]


def variable_for_lane(
    cbuffers: list[dict[str, Any]],
    bind: int,
    row: int,
    component: str,
    assignments: dict[str, str],
) -> dict[str, Any]:
    if component not in "xyzw":
        raise base.BindingError(f"invalid component {component!r}")
    offset = row * 16 + "xyzw".index(component) * 4
    bs = [b for b in cbuffers if b["bindPoint"] == bind]
    if len(bs) != 1:
        raise base.BindingError(f"RDEF b{bind} cbuffer count {len(bs)}, expected one")
    hits = [v for v in bs[0]["variables"] if v["startOffset"] <= offset and offset + 4 <= v["endOffset"]]
    if len(hits) != 1:
        raise base.BindingError(f"RDEF b{bind}[{row}].{component} byte {offset} owner count {len(hits)}, expected one")
    v = hits[0]
    src = assignments.get(v["name"])
    if not src:
        raise base.BindingError(f"RDEF {bs[0]['name']}.{v['name']} has no exact selected-pass constant.* source")
    return {
        "cbuffer": bs[0]["name"],
        "bindPoint": bind,
        "row": row,
        "component": component,
        "byteOffset": offset,
        "shaderVariable": v["name"],
        "variableStartOffset": v["startOffset"],
        "variableSizeBytes": v["sizeBytes"],
        "sourceAccessor": src,
    }


def build(census_path: Path) -> dict[str, Any]:
    census = json.loads(census_path.read_text(encoding="utf-8"))
    if census.get("format") != "t6-nuketown-special-material-census-v1":
        raise base.BindingError(f"unexpected special census format {census.get('format')!r}")
    ug, eg, owner, technique = base.selected_programs(census)
    uvs = base.stage(ug, "vertexShader", base.VS_SHA256)
    ups = base.stage(ug, "pixelShader", base.PS_SHA256)
    evs = base.stage(eg, "vertexShader", base.VS_SHA256)
    eps = base.stage(eg, "pixelShader", base.PS_SHA256)
    for a, b, label in ((uvs, evs, "VS"), (ups, eps, "PS")):
        if a.get("relativeFile") != b.get("relativeFile") or a.get("asset") != b.get("asset"):
            raise base.BindingError(f"unlit/emissive exact {label} identity differs")

    vs_path = owner / str(uvs.get("relativeFile") or "")
    dxbc = vs_path.read_bytes()
    if base.hashlib.sha256(dxbc).hexdigest() != base.VS_SHA256:
        raise base.BindingError(f"{vs_path}: exact VS SHA mismatch")
    cbuffers = base.rdef_cbuffers(dxbc)

    tech_path = owner / "techniques" / f"{technique}.tech"
    text = tech_path.read_text(encoding="utf-8")
    passes = base.split_passes(text)
    vs_asset = str(uvs.get("asset") or "")
    ps_asset = str(ups.get("asset") or "")
    matches = [
        p for p in passes
        if any(base.shader_decl(x, "vertexShader") == vs_asset for x in p)
        and any(base.shader_decl(x, "pixelShader") == ps_asset for x in p)
    ]
    if len(matches) != 1:
        raise base.BindingError(f"{tech_path}: exact VS/PS pair appears in {len(matches)} passes, expected one")
    assignments = base.vertex_assignments(matches[0], vs_asset)

    fade_lanes = [variable_for_lane(cbuffers, 0, row, component, assignments) for row, component in FADE_COMPONENTS]
    fade_variables = []
    seen = set()
    for lane in fade_lanes:
        key = (lane["cbuffer"], lane["shaderVariable"], lane["variableStartOffset"], lane["variableSizeBytes"], lane["sourceAccessor"])
        if key in seen:
            continue
        seen.add(key)
        fade_variables.append({
            "cbuffer": lane["cbuffer"],
            "bindPoint": lane["bindPoint"],
            "shaderVariable": lane["shaderVariable"],
            "startOffset": lane["variableStartOffset"],
            "sizeBytes": lane["variableSizeBytes"],
            "sourceAccessor": lane["sourceAccessor"],
        })

    world = base.intersecting_variables(cbuffers, base.WORLD_CB, base.WORLD_START, base.WORLD_END, assignments)
    view = base.intersecting_variables(cbuffers, base.VIEWPROJ_CB, base.VIEWPROJ_START, base.VIEWPROJ_END, assignments)
    unresolved = [r for r in world + view if not r["sourceAccessor"]]
    if unresolved:
        raise base.BindingError(f"matrix VS ranges have unresolved OAT sources: {[r['shaderVariable'] for r in unresolved]}")

    return {
        "format": FORMAT,
        "producer": "tools/t6_nuketown_special_multiply_decal_vs_bindings_v2.py",
        "map": "mp_nuketown_2020",
        "techniqueSet": base.TECHNIQUE_SET,
        "technique": technique,
        "techniqueOwner": str(owner),
        "vertexShader": {"asset": vs_asset, "sha256": base.VS_SHA256, "relativeFile": uvs.get("relativeFile")},
        "pixelShader": {"asset": ps_asset, "sha256": base.PS_SHA256, "relativeFile": ups.get("relativeFile")},
        "fadeInput": {
            "bindPoint": 0,
            "exactReadLaneCount": len(fade_lanes),
            "lanes": fade_lanes,
            "variables": fade_variables,
        },
        "worldMatrixRange": {"bindPoint": base.WORLD_CB, "startOffset": base.WORLD_START, "endOffset": base.WORLD_END, "variables": world},
        "viewProjectionRange": {"bindPoint": base.VIEWPROJ_CB, "startOffset": base.VIEWPROJ_START, "endOffset": base.VIEWPROJ_END, "variables": view},
        "proofBoundary": (
            "The exact symbolic VS DAG identifies the twelve cb0 float lanes read by TEXCOORD0.z. Each lane is joined to exactly one reflected RDEF variable and that variable to the exact selected OAT vertexShader constant.* accessor. RDEF padding is intentionally not treated as data. World/viewProjection ranges are independently required to be fully reflected and source-bound. No runtime values are inferred."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--special-census", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = build(a.special_census)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"fadeInput": d["fadeInput"], "worldMatrixRange": d["worldMatrixRange"], "viewProjectionRange": d["viewProjectionRange"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
