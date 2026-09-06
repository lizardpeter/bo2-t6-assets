#!/usr/bin/env python3
import copy, importlib.util, json, tempfile
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent; TOOL=HERE/"t6_player_body_retail_proof_v3.py"
s=importlib.util.spec_from_file_location("proofv3",TOOL)
if s is None or s.loader is None: raise RuntimeError("cannot import proof v3")
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
def dump(p,o): p.write_text(json.dumps(o)+"\n",encoding="utf-8")
name="target"; owner={"name":"owner","xassetIndex":2,"fixedSourceStart":50}; comp={"field":"XModel.surfs","actualOffset":4096,"predictedOffset":4096,"match":True}
sk={"format":"t6-xmodel-skeleton-normalized-v3","identity":{"name":name},"skeletonSource":{"mode":"packed_reusable_owner_top_level_surfs","topLevelSurfsAliasProven":True,"owner":owner,"topLevelSurfsComparison":comp}}
mesh={"format":"t6-xmodel-mesh-normalized-v4","identity":{"name":name},"reuseProof":{"mode":"exact-packed-top-level-XModel.surfs-alias","topLevelSurfsBorrowed":True,"nestedPayloadsTransitivelyOwnedByAliasedSurfaceObject":True,"owner":owner,"topLevelSurfsComparison":comp},"validation":{"targetHeaderAndLodsAuthoritative":True,"surfaceArrayExactOwnerAlias":True,"recursiveOwnerMeshReuseSupported":False},"surfaces":[{"payloadProvenance":{"mode":"aliased-with-top-level-XSurface-object","owner":owner,"topLevelSurfsComparison":comp}}]}
class V2:
    calls=0; saw_patched=False
    @classmethod
    def build(cls,**kw):
        cls.calls+=1; v1=kw["v1_module"]; cls.saw_patched=(v1.SKELETON_FORMAT=="t6-xmodel-skeleton-normalized-v3" and "t6-xmodel-mesh-normalized-v4" in v1.MESH_FORMATS)
        return {"format":"t6-player-body-retail-proof-v2","fullBody":{"name":kw["name"],"mesh":{"vertices":10,"triangles":5}}}
v1=SimpleNamespace(SKELETON_FORMAT="t6-xmodel-skeleton-normalized-v2",MESH_FORMATS={"t6-xmodel-mesh-normalized-v1","t6-xmodel-mesh-normalized-v2"})
mods=SimpleNamespace(v1=v1,v2=V2)
with tempfile.TemporaryDirectory() as d:
    td=Path(d); sp=td/"sk.json"; mp=td/"mesh.json"; dump(sp,sk); dump(mp,mesh)
    dummy=td/"dummy"; dummy.write_bytes(b"x")
    out=m.build(name=name,zone_name="zone",fastfile_path=dummy,expanded_path=dummy,probe_path=dummy,skeleton_path=sp,mesh_path=mp,modules=mods)
    assert out["format"]=="t6-player-body-retail-proof-v3" and V2.saw_patched
    assert out["fullBody"]["mesh"]["reuseMode"]=="exact-packed-top-level-XModel.surfs-alias"
    assert out["fullBody"]["mesh"]["aliasedSurfaceCount"]==1
    assert v1.SKELETON_FORMAT=="t6-xmodel-skeleton-normalized-v2" and "t6-xmodel-mesh-normalized-v4" not in v1.MESH_FORMATS

    bad=copy.deepcopy(mesh); bad["reuseProof"]["owner"]=dict(owner); bad["reuseProof"]["owner"]["xassetIndex"]=3; dump(mp,bad)
    try: m.build(name=name,zone_name="zone",fastfile_path=dummy,expanded_path=dummy,probe_path=dummy,skeleton_path=sp,mesh_path=mp,modules=mods)
    except ValueError as e: assert "reusable owners differ" in str(e)
    else: raise AssertionError("different skeleton/mesh owners accepted")

    bad=copy.deepcopy(mesh); bad["reuseProof"]["topLevelSurfsComparison"]=dict(comp); bad["reuseProof"]["topLevelSurfsComparison"]["predictedOffset"]+=16; dump(mp,bad)
    try: m.build(name=name,zone_name="zone",fastfile_path=dummy,expanded_path=dummy,probe_path=dummy,skeleton_path=sp,mesh_path=mp,modules=mods)
    except ValueError as e: assert "comparisons differ" in str(e)
    else: raise AssertionError("different alias comparisons accepted")

    bad=copy.deepcopy(mesh); bad["surfaces"][0]["payloadProvenance"]["mode"]="target-inline"; dump(mp,bad)
    try: m.build(name=name,zone_name="zone",fastfile_path=dummy,expanded_path=dummy,probe_path=dummy,skeleton_path=sp,mesh_path=mp,modules=mods)
    except ValueError as e: assert "lacks whole-object alias provenance" in str(e)
    else: raise AssertionError("surface without alias provenance accepted")

print("PASS t6_player_body_retail_proof_v3")
