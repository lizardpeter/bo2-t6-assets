#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, struct, hashlib
from pathlib import Path

T6_UNIT_TO_METERS=0.0254
SQRT_HALF=math.sqrt(0.5)
WORLD_Q=[-SQRT_HALF,0.0,0.0,SQRT_HALF]

class ExportError(RuntimeError): pass

def unit(q):
    n=math.sqrt(sum(float(x)*float(x) for x in q))
    if not math.isfinite(n) or n <= 1e-12: raise ExportError(f"bad quaternion norm {n}")
    return [float(x)/n for x in q]

def hemi(rows):
    out=[]
    for q in rows:
        q=unit(q)
        if out and sum(a*b for a,b in zip(out[-1],q))<0:
            q=[-x for x in q]
        out.append(q)
    return out

def expand_quat(q):
    typ=q.get("type")
    if not q or typ=="NO_QUAT": return None
    raw=q.get("rawInt16Frames") or []
    if typ in ("HALF_QUAT","HALF_QUAT_NO_SIZE"):
        rows=[[0.0,0.0,r[0]/32767.0,r[1]/32767.0] for r in raw]
    elif typ in ("FULL_QUAT","FULL_QUAT_NO_SIZE"):
        rows=[[v/32767.0 for v in r] for r in raw]
    else: raise ExportError(f"unknown quat type {typ}")
    rows=hemi(rows)
    if typ in ("HALF_QUAT","FULL_QUAT"):
        inds=[int(x) for x in q.get("indices",[])]
        if len(inds)!=len(rows): raise ExportError("quat indices mismatch")
    else:
        if len(rows)!=1: raise ExportError("constant quat frame mismatch")
        inds=[0]
    return inds,rows,typ

def translation(track,bone):
    t=track.get("trans") or {}
    typ=t.get("type")
    if not t or typ=="NO_TRANS": return None
    if typ in ("SMALL_TRANS","FULL_TRANS"):
        rows=t.get("decodedFrames") or []
        inds=[int(x) for x in t.get("indices",[])]
        if len(rows)!=len(inds): raise ExportError("translation indices mismatch")
    elif typ=="TRANS_NO_SIZE":
        if t.get("constant") is None: raise ExportError("missing constant trans")
        rows=[t["constant"]]; inds=[0]
    else: raise ExportError(f"unknown translation type {typ}")
    vals=[[float(x) for x in r] for r in rows]
    if bone.get("parentIndex") is None:
        kind="rootRawXAnim"
    else:
        bind=[float(x) for x in bone.get("localTranslation",[0,0,0])]
        vals=[[bind[k]+row[k] for k in range(3)] for row in vals]
        kind="nonRootBindPlusDelta"
    return inds,vals,typ,kind

def qmul(a,b):
    ax,ay,az,aw=a;bx,by,bz,bw=b
    return [aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,
            aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz]
def qrot(q,v):
    x,y,z,w=q;vx,vy,vz=v
    tx=2*(y*vz-z*vy);ty=2*(z*vx-x*vz);tz=2*(x*vy-y*vx)
    return [vx+w*tx+y*tz-z*ty,vy+w*ty+z*tx-x*tz,vz+w*tz+x*ty-y*tx]
def qmat(q):
    x,y,z,w=unit(q);xx=x*x;yy=y*y;zz=z*z;xy=x*y;xz=x*z;yz=y*z;wx=w*x;wy=w*y;wz=w*z
    return [[1-2*(yy+zz),2*(xy-wz),2*(xz+wy)],
            [2*(xy+wz),1-2*(xx+zz),2*(yz-wx)],
            [2*(xz-wy),2*(yz+wx),1-2*(xx+yy)]]
def inv_bind(q,t):
    R=qmat(q); Rt=[[R[j][i] for j in range(3)] for i in range(3)]
    it=[-sum(Rt[i][j]*t[j] for j in range(3)) for i in range(3)]
    return [Rt[0][0],Rt[1][0],Rt[2][0],0, Rt[0][1],Rt[1][1],Rt[2][1],0,
            Rt[0][2],Rt[1][2],Rt[2][2],0, it[0],it[1],it[2],1]

