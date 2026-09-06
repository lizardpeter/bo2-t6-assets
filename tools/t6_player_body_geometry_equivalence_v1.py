#!/usr/bin/env python3
"""Prove render/skeleton equivalence across multiple retail player-body proofs.

This is deliberately narrower than full XModel equivalence. It compares:
- resolved bone identity/hierarchy/local transforms/global base matrices;
- render vertices, triangles, skin joints/weights and surface scalar metadata;
- target LOD surface layout.

It intentionally does NOT claim equivalence of Material handles/textures or raw
collision-tree node/leaf payload bytes, which are not fully represented in the
normalized body proof artifacts. Equivalent variants may therefore share the
animation/geometry registry while remaining separate visual/material variants.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

FORMAT="t6-player-body-geometry-equivalence-v1"
SK_FORMATS={"t6-xmodel-skeleton-normalized-v2","t6-xmodel-skeleton-normalized-v3"}
MESH_FORMATS={"t6-xmodel-mesh-normalized-v1","t6-xmodel-mesh-normalized-v2","t6-xmodel-mesh-normalized-v3","t6-xmodel-mesh-normalized-v4"}

def load(path:Path):
    d=json.loads(path.read_text(encoding="utf-8-sig"));
    if not isinstance(d,dict): raise ValueError(f"{path}: expected JSON object")
    return d
def sha(path:Path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical_sha(obj:Any): return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def resolve_artifact(proof_path:Path,stored:str):
    p=Path(stored); candidates=[p]
    if not p.is_absolute(): candidates += [proof_path.parent/p, proof_path.parent/p.name]
    for c in candidates:
        if c.is_file(): return c.resolve()
    raise FileNotFoundError(f"artifact {stored!r} from {proof_path} is not materialized")
def verify_artifact(proof_path:Path,art:dict[str,Any],label:str):
    if not isinstance(art,dict) or not isinstance(art.get("path"),str) or not isinstance(art.get("sha256"),str): raise ValueError(f"{proof_path}: {label} artifact metadata incomplete")
    p=resolve_artifact(proof_path,art["path"]); actual=sha(p)
    if actual!=art["sha256"]: raise ValueError(f"{proof_path}: {label} artifact SHA mismatch")
    return p,actual

def skeleton_semantic(sk:dict[str,Any]):
    if sk.get("format") not in SK_FORMATS: raise ValueError(f"unsupported skeleton format {sk.get('format')}")
    val=sk.get("validation") or {}; s=sk.get("skeleton") or {}; bones=s.get("bones")
    if val.get("allBoneNamesResolved") is not True or val.get("hierarchyValid") is not True: raise ValueError("skeleton integrity is not closed")
    if not isinstance(bones,list) or len(bones)!=int(s.get("numBones",-1)): raise ValueError("skeleton bone cardinality mismatch")
    rows=[]
    for i,b in enumerate(bones):
        if not isinstance(b,dict) or b.get("index")!=i or not isinstance(b.get("name"),str): raise ValueError(f"skeleton bone {i} malformed")
        bm=b.get("globalBaseMat") or {}
        rows.append({"index":i,"name":b["name"],"parentIndex":b.get("parentIndex"),"partClassificationRaw":b.get("partClassificationRaw"),"localRotationInt16":b.get("localRotationInt16"),"localTranslation":b.get("localTranslation"),"globalBaseMat":{"quat":bm.get("quat"),"trans":bm.get("trans"),"transWeight":bm.get("transWeight")}})
    return {"numBones":int(s["numBones"]),"numRootBones":int(s["numRootBones"]),"bones":rows}
def _rigid_semantic(rows):
    out=[]
    for r in rows or []:
        if not isinstance(r,dict): raise ValueError("rigid list row malformed")
        tree=r.get("collisionTree")
        out.append({"index":r.get("index"),"boneOffset":r.get("boneOffset"),"joint":r.get("joint"),"vertCount":r.get("vertCount"),"triOffset":r.get("triOffset"),"triCount":r.get("triCount"),"collisionTreeShape":None if not isinstance(tree,dict) else {"nodeCount":tree.get("nodeCount"),"leafCount":tree.get("leafCount")}})
    return out
def mesh_semantic(mesh:dict[str,Any]):
    if mesh.get("format") not in MESH_FORMATS: raise ValueError(f"unsupported mesh format {mesh.get('format')}")
    val=mesh.get("validation") or {}; x=mesh.get("xmodel") or {}; surfs=mesh.get("surfaces")
    if val.get("allLocalTriangleIndicesInRange") is not True: raise ValueError("mesh local triangle validation is not closed")
    if not isinstance(surfs,list) or len(surfs)!=int(x.get("numSurfs",-1)): raise ValueError("mesh surface cardinality mismatch")
    lods=[]
    for l in x.get("lods") or []:
        lods.append({"index":l.get("index"),"dist":l.get("dist"),"numSurfs":l.get("numSurfs"),"surfIndex":l.get("surfIndex"),"partBits":l.get("partBits")})
    rows=[]
    for i,s in enumerate(surfs):
        if not isinstance(s,dict): raise ValueError(f"surface {i} malformed")
        vc=int(s.get("vertCount",-1)); tc=int(s.get("triCount",-1)); verts=s.get("vertices"); tris=s.get("triangles"); joints=s.get("joints0"); weights=s.get("weights0")
        if vc<0 or tc<0 or not isinstance(verts,list) or not isinstance(tris,list) or not isinstance(joints,list) or not isinstance(weights,list): raise ValueError(f"surface {i} arrays missing")
        if len(verts)!=vc or len(tris)!=tc or len(joints)!=vc or len(weights)!=vc: raise ValueError(f"surface {i} array cardinality mismatch")
        rows.append({"index":i,"tileMode":s.get("tileMode"),"flags":s.get("flags"),"vertCount":vc,"triCount":tc,"baseVertIndex":s.get("baseVertIndex"),"blendCounts":s.get("blendCounts"),"vertices":verts,"triangles":tris,"joints0":joints,"weights0":weights,"rigidVertLists":_rigid_semantic(s.get("rigidVertLists")),"unweightedVertexCount":s.get("unweightedVertexCount")})
    return {"numBones":int(x["numBones"]),"numRootBones":int(x["numRootBones"]),"numSurfs":int(x["numSurfs"]),"numLods":int(x["numLods"]),"lods":lods,"surfaces":rows}
def proof_semantics(proof_path:Path):
    proof=load(proof_path); body=proof.get("fullBody") or {}; status=proof.get("status") or {}; arts=proof.get("proofArtifacts") or {}
    name=body.get("name")
    if not isinstance(name,str) or status.get("fullBodyGeometryRetailProven") is not True or status.get("fullBodySkeletonRetailProven") is not True: raise ValueError(f"{proof_path}: body proof is not retail-closed")
    skp,sksha=verify_artifact(proof_path,arts.get("skeleton"),"skeleton"); mp,meshsha=verify_artifact(proof_path,arts.get("mesh"),"mesh")
    if (body.get("skeleton") or {}).get("normalizedJsonSha256")!=sksha: raise ValueError(f"{proof_path}: fullBody skeleton SHA does not match proof artifact")
    if (body.get("mesh") or {}).get("normalizedJsonSha256")!=meshsha: raise ValueError(f"{proof_path}: fullBody mesh SHA does not match proof artifact")
    sk=load(skp); mesh=load(mp); ss=skeleton_semantic(sk); ms=mesh_semantic(mesh)
    if ss["numBones"]!=ms["numBones"] or ss["numRootBones"]!=ms["numRootBones"]: raise ValueError(f"{proof_path}: skeleton/mesh bone cardinality disagreement")
    return {"proofPath":str(proof_path),"name":name,"zoneName":(proof.get("sourceFastfile") or {}).get("zoneName"),"fastfileSha256":(proof.get("sourceFastfile") or {}).get("sha256"),"expandedSha256":(proof.get("expandedStream") or {}).get("sha256"),"fixedRecordSha256":body.get("fixedRecordSha256"),"fixedPlusNameSha256":body.get("fixedPlusNameSha256"),"skeletonSemanticSha256":canonical_sha(ss),"renderSkinSemanticSha256":canonical_sha(ms),"skeletonArtifactSha256":sksha,"meshArtifactSha256":meshsha,"skeletonSemantic":ss,"meshSemantic":ms}
def build(proof_paths:list[Path]):
    if len(proof_paths)<2: raise ValueError("equivalence proof requires at least two retail body proofs")
    rows=[proof_semantics(p) for p in proof_paths]; names={r["name"] for r in rows}
    if len(names)!=1: raise ValueError(f"body proof names differ: {sorted(names)}")
    sk={r["skeletonSemanticSha256"] for r in rows}; mesh={r["renderSkinSemanticSha256"] for r in rows}; equivalent=len(sk)==1 and len(mesh)==1
    sources=[{k:r[k] for k in ("proofPath","zoneName","fastfileSha256","expandedSha256","fixedRecordSha256","fixedPlusNameSha256","skeletonSemanticSha256","renderSkinSemanticSha256","skeletonArtifactSha256","meshArtifactSha256")} for r in rows]
    return {"format":FORMAT,"name":next(iter(names)),"status":"equivalent-render-skeleton" if equivalent else "different-render-skeleton","equivalent":equivalent,"summary":{"proofCount":len(rows),"distinctSkeletonSemanticFingerprints":len(sk),"distinctRenderSkinSemanticFingerprints":len(mesh),"fixedRecordByteIdentical":len({r["fixedRecordSha256"] for r in rows})==1,"fixedPlusNameByteIdentical":len({r["fixedPlusNameSha256"] for r in rows})==1},"sources":sources,"scope":{"skeletonHierarchyAndTransformsCompared":True,"renderVerticesTrianglesSkinAndLodsCompared":True,"materialsAndTexturesCompared":False,"rawCollisionTreeNodeLeafPayloadBytesCompared":False},"proofBoundary":"Equivalent means only that the normalized skeleton and render/skinning/LOD semantics are identical. It does not collapse material/texture variants or claim full serialized XModel equivalence."}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("proof",type=Path,nargs="+"); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args(); out=build(a.proof); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"out":str(a.out),"name":out["name"],"status":out["status"],**out["summary"]},indent=2)); return 0 if out["equivalent"] else 2
if __name__=="__main__": raise SystemExit(main())
