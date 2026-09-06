#!/usr/bin/env python3
import copy, hashlib, importlib.util, json, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent; TOOL=HERE/"t6_player_body_geometry_equivalence_v1.py"
s=importlib.util.spec_from_file_location("eq",TOOL)
if s is None or s.loader is None: raise RuntimeError("cannot import equivalence")
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
def dump(p,o): p.write_text(json.dumps(o,sort_keys=True)+"\n",encoding="utf-8"); return hashlib.sha256(p.read_bytes()).hexdigest()
def skeleton(source_tag):
    bones=[]
    for i,(name,parent) in enumerate((("tag_origin",None),("j_spine",0),("j_head",1))):
        bones.append({"index":i,"scriptStringId":10+i+(100 if source_tag=="B" else 0),"name":name,"parentIndex":parent,"parentDeltaRaw":None if parent is None else i-parent,"partClassificationRaw":i,"localRotationInt16":None if i==0 else [0,0,0,32767],"localRotation":[0,0,0,1],"localTranslation":[0,0,float(i)],"globalBaseMat":{"quat":[0,0,0,1],"trans":[0,0,float(i)],"transWeight":1.0}})
    return {"format":"t6-xmodel-skeleton-normalized-v2","source":{"expandedSha256":source_tag*64,"xmodelFixedStart":100 if source_tag=="A" else 200},"identity":{"name":"body"},"skeletonSource":{"mode":"inline_owned","noise":source_tag},"skeleton":{"numBones":3,"numRootBones":1,"bones":bones},"validation":{"allBoneNamesResolved":True,"hierarchyValid":True}}
def mesh(source_tag):
    return {"format":"t6-xmodel-mesh-normalized-v1","expandedSha256":source_tag*64,"identity":{"name":"body"},"source":{"assetFixedStart":100 if source_tag=="A" else 200},"xmodel":{"numBones":3,"numRootBones":1,"numSurfs":1,"numLods":1,"lods":[{"index":0,"dist":100.0,"numSurfs":1,"surfIndex":0,"partBits":[1,2,3,4,5]}]},"surfaces":[{"index":0,"tileMode":2,"flags":0,"vertCount":3,"triCount":1,"baseVertIndex":0,"blendCounts":[0,0,0,0],"vertices":[{"position":[0,0,0],"raw":{"normal":"0x1"}},{"position":[1,0,0],"raw":{"normal":"0x2"}},{"position":[0,1,0],"raw":{"normal":"0x3"}}],"triangles":[[0,1,2]],"joints0":[[0,0,0,0],[1,0,0,0],[2,0,0,0]],"weights0":[[1.0,0,0,0],[1.0,0,0,0],[1.0,0,0,0]],"rigidVertLists":[{"index":0,"boneOffset":64,"joint":1,"vertCount":1,"triOffset":0,"triCount":1,"collisionTreePointer":{"kind":"following"},"collisionTree":{"nodeCount":2,"leafCount":1,"nodesPointer":{"kind":"following"}}}],"unweightedVertexCount":0,"pointers":{"verts0":{"kind":"following","noise":source_tag}}}],"sections":[{"sourceNoise":source_tag}],"validation":{"allLocalTriangleIndicesInRange":True}}
def proof(path,skp,mep,tag,fixed):
    sksha=hashlib.sha256(skp.read_bytes()).hexdigest(); mesha=hashlib.sha256(mep.read_bytes()).hexdigest()
    p={"format":"t6-player-body-retail-proof-v3","sourceFastfile":{"zoneName":"zone"+tag,"sha256":tag.lower()*64},"expandedStream":{"sha256":tag*64},"fullBody":{"name":"body","fixedRecordSha256":fixed,"fixedPlusNameSha256":fixed[::-1],"skeleton":{"normalizedJsonSha256":sksha},"mesh":{"normalizedJsonSha256":mesha}},"status":{"fullBodyGeometryRetailProven":True,"fullBodySkeletonRetailProven":True},"proofArtifacts":{"skeleton":{"path":str(skp),"sha256":sksha},"mesh":{"path":str(mep),"sha256":mesha}}}
    dump(path,p)
with tempfile.TemporaryDirectory() as d:
    td=Path(d); sk1=td/"sk1.json"; sk2=td/"sk2.json"; me1=td/"me1.json"; me2=td/"me2.json"; dump(sk1,skeleton("A")); dump(sk2,skeleton("B")); dump(me1,mesh("A")); dump(me2,mesh("B")); p1=td/"p1.json"; p2=td/"p2.json"; proof(p1,sk1,me1,"A","1"*64); proof(p2,sk2,me2,"B","2"*64)
    out=m.build([p1,p2]); assert out["equivalent"] is True and out["status"]=="equivalent-render-skeleton"
    assert out["summary"]["distinctSkeletonSemanticFingerprints"]==1 and out["summary"]["distinctRenderSkinSemanticFingerprints"]==1
    assert out["summary"]["fixedRecordByteIdentical"] is False and out["scope"]["materialsAndTexturesCompared"] is False
    assert out["sources"][0]["skeletonArtifactSha256"]!=out["sources"][1]["skeletonArtifactSha256"]

    changed=mesh("B"); changed["surfaces"][0]["vertices"][1]["position"][0]=1.5; dump(me2,changed); proof(p2,sk2,me2,"B","2"*64)
    out=m.build([p1,p2]); assert out["equivalent"] is False and out["summary"]["distinctRenderSkinSemanticFingerprints"]==2

    dump(me2,mesh("B")); badsk=skeleton("B"); badsk["skeleton"]["bones"][2]["parentIndex"]=0; dump(sk2,badsk); proof(p2,sk2,me2,"B","2"*64)
    out=m.build([p1,p2]); assert out["equivalent"] is False and out["summary"]["distinctSkeletonSemanticFingerprints"]==2

    dump(sk2,skeleton("B")); dump(me2,mesh("B")); proof(p2,sk2,me2,"B","2"*64); doc=json.loads(p2.read_text()); doc["proofArtifacts"]["mesh"]["sha256"]="0"*64; dump(p2,doc)
    try: m.build([p1,p2])
    except ValueError as e: assert "artifact SHA mismatch" in str(e)
    else: raise AssertionError("mismatched artifact hash accepted")

print("PASS t6_player_body_geometry_equivalence_v1")
