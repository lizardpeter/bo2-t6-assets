#!/usr/bin/env python3
"""Transitive cross-map alias proof for packed special shader objects/vertex decls.

Builds an undirected equivalence graph from exact retained pass keys:
  (TechniqueSet, slot, passIndex, worldVertFormat, child-kind).
Each occurrence contributes exactly one node: either a physically direct payload
SHA or an exact map/block/offset/raw packed pointer identity. All nodes observed
under the same exact key are unioned. A component resolves only when it contains
exactly one direct SHA; components with >1 direct SHA fail closed as conflicts,
and components with no direct SHA remain unresolved.

This is the validated reflection packed-alias relation generalized to the seven
retained special families. No adjacency or pointer arithmetic is admitted.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path

FORMAT="t6-retail-special-packed-child-alias-v2"
def loadmod(p:Path,n:str):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def jd(x)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def key(ts,slot,pi,fmt,kind):return (ts,int(slot),int(pi),int(fmt),kind)
def ptrnode(kind,mapname,ch):return ("ptr",kind,mapname,int(ch["block"]),int(ch["offset"]),str(ch["raw"]))
def shanode(kind,sha):return ("sha",kind,sha)

class DSU:
    def __init__(self):self.p={};self.rank={}
    def add(self,x):
        if x not in self.p:self.p[x]=x;self.rank[x]=0
    def find(self,x):
        self.add(x)
        if self.p[x]!=x:self.p[x]=self.find(self.p[x])
        return self.p[x]
    def union(self,a,b):
        a=self.find(a);b=self.find(b)
        if a==b:return
        if self.rank[a]<self.rank[b]:a,b=b,a
        self.p[b]=a
        if self.rank[a]==self.rank[b]:self.rank[a]+=1

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--family-manifest",type=Path,default=Path("manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json"))
    ap.add_argument("--parser",type=Path,default=Path("tools/t6_retail_special_shader_payload_census_v1.py"))
    ap.add_argument("--helper",type=Path,default=Path("tools/t6_retail_world_helper_compat_v1.py"))
    ap.add_argument("--v1",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_PACKED_CHILD_ALIAS_V1.json"))
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    parser=loadmod(a.parser,"parser");helper=loadmod(a.helper,"helper")
    famdoc=json.loads(a.family_manifest.read_text());families={x["techniqueSet"]:x["family"] for x in famdoc["specialTechniqueSets"]}
    v1=json.loads(a.v1.read_text())
    if v1.get("format")!="t6-retail-special-packed-child-alias-v1":raise SystemExit("v1 format drift")

    by_key=collections.defaultdict(set);ptr_uses=collections.defaultdict(list);direct_occ=collections.Counter();packed_occ=collections.Counter()

    for mapname,cfg in parser.MAPS.items():
        data=(a.root/cfg["rel"]).read_bytes();got=h(data)
        if got!=cfg["sha"]:raise SystemExit(f"{mapname}: expanded SHA drift {got}")
        blocks=helper.parse_front(data)["blockSizes"]
        rs=helper.scan_techsets(data,blocks,before=cfg["world"])[-(cfg["q1"]-cfg["q0"]+1):]
        if len(rs)!=cfg["q1"]-cfg["q0"]+1:raise SystemExit(f"{mapname}: TechniqueSet count drift")
        for i,r in enumerate(rs):r["xassetIndex"]=cfg["q0"]+i
        parsed=[]
        for i,r in enumerate(rs):
            nxt=rs[i+1]["fixedStart"] if i+1<len(rs) else cfg["world"]
            parsed.append(parser.parse_techset(data,r,nxt,blocks,helper))

        # Shader child nodes from authoritative parser.
        for ts in parsed:
            fam=families.get(ts["name"])
            if fam is None:continue
            for tr in ts["techniqueRefs"]:
                it=tr.get("inlineTechnique")
                if not it:continue
                for pa in it["passes"]:
                    for fld,kind in (("vertexShader","vs"),("pixelShader","ps")):
                        k=key(ts["name"],tr["slot"],pa["passIndex"],ts["worldVertFormat"],kind)
                        ch=pa["children"][fld]
                        if ch["kind"]=="packed":
                            n=ptrnode(kind,mapname,ch);packed_occ[kind]+=1;ptr_uses[n].append({"key":k,"family":fam});by_key[k].add(n)
                        else:
                            sh=ch.get("inline")
                            if sh and sh["program"].get("direct"):
                                n=shanode(kind,sh["program"]["sha256"]);direct_occ[kind]+=1;by_key[k].add(n)

        # Replay inline child stream only to expose direct 116-byte VD identities.
        for ts in parsed:
            fam=families.get(ts["name"])
            if fam is None:continue
            for tr in ts["techniqueRefs"]:
                it=tr.get("inlineTechnique")
                if not it:continue
                p=it["fixedStart"]+8+24*it["passCount"]
                for pa in it["passes"]:
                    for fld,ck in (("vertexShader","vs"),("vertexDecl","vd"),("pixelShader","ps"),("args","args")):
                        ch=pa["children"][fld]
                        k=key(ts["name"],tr["slot"],pa["passIndex"],ts["worldVertFormat"],ck)
                        if ch["kind"]=="packed":
                            if ck=="vd":
                                n=ptrnode("vd",mapname,ch);packed_occ["vd"]+=1;ptr_uses[n].append({"key":k,"family":fam});by_key[k].add(n)
                            continue
                        if ch["kind"] not in ("following","insert"):continue
                        if ck in ("vs","ps"):
                            p,_=parser.parse_shader(data,p,blocks,helper,ck)
                        elif ck=="vd":
                            blob=data[p:p+116]
                            if len(blob)!=116 or any(struct.unpack_from("<20I",blob,36)):raise SystemExit(f"{mapname}/{ts['name']}: VD drift at {p}")
                            n=shanode("vd",h(blob));direct_occ["vd"]+=1;by_key[k].add(n);p+=116
                        else:
                            p=parser.parse_args(data,p,pa["argCount"],blocks,helper)
                nk=parser.kind(struct.unpack_from("<I",data,it["fixedStart"])[0],blocks,helper)
                if nk in ("following","insert"):_,p=parser.cstr(data,p)

    expected={"vs":419,"ps":260,"vd":459}
    got={k:packed_occ[k] for k in expected}
    if got!=expected:raise SystemExit(f"packed denominator drift {got}")
    if len(ptr_uses)!=129:raise SystemExit(f"pointer identity denominator {len(ptr_uses)} != 129")

    dsu=DSU()
    for k,nodes in by_key.items():
        q=sorted(nodes,key=repr)
        if not q:continue
        for n in q:dsu.add(n)
        for n in q[1:]:dsu.union(q[0],n)

    comps=collections.defaultdict(set)
    for n in dsu.p:comps[dsu.find(n)].add(n)
    comp_sha={};conflicts=[]
    for root,nodes in comps.items():
        shas=sorted({n[2] for n in nodes if n[0]=="sha"})
        if len(shas)==1:comp_sha[root]=shas[0]
        elif len(shas)>1:
            conflicts.append({"directSha256":shas,"nodeCount":len(nodes),"nodes":[list(n) for n in sorted(nodes,key=repr)]})
    # Direct conflicts are evidence, not auto-promoted. For exactness, a pointer in a
    # conflicting component remains unresolved.
    rows=[];resolved={};reasons=collections.Counter();kindc=collections.defaultdict(collections.Counter)
    for n,uses in sorted(ptr_uses.items(),key=lambda kv:repr(kv[0])):
        root=dsu.find(n);nodes=comps[root];shas=sorted({q[2] for q in nodes if q[0]=="sha"})
        if len(shas)==1:
            status="resolved-transitive-cross-map-key";rs=shas[0];resolved[n]=rs
        elif len(shas)>1:
            status="component-direct-sha-conflict";rs=None;reasons[status]+=1
        else:
            status="component-no-direct-anchor";rs=None;reasons[status]+=1
        r={"pointer":{"kind":n[1],"map":n[2],"block":n[3],"offset":n[4],"raw":n[5]},
           "occurrenceCount":len(uses),"status":status,"resolvedSha256":rs,
           "componentNodeCount":len(nodes),"componentDirectSha256":shas,
           "useKeys":[list(u["key"]) for u in uses]}
        rows.append(r);kc=kindc[n[1]];kc["pointerIdentities"]+=1;kc["occurrences"]+=len(uses)
        if rs:kc["resolvedPointerIdentities"]+=1;kc["resolvedOccurrences"]+=len(uses)
        else:kc["unresolvedPointerIdentities"]+=1;kc["unresolvedOccurrences"]+=len(uses)

    res_occ=sum(r["occurrenceCount"] for r in rows if r["resolvedSha256"])
    summary={
      "packedChildOccurrenceCount":sum(packed_occ.values()),"packedChildPointerIdentityCount":len(rows),
      "resolvedPointerIdentityCount":len(resolved),"unresolvedPointerIdentityCount":len(rows)-len(resolved),
      "resolvedOccurrenceCount":res_occ,"unresolvedOccurrenceCount":sum(packed_occ.values())-res_occ,
      "structuralKeyCount":len(by_key),"equivalenceComponentCount":len(comps),
      "componentsWithOneDirectShaCount":sum(len({n[2] for n in nodes if n[0]=="sha"})==1 for nodes in comps.values()),
      "componentsWithNoDirectShaCount":sum(not {n[2] for n in nodes if n[0]=="sha"} for nodes in comps.values()),
      "componentsWithMultipleDirectShaCount":len(conflicts),
      "kindCounts":{k:dict(v) for k,v in sorted(kindc.items())},
      "unresolvedReasonCounts":dict(sorted(reasons.items())),
      "v1ResolvedPointerIdentityCount":int(v1["summary"]["resolvedPointerIdentityCount"]),
      "newlyResolvedPointerIdentityCountBeyondV1":len(resolved)-int(v1["summary"]["resolvedPointerIdentityCount"]),
    }
    doc={
      "format":FORMAT,
      "sources":{"v1":str(a.v1),"familyManifest":str(a.family_manifest),"parser":str(a.parser),"helper":str(a.helper),
        "expandedWorlds":{m:{"file":cfg["rel"],"sha256":cfg["sha"]} for m,cfg in parser.MAPS.items()}},
      "relation":{"equivalenceKey":["TechniqueSet","slot","passIndex","worldVertFormat","child-kind"],
        "componentPromotion":"exactly one physically direct payload SHA anywhere in the connected component"},
      "summary":summary,"conflictingComponents":conflicts,"pointerAliases":rows,
      "resolvedAliasSetSha256":jd(sorted((list(k),v) for k,v in resolved.items())),
      "proofBoundary":"Transitive cross-map structural alias proof only. Nodes are connected exclusively by equality of exact retained pass keys. A packed child is promoted only when its complete equivalence component contains exactly one physically direct byte SHA. Components with zero or multiple direct SHAs remain unresolved. No pointer-offset dereference, adjacency, introduction sequence, naming similarity, family similarity, first-match behavior, or visual/translated resemblance is used."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
