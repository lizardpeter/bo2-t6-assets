#!/usr/bin/env python3
"""Player-body closure v3 with exact top-level XModel.surfs alias fallback.

Primary path is t6_player_body_close_v2. v3 adds exactly one fallback: when v2
stops at the skeleton stage, the target may be the packed-skeleton + packed
XModel.surfs reuse shape closed by skeleton-v3 and mesh-v4. No earlier blocker
is bypassed.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

FORMAT="t6-player-body-closure-v3"

def load_module(path:Path,name:str):
    s=importlib.util.spec_from_file_location(name,path)
    if s is None or s.loader is None: raise RuntimeError(f"cannot import {path}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def default_modules(here:Path):
    return SimpleNamespace(v2=load_module(here/"t6_player_body_close_v2.py","t6_close_v3_base"),skeletonv3=load_module(here/"t6_xmodel_skeleton_normalize_v3.py","t6_close_v3_skeleton"),meshv4=load_module(here/"t6_xmodel_mesh_normalize_v4.py","t6_close_v3_mesh"),promoter=load_module(here/"t6_player_body_retail_proof_v3.py","t6_close_v3_promoter"))
def dump(path:Path,obj:dict[str,Any]):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8"); raw=path.read_bytes(); return {"path":str(path),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
def clean(out:Path):
    for n in ("player_body_retail_proof_v3.json","player_body_closure_v3.json","xmodel_skeleton_normalized_v3.json","xmodel_mesh_normalized_v4.json"):
        p=out/n
        if p.exists(): p.unlink()
def promote(mods,*,name,zone_name,fastfile,expanded,probe,skeleton,mesh,out_dir):
    proof=mods.promoter.build(name=name,zone_name=zone_name,fastfile_path=fastfile,expanded_path=expanded,probe_path=Path(probe["path"]),skeleton_path=Path(skeleton["path"]),mesh_path=Path(mesh["path"])); return proof,dump(out_dir/"player_body_retail_proof_v3.json",proof)

def close_body(*,name:str,zone_name:str,fastfile:Path,expanded:Path,raw_parser_path:Path,out_dir:Path,modules=None):
    out_dir.mkdir(parents=True,exist_ok=True); clean(out_dir); here=Path(__file__).resolve().parent; mods=modules or default_modules(here)
    base=mods.v2.close_body(name=name,zone_name=zone_name,fastfile=fastfile,expanded=expanded,raw_parser_path=raw_parser_path,out_dir=out_dir)
    report=out_dir/"player_body_closure_v3.json"
    common={"format":FORMAT,"name":name,"zoneName":zone_name,"primaryClosureV2":{"status":base.get("status"),"blockerStage":base.get("blockerStage"),"blocker":base.get("blocker"),"meshPath":base.get("meshPath")},"sourceFastfile":base.get("sourceFastfile"),"expandedStream":base.get("expandedStream"),"xmodelProbe":base.get("xmodelProbe"),"xassetBinding":base.get("xassetBinding"),"proofBoundary":"v3 never bypasses XModel identity or XAsset binding. The top-level surface-alias fallback is attempted only when closer-v2 stops at skeleton and exact XAsset binding is already available."}
    if base.get("status")=="closed":
        try: proof,pa=promote(mods,name=name,zone_name=zone_name,fastfile=fastfile,expanded=expanded,probe=base["xmodelProbe"],skeleton=base["skeleton"],mesh=base["mesh"],out_dir=out_dir)
        except Exception as e:
            out={**common,"status":"blocked","blockerStage":"promotion-v3","blocker":str(e),"skeleton":base.get("skeleton"),"mesh":base.get("mesh"),"retailProof":None}; dump(report,out); return out
        out={**common,"status":"closed","blockerStage":None,"blocker":None,"skeleton":base.get("skeleton"),"mesh":base.get("mesh"),"meshPath":base.get("meshPath"),"retailProof":pa,"summary":{"xassetIndex":base.get("xassetBinding",{}).get("xassetIndex"),"bones":proof["fullBody"]["bones"],"rootBones":proof["fullBody"]["rootBones"],"surfaces":proof["fullBody"]["surfaces"],"vertices":proof["fullBody"]["mesh"]["vertices"],"triangles":proof["fullBody"]["mesh"]["triangles"],"meshReuseMode":proof["fullBody"]["mesh"].get("reuseMode")}}; dump(report,out); return out
    if base.get("blockerStage")!="skeleton":
        out={**common,"status":"blocked","blockerStage":base.get("blockerStage"),"blocker":base.get("blocker"),"skeleton":base.get("skeleton"),"mesh":base.get("mesh"),"retailProof":None}; dump(report,out); return out
    bind=base.get("xassetBinding") or {}; fixed=bind.get("fixedSourceStart"); idx=bind.get("xassetIndex")
    if not isinstance(fixed,int) or not isinstance(idx,int) or not isinstance(base.get("xmodelProbe"),dict):
        out={**common,"status":"blocked","blockerStage":"skeleton-v3-precondition","blocker":"closer-v2 skeleton failure lacks exact XAsset fixed start/index or target probe","skeleton":None,"mesh":None,"retailProof":None}; dump(report,out); return out
    data=expanded.read_bytes()
    try:
        sk=mods.skeletonv3.normalize_skeleton(data,fixed,xasset_index=idx,identity_name=name); ska=dump(out_dir/"xmodel_skeleton_normalized_v3.json",sk)
        if (sk.get("skeletonSource") or {}).get("topLevelSurfsAliasProven") is not True: raise ValueError("skeleton-v3 did not produce top-level surface alias proof")
    except Exception as e:
        out={**common,"status":"blocked","blockerStage":"skeleton-v3-alias","blocker":str(e),"skeleton":None,"mesh":None,"retailProof":None,"fallback":{"attempted":True,"primarySkeletonBlocker":base.get("blocker")}}; dump(report,out); return out
    try: mesh=mods.meshv4.normalize_mesh(data,fixed,sk); ma=dump(out_dir/"xmodel_mesh_normalized_v4.json",mesh)
    except Exception as e:
        out={**common,"status":"blocked","blockerStage":"mesh-v4-alias","blocker":str(e),"skeleton":ska,"mesh":None,"retailProof":None,"fallback":{"attempted":True,"primarySkeletonBlocker":base.get("blocker")}}; dump(report,out); return out
    try: proof,pa=promote(mods,name=name,zone_name=zone_name,fastfile=fastfile,expanded=expanded,probe=base["xmodelProbe"],skeleton=ska,mesh=ma,out_dir=out_dir)
    except Exception as e:
        out={**common,"status":"blocked","blockerStage":"promotion-v3","blocker":str(e),"skeleton":ska,"mesh":ma,"retailProof":None,"fallback":{"attempted":True,"primarySkeletonBlocker":base.get("blocker")}}; dump(report,out); return out
    out={**common,"status":"closed","blockerStage":None,"blocker":None,"skeleton":ska,"mesh":ma,"meshPath":"top-level-surfs-alias-v4","retailProof":pa,"fallback":{"attempted":True,"primarySkeletonBlocker":base.get("blocker")},"summary":{"xassetIndex":idx,"bones":proof["fullBody"]["bones"],"rootBones":proof["fullBody"]["rootBones"],"surfaces":proof["fullBody"]["surfaces"],"vertices":proof["fullBody"]["mesh"]["vertices"],"triangles":proof["fullBody"]["mesh"]["triangles"],"meshReuseMode":proof["fullBody"]["mesh"].get("reuseMode"),"aliasedSurfaceCount":proof["fullBody"]["mesh"].get("aliasedSurfaceCount")}}; dump(report,out); return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--name",required=True); ap.add_argument("--zone-name",required=True); ap.add_argument("--fastfile",type=Path,required=True); ap.add_argument("--expanded",type=Path,required=True); ap.add_argument("--raw-parser",type=Path,default=Path(__file__).with_name("t6_raw_xasset_inventory_v2.py")); ap.add_argument("--out-dir",type=Path,required=True); a=ap.parse_args(); out=close_body(name=a.name,zone_name=a.zone_name,fastfile=a.fastfile,expanded=a.expanded,raw_parser_path=a.raw_parser,out_dir=a.out_dir); print(json.dumps({"status":out["status"],"name":a.name,"blockerStage":out.get("blockerStage"),"blocker":out.get("blocker"),"meshPath":out.get("meshPath"),"summary":out.get("summary")},indent=2)); return 0 if out["status"]=="closed" else 2
if __name__=="__main__": raise SystemExit(main())