class Buf:
    def __init__(self): self.data=bytearray();self.views=[];self.acc=[]
    def align(self):
        while len(self.data)%4:self.data.append(0)
    def raw(self,b,component,count,typ,name,minv=None,maxv=None,target=None):
        self.align(); off=len(self.data); self.data.extend(b); vi=len(self.views)
        view={"buffer":0,"byteOffset":off,"byteLength":len(b),"name":name}
        if target is not None: view["target"]=target
        self.views.append(view)
        a={"bufferView":vi,"componentType":component,"count":count,"type":typ,"name":name}
        if minv is not None:a["min"]=minv
        if maxv is not None:a["max"]=maxv
        ai=len(self.acc);self.acc.append(a);return ai
    def f32(self,rows,typ,name,target=None):
        comps={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}[typ]
        if typ=="SCALAR":
            vals=[float(x) for x in rows]; count=len(vals)
        else:
            if any(len(r)!=comps for r in rows): raise ExportError(f"{name} malformed")
            vals=[float(x) for r in rows for x in r];count=len(rows)
        if not all(math.isfinite(x) for x in vals): raise ExportError(f"{name} nonfinite")
        minv=maxv=None
        if typ=="SCALAR" and vals:minv=[min(vals)];maxv=[max(vals)]
        elif typ=="VEC3" and rows:
            minv=[min(float(r[k]) for r in rows) for k in range(3)]
            maxv=[max(float(r[k]) for r in rows) for k in range(3)]
        return self.raw(struct.pack("<"+"f"*len(vals),*vals),5126,count,typ,name,minv,maxv,target)
    def u16(self,rows,typ,name,target=None):
        comps={"SCALAR":1,"VEC4":4}[typ]
        if typ=="SCALAR":vals=[int(x) for x in rows];count=len(vals)
        else:
            vals=[int(x) for r in rows for x in r];count=len(rows)
            if any(len(r)!=comps for r in rows):raise ExportError(f"{name} malformed")
        if any(x<0 or x>65535 for x in vals):raise ExportError(f"{name} u16 overflow")
        minv=maxv=None
        if typ=="SCALAR" and vals:minv=[min(vals)];maxv=[max(vals)]
        return self.raw(struct.pack("<"+"H"*len(vals),*vals),5123,count,typ,name,minv,maxv,target)

def canonical_material(name):
    return name[1:] if isinstance(name,str) and name.startswith(",") else name

