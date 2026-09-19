#!/usr/bin/env python3
"""Fail-closed cross-map alias proof for retained special packed Techniques.

A direct inline Technique becomes an eligible anchor only when its complete
serialized semantic graph can be normalized without unresolved child ownership:
- exact technique name/flags/passCount;
- per-pass fixed counts;
- VS/PS identities as exact direct SHA or child-alias-v2 resolved SHA;
- vertex declaration identities as exact 116-byte SHA or child-alias-v2 SHA;
- exact inline argument serialized span SHA (or exact null);
- no packed argument pointer.

Exact keys (TechniqueSet, slot, worldVertFormat) union eligible direct signatures
and packed Technique pointer identities. A connected component resolves only if
it contains exactly one eligible direct signature.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path

FORMAT="t6-retail-special-packed-technique-alias-v1"
def loadmod(p:Path,n:str):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def jd(x)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

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

def ptr_key(kind,mapname,ch):
    return (kind,mapname,int(ch["block"]),int(ch["offset"]),str(ch["raw"]))
def tech_ptr_node(mapname,tr):
    return ("ptr",mapname,int(tr["block"]),int(tr["offset"]),str(tr["raw"]))
def key(ts,slot,fmt):return (ts,int(slot),int(fmt))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--child-alias",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_PACKED_CHILD_ALIAS_V2.json"))
    ap.add_argument("--family-manifest",type=Path,default=Path("manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json"))
    ap.add_argument("--parser",type=Path,default=Path("tools/t6_retail_special_shader_payload_census_v1.py"))
    ap.add_argument("--helper",type=Path,default=Path("tools/t6_retail_world_helper_compat_v1.py"))
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()

    parser=loadmod(a.parser,"parser");helper=loadmod(a.helper,"helper")
    famdoc=json.loads(a.family_manifest.read_text());families={x["techniqueSet"]:x["family"] for x in famdoc["specialTechniqueSets"]}
    ca=json.loads(a.child_alias.read_text())
    if ca.get("format")!="t6-retail-special-packed-child-alias-v2":raise SystemExit("child alias format drift")
    child={}
    for r in ca["pointerAliases"]:
        q=r["pointer"]
        if r.get("resolvedSha256"):
            child[(q["kind"],q["map"],int(q["block"]),int(q["offset"]),str(q["raw"]))]=r["resolvedSha256"]

    by_key=collections.defaultdict(set);ptr_uses=collections.defaultdict(list)
    sig_docs={};direct_eligible=direct_ineligible=0;ineligible_reasons=collections.Counter()
    packed_occ=0;occurrences=0

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

        for ts in parsed:
            fam=families.get(ts["name"])
            if fam is None:continue
            occurrences+=1
            for tr in ts["techniqueRefs"]:
                if tr["kind"]=="null":continue
                k=key(ts["name"],tr["slot"],ts["worldVertFormat"])
                if tr["kind"]=="packed":
                    n=tech_ptr_node(mapname,tr);packed_occ+=1;by_key[k].add(n)
                    ptr_uses[n].append({"key":k,"family":fam})
                    continue
                it=tr.get("inlineTechnique")
                if not it:raise SystemExit(f"{mapname}/{ts['name']}/slot{tr['slot']}: inline Technique missing parse")

                # Replay exact child stream, accumulating normalized pass graph.
                p=it["fixedStart"]+8+24*it["passCount"];passes=[];eligible=True;reasons=[]
                for pa in it["passes"]:
                    nr={"passIndex":pa["passIndex"],"counts":pa["counts"],"argCount":pa["argCount"]}
                    for fld,kind in (("vertexShader","vs"),("vertexDecl","vd"),("pixelShader","ps"),("args","args")):
                        ch=pa["children"][fld]
                        if ch["kind"]=="packed":
                            if kind=="args":
                                eligible=False;reasons.append("packed-args")
                            else:
                                rk=ptr_key(kind,mapname,ch);rs_sha=child.get(rk)
                                if rs_sha is None:
                                    eligible=False;reasons.append(f"unresolved-packed-{kind}")
                                nr[kind+"Sha256"]=rs_sha
                            continue
                        if ch["kind"]=="null":
                            nr[kind+"Null"]=True
                            continue
                        if ch["kind"] not in ("following","insert"):
                            eligible=False;reasons.append(f"unexpected-{kind}-pointer-{ch['kind']}");continue
                        if kind in ("vs","ps"):
                            start=p;p,sh=parser.parse_shader(data,p,blocks,helper,kind)
                            if not sh["program"].get("direct"):
                                pp=sh["program"].get("pointer")
                                if not pp or pp.get("kind")!="packed":
                                    eligible=False;reasons.append(f"non-direct-{kind}-program")
                                    nr[kind+"Sha256"]=None
                                else:
                                    # Topology v1 proved this retained corpus has zero
                                    # packed inline shader program refs, so encountering one
                                    # here is denominator drift.
                                    raise SystemExit(f"{mapname}/{ts['name']}: unexpected packed inline {kind} program")
                            else:nr[kind+"Sha256"]=sh["program"]["sha256"]
                        elif kind=="vd":
                            blob=data[p:p+116]
                            if len(blob)!=116 or any(struct.unpack_from("<20I",blob,36)):raise SystemExit(f"{mapname}/{ts['name']}: VD drift at {p}")
                            nr["vdSha256"]=h(blob);p+=116
                        else:
                            start=p;p=parser.parse_args(data,p,pa["argCount"],blocks,helper)
                            nr["argsBytes"]=p-start;nr["argsSha256"]=h(data[start:p])
                    passes.append(nr)
                nk=parser.kind(struct.unpack_from("<I",data,it["fixedStart"])[0],blocks,helper)
                if nk in ("following","insert"):name,p=parser.cstr(data,p)
                elif nk=="packed":
                    eligible=False;reasons.append("packed-technique-name");name=it.get("name")
                else:name=it.get("name")
                # The parser already proved the enclosing TechniqueSet boundary; keep exact
                # direct Technique graph compact and independent of map offsets.
                graph={"name":name,"flags":it["flags"],"passCount":it["passCount"],"passes":passes}
                sig=jd(graph)
                if eligible:
                    direct_eligible+=1;node=("sig",sig);by_key[k].add(node)
                    old=sig_docs.setdefault(sig,graph)
                    if old!=graph:raise SystemExit("signature collision")
                else:
                    direct_ineligible+=1
                    for r in set(reasons):ineligible_reasons[r]+=1

    if packed_occ!=277:raise SystemExit(f"packed Technique occurrence denominator {packed_occ} != 277")
    dsu=DSU()
    for k,nodes in by_key.items():
        q=sorted(nodes,key=repr)
        for n in q:dsu.add(n)
        for n in q[1:]:dsu.union(q[0],n)
    comps=collections.defaultdict(set)
    for n in dsu.p:comps[dsu.find(n)].add(n)

    rows=[];resolved={};reason=collections.Counter();conflicts=[]
    for n,uses in sorted(ptr_uses.items(),key=lambda kv:repr(kv[0])):
        nodes=comps[dsu.find(n)];sigs=sorted({x[1] for x in nodes if x[0]=="sig"})
        if len(sigs)==1:
            status="resolved-exact-direct-technique-graph";sig=sigs[0];resolved[n]=sig
        elif len(sigs)>1:
            status="component-technique-signature-conflict";sig=None;reason[status]+=1
            conflicts.append({"pointer":list(n),"signatureSha256":sigs})
        else:
            status="component-no-eligible-direct-technique";sig=None;reason[status]+=1
        rows.append({"pointer":{"map":n[1],"block":n[2],"offset":n[3],"raw":n[4]},
          "occurrenceCount":len(uses),"status":status,"resolvedTechniqueSignatureSha256":sig,
          "componentDirectSignatureSha256":sigs,"useKeys":[list(u["key"]) for u in uses]})
    ro=sum(r["occurrenceCount"] for r in rows if r["resolvedTechniqueSignatureSha256"])
    summary={
      "specialTechniqueSetOccurrenceCount":occurrences,
      "packedTechniqueOccurrenceCount":packed_occ,
      "packedTechniquePointerIdentityCount":len(rows),
      "eligibleDirectTechniqueOccurrenceCount":direct_eligible,
      "ineligibleDirectTechniqueOccurrenceCount":direct_ineligible,
      "eligibleDirectTechniqueSignatureCount":len(sig_docs),
      "resolvedPackedTechniquePointerIdentityCount":len(resolved),
      "unresolvedPackedTechniquePointerIdentityCount":len(rows)-len(resolved),
      "resolvedPackedTechniqueOccurrenceCount":ro,
      "unresolvedPackedTechniqueOccurrenceCount":packed_occ-ro,
      "ineligibleDirectTechniqueReasonCounts":dict(sorted(ineligible_reasons.items())),
      "unresolvedReasonCounts":dict(sorted(reason.items())),
      "componentConflictCount":len(conflicts),
    }
    doc={
      "format":FORMAT,
      "sources":{"childAlias":str(a.child_alias),"familyManifest":str(a.family_manifest),"parser":str(a.parser),"helper":str(a.helper),
        "expandedWorlds":{m:{"file":cfg["rel"],"sha256":cfg["sha"]} for m,cfg in parser.MAPS.items()}},
      "relation":{"equivalenceKey":["TechniqueSet","slot","worldVertFormat"],
        "eligibleDirectAnchor":"complete normalized direct Technique graph with resolved VS/PS/VD SHA identities and exact args bytes"},
      "summary":summary,"techniqueSignatures":sig_docs,"packedTechniqueAliases":rows,"conflicts":conflicts,
      "resolvedAliasSetSha256":jd(sorted((list(k),v) for k,v in resolved.items())),
      "proofBoundary":"Packed Technique ownership only. Exact cross-map keys connect packed Technique identities to complete direct Technique semantic signatures only when every shader/vertex-decl child in that direct anchor has exact byte ownership and every inline argument span is exactly hashed. Ineligible direct Techniques do not vote. Components with zero or multiple eligible signatures remain unresolved. No adjacency, pointer arithmetic, Technique-name similarity, first-match selection, family inference, or visual behavior is used."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
