#!/usr/bin/env python3
"""Expand special packed child alias anchors to all exact world TechniqueSets.

Target denominator remains the exact 129 packed child pointer identities / 1,138
special-family occurrences from alias-v2. The graph, however, is built from every
TechniqueSet in each source-closed world TechniqueSet XAsset block. If a special
packed child is reused by a non-special TechniqueSet, that exact pointer identity
can therefore connect to a physically direct byte SHA through the same pass-key
relation.

No new target is admitted and no cross-name similarity is used.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path

FORMAT="t6-retail-special-packed-child-alias-v3"
def loadmod(p:Path,n:str):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def jd(x)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def key(ts,slot,pi,fmt,kind):return (ts,int(slot),int(pi),int(fmt),kind)
def ptrnode(kind,mapname,ch):return ("ptr",kind,mapname,int(ch["block"]),int(ch["offset"]),str(ch["raw"]))
def shanode(kind,sha):return ("sha",kind,sha)

class DSU:
    def __init__(self):self.p={};self.r={}
    def add(self,x):
        if x not in self.p:self.p[x]=x;self.r[x]=0
    def find(self,x):
        self.add(x)
        if self.p[x]!=x:self.p[x]=self.find(self.p[x])
        return self.p[x]
    def union(self,a,b):
        a=self.find(a);b=self.find(b)
        if a==b:return
        if self.r[a]<self.r[b]:a,b=b,a
        self.p[b]=a
        if self.r[a]==self.r[b]:self.r[a]+=1

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--v2",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_PACKED_CHILD_ALIAS_V2.json"))
    ap.add_argument("--parser",type=Path,default=Path("tools/t6_retail_special_shader_payload_census_v1.py"))
    ap.add_argument("--helper",type=Path,default=Path("tools/t6_retail_world_helper_compat_v1.py"))
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    parser=loadmod(a.parser,"parser");helper=loadmod(a.helper,"helper")
    v2=json.loads(a.v2.read_text())
    if v2.get("format")!="t6-retail-special-packed-child-alias-v2":raise SystemExit("v2 format drift")

    targets=set()
    target_special_occ={}
    for r in v2["pointerAliases"]:
        q=r["pointer"];n=("ptr",q["kind"],q["map"],int(q["block"]),int(q["offset"]),str(q["raw"]))
        targets.add(n);target_special_occ[n]=int(r["occurrenceCount"])
    if len(targets)!=129 or sum(target_special_occ.values())!=1138:raise SystemExit("v2 target denominator drift")

    by_key=collections.defaultdict(set);ptr_uses=collections.defaultdict(list)
    direct_occ=collections.Counter();world_ts_counts={}

    for mapname,cfg in parser.MAPS.items():
        data=(a.root/cfg["rel"]).read_bytes();got=h(data)
        if got!=cfg["sha"]:raise SystemExit(f"{mapname}: expanded SHA drift {got}")
        blocks=helper.parse_front(data)["blockSizes"]
        rs=helper.scan_techsets(data,blocks,before=cfg["world"])[-(cfg["q1"]-cfg["q0"]+1):]
        expected=cfg["q1"]-cfg["q0"]+1
        if len(rs)!=expected:raise SystemExit(f"{mapname}: TechniqueSet count {len(rs)} != {expected}")
        world_ts_counts[mapname]=len(rs)
        for i,r in enumerate(rs):r["xassetIndex"]=cfg["q0"]+i
        parsed=[]
        for i,r in enumerate(rs):
            nxt=rs[i+1]["fixedStart"] if i+1<len(rs) else cfg["world"]
            parsed.append(parser.parse_techset(data,r,nxt,blocks,helper))

        for ts in parsed:
            for tr in ts["techniqueRefs"]:
                it=tr.get("inlineTechnique")
                if not it:continue
                for pa in it["passes"]:
                    for fld,kind in (("vertexShader","vs"),("pixelShader","ps")):
                        k=key(ts["name"],tr["slot"],pa["passIndex"],ts["worldVertFormat"],kind)
                        ch=pa["children"][fld]
                        if ch["kind"]=="packed":
                            n=ptrnode(kind,mapname,ch);by_key[k].add(n)
                            ptr_uses[n].append(k)
                        else:
                            sh=ch.get("inline")
                            if sh and sh["program"].get("direct"):
                                n=shanode(kind,sh["program"]["sha256"]);by_key[k].add(n);direct_occ[kind]+=1

        # Exact VD identities for every inline world TechniqueSet.
        for ts in parsed:
            for tr in ts["techniqueRefs"]:
                it=tr.get("inlineTechnique")
                if not it:continue
                p=it["fixedStart"]+8+24*it["passCount"]
                for pa in it["passes"]:
                    for fld,ck in (("vertexShader","vs"),("vertexDecl","vd"),("pixelShader","ps"),("args","args")):
                        ch=pa["children"][fld];k=key(ts["name"],tr["slot"],pa["passIndex"],ts["worldVertFormat"],ck)
                        if ch["kind"]=="packed":
                            if ck=="vd":
                                n=ptrnode("vd",mapname,ch);by_key[k].add(n);ptr_uses[n].append(k)
                            continue
                        if ch["kind"] not in ("following","insert"):continue
                        if ck in ("vs","ps"):p,_=parser.parse_shader(data,p,blocks,helper,ck)
                        elif ck=="vd":
                            blob=data[p:p+116]
                            if len(blob)!=116 or any(struct.unpack_from("<20I",blob,36)):raise SystemExit(f"{mapname}/{ts['name']}: VD drift at {p}")
                            by_key[k].add(shanode("vd",h(blob)));direct_occ["vd"]+=1;p+=116
                        else:p=parser.parse_args(data,p,pa["argCount"],blocks,helper)
                nk=parser.kind(struct.unpack_from("<I",data,it["fixedStart"])[0],blocks,helper)
                if nk in ("following","insert"):_,p=parser.cstr(data,p)

    dsu=DSU()
    for k,nodes in by_key.items():
        q=sorted(nodes,key=repr)
        for n in q:dsu.add(n)
        for n in q[1:]:dsu.union(q[0],n)
    comps=collections.defaultdict(set)
    for n in dsu.p:comps[dsu.find(n)].add(n)

    rows=[];resolved={};reason=collections.Counter();kindc=collections.defaultdict(collections.Counter);conflicts=[]
    for n in sorted(targets,key=repr):
        if n not in dsu.p:
            shas=[];nodes={n};status="target-absent-from-expanded-anchor-graph";rs=None;reason[status]+=1
        else:
            nodes=comps[dsu.find(n)];shas=sorted({x[2] for x in nodes if x[0]=="sha"})
            if len(shas)==1:
                status="resolved-all-world-techniqueset-anchor";rs=shas[0];resolved[n]=rs
            elif len(shas)>1:
                status="component-direct-sha-conflict";rs=None;reason[status]+=1
                conflicts.append({"pointer":list(n),"directSha256":shas,"componentNodeCount":len(nodes)})
            else:
                status="component-no-direct-anchor";rs=None;reason[status]+=1
        occ=target_special_occ[n];kc=kindc[n[1]]
        kc["pointerIdentities"]+=1;kc["specialOccurrences"]+=occ
        if rs:kc["resolvedPointerIdentities"]+=1;kc["resolvedSpecialOccurrences"]+=occ
        else:kc["unresolvedPointerIdentities"]+=1;kc["unresolvedSpecialOccurrences"]+=occ
        rows.append({"pointer":{"kind":n[1],"map":n[2],"block":n[3],"offset":n[4],"raw":n[5]},
          "specialOccurrenceCount":occ,"allWorldUseCount":len(ptr_uses.get(n,[])),
          "status":status,"resolvedSha256":rs,"componentNodeCount":len(nodes),
          "componentDirectSha256":shas})

    res_occ=sum(r["specialOccurrenceCount"] for r in rows if r["resolvedSha256"])
    v2res=int(v2["summary"]["resolvedPointerIdentityCount"])
    summary={
      "worldTechniqueSetCounts":world_ts_counts,"worldTechniqueSetCount":sum(world_ts_counts.values()),
      "specialTargetPointerIdentityCount":len(rows),"specialTargetOccurrenceCount":sum(target_special_occ.values()),
      "resolvedPointerIdentityCount":len(resolved),"unresolvedPointerIdentityCount":len(rows)-len(resolved),
      "resolvedSpecialOccurrenceCount":res_occ,"unresolvedSpecialOccurrenceCount":1138-res_occ,
      "v2ResolvedPointerIdentityCount":v2res,"newlyResolvedPointerIdentityCountBeyondV2":len(resolved)-v2res,
      "allWorldStructuralKeyCount":len(by_key),"allWorldGraphPointerIdentityCount":len(ptr_uses),
      "allWorldDirectOccurrenceCounts":dict(sorted(direct_occ.items())),
      "kindCounts":{k:dict(v) for k,v in sorted(kindc.items())},
      "conflictCount":len(conflicts),"unresolvedReasonCounts":dict(sorted(reason.items())),
    }
    doc={"format":FORMAT,
      "sources":{"v2":str(a.v2),"parser":str(a.parser),"helper":str(a.helper),
        "expandedWorlds":{m:{"file":cfg["rel"],"sha256":cfg["sha"],"techniqueSetAssetRange":[cfg["q0"],cfg["q1"]]} for m,cfg in parser.MAPS.items()}},
      "targetPolicy":"exact v2 special packed child pointer identities only; non-special TechniqueSets are anchors, never added targets",
      "relation":{"equivalenceKey":["TechniqueSet","slot","passIndex","worldVertFormat","child-kind"],
        "promotion":"one direct byte SHA in full exact world-TechniqueSet equivalence component"},
      "summary":summary,"conflicts":conflicts,"pointerAliases":rows,
      "resolvedAliasSetSha256":jd(sorted((list(k),v) for k,v in resolved.items())),
      "proofBoundary":"Anchor-universe expansion only. The target denominator is frozen to the exact 129 special packed child identities / 1,138 special occurrences from alias-v2. All additional nodes come from structurally closed TechniqueSets in the same five exact world XAsset ranges. A target resolves only through exact pass-key connectivity to one physical direct byte SHA. Non-special names do not match special names; they help only when an exact packed pointer identity is reused across keys. Conflicting/no-anchor components remain unresolved. No adjacency, pointer arithmetic, introduction order, family similarity, or visual behavior is used."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