def build(mesh,skel,proof,anims,lod=0):
    bones=skel["skeleton"]["bones"]
    if mesh["identity"]["name"]!=skel["identity"]["name"]:raise ExportError("identity mismatch")
    by_name={b["name"]:b for b in bones}
    if len(by_name)!=len(bones):raise ExportError("duplicate bones")
    max_q=max_t=0.0
    for b in bones:
        p=b.get("parentIndex"); lq=unit(b["localRotation"]);lt=[float(x) for x in b["localTranslation"]]
        if p is None:pq=[0,0,0,1];pt=[0,0,0]
        else:pq=unit(bones[int(p)]["globalBaseMat"]["quat"]);pt=bones[int(p)]["globalBaseMat"]["trans"]
        cq=qmul(pq,lq);rv=qrot(pq,lt);ct=[pt[i]+rv[i] for i in range(3)]
        gq=unit(b["globalBaseMat"]["quat"]);gt=b["globalBaseMat"]["trans"]
        qe=min(max(abs(cq[i]-gq[i]) for i in range(4)),max(abs(cq[i]+gq[i]) for i in range(4)))
        te=max(abs(ct[i]-gt[i]) for i in range(3))
        max_q=max(max_q,qe);max_t=max(max_t,te)
    if max_q>2e-4 or max_t>2e-3:raise ExportError(f"hierarchy mismatch {max_q} {max_t}")
    buf=Buf();nodes=[];roots=[];children={}
    for b in bones:
        i=int(b["index"]); p=b.get("parentIndex")
        nodes.append({"name":b["name"],"translation":[float(x) for x in b["localTranslation"]],
                      "rotation":unit(b["localRotation"]),
                      "extras":{"t6BoneIndex":i,"scriptStringId":b.get("scriptStringId"),
                                "partClassificationRaw":b.get("partClassificationRaw")}})
        if p is None:roots.append(i)
        else:children.setdefault(int(p),[]).append(i)
    for p,ch in children.items():nodes[p]["children"]=ch
    if len(roots)!=1:raise ExportError(f"expected one root, got {roots}")
    delta_node=len(nodes)
    nodes.append({"name":"__T6_DELTA_ROOT__","translation":[0,0,0],"rotation":[0,0,0,1],
                  "children":list(roots),"extras":{"t6DeltaRoot":True}})
    surface_rows=proof.get("targetAssignments")
    if not isinstance(surface_rows,list):
        body=proof.get("bodyMaterials") or {};surface_rows=body.get("surfaceAssignments")
    if not isinstance(surface_rows,list) and isinstance(proof.get("surfaceMaterialSequence"),list):
        surface_rows=[{"surfaceIndex":i,"materialName":n,"evidence":"exact-retail-material-handle-proof-sequence"} for i,n in enumerate(proof["surfaceMaterialSequence"])]
    if not isinstance(surface_rows,list):raise ExportError("surface material proof has no assignments")
    assigns={int(r["surfaceIndex"]):r for r in surface_rows}
    lodrow=next((x for x in mesh["xmodel"]["lods"] if int(x["index"])==int(lod)),None)
    if lodrow is None:raise ExportError(f"LOD{lod} unavailable")
    surf_start=int(lodrow["surfIndex"]);surf_end=surf_start+int(lodrow["numSurfs"])
    selected_indices=list(range(surf_start,surf_end))
    if any(si not in assigns for si in selected_indices):raise ExportError("selected LOD has unresolved material handle")
    unique=[]; mat_index={}
    for si in selected_indices:
        raw=assigns[si]["materialName"];can=canonical_material(raw)
        if can not in mat_index:
            mat_index[can]=len(unique)
            unique.append({"name":can,"pbrMetallicRoughness":{"baseColorFactor":[1,1,1,1],"metallicFactor":0.0,"roughnessFactor":1.0},
                           "extras":{"T6":{"rawMaterialHandleName":raw,"materialPixelsClosed":False}}})
    prim=[];total_v=total_t=0
    for si in selected_indices:
        s=mesh["surfaces"][si]
        pos=[[float(x) for x in v["position"]] for v in s["vertices"]];norm=[]
        for v in s["vertices"]:
            n=[float(x) for x in v["normal"]];nn=math.sqrt(sum(x*x for x in n))
            if nn<=0:raise ExportError("zero normal")
            norm.append([x/nn for x in n])
        uv=[[float(x) for x in v["texcoord0"]] for v in s["vertices"]];col=[[float(x) for x in v["colorRGBA"]] for v in s["vertices"]]
        joints=[[int(x) for x in r] for r in s["joints0"]];weights=[[float(x) for x in r] for r in s["weights0"]]
        for jr,wr in zip(joints,weights):
            if any(j>=len(bones) for j in jr):raise ExportError("joint range")
            if abs(sum(wr)-1)>2e-5:raise ExportError(f"weights {wr}")
        idx=[int(x) for tri in s["triangles"] for x in tri]
        if any(i<0 or i>=len(pos) for i in idx):raise ExportError("index range")
        attrs={"POSITION":buf.f32(pos,"VEC3",f"surf{si}:POSITION",34962),"NORMAL":buf.f32(norm,"VEC3",f"surf{si}:NORMAL",34962),"TEXCOORD_0":buf.f32(uv,"VEC2",f"surf{si}:TEXCOORD_0",34962),"COLOR_0":buf.f32(col,"VEC4",f"surf{si}:COLOR_0",34962),"JOINTS_0":buf.u16(joints,"VEC4",f"surf{si}:JOINTS_0",34962),"WEIGHTS_0":buf.f32(weights,"VEC4",f"surf{si}:WEIGHTS_0",34962)}
        ia=buf.u16(idx,"SCALAR",f"surf{si}:INDICES",34963);can=canonical_material(assigns[si]["materialName"])
        prim.append({"attributes":attrs,"indices":ia,"material":mat_index[can],"mode":4,"extras":{"T6":{"surfaceIndex":si,"rawMaterialHandleName":assigns[si]["materialName"],"materialEvidence":assigns[si]["evidence"]}}})
        total_v+=len(pos);total_t+=len(idx)//3
    meshes=[{"name":mesh["identity"]["name"]+f"_lod{lod}","primitives":prim,"extras":{"T6":{"lod":lod}}}]
    ibms=[inv_bind(b["globalBaseMat"]["quat"],b["globalBaseMat"]["trans"]) for b in bones];ibm_acc=buf.f32(ibms,"MAT4","skin:inverseBindMatrices")
    skin={"joints":list(range(len(bones))),"inverseBindMatrices":ibm_acc,"skeleton":roots[0],"name":mesh["identity"]["name"]+"_skin"}
    mesh_node=len(nodes);nodes.append({"name":mesh["identity"]["name"]+"_mesh","mesh":0,"skin":0,"extras":{"T6":{"lod":lod}}});nodes[delta_node]["children"].append(mesh_node)
    world_node=len(nodes);nodes.append({"name":"__T6_WORLD_TO_GLTF__","rotation":WORLD_Q,"scale":[T6_UNIT_TO_METERS]*3,"children":[delta_node],"extras":{"T6":{"axisConversion":"rotate -90deg X: T6 Z-up -> glTF Y-up","unitToMeters":T6_UNIT_TO_METERS}}})
    animations=[];binding_stats={};skel_sha=(skel.get("source") or {}).get("expandedSha256")
    for a in anims:
        fps=float(a["header"]["framerate"]); xsha=a.get("expandedSha256");same_table=bool(skel_sha and xsha and skel_sha.lower()==xsha.lower());bound=[];unbound=[];numeric_mismatch=[]
        for tr in a["boneTracks"]:
            name=tr["name"];bone=by_name.get(name)
            if bone is None:unbound.append({"name":name,"scriptString":tr.get("scriptString")});continue
            ts=tr.get("scriptString");bs=bone.get("scriptStringId")
            if ts is not None and bs is not None and int(ts)!=int(bs):
                if same_table:raise ExportError(f"{a['name']} same-table ScriptString mismatch {name}")
                if len(numeric_mismatch)<16:numeric_mismatch.append({"name":name,"xanim":int(ts),"xmodel":int(bs)})
            bound.append(tr)
        if not bound:raise ExportError(f"{a['name']} zero intersection")
        samplers=[];channels=[]
        def add(path,node,inds,vals,typ,extras):
            if any(b<=aa for aa,b in zip(inds,inds[1:])):raise ExportError(f"{a['name']} indices not increasing")
            times=[i/fps for i in inds];ia=buf.f32(times,"SCALAR",f"{a['name']}:{extras['trackName']}:{path}:time");oa=buf.f32(vals,typ,f"{a['name']}:{extras['trackName']}:{path}:value");si=len(samplers);samplers.append({"input":ia,"output":oa,"interpolation":"LINEAR"});channels.append({"sampler":si,"target":{"node":node,"path":path},"extras":extras})
        for tr in bound:
            bone=by_name[tr["name"]];bi=int(bone["index"]);qr=expand_quat(tr.get("quat") or {})
            if qr:add("rotation",bi,qr[0],qr[1],"VEC4",{"trackName":tr["name"],"t6TrackType":qr[2]})
            tt=translation(tr,bone)
            if tt:add("translation",bi,tt[0],tt[1],"VEC3",{"trackName":tr["name"],"t6TrackType":tt[2],"t6Composition":tt[3]})
        d=a.get("delta") or {};dt=d.get("trans")
        if dt:
            if dt.get("mode")=="dynamic":
                inds=[int(x) for x in dt["indices"]]
                if inds[0]!=0 or inds[-1]!=int(a["header"]["numframes"]):raise ExportError(f"{a['name']} delta domain {inds}")
                vals=[[float(x) for x in r] for r in dt["decodedFrames"]]
            elif dt.get("mode")=="constant":
                inds=[0,int(a["header"]["numframes"])] if int(a["header"]["numframes"]) else [0];vals=[list(map(float,dt["value"])) for _ in inds]
            else:raise ExportError("bad delta trans mode")
            add("translation",delta_node,inds,vals,"VEC3",{"trackName":"__T6_DELTA_ROOT__","t6DeltaType":"translation","t6NativeDomainValidated":True})
        if d.get("quat2") or d.get("quat"):raise ExportError(f"{a['name']} delta quaternion requires v7 cubic path")
        duration=int(a["header"]["numframes"])/fps;stats={"originalTrackCount":len(a["boneTracks"]),"boundTrackCount":len(bound),"unboundTrackCount":len(unbound),"unboundTracks":unbound,"sameSerializedScriptStringTable":same_table,"numericIdComparison":"enforced" if same_table else "not-comparable-cross-zone","crossZoneNumericIdMismatchCount":sum(1 for tr in bound if tr.get("scriptString") is not None and by_name[tr["name"]].get("scriptStringId") is not None and int(tr["scriptString"])!=int(by_name[tr["name"]]["scriptStringId"])),"crossZoneNumericIdMismatchSamples":numeric_mismatch,"noFabricatedBones":True,"noTrackNameAliases":True};binding_stats[a["name"]]=stats
        animations.append({"name":a["name"],"samplers":samplers,"channels":channels,"extras":{"T6":{"assetFixedStart":a["assetFixedStart"],"assetSerializedEnd":a["assetSerializedEnd"],"assetSerializedSha256":a["assetSerializedSha256"],"numframes":a["header"]["numframes"],"framerate":fps,"durationSeconds":duration,"looped":bool(a["header"]["bLoop"]),"notifies":a.get("notifies",[]),"runtimeTrackBinding":stats}}})
    doc={"asset":{"version":"2.0","generator":"bo2-t6-assets t6_xanim_skinned_gltf_multianim_export_v1.py"},"scene":0,"scenes":[{"name":mesh["identity"]["name"]+" multi-animation export","nodes":[world_node]}],"nodes":nodes,"meshes":meshes,"skins":[skin],"materials":unique,"animations":animations,"bufferViews":buf.views,"accessors":buf.acc,"buffers":[{"byteLength":len(buf.data)}],"extras":{"T6":{"xmodelName":mesh["identity"]["name"],"lod":lod,"factionExpandedSha256":skel_sha,"commonMpExpandedSha256":anims[0].get("expandedSha256"),"vertices":total_v,"triangles":total_t,"joints":len(bones),"materialPixelsClosed":False,"animationCount":len(anims),"runtimeTrackBinding":binding_stats,"bindHierarchyValidation":{"maxQuaternionCompositionError":max_q,"maxTranslationCompositionError":max_t},"coordinateSystem":"native T6 under -90deg X + 0.0254 wrapper"}}}
    return doc,bytes(buf.data)

