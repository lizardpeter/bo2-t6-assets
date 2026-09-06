#!/usr/bin/env python3
import copy
import hashlib
import importlib.util
import struct
from pathlib import Path

HERE=Path(__file__).resolve().parent; TOOL=HERE/"t6_xmodel_mesh_normalize_v4.py"
spec=importlib.util.spec_from_file_location("meshv4",TOOL)
if spec is None or spec.loader is None: raise RuntimeError("cannot import mesh v4")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def packed(block,off): return ((block<<29)|off)+1

data=bytearray(400); start=0; name="target_body"; owner="owner_body"; off=0x1230
data[start+4]=3; data[start+5]=1; data[start+6]=1
struct.pack_into("<I",data,start+32,packed(5,off)); struct.pack_into("<H",data,start+196,1)
struct.pack_into("<fHH5I",data,start+40,222.0,1,0,1,2,3,4,5)
raw=bytes(data); sha=hashlib.sha256(raw).hexdigest()
sk={"format":"t6-xmodel-skeleton-normalized-v3","source":{"expandedSha256":sha,"xmodelFixedStart":start},
    "identity":{"name":name,"xassetIndex":8},"skeleton":{"numBones":3,"numRootBones":1},"validation":{"allBoneNamesResolved":True,"hierarchyValid":True},
    "skeletonSource":{"mode":"packed_reusable_owner_top_level_surfs","topLevelSurfsAliasProven":True,
        "owner":{"name":owner,"xassetIndex":2,"fixedSourceStart":250},
        "topLevelSurfsComparison":{"field":"XModel.surfs","actualOffset":off,"predictedOffset":off,"match":True}}}
owner_mesh={"format":"t6-xmodel-mesh-normalized-v1","identity":{"name":owner},
    "xmodel":{"numBones":3,"numRootBones":1,"numSurfs":1,"numLods":1,"lods":[{"index":0,"dist":999.0,"numSurfs":1,"surfIndex":0}]},
    "surfaces":[{"index":0,"vertCount":3,"triCount":1,"vertices":[{"v":0},{"v":1},{"v":2}],"triangles":[[0,1,2]],
        "joints0":[[0,0,0,0],[1,0,0,0],[2,0,0,0]],"weights0":[[1.0,0,0,0],[1.0,0,0,0],[1.0,0,0,0]],
        "rigidVertLists":[],"blendCounts":[0,0,0,0],"unweightedVertexCount":0}]}

out=m.build_from_owner(raw,start,sk,owner_mesh)
assert out["format"]=="t6-xmodel-mesh-normalized-v4"
assert out["reuseProof"]["topLevelSurfsBorrowed"] is True
assert out["reuseProof"]["nestedPayloadsTransitivelyOwnedByAliasedSurfaceObject"] is True
assert out["xmodel"]["lods"][0]["dist"]==222.0
assert out["surfaces"][0]["vertices"]==owner_mesh["surfaces"][0]["vertices"]
assert out["surfaces"][0]["payloadProvenance"]["mode"]=="aliased-with-top-level-XSurface-object"
assert out["summary"]=={"vertices":3,"triangles":1}

bad=copy.deepcopy(sk); bad["skeletonSource"]["topLevelSurfsComparison"]["predictedOffset"]+=16
try: m.build_from_owner(raw,start,bad,owner_mesh)
except ValueError as e: assert "replay offset" in str(e)
else: raise AssertionError("wrong top-level alias offset accepted")

bad_owner=copy.deepcopy(owner_mesh); bad_owner["identity"]["name"]="wrong"
try: m.build_from_owner(raw,start,sk,bad_owner)
except ValueError as e: assert "owner mesh identity" in str(e)
else: raise AssertionError("wrong owner identity accepted")

bad_owner=copy.deepcopy(owner_mesh); bad_owner["format"]="t6-xmodel-mesh-normalized-v3"
try: m.build_from_owner(raw,start,sk,bad_owner)
except ValueError as e: assert "fully inline mesh-v1 owner" in str(e)
else: raise AssertionError("recursive owner reuse accepted")

bad_owner=copy.deepcopy(owner_mesh); bad_owner["surfaces"][0]["joints0"][2]=[9,0,0,0]
try: m.build_from_owner(raw,start,sk,bad_owner)
except ValueError as e: assert "joint outside target skeleton" in str(e)
else: raise AssertionError("out-of-skeleton owner skin row accepted")

data2=bytearray(raw); struct.pack_into("<HH",data2,start+44,2,0); raw2=bytes(data2); sk2=copy.deepcopy(sk); sk2["source"]["expandedSha256"]=hashlib.sha256(raw2).hexdigest()
try: m.build_from_owner(raw2,start,sk2,owner_mesh)
except ValueError as e: assert "LOD0 surface span" in str(e)
else: raise AssertionError("target LOD outside aliased surface array accepted")

print("PASS t6_xmodel_mesh_normalize_v4")
