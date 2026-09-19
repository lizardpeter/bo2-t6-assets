#!/usr/bin/env python3
"""Cross-map structural alias proof for retained special packed shader objects
and vertex declarations.

A packed child is resolved only when:
  1. its exact pass key (TechniqueSet, slot, passIndex, worldVertFormat, stage)
     has one and only one physically inline direct payload SHA across retained maps;
  2. every pass key using the same exact packed pointer identity agrees on that SHA.

Vertex declarations use the analogous pass key and exact 116-byte direct payload SHA.
Conflicts and keys with no direct anchor remain unresolved. No adjacency, names,
pointer spacing, introduction order, or visual similarity is used.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path

FORMAT="t6-retail-special-packed-child-alias-v1"
def loadmod(p:Path,n:str):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def jd(x)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def pident(mapname,ch):
    return (mapname,int(ch["block"]),int(ch["offset"]),str(ch["raw"]))
def key(ts,slot,pi,fmt,kind):
    return (ts,int(slot),int(pi),int(fmt),kind)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--family-manifest",type=Path,default=Path("manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json"))
    ap.add_argument("--parser",type=Path,default=Path("tools/t6_retail_special_shader_payload_census_v1.py"))
    ap.add_argument("--helper",type=Path,default=Path("tools/t6_retail_world_helper_compat_v1.py"))
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    parser=loadmod(a.parser,"parser");helper=loadmod(a.helper,"helper")
    famdoc=json.loads(a.family_manifest.read_text());families={x["techniqueSet"]:x["family"] for x in famdoc["specialTechniqueSets"]}

    # exact structural-key direct anchors and packed uses
    anchors=collections.defaultdict(set)
    packed_uses=collections.defaultdict(list)
    direct_rows=[]
    packed_occ_counts=collections.Counter()
    direct_vdecl_bytes={}

    for mapname,cfg in parser.MAPS.items():
        data=(a.root/cfg["rel"]).read_bytes(); got=h(data)
        if got!=cfg["sha"]:raise SystemExit(f"{mapname}: expanded SHA drift {got}")
        front=helper.parse_front(data);blocks=front["blockSizes"]
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
            for tr in ts["techniqueRefs"]:
                it=tr.get("inlineTechnique")
                if not it:continue
                for pa in it["passes"]:
                    pi=pa["passIndex"]; fmt=ts["worldVertFormat"]; slot=tr["slot"]
                    for fld,stage in (("vertexShader","vs"),("pixelShader","ps")):
                        ch=pa["children"][fld]; k=key(ts["name"],slot,pi,fmt,stage)
                        if ch["kind"]=="packed":
                            ident=pident(mapname,ch);packed_uses[ident].append({"key":k,"family":fam,"map":mapname})
                            packed_occ_counts[stage]+=1
                        else:
                            sh=ch.get("inline")
                            if sh and sh["program"].get("direct"):
                                sha=sh["program"]["sha256"];anchors[k].add(sha)
                                direct_rows.append({"key":k,"sha256":sha,"family":fam,"map":mapname,"kind":stage})
                    vd=pa["children"]["vertexDecl"];k=key(ts["name"],slot,pi,fmt,"vd")
                    if vd["kind"]=="packed":
                        ident=pident(mapname,vd);packed_uses[ident].append({"key":k,"family":fam,"map":mapname})
                        packed_occ_counts["vd"]+=1
                    elif vd["kind"] in ("following","insert"):
                        # Parser consumes exactly 116 bytes at the current inline VD location,
                        # but does not retain the start. Derive it from pass serialization order
                        # by reparsing this inline Technique with a tiny instrumented walker below.
                        pass

        # Instrument exact inline VD starts by replaying each selected inline Technique.
        for ts in parsed:
            fam=families.get(ts["name"])
            if fam is None:continue
            for tr in ts["techniqueRefs"]:
                it=tr.get("inlineTechnique")
                if not it:continue
                # Reconstruct child stream cursor exactly: fixed header + 24*passCount.
                p=it["fixedStart"]+8+24*it["passCount"]
                # Children serialize per pass in VS, VD, PS, args order.
                for pa in it["passes"]:
                    for fld,ck in (("vertexShader","vs"),("vertexDecl","vd"),("pixelShader","ps"),("args","args")):
                        ch=pa["children"][fld]
                        if ch["kind"] not in ("following","insert"):continue
                        if ck in ("vs","ps"):
                            p2,sh=parser.parse_shader(data,p,blocks,helper,ck);p=p2
                        elif ck=="vd":
                            blob=data[p:p+116]
                            if len(blob)!=116 or any(struct.unpack_from("<20I",blob,36)):
                                raise SystemExit(f"{mapname}/{ts['name']}: direct VD structural drift at {p}")
                            sha=h(blob);direct_vdecl_bytes.setdefault(sha,blob)
                            k=key(ts["name"],tr["slot"],pa["passIndex"],ts["worldVertFormat"],"vd")
                            anchors[k].add(sha)
                            direct_rows.append({"key":k,"sha256":sha,"family":fam,"map":mapname,"kind":"vd"})
                            p+=116
                        else:
                            p=parser.parse_args(data,p,pa["argCount"],blocks,helper)
                # Inline technique name follows children.
                nk=parser.kind(struct.unpack_from("<I",data,it["fixedStart"])[0],blocks,helper)
                if nk in ("following","insert"):
                    _,p=parser.cstr(data,p)

    # Classify structural keys.
    key_status={}
    key_conflicts=[]
    for k,vals in anchors.items():
        if len(vals)==1:key_status[k]=next(iter(vals))
        elif len(vals)>1:key_conflicts.append({"key":list(k),"directSha256":sorted(vals)})
    # Resolve exact pointer identities only if every anchored key that uses them agrees
    # and no key has conflicting direct anchors. Keys with no direct anchor do not vote.
    rows=[];resolved={};unresolved=collections.Counter()
    for ident,uses in sorted(packed_uses.items()):
        votes=set();conflicting_keys=[];unanchored=[]
        for u in uses:
            k=u["key"]
            if k in key_status:votes.add(key_status[k])
            elif len(anchors.get(k,set()))>1:conflicting_keys.append(list(k))
            else:unanchored.append(list(k))
        if conflicting_keys:
            status="conflicting-key-anchor";unresolved[status]+=1;sha=None
        elif len(votes)>1:
            status="pointer-cross-key-sha-conflict";unresolved[status]+=1;sha=None
        elif len(votes)==1:
            status="resolved-cross-map-key";sha=next(iter(votes));resolved[ident]=sha
        else:
            status="no-direct-anchor";unresolved[status]+=1;sha=None
        rows.append({
          "pointer":{"map":ident[0],"block":ident[1],"offset":ident[2],"raw":ident[3]},
          "kind":uses[0]["key"][4],"occurrenceCount":len(uses),"status":status,
          "resolvedSha256":sha,"anchorVoteSha256":sorted(votes),
          "unanchoredKeyCount":len(unanchored),"conflictingKeys":conflicting_keys,
          "useKeys":[list(u["key"]) for u in uses],
        })
    occ_total=sum(len(v) for v in packed_uses.values())
    resolved_occ=sum(r["occurrenceCount"] for r in rows if r["resolvedSha256"])
    kinds=collections.defaultdict(lambda:collections.Counter())
    for r in rows:
        k=r["kind"];kinds[k]["pointerIdentities"]+=1;kinds[k]["occurrences"]+=r["occurrenceCount"]
        if r["resolvedSha256"]:
            kinds[k]["resolvedPointerIdentities"]+=1;kinds[k]["resolvedOccurrences"]+=r["occurrenceCount"]
        else:kinds[k]["unresolvedPointerIdentities"]+=1;kinds[k]["unresolvedOccurrences"]+=r["occurrenceCount"]
    expected_occ={"vs":419,"ps":260,"vd":459}
    got={k:packed_occ_counts[k] for k in expected_occ}
    if got!=expected_occ:raise SystemExit(f"packed occurrence denominator drift {got}")
    summary={
      "packedChildOccurrenceCount":occ_total,
      "packedChildPointerIdentityCount":len(rows),
      "resolvedPointerIdentityCount":sum(bool(r["resolvedSha256"]) for r in rows),
      "unresolvedPointerIdentityCount":sum(not r["resolvedSha256"] for r in rows),
      "resolvedOccurrenceCount":resolved_occ,
      "unresolvedOccurrenceCount":occ_total-resolved_occ,
      "directStructuralKeyCount":len(anchors),
      "uniqueDirectAnchorKeyCount":len(key_status),
      "conflictingDirectAnchorKeyCount":len(key_conflicts),
      "kindCounts":{k:dict(v) for k,v in sorted(kinds.items())},
      "unresolvedReasonCounts":dict(sorted(unresolved.items())),
    }
    doc={
      "format":FORMAT,
      "sources":{"familyManifest":str(a.family_manifest),"parser":str(a.parser),"helper":str(a.helper),
        "expandedWorlds":{m:{"file":cfg["rel"],"sha256":cfg["sha"]} for m,cfg in parser.MAPS.items()}},
      "relation":{"shaderKey":["TechniqueSet","slot","passIndex","worldVertFormat","stage"],
        "vertexDeclKey":["TechniqueSet","slot","passIndex","worldVertFormat","vd"]},
      "summary":summary,
      "directAnchorConflicts":key_conflicts,
      "pointerAliases":rows,
      "resolvedAliasSetSha256":jd(sorted((list(k),v) for k,v in resolved.items())),
      "proofBoundary":"Cross-map structural alias proof only. A packed shader-object or vertex-decl pointer is resolved only when exact retained pass keys independently expose one direct byte SHA and every anchored key using that exact pointer identity agrees. Keys with no direct occurrence remain non-voting; multi-SHA keys and cross-key disagreement remain unresolved. No pointer offset dereference, adjacency, introduction order, shader/Technique names, family similarity, translated appearance, or first-match rule is used."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
