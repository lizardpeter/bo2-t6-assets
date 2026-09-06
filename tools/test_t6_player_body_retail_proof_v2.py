#!/usr/bin/env python3
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "t6_player_body_retail_proof_v2.py"
REGISTRY = HERE / "t6_player_body_identity_registry_v1.py"


def loadmod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


m = loadmod(TOOL, "bodyproofv2")
registry = loadmod(REGISTRY, "bodyregistryv2test")


def dump(path, obj): path.write_text(json.dumps(obj, sort_keys=True)+"\n", encoding="utf-8")
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(td: Path):
    ff=td/"f.ff"; exp=td/"f.expanded"; ff.write_bytes(b"ff-retail"); exp.write_bytes(b"expanded-retail")
    es=sha(exp); name="c_test_mp_unit_smg_fb"; start=100
    probe={"format":"t6-xmodel-target-probe-v1","source":{"bytes":exp.stat().st_size,"sha256":es},"targets":[{
        "status":"exact_inline_xmodel","name":name,"rawStructOffset":start,"fixedRecordSha256":"1"*64,"fixedPlusNameSha256":"2"*64,
        "numBones":3,"numRootBones":1,"numSurfs":1,"numLods":1,"lods":[{"index":0,"dist":100.0,"numSurfs":1,"surfIndex":0}],"pointers":{}}]}
    skeleton={"format":"t6-xmodel-skeleton-normalized-v2","source":{"expandedSha256":es,"xmodelFixedStart":start},
        "identity":{"name":name,"xassetIndex":5},"skeletonSource":{"mode":"packed_reusable_owner"},
        "skeleton":{"numBones":3,"numRootBones":1,"bones":[{"name":"tag_origin"},{"name":"j_spine"},{"name":"j_head"}],"allocationTailAllZero":True},
        "validation":{"allBoneNamesResolved":True,"hierarchyValid":True}}
    null={"kind":"null","raw":0,"rawHex":"0x00000000"}; follow={"kind":"following","raw":0xFFFFFFFF,"rawHex":"0xFFFFFFFF"}
    packed={"kind":"packed","raw":0xA0000121,"rawHex":"0xA0000121","block":5,"offset":0x120}
    mesh={"format":"t6-xmodel-mesh-normalized-v3","expandedSha256":es,"identity":{"name":name},"source":{"assetFixedStart":start},
        "xmodel":{"numBones":3,"numRootBones":1,"numSurfs":1,"numLods":1},
        "surfaces":[{"vertCount":3,"triCount":1,"vertices":[{},{},{}],"triangles":[[0,1,2]],
            "pointers":{"verts0":packed,"vertList":null,"triIndices":follow,"vertsBlend":null,"tensionData":null},
            "payloadProvenance":{"verts0":{"mode":"packed-reusable-owner","comparison":{"field":"surfs[0].verts0","actualOffset":0x120,"predictedOffset":0x120,"match":True}},
                "vertList":{"mode":"target-null"},"triIndices":{"mode":"target-inline"},"vertsBlend":{"mode":"target-null"},"tensionData":{"mode":"target-null"}}}],
        "reuseProof":{"owner":{"name":"c_test_mp_owner_smg_fb","fixedSourceStart":50,"xassetIndex":2},"borrowedFields":["surfs[0].verts0"],"borrowedFieldCount":1,
            "allBorrowedFieldsHaveExplicitReplayComparison":True,"topLevelSurfsBorrowed":False},
        "validation":{"allLocalTriangleIndicesInRange":True,"targetHeaderAndLodsAuthoritative":True,"targetSurfaceScalarRecordsAuthoritative":True,
            "packedTopLevelSurfsSupported":False}}
    pp=td/"probe.json"; sp=td/"sk.json"; mp=td/"mesh.json"; dump(pp,probe); dump(sp,skeleton); dump(mp,mesh)
    return name,ff,exp,pp,sp,mp,mesh

with tempfile.TemporaryDirectory() as d:
    td=Path(d); name,ff,exp,pp,sp,mp,mesh=fixture(td)
    out=m.build(name=name,zone_name="faction_test_mp",fastfile_path=ff,expanded_path=exp,probe_path=pp,skeleton_path=sp,mesh_path=mp)
    assert out["format"]=="t6-player-body-retail-proof-v2"
    assert out["fullBody"]["mesh"]["reuseMode"]=="exact-nested-packed-render-payloads"
    assert out["fullBody"]["mesh"]["borrowedFields"]==["surfs[0].verts0"]
    proof=td/"proof.json"; dump(proof,out); rr=registry.proof_row(proof,out); assert rr["name"]==name

    bad=copy.deepcopy(mesh); bad["surfaces"][0]["payloadProvenance"]["verts0"]["comparison"]["predictedOffset"]+=4; dump(mp,bad)
    try: m.build(name=name,zone_name="faction_test_mp",fastfile_path=ff,expanded_path=exp,probe_path=pp,skeleton_path=sp,mesh_path=mp)
    except ValueError as e: assert "replay offsets" in str(e)
    else: raise AssertionError("bad v3 replay promoted")

    bad=copy.deepcopy(mesh); bad["reuseProof"]["borrowedFields"]=[]; dump(mp,bad)
    try: m.build(name=name,zone_name="faction_test_mp",fastfile_path=ff,expanded_path=exp,probe_path=pp,skeleton_path=sp,mesh_path=mp)
    except ValueError as e: assert "borrowedFields ledger mismatch" in str(e)
    else: raise AssertionError("bad borrowed-field ledger promoted")

    bad=copy.deepcopy(mesh); bad["surfaces"][0]["pointers"]["verts0"]["block"]=4; dump(mp,bad)
    try: m.build(name=name,zone_name="faction_test_mp",fastfile_path=ff,expanded_path=exp,probe_path=pp,skeleton_path=sp,mesh_path=mp)
    except ValueError as e: assert "VIRTUAL block 5" in str(e)
    else: raise AssertionError("non-VIRTUAL render reuse promoted")

    # Ordinary v1 remains delegated to the unchanged v1 promoter path.
    ordinary=copy.deepcopy(mesh); ordinary["format"]="t6-xmodel-mesh-normalized-v1"; ordinary.pop("reuseProof"); ordinary.pop("validation"); ordinary["validation"]={"allLocalTriangleIndicesInRange":True}; ordinary["surfaces"][0].pop("pointers"); ordinary["surfaces"][0].pop("payloadProvenance"); dump(mp,ordinary)
    out2=m.build(name=name,zone_name="faction_test_mp",fastfile_path=ff,expanded_path=exp,probe_path=pp,skeleton_path=sp,mesh_path=mp)
    assert out2["format"]=="t6-player-body-retail-proof-v2" and "reuseMode" not in out2["fullBody"]["mesh"]

print("PASS t6_player_body_retail_proof_v2")