def write_glb(doc,bin_data,path):
    j=json.dumps(doc,separators=(",",":"),ensure_ascii=False).encode("utf-8");j+=b" " *((4-len(j)%4)%4);b=bin_data+b"\0"*((4-len(bin_data)%4)%4);total=12+8+len(j)+8+len(b);out=bytearray(struct.pack("<4sII",b"glTF",2,total));out+=struct.pack("<I4s",len(j),b"JSON")+j;out+=struct.pack("<I4s",len(b),b"BIN\0")+b;Path(path).write_bytes(out);return hashlib.sha256(out).hexdigest(),len(out)

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("mesh_json",type=Path);ap.add_argument("skeleton_json",type=Path);ap.add_argument("surface_proof",type=Path);ap.add_argument("output_glb",type=Path);ap.add_argument("--xanim",type=Path,action="append",required=True);ap.add_argument("--lod",type=int,default=0);ap.add_argument("--manifest",type=Path)
    a=ap.parse_args();mesh=json.loads(a.mesh_json.read_text());skel=json.loads(a.skeleton_json.read_text());proof=json.loads(a.surface_proof.read_text());anims=[json.loads(p.read_text()) for p in a.xanim]
    if len({x.get("name") for x in anims})!=len(anims):raise ExportError("duplicate or unnamed XAnim inputs")
    doc,b=build(mesh,skel,proof,anims,a.lod);sha,n=write_glb(doc,b,a.output_glb);out={"format":"t6-xanim-skinned-gltf-multianim-export-v1","outputGlb":{"path":str(a.output_glb),"sha256":sha,"bytes":n},"xmodelName":mesh["identity"]["name"],"lod":a.lod,"vertices":doc["extras"]["T6"]["vertices"],"triangles":doc["extras"]["T6"]["triangles"],"joints":doc["extras"]["T6"]["joints"],"materials":[m["name"] for m in doc["materials"]],"animations":[{"name":x["name"],"channels":len(x["channels"]),"runtimeTrackBinding":x["extras"]["T6"]["runtimeTrackBinding"]} for x in doc["animations"]],"validation":{"bindHierarchy":doc["extras"]["T6"]["bindHierarchyValidation"],"noFabricatedBones":all(x["extras"]["T6"]["runtimeTrackBinding"]["noFabricatedBones"] for x in doc["animations"]),"noTrackNameAliases":all(x["extras"]["T6"]["runtimeTrackBinding"]["noTrackNameAliases"] for x in doc["animations"])}}
    if a.manifest:a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"glb":str(a.output_glb),"sha256":sha,"bytes":n,"vertices":out["vertices"],"triangles":out["triangles"],"joints":out["joints"],"materials":len(out["materials"]),"animations":len(out["animations"])},indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
