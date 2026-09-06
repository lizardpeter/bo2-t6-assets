#!/usr/bin/env python3
import hashlib, importlib.util, json, tempfile
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent; TOOL=HERE/"t6_player_body_close_v3.py"
s=importlib.util.spec_from_file_location("closev3",TOOL)
if s is None or s.loader is None: raise RuntimeError("cannot import close v3")
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
def dump(p,o):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o)+"\n",encoding="utf-8"); raw=p.read_bytes(); return {"path":str(p),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
class V2:
    mode="closed"
    @classmethod
    def close_body(cls,*,name,zone_name,fastfile,expanded,raw_parser_path,out_dir):
        probe=dump(out_dir/"probe.json",{"fixture":1}); common={"sourceFastfile":{"sha256":"f"*64},"expandedStream":{"sha256":"e"*64},"xmodelProbe":probe,"xassetBinding":{"xassetIndex":7,"fixedSourceStart":100}}
        if cls.mode=="identity": return {**common,"status":"blocked","blockerStage":"xmodel-identity","blocker":"missing","skeleton":None,"mesh":None}
        if cls.mode=="skeleton": return {**common,"status":"blocked","blockerStage":"skeleton","blocker":"v2 owner unresolved","skeleton":None,"mesh":None}
        sk=dump(out_dir/"skv2.json",{"format":"t6-xmodel-skeleton-normalized-v2"}); mesh=dump(out_dir/"meshv2.json",{"format":"t6-xmodel-mesh-normalized-v2"})
        return {**common,"status":"closed","blockerStage":None,"blocker":None,"skeleton":sk,"mesh":mesh,"meshPath":"primary-v2"}
class SK3:
    fail=False; calls=0
    @classmethod
    def normalize_skeleton(cls,data,fixed,*,xasset_index,identity_name):
        cls.calls+=1
        if cls.fail: raise ValueError("surfs replay mismatch")
        assert fixed==100 and xasset_index==7
        return {"format":"t6-xmodel-skeleton-normalized-v3","identity":{"name":identity_name},"skeletonSource":{"topLevelSurfsAliasProven":True}}
class MV4:
    fail=False; calls=0
    @classmethod
    def normalize_mesh(cls,data,fixed,sk):
        cls.calls+=1
        if cls.fail: raise ValueError("owner mesh not inline")
        return {"format":"t6-xmodel-mesh-normalized-v4","identity":sk["identity"]}
class Promo:
    fail=False; calls=0
    @classmethod
    def build(cls,**kw):
        cls.calls+=1
        if cls.fail: raise ValueError("promotion mismatch")
        top=Path(kw["mesh_path"]).name.endswith("v4.json")
        mesh={"vertices":20,"triangles":10}
        if top: mesh.update({"reuseMode":"exact-packed-top-level-XModel.surfs-alias","aliasedSurfaceCount":42})
        return {"format":"t6-player-body-retail-proof-v3","fullBody":{"name":kw["name"],"bones":102,"rootBones":1,"surfaces":42,"mesh":mesh}}
mods=SimpleNamespace(v2=V2,skeletonv3=SK3,meshv4=MV4,promoter=Promo)
with tempfile.TemporaryDirectory() as d:
    td=Path(d); ff=td/"f.ff"; exp=td/"f.expanded"; ff.write_bytes(b"ff"); exp.write_bytes(b"expanded")
    V2.mode="closed"; SK3.calls=MV4.calls=Promo.calls=0; SK3.fail=MV4.fail=Promo.fail=False
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw",out_dir=td/"closed",modules=mods)
    assert out["status"]=="closed" and out["meshPath"]=="primary-v2" and SK3.calls==0 and MV4.calls==0 and Promo.calls==1

    V2.mode="identity"; SK3.calls=MV4.calls=Promo.calls=0
    stale=td/"identity"/"player_body_retail_proof_v3.json"; dump(stale,{"stale":1})
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw",out_dir=td/"identity",modules=mods)
    assert out["status"]=="blocked" and out["blockerStage"]=="xmodel-identity" and SK3.calls==MV4.calls==Promo.calls==0 and not stale.exists()

    V2.mode="skeleton"; SK3.calls=MV4.calls=Promo.calls=0
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw",out_dir=td/"fallback",modules=mods)
    assert out["status"]=="closed" and out["meshPath"]=="top-level-surfs-alias-v4" and SK3.calls==1 and MV4.calls==1 and Promo.calls==1
    assert out["summary"]["meshReuseMode"]=="exact-packed-top-level-XModel.surfs-alias" and out["summary"]["aliasedSurfaceCount"]==42

    SK3.fail=True; SK3.calls=MV4.calls=Promo.calls=0
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw",out_dir=td/"skfail",modules=mods)
    assert out["status"]=="blocked" and out["blockerStage"]=="skeleton-v3-alias" and "replay mismatch" in out["blocker"] and MV4.calls==Promo.calls==0
    SK3.fail=False

    MV4.fail=True; SK3.calls=MV4.calls=Promo.calls=0
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw",out_dir=td/"meshfail",modules=mods)
    assert out["status"]=="blocked" and out["blockerStage"]=="mesh-v4-alias" and "owner mesh not inline" in out["blocker"] and Promo.calls==0
    MV4.fail=False

    Promo.fail=True; SK3.calls=MV4.calls=Promo.calls=0
    out=m.close_body(name="body",zone_name="zone",fastfile=ff,expanded=exp,raw_parser_path=td/"raw",out_dir=td/"promofail",modules=mods)
    assert out["status"]=="blocked" and out["blockerStage"]=="promotion-v3" and Promo.calls==1 and not (td/"promofail"/"player_body_retail_proof_v3.json").exists()

print("PASS t6_player_body_close_v3")
