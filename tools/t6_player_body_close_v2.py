#!/usr/bin/env python3
"""Player-body closure v2 with exact nested render-reuse fallback.

v2 preserves t6_player_body_close_v1 as the primary path. If v1 closes, its
mesh artifact is re-promoted through the audited body-proof v2 wrapper. If v1
blocks specifically at mesh decoding and skeleton-v2 proves a unique reusable
owner, mesh-v3 is attempted. No other blocker is bypassed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

FORMAT = "t6-player-body-closure-v2"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def load_json(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict): raise ValueError(f"{path}: expected JSON object")
    return doc


def default_modules(here: Path):
    return SimpleNamespace(
        v1=load_module(here / "t6_player_body_close_v1.py", "t6_body_close_v2_base"),
        meshv3=load_module(here / "t6_xmodel_mesh_normalize_v3.py", "t6_body_close_v2_meshv3"),
        promoter=load_module(here / "t6_player_body_retail_proof_v2.py", "t6_body_close_v2_promoter"),
    )


def _dump(path: Path, obj: dict[str, Any]) -> dict[str, Any]:
    # Reuse v1's artifact helper when available through caller; local metadata is
    # intentionally minimal and deterministic here.
    import hashlib
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    raw=path.read_bytes()
    return {"path":str(path),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def _clean_generated(out_dir: Path) -> None:
    for name in (
        "player_body_retail_proof_v1.json", "player_body_retail_proof_v2.json",
        "player_body_closure_v1.json", "player_body_closure_v2.json",
        "xmodel_mesh_normalized_v3.json",
    ):
        p=out_dir/name
        if p.exists(): p.unlink()


def _promote_v2(mods, *, name, zone_name, fastfile, expanded, base, mesh_path: Path, out_dir: Path):
    proof = mods.promoter.build(
        name=name, zone_name=zone_name, fastfile_path=fastfile, expanded_path=expanded,
        probe_path=Path(base["xmodelProbe"]["path"]), skeleton_path=Path(base["skeleton"]["path"]), mesh_path=mesh_path,
    )
    return proof, _dump(out_dir/"player_body_retail_proof_v2.json", proof)


def close_body(*, name: str, zone_name: str, fastfile: Path, expanded: Path, raw_parser_path: Path,
               out_dir: Path, modules=None) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True); _clean_generated(out_dir)
    here=Path(__file__).resolve().parent; mods=modules or default_modules(here)
    base=mods.v1.close_body(name=name, zone_name=zone_name, fastfile=fastfile, expanded=expanded,
                            raw_parser_path=raw_parser_path, out_dir=out_dir)
    report_path=out_dir/"player_body_closure_v2.json"
    common={
        "format":FORMAT,"name":name,"zoneName":zone_name,
        "primaryClosure":{"format":base.get("format"),"status":base.get("status"),"blockerStage":base.get("blockerStage"),"blocker":base.get("blocker")},
        "sourceFastfile":base.get("sourceFastfile"),"expandedStream":base.get("expandedStream"),
        "xmodelProbe":base.get("xmodelProbe"),"xassetBinding":base.get("xassetBinding"),"skeleton":base.get("skeleton"),
        "proofBoundary":"v2 never bypasses identity, XAsset-index or skeleton blockers. Nested render reuse is attempted only after the primary mesh path fails and skeleton-v2 already proves a unique reusable owner.",
    }

    if base.get("status")=="closed":
        try:
            mesh_path=Path(base["mesh"]["path"])
            proof, proof_art=_promote_v2(mods,name=name,zone_name=zone_name,fastfile=fastfile,expanded=expanded,base=base,mesh_path=mesh_path,out_dir=out_dir)
        except Exception as e:
            out={**common,"status":"blocked","blockerStage":"promotion-v2","blocker":str(e),"mesh":base.get("mesh"),"retailProof":None}
            _dump(report_path,out); return out
        out={**common,"status":"closed","blockerStage":None,"blocker":None,"mesh":base.get("mesh"),"meshPath":"primary-v2",
             "retailProof":proof_art,"summary":{
                 "xassetIndex":base.get("xassetBinding",{}).get("xassetIndex"),"bones":proof["fullBody"]["bones"],"rootBones":proof["fullBody"]["rootBones"],
                 "surfaces":proof["fullBody"]["surfaces"],"vertices":proof["fullBody"]["mesh"]["vertices"],"triangles":proof["fullBody"]["mesh"]["triangles"],
                 "meshReuseMode":proof["fullBody"]["mesh"].get("reuseMode")}}
        _dump(report_path,out); return out

    if base.get("blockerStage")!="mesh":
        out={**common,"status":"blocked","blockerStage":base.get("blockerStage"),"blocker":base.get("blocker"),"mesh":base.get("mesh"),"retailProof":None}
        _dump(report_path,out); return out

    sk_art=base.get("skeleton")
    if not isinstance(sk_art,dict) or not isinstance(sk_art.get("path"),str):
        out={**common,"status":"blocked","blockerStage":"mesh-v3-precondition","blocker":"primary mesh failed but no closed skeleton artifact exists","mesh":None,"retailProof":None}
        _dump(report_path,out); return out
    sk=load_json(Path(sk_art["path"])); source=sk.get("skeletonSource") or {}
    if source.get("mode")!="packed_reusable_owner" or not isinstance(source.get("owner"),dict):
        out={**common,"status":"blocked","blockerStage":"mesh","blocker":base.get("blocker"),"mesh":None,"retailProof":None,
             "meshV3":{"attempted":False,"reason":"skeleton-v2 has no unique packed_reusable_owner"}}
        _dump(report_path,out); return out

    fixed=(base.get("xassetBinding") or {}).get("fixedSourceStart")
    if not isinstance(fixed,int):
        out={**common,"status":"blocked","blockerStage":"mesh-v3-precondition","blocker":"exact target fixedSourceStart missing from XAsset binding","mesh":None,"retailProof":None}
        _dump(report_path,out); return out
    try:
        data=expanded.read_bytes(); mesh=mods.meshv3.normalize_mesh(data,fixed,sk)
        mesh_art=_dump(out_dir/"xmodel_mesh_normalized_v3.json",mesh)
    except Exception as e:
        out={**common,"status":"blocked","blockerStage":"mesh-v3-reuse","blocker":str(e),"mesh":None,"retailProof":None,
             "meshV3":{"attempted":True,"primaryMeshBlocker":base.get("blocker")}}
        _dump(report_path,out); return out
    base_for_promotion=dict(base); base_for_promotion["mesh"]=mesh_art
    try:
        proof,proof_art=_promote_v2(mods,name=name,zone_name=zone_name,fastfile=fastfile,expanded=expanded,base=base_for_promotion,mesh_path=Path(mesh_art["path"]),out_dir=out_dir)
    except Exception as e:
        out={**common,"status":"blocked","blockerStage":"promotion-v2","blocker":str(e),"mesh":mesh_art,"retailProof":None,
             "meshV3":{"attempted":True,"primaryMeshBlocker":base.get("blocker")}}
        _dump(report_path,out); return out
    out={**common,"status":"closed","blockerStage":None,"blocker":None,"mesh":mesh_art,"meshPath":"nested-reuse-v3","retailProof":proof_art,
         "meshV3":{"attempted":True,"primaryMeshBlocker":base.get("blocker")},"summary":{
             "xassetIndex":base.get("xassetBinding",{}).get("xassetIndex"),"bones":proof["fullBody"]["bones"],"rootBones":proof["fullBody"]["rootBones"],
             "surfaces":proof["fullBody"]["surfaces"],"vertices":proof["fullBody"]["mesh"]["vertices"],"triangles":proof["fullBody"]["mesh"]["triangles"],
             "meshReuseMode":proof["fullBody"]["mesh"].get("reuseMode"),"borrowedFieldCount":proof["fullBody"]["mesh"].get("borrowedFieldCount",0)}}
    _dump(report_path,out); return out


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--name",required=True); ap.add_argument("--zone-name",required=True)
    ap.add_argument("--fastfile",type=Path,required=True); ap.add_argument("--expanded",type=Path,required=True)
    ap.add_argument("--raw-parser",type=Path,default=Path(__file__).with_name("t6_raw_xasset_inventory_v2.py")); ap.add_argument("--out-dir",type=Path,required=True)
    a=ap.parse_args(); out=close_body(name=a.name,zone_name=a.zone_name,fastfile=a.fastfile,expanded=a.expanded,raw_parser_path=a.raw_parser,out_dir=a.out_dir)
    print(json.dumps({"status":out["status"],"name":a.name,"blockerStage":out.get("blockerStage"),"blocker":out.get("blocker"),"meshPath":out.get("meshPath"),"summary":out.get("summary")},indent=2))
    return 0 if out["status"]=="closed" else 2

if __name__=="__main__": raise SystemExit(main())
