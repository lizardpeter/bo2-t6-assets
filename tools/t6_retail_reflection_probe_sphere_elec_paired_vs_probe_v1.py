#!/usr/bin/env python3
"""Resolve and profile the paired VS nodes for the 24 Tomb sphere-electric PS owners.

Consumes the fail-closed packed-PS ownership probe. If that probe uniquely resolves
all 24 pixel owners, this stage resolves each paired VS through two independent
retained sources when available:
  * broad cross-map TechniqueSet/slot/pass/worldVertFormat equality;
  * the committed packed-VS alias manifest.
Disagreement is fatal. Resolved direct VS payloads are then inspected directly for
TEXCOORD producer ancestry and exact cb3/worldMatrix POSITION/NORMAL/TANGENT forms.

This remains a probe until all target owners resolve and their physical roles match
the pixel-side shifted-TBN requirements. It never promotes a role from a name.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def jhash(x):
    return hashlib.sha256(
        json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def load_committed_packed_vs(path: Path):
    d = json.loads(path.read_text())
    enc = d["encoding"]
    maps = enc["mapTable"]
    shas = enc["vertexShaderTable"]
    out = {}
    for r in d["pointerAliases"]:
        key = ("ptr", maps[r[0]], r[1], r[2])
        val = shas[r[4]]
        old = out.setdefault(key, val)
        if old != val:
            raise ValueError(f"packed VS manifest conflict {key}: {old} vs {val}")
    return out


def resolve_vs_node(node, structural, committed):
    if node is None:
        return None, []
    node = tuple(node)
    if node[0] == "sha":
        return node[1], ["direct"]
    if node[0] != "ptr":
        raise ValueError(f"unknown VS node {node}")
    vals = []
    sources = []
    if node in structural:
        vals.append(structural[node])
        sources.append("crossMapPassKey")
    if node in committed:
        vals.append(committed[node])
        sources.append("committedPackedVsAlias")
    if len(set(vals)) > 1:
        raise ValueError(f"paired VS resolver disagreement {node}: {vals}")
    return (vals[0] if vals else None), sources


def output_reg(base, blob, semantic):
    so = base.signature(blob, b"OSGN")
    regs = [r for r, s in so.items() if s == semantic]
    if len(regs) != 1:
        return None
    return regs[0]


def component_profile(base, blob, tc: int):
    w = base.words(blob)
    inst = list(base.walk(w))
    si = base.signature(blob, b"ISGN")
    reg = output_reg(base, blob, ("TEXCOORD", tc))
    if reg is None:
        return None
    rows = []
    for comp in "xyzw":
        q = base.latest(inst, w, len(inst), base.OUTPUT, reg, comp)
        if q is None:
            continue
        qi, qp, op, dest, ops = q
        leaves = set()
        for src in ops[1:]:
            leaves |= base.input_leaves(blob, w, inst, qi, src, si)
        rows.append(
            {
                "component": comp,
                "writerOpcode": op,
                "inputLeaves": [list(x) for x in sorted(leaves)],
            }
        )
    return rows


def mov_source(base, blob, tc: int):
    w = base.words(blob)
    inst = list(base.walk(w))
    reg = output_reg(base, blob, ("TEXCOORD", tc))
    if reg is None:
        raise ValueError("missing output")
    ow = [base.latest(inst, w, len(inst), base.OUTPUT, reg, c) for c in "xyz"]
    if any(x is None for x in ow) or len({x[0] for x in ow}) != 1 or ow[0][2] != 54:
        raise ValueError("output xyz is not one MOV")
    ops = ow[0][4]
    if len(ops) != 2:
        raise ValueError("MOV arity")
    return w, inst, ow[0][0], ops[1]


def unwrap_movs(base, w, inst, before, src):
    cur = src
    for _ in range(6):
        if cur["type"] != base.TEMP or len(cur["idx"]) != 1:
            break
        r = cur["idx"][0]
        ww = [base.latest(inst, w, before, base.TEMP, r, c) for c in "xyz"]
        if any(x is None for x in ww) or len({x[0] for x in ww}) != 1 or ww[0][2] != 54:
            break
        ops = ww[0][4]
        if len(ops) != 2:
            break
        before = ww[0][0]
        cur = ops[1]
    return before, cur


def cb3_rows(base, writes, opcode):
    if any(x is None for x in writes) or [x[2] for x in writes] != [opcode] * 3:
        raise ValueError("matrix opcode")
    rows = []
    for q in writes:
        cbs = [x for x in q[4][1:] if x["type"] == base.CB and len(x["idx"]) >= 2]
        if len(cbs) != 1 or cbs[0]["idx"][0] != 3:
            raise ValueError("matrix cbuffer")
        rows.append(cbs[0]["idx"][1])
    if rows != [0, 1, 2]:
        raise ValueError(f"matrix rows {rows}")
    return rows


def prove_world_position(base, blob, tc: int):
    w, inst, before, src = mov_source(base, blob, tc)
    si = base.signature(blob, b"ISGN")
    leaves = base.input_leaves(blob, w, inst, before, src, si)
    if leaves != {("POSITION", 0)}:
        raise ValueError(f"position leaves {leaves}")
    before, cur = unwrap_movs(base, w, inst, before, src)
    if cur["type"] != base.TEMP or len(cur["idx"]) != 1:
        raise ValueError("position source temp")
    r = cur["idx"][0]
    writes = [base.latest(inst, w, before, base.TEMP, r, c) for c in "xyz"]
    rows = cb3_rows(base, writes, 17)
    return {"semantic": f"TEXCOORD{tc}", "input": "POSITION0", "worldMatrixRows": rows}


def normalized_raw_direction(base, blob, tc: int, input_semantic: str):
    w, inst, out_before, src = mov_source(base, blob, tc)
    if src["type"] != base.TEMP or len(src["idx"]) != 1:
        raise ValueError("normalized source temp")
    r = src["idx"][0]
    nw = [base.latest(inst, w, out_before, base.TEMP, r, c) for c in "xyz"]
    if any(x is None for x in nw) or len({x[0] for x in nw}) != 1 or nw[0][2] != 56:
        raise ValueError("normalize MUL")
    mul = nw[0][4]
    vec = None
    for scalar, raw in ((mul[1], mul[2]), (mul[2], mul[1])):
        if (
            scalar["type"] == base.TEMP
            and len(set(scalar["comps"][:3])) == 1
            and raw["type"] == base.TEMP
        ):
            vec = raw
    if vec is None or len(vec["idx"]) != 1:
        raise ValueError("normalize split")
    si = base.signature(blob, b"ISGN")
    leaves = base.input_leaves(blob, w, inst, nw[0][0], vec, si)
    if leaves != {(input_semantic, 0)}:
        raise ValueError(f"direction leaves {leaves}")
    vr = vec["idx"][0]
    writes = [base.latest(inst, w, nw[0][0], base.TEMP, vr, c) for c in "xyz"]
    rows = cb3_rows(base, writes, 16)
    return {
        "semantic": f"TEXCOORD{tc}",
        "input": f"{input_semantic}0",
        "normalized": True,
        "worldMatrixRows": rows,
    }


def raw_world_direction(base, blob, tc: int, input_semantic: str):
    w, inst, before, src = mov_source(base, blob, tc)
    si = base.signature(blob, b"ISGN")
    leaves = base.input_leaves(blob, w, inst, before, src, si)
    if leaves != {(input_semantic, 0)}:
        raise ValueError(f"direction leaves {leaves}")
    before, cur = unwrap_movs(base, w, inst, before, src)
    if cur["type"] != base.TEMP or len(cur["idx"]) != 1:
        raise ValueError("direction source temp")
    r = cur["idx"][0]
    writes = [base.latest(inst, w, before, base.TEMP, r, c) for c in "xyz"]
    rows = cb3_rows(base, writes, 16)
    return {
        "semantic": f"TEXCOORD{tc}",
        "input": f"{input_semantic}0",
        "normalized": False,
        "worldMatrixRows": rows,
    }


def exact_role_candidates(base, blob):
    out = {"worldPosition": [], "worldNormal": [], "worldTangent": []}
    for tc in range(6):
        try:
            out["worldPosition"].append(prove_world_position(base, blob, tc))
        except Exception:
            pass
        try:
            out["worldNormal"].append(normalized_raw_direction(base, blob, tc, "NORMAL"))
        except Exception:
            pass
        for fn in (normalized_raw_direction, raw_world_direction):
            try:
                q = fn(base, blob, tc, "TANGENT")
            except Exception:
                continue
            if q not in out["worldTangent"]:
                out["worldTangent"].append(q)
    return out


def build(root: Path, owner_probe_path: Path, base_path: Path, broad_path: Path, packed_vs_alias_path: Path):
    owner_probe = load(owner_probe_path, "sphere_owner_probe")
    base = load(base_path, "sphere_base")
    broad = load(broad_path, "sphere_broad")

    ownership = owner_probe.build(root, base_path, broad_path)
    if not ownership["summary"]["targetBankUniquelyResolved"]:
        raise ValueError(
            f"pixel owner bank unresolved: {ownership['summary']['candidateTargetBankCount']} candidates"
        )
    if ownership["summary"]["resolvedTargetShaderCount"] != 24:
        raise ValueError("pixel owner coverage is not 24/24")

    events, direct_blobs, direct_objects, scan_rows = owner_probe.collect_broad_events(root, base, broad)
    structural_vs, all_vs_ptrs, _ = owner_probe.structural_aliases(events, "vs")
    committed_vs = load_committed_packed_vs(packed_vs_alias_path)

    owner_rows = []
    unresolved_nodes = set()
    for row in ownership["ownerRows"]:
        q = dict(row)
        h, sources = resolve_vs_node(row["pairedVertexNode"], structural_vs, committed_vs)
        q["resolvedVertexShaderSha256"] = h
        q["vertexResolutionSources"] = sources
        if h is None:
            unresolved_nodes.add(tuple(row["pairedVertexNode"]) if row["pairedVertexNode"] else None)
        owner_rows.append(q)

    used_vs = sorted({r["resolvedVertexShaderSha256"] for r in owner_rows if r["resolvedVertexShaderSha256"]})
    profiles = []
    missing_blobs = []
    for h in used_vs:
        blob = direct_blobs["vs"].get(h)
        if blob is None:
            missing_blobs.append(h)
            continue
        tex = {}
        for tc in range(6):
            p = component_profile(base, blob, tc)
            if p is not None:
                tex[f"TEXCOORD{tc}"] = p
        specialized = {}
        try:
            specialized["texcoord2NormalTexcoord1Position"] = base.prove_vs(blob)
        except Exception:
            pass
        try:
            specialized["texcoord3NormalTexcoord1Position"] = broad.prove_vs_tc3(base, blob)
        except Exception:
            pass
        profiles.append(
            {
                "vertexShaderSha256": h,
                "texcoordComponentAncestry": tex,
                "exactRoleCandidates": exact_role_candidates(base, blob),
                "specializedExistingProofMatches": specialized,
            }
        )

    all_resolved = not unresolved_nodes and not missing_blobs
    summary = {
        "targetPixelShaderCount": 24,
        "ownerOccurrenceCount": len(owner_rows),
        "pairedVertexNodeIdentityCount": len(
            {tuple(r["pairedVertexNode"]) if r["pairedVertexNode"] else None for r in owner_rows}
        ),
        "resolvedPairedVertexShaderCount": len(used_vs),
        "unresolvedPairedVertexNodeCount": len(unresolved_nodes),
        "missingResolvedVertexBlobCount": len(missing_blobs),
        "allPairedVertexPayloadsResolved": all_resolved,
        "structurallyAnchoredPackedVertexPointerCount": len(structural_vs),
        "committedPackedVertexAliasCount": len(committed_vs),
        "ownerRowsSha256": jhash(owner_rows),
        "profileRowsSha256": jhash(profiles),
    }
    return {
        "format": "t6-retail-reflection-probe-sphere-elec-paired-vs-probe-v1",
        "producer": "tools/t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py",
        "sources": {
            "pixelOwnerProbe": "tools/t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v1.py",
            "packedVsAlias": str(packed_vs_alias_path),
            "pixelMath": "manifests/render/T6_RETAIL_REFLECTION_PROBE_SHIFTED_TANGENT_BASIS_NORMAL_V1.json",
        },
        "ownerRows": owner_rows,
        "unresolvedPairedVertexNodes": [list(x) if x is not None else None for x in sorted(unresolved_nodes, key=str)],
        "missingResolvedVertexBlobs": missing_blobs,
        "vertexProfiles": profiles,
        "summary": summary,
        "proofBoundary": (
            "Exploratory physical-producer stage. A paired VS is assigned only from a physically direct node, an exact "
            "cross-map pass-key anchor, or the independently committed packed-VS alias manifest; disagreement is fatal. "
            "TEXCOORD role candidates are derived directly from retained SM4 output dataflow and require exact POSITION0 "
            "DP4 cb3 rows 0..2, normalized NORMAL0 DP3 cb3 rows 0..2, or TANGENT0 DP3 cb3 rows 0..2 forms. This output "
            "still does not close the 24-family until every actual pixel-side base/tangent semantic is matched to the paired "
            "VS role proof and TEXCOORD0 is physically proved as the opposing world-position/view vector for every owner."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/mnt/data/t6_xanim_corpus"))
    ap.add_argument(
        "--owner-probe",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v1.py"),
    )
    ap.add_argument(
        "--base-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py"),
    )
    ap.add_argument(
        "--broad-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py"),
    )
    ap.add_argument(
        "--packed-vs-alias",
        type=Path,
        default=Path("manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json"),
    )
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = build(a.root, a.owner_probe, a.base_verifier, a.broad_verifier, a.packed_vs_alias)
    a.out.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
    print(json.dumps(d["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
