#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent; TOOL=HERE/"t6_player_body_close_v2.py"
spec=importlib.util.spec_from_file_location("closev2",TOOL)
if spec is None or spec.loader is None: raise RuntimeError("cannot import close v2")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj)+"\n",encoding="utf-8")
    raw=path.read_bytes(); return {"path":str(path),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}

class V1:
    mode="closed"
    @classmethod
    def close_body(cls,*,name,zone_name,fastfile,expanded,raw_parser_path,out_dir):
        probe=dump(out_dir/"xmodel_target_probe_v1.json",{"fixture":True})
        source_mode="inline_owned" if cls.mode=="mesh-no-owner" else "packed_reusable_owner"
        sk={"format":"t6-xmodel-skeleton-normalized-v2","skeletonSource":{"mode":source_mode,"owner":{"name":"owner","fixedSourceStart":50} if source_mode=="packed_reusable_owner" else None}}
        skeleton=dump(out_dir/"xmodel_skeleton_normalized_v2.json",sk)
        common={"format":"t6-player-body-closure-v1","sourceFastfile":{"sha256":"f"*64},"expandedStream":{"sha256":"e"*64},
                "xmodelProbe":probe,"xassetBinding":{"xassetIndex":9,"fixedSourceStart":100},"skeleton":skeleton}
        if cls.mode=="identity": return {**common,"status":"blocked","blockerStage":"xmodel-identity","blocker":"missing","mesh":None}
        if cls.mode in ("mesh","mesh-no-owner"): return {**common,"status":"blocked","blockerStage":"mesh","blocker":"v2 packed verts0 unsupported","mesh":None}
        mesh=dump(out_dir/"xmodel_mesh_normalized_v2.json",{"format":"t6-xmodel-mesh-normalized-v2"})
        dump(out_dir/"player_body_retail_proof_v1.json",{"old":True})
        return {**common,"status":"closed","blockerStage":None,"blocker":None,"mesh":mesh}

class MeshV3:
    fail=False; calls=0
    @classmethod
    def normalize_mesh(cls,data,fixed,sk):
        cls.calls+=1
        if cls.fail: raise ValueError("v3 replay mismatch")
        assert fixed==100 and sk["skeletonSource"]["mode"]=="packed_reusable_owner"
        return {"format":"t6-xmodel-mesh-normalized-v3","fixture":True}

class Promoter:
    fail=False; calls=0
    @classmethod
    def build(cls,**kw):
        cls.calls+=1
        if cls.fail: raise ValueError("promotion audit failed")
        reuse="exact-nested-packed-render-payloads" if Path(kw["mesh_path"]).name.endswith("v3.json") else None
        mesh={"vertices":12,"triangles":7}
        if reuse: mesh.update({"reuseMode":reuse,"borrowedFieldCount":3})
        return {"format":"t6-player-body-retail-proof-v2","fullBody":{"name":kw["name"],"bones":102,"rootBones":1,"surfaces":42,"mesh":mesh}}

mods=SimpleNamespace(v1=V1,meshv3=MeshV3,promoter=Promoter)

with tempfile.TemporaryDirectory() as d:
    td=Path(d); ff=td/"f.ff"; exp=td/"f.expanded"; ff.write_bytes(b"ff"); exp.write_bytes(b"expanded")

    V1.mode="closed"; MeshV3.fail=False; MeshV3.calls=0; Promoter.fail=False; Promoter.calls=0
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw.py",out_dir=td/"closed",modules=mods)
    assert out["status"]=="closed" and out["meshPath"]=="primary-v2" and MeshV3.calls==0 and Promoter.calls==1
    assert Path(out["retailProof"]["path"]).name=="player_body_retail_proof_v2.json"

    V1.mode="identity"; MeshV3.calls=0; Promoter.calls=0
    stale=td/"identity"/"player_body_retail_proof_v2.json"; dump(stale,{"stale":True})
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw.py",out_dir=td/"identity",modules=mods)
    assert out["status"]=="blocked" and out["blockerStage"]=="xmodel-identity" and MeshV3.calls==0 and Promoter.calls==0
    assert not stale.exists()

    V1.mode="mesh-no-owner"; MeshV3.calls=0; Promoter.calls=0
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw.py",out_dir=td/"noowner",modules=mods)
    assert out["status"]=="blocked" and out["blockerStage"]=="mesh" and MeshV3.calls==0
    assert out["meshV3"]["attempted"] is False

    V1.mode="mesh"; MeshV3.calls=0; Promoter.calls=0
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw.py",out_dir=td/"fallback",modules=mods)
    assert out["status"]=="closed" and out["meshPath"]=="nested-reuse-v3" and MeshV3.calls==1 and Promoter.calls==1
    assert out["summary"]["meshReuseMode"]=="exact-nested-packed-render-payloads" and out["summary"]["borrowedFieldCount"]==3

    V1.mode="mesh"; MeshV3.fail=True; MeshV3.calls=0; Promoter.calls=0
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw.py",out_dir=td/"v3fail",modules=mods)
    assert out["status"]=="blocked" and out["blockerStage"]=="mesh-v3-reuse" and "replay mismatch" in out["blocker"]
    assert Promoter.calls==0 and not (td/"v3fail"/"player_body_retail_proof_v2.json").exists()
    MeshV3.fail=False

    V1.mode="mesh"; Promoter.fail=True; MeshV3.calls=0; Promoter.calls=0
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw.py",out_dir=td/"promofail",modules=mods)
    assert out["status"]=="blocked" and out["blockerStage"]=="promotion-v2" and Promoter.calls==1
    assert not (td/"promofail"/"player_body_retail_proof_v2.json").exists()

print("PASS t6_player_body_close_v2")
