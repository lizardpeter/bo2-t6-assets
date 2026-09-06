#!/usr/bin/env python3
"""Retail player-body proof promoter v2 with audited mesh-v3 reuse support.

The v1 promoter remains unchanged. v2 delegates ordinary mesh-v1/v2 proofs to
that mature gate. For t6-xmodel-mesh-normalized-v3, it first independently
audits every borrowed packed render field and then reuses all v1 identity,
hash, skeleton, geometry-cardinality and triangle-range checks.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-player-body-retail-proof-v2"
MESH_V3 = "t6-xmodel-mesh-normalized-v3"
PACKED_FIELDS = {
    "verts0": "verts0",
    "vertList": "vertList",
    "triIndices": "triIndices",
    "vertsBlend": "vertsBlend",
    "tensionData": "tensionData",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_json(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected JSON object")
    return doc


def _audit_comparison(pointer: dict[str, Any], provenance: dict[str, Any], label: str) -> None:
    if pointer.get("kind") != "packed":
        return
    if pointer.get("block") != 5:
        raise ValueError(f"{label}: packed render reuse is not VIRTUAL block 5")
    if provenance.get("mode") != "packed-reusable-owner":
        raise ValueError(f"{label}: packed pointer lacks reusable-owner provenance")
    comp = provenance.get("comparison")
    if not isinstance(comp, dict) or comp.get("match") is not True:
        raise ValueError(f"{label}: packed pointer lacks exact replay comparison")
    off = int(pointer.get("offset", -1))
    if int(comp.get("actualOffset", -2)) != off or int(comp.get("predictedOffset", -3)) != off:
        raise ValueError(f"{label}: replay offsets do not equal packed target offset")


def audit_mesh_v3(mesh: dict[str, Any]) -> dict[str, Any]:
    if mesh.get("format") != MESH_V3:
        raise ValueError(f"mesh format must be {MESH_V3}")
    reuse = mesh.get("reuseProof")
    val = mesh.get("validation")
    surfaces = mesh.get("surfaces")
    if not isinstance(reuse, dict) or not isinstance(val, dict) or not isinstance(surfaces, list):
        raise ValueError("mesh v3 is missing reuseProof/validation/surfaces")
    owner = reuse.get("owner")
    if not isinstance(owner, dict) or not isinstance(owner.get("name"), str) or not isinstance(owner.get("fixedSourceStart"), int):
        raise ValueError("mesh v3 reusable owner identity is incomplete")
    if reuse.get("allBorrowedFieldsHaveExplicitReplayComparison") is not True:
        raise ValueError("mesh v3 does not assert exact comparison coverage")
    if reuse.get("topLevelSurfsBorrowed") is not False:
        raise ValueError("mesh v3 cannot promote borrowed top-level XModel.surfs")
    if val.get("targetHeaderAndLodsAuthoritative") is not True or val.get("targetSurfaceScalarRecordsAuthoritative") is not True:
        raise ValueError("mesh v3 target header/surface scalar authority is not closed")
    if val.get("packedTopLevelSurfsSupported") is not False:
        raise ValueError("mesh v3 top-level packed-surface boundary changed")

    observed = []
    for i, surf in enumerate(surfaces):
        if not isinstance(surf, dict):
            raise ValueError(f"mesh v3 surface {i} is not an object")
        pointers = surf.get("pointers")
        prov = surf.get("payloadProvenance")
        if not isinstance(pointers, dict) or not isinstance(prov, dict):
            raise ValueError(f"mesh v3 surface {i}: pointer/provenance ledger missing")
        for pointer_key, prov_key in PACKED_FIELDS.items():
            p = pointers.get(pointer_key)
            q = prov.get(prov_key)
            if not isinstance(p, dict) or not isinstance(q, dict):
                raise ValueError(f"mesh v3 surface {i} {pointer_key}: pointer/provenance row missing")
            _audit_comparison(p, q, f"surface {i} {pointer_key}")
            if p.get("kind") == "packed":
                observed.append(f"surfs[{i}].{prov_key}")

    declared = reuse.get("borrowedFields")
    if not isinstance(declared, list) or any(not isinstance(x, str) for x in declared):
        raise ValueError("mesh v3 borrowedFields must be a string list")
    if len(declared) != len(set(declared)):
        raise ValueError("mesh v3 borrowedFields contains duplicates")
    if sorted(declared) != sorted(observed):
        raise ValueError(f"mesh v3 borrowedFields ledger mismatch: declared={sorted(declared)} observed={sorted(observed)}")
    if int(reuse.get("borrowedFieldCount", -1)) != len(observed):
        raise ValueError("mesh v3 borrowedFieldCount mismatch")
    return {"owner": owner, "borrowedFields": sorted(observed), "borrowedFieldCount": len(observed)}


def build(*, name: str, zone_name: str, fastfile_path: Path, expanded_path: Path,
          probe_path: Path, skeleton_path: Path, mesh_path: Path, v1_module=None) -> dict[str, Any]:
    here = Path(__file__).resolve().parent
    v1 = v1_module or load_module(here / "t6_player_body_retail_proof_v1.py", "t6_body_proof_v2_base")
    mesh = load_json(mesh_path)
    reuse_summary = None
    if mesh.get("format") == MESH_V3:
        reuse_summary = audit_mesh_v3(mesh)
        old = set(v1.MESH_FORMATS)
        try:
            v1.MESH_FORMATS.add(MESH_V3)
            out = v1.build(name=name, zone_name=zone_name, fastfile_path=fastfile_path, expanded_path=expanded_path,
                           probe_path=probe_path, skeleton_path=skeleton_path, mesh_path=mesh_path)
        finally:
            v1.MESH_FORMATS.clear(); v1.MESH_FORMATS.update(old)
    else:
        out = v1.build(name=name, zone_name=zone_name, fastfile_path=fastfile_path, expanded_path=expanded_path,
                       probe_path=probe_path, skeleton_path=skeleton_path, mesh_path=mesh_path)
    out = dict(out)
    out["format"] = FORMAT
    out["promoterVersion"] = 2
    if reuse_summary is not None:
        full = dict(out["fullBody"]); mesh_summary = dict(full["mesh"])
        mesh_summary["reuseMode"] = "exact-nested-packed-render-payloads"
        mesh_summary["reuseOwner"] = reuse_summary["owner"]
        mesh_summary["borrowedFields"] = reuse_summary["borrowedFields"]
        mesh_summary["borrowedFieldCount"] = reuse_summary["borrowedFieldCount"]
        full["mesh"] = mesh_summary; out["fullBody"] = full
    out["proofBoundary"] = (
        "Promoter v2 preserves the v1 retail identity, source-hash, skeleton, geometry-cardinality and triangle-range gates. "
        "Mesh-v3 is additionally permitted only when every packed nested render payload has exact VIRTUAL reusable-owner replay provenance. "
        "Packed top-level XModel.surfs remains outside the proof boundary."
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True); ap.add_argument("--zone-name", required=True)
    ap.add_argument("--fastfile", type=Path, required=True); ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--probe", type=Path, required=True); ap.add_argument("--skeleton", type=Path, required=True)
    ap.add_argument("--mesh", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = build(name=a.name, zone_name=a.zone_name, fastfile_path=a.fastfile, expanded_path=a.expanded,
                probe_path=a.probe, skeleton_path=a.skeleton, mesh_path=a.mesh)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(a.out), "format": out["format"], "name": out["fullBody"]["name"],
                      "meshReuseMode": out["fullBody"]["mesh"].get("reuseMode"),
                      "borrowedFieldCount": out["fullBody"]["mesh"].get("borrowedFieldCount", 0)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
