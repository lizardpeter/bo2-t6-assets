#!/usr/bin/env python3
import copy
import importlib.util
import struct
from pathlib import Path
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent; TOOL=HERE/"t6_xmodel_skeleton_normalize_v3.py"
spec=importlib.util.spec_from_file_location("skv3",TOOL)
if spec is None or spec.loader is None: raise RuntimeError("cannot import skeleton v3")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
FOLLOW=0xFFFFFFFF

def packed(block,off): return ((block<<29)|off)+1

def alloc(cur,a,size):
    s=(cur+a-1)&~(a-1); return s,s+size

n=3; roots=1; nr=2; ns=1; target=0; owner=500; baseoff=0x1000
raw=bytearray(1200)
# owner allocates all skeleton arrays and top-level XSurface records inline
for off in (8,12,16,20,24,28,32): struct.pack_into("<I",raw,owner+off,FOLLOW)
# target points to the same replayed VIRTUAL allocation sequence
cur=baseoff
specs=[(8,2,n*2),(12,1,nr),(16,2,nr*8),(20,4,nr*16),(24,1,n),(28,4,n*32)]
expected={}
for off,a,size in specs:
    s,cur=alloc(cur,a,size); expected[off]=s; struct.pack_into("<I",raw,target+off,packed(5,s))
surfs,cur=alloc(cur,16,ns*80); expected[32]=surfs; struct.pack_into("<I",raw,target+32,packed(5,surfs))
raw=bytes(raw)

class FakeWalker:
    def __init__(self,data,start): self.start=start
    def walk_xmodel(self):
        x={"name":"target" if self.start==target else "owner","numBones":n,"numRootBones":roots,"numSurfs":ns}
        sections=[]
        if self.start!=target:
            for k in ("XModel.boneNames","XModel.parentList","XModel.quats","XModel.trans","XModel.partClassification","XModel.baseMat","XModel.surfs.fixed"):
                sections.append({"name":k,"start":700,"end":701})
        return {"xmodel":x,"sections":sections,"blockers":[],"assetSerializedEnd":900,"assetSerializedBytes":400,"assetSerializedSha256":"a"*64}

proof=m.replay_owner_signature_top_surfs(raw,owner,target,walker_cls=FakeWalker)
assert proof is not None and proof["topLevelSurfsAlias"] is True
assert proof["comparisonCount"]==7 and proof["topLevelSurfsPredictedOffset"]==surfs
assert {r["field"] for r in proof["comparisons"]}=={
    "XModel.boneNames","XModel.parentList","XModel.quats","XModel.trans","XModel.partClassification","XModel.baseMat","XModel.surfs"
}
assert all(r["match"] for r in proof["comparisons"])

# Any wrong top-level surface offset destroys the owner signature.
bad=bytearray(raw); struct.pack_into("<I",bad,target+32,packed(5,surfs+16))
assert m.replay_owner_signature_top_surfs(bytes(bad),owner,target,walker_cls=FakeWalker) is None
# Mixed inline/reused skeleton ownership is outside this proof shape.
bad=bytearray(raw); struct.pack_into("<I",bad,target+20,FOLLOW)
assert m.replay_owner_signature_top_surfs(bytes(bad),owner,target,walker_cls=FakeWalker) is None
# Non-VIRTUAL packed fields are never accepted.
bad=bytearray(raw); struct.pack_into("<I",bad,target+24,packed(4,expected[24]))
assert m.replay_owner_signature_top_surfs(bytes(bad),owner,target,walker_cls=FakeWalker) is None

base=SimpleNamespace(); base.XModelWalker=FakeWalker
base.build_xmodel_catalog=lambda data,maxi:{2:{"fixedSourceStart":owner,"name":"owner"}}
base.resolve_reusable_owner=lambda *args: (_ for _ in ()).throw(AssertionError("v2 resolver should be patched"))
def fake_normalize(data,asset_start,*,xasset_index=None,identity_name=None):
    p=base.resolve_reusable_owner(data,asset_start,xasset_index)
    return {"format":"t6-xmodel-skeleton-normalized-v2","source":{"expandedSha256":"fixture","xmodelFixedStart":asset_start},
        "identity":{"name":identity_name,"xassetIndex":xasset_index},
        "skeletonSource":{"mode":"packed_reusable_owner","owner":{"xassetIndex":p["ownerAssetIndex"],"name":p["ownerName"],"fixedSourceStart":p["ownerFixedStart"]},
            "virtualReplayBase":p["virtualReplayBase"],"comparisonCount":p["comparisonCount"],"surfaceComparisonCount":p["surfaceComparisonCount"],"comparisons":p["comparisons"]},
        "skeleton":{"numBones":n,"numRootBones":roots,"bones":[{"name":"a"},{"name":"b"},{"name":"c"}]},
        "validation":{"allBoneNamesResolved":True,"hierarchyValid":True}}
base.normalize_skeleton=fake_normalize
out=m.normalize_skeleton(raw,target,xasset_index=9,identity_name="target",base_module=base,walker_cls=FakeWalker)
assert out["format"]=="t6-xmodel-skeleton-normalized-v3"
assert out["skeletonSource"]["mode"]=="packed_reusable_owner_top_level_surfs"
assert out["skeletonSource"]["topLevelSurfsAliasProven"] is True
assert out["skeletonSource"]["topLevelSurfsComparison"]["actualOffset"]==surfs
assert out["validation"]["packedTopLevelSurfsAliasProof"]=="exact-relative-VIRTUAL-replay"

# Two exact earlier owners must remain ambiguous.
base2=SimpleNamespace(**base.__dict__)
base2.build_xmodel_catalog=lambda data,maxi:{2:{"fixedSourceStart":owner,"name":"ownerA"},3:{"fixedSourceStart":owner,"name":"ownerB"}}
try:
    m.resolve_reusable_owner_top_surfs(raw,target,9,base_module=base2,walker_cls=FakeWalker)
except ValueError as e:
    assert "not unique" in str(e)
else:
    raise AssertionError("ambiguous top-level surface owner promoted")

print("PASS t6_xmodel_skeleton_normalize_v3")
