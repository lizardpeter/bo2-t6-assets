#!/usr/bin/env python3
"""Exact topology census of every packed/reused dependency reachable from the
31 retained special TechniqueSets in the five SHA-pinned expanded worlds.

The legacy family extractor counted packed Technique refs and packed VS/PS object
refs. This census additionally counts packed shader *program* pointers inside
inline shader objects, packed shader-name pointers, packed vertex declarations,
and packed pass-argument arrays. It does not resolve any of them.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path

FORMAT="t6-retail-special-packed-reference-topology-v1"

def loadmod(p:Path,n:str):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--family-manifest",type=Path,default=Path("manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json"))
    ap.add_argument("--parser",type=Path,default=Path("tools/t6_retail_special_shader_payload_census_v1.py"))
    ap.add_argument("--helper",type=Path,default=Path("tools/t6_retail_world_helper_compat_v1.py"))
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    parser=loadmod(a.parser,"parser");helper=loadmod(a.helper,"helper")
    famdoc=json.loads(a.family_manifest.read_text())
    family={x["techniqueSet"]:x["family"] for x in famdoc["specialTechniqueSets"]}
    totals=collections.Counter();byfam=collections.defaultdict(collections.Counter);bymap=collections.defaultdict(collections.Counter)
    identities=collections.defaultdict(set);rows=[];occurrences=0

    def add(kind,mapname,fam,raw,block,offset,owner):
        totals[kind]+=1;byfam[fam][kind]+=1;bymap[mapname][kind]+=1
        ident=(mapname,int(block) if block is not None else None,int(offset) if offset is not None else None,str(raw))
        identities[kind].add(ident)
        rows.append({"kind":kind,"map":mapname,"family":fam,"raw":raw,"block":block,"offset":offset,**owner})

    for mapname,cfg in parser.MAPS.items():
        data=(a.root/cfg["rel"]).read_bytes()
        got=hashlib.sha256(data).hexdigest()
        if got!=cfg["sha"]:raise SystemExit(f"{mapname}: expanded SHA drift {got}")
        front=helper.parse_front(data);blocks=front["blockSizes"]
        rs=helper.scan_techsets(data,blocks,before=cfg["world"])[-(cfg["q1"]-cfg["q0"]+1):]
        if len(rs)!=cfg["q1"]-cfg["q0"]+1:raise SystemExit(f"{mapname}: TechniqueSet count drift")
        for i,r in enumerate(rs):r["xassetIndex"]=cfg["q0"]+i
        parsed=[]
        for i,r in enumerate(rs):
            nxt=rs[i+1]["fixedStart"] if i+1<len(rs) else cfg["world"]
            parsed.append(parser.parse_techset(data,r,nxt,blocks,helper))
        if parsed[-1]["end"]!=cfg["world"]:raise SystemExit(f"{mapname}: TechniqueSet block end drift")
        for ts in parsed:
            fam=family.get(ts["name"])
            if fam is None:continue
            occurrences+=1
            for tr in ts["techniqueRefs"]:
                if tr["kind"]=="packed":
                    add("packedTechniqueRef",mapname,fam,tr["raw"],tr.get("block"),tr.get("offset"),
                        {"techniqueSet":ts["name"],"techniqueSlot":tr["slot"]})
                    continue
                it=tr.get("inlineTechnique")
                if not it:continue
                # Inline Technique name pointer is the first dword of the serialized object.
                raw_name=struct.unpack_from("<I",data,it["fixedStart"])[0]
                np=parser.ptr(raw_name,blocks,helper)
                if np["kind"]=="packed":
                    add("packedInlineTechniqueNameRef",mapname,fam,np["raw"],np.get("block"),np.get("offset"),
                        {"techniqueSet":ts["name"],"techniqueSlot":tr["slot"],"technique":it.get("name")})
                for pa in it["passes"]:
                    base={"techniqueSet":ts["name"],"techniqueSlot":tr["slot"],"technique":it.get("name"),"passIndex":pa["passIndex"]}
                    for fld,stage in (("vertexShader","vs"),("pixelShader","ps")):
                        ch=pa["children"][fld]
                        if ch["kind"]=="packed":
                            add(f"packed{stage.upper()}ObjectRef",mapname,fam,ch["raw"],ch.get("block"),ch.get("offset"),base)
                            continue
                        sh=ch.get("inline")
                        if not sh:continue
                        n=sh["namePointer"]
                        if n and n["kind"]=="packed":
                            add(f"packedInline{stage.upper()}NameRef",mapname,fam,n["raw"],n.get("block"),n.get("offset"),base)
                        pr=sh["program"]
                        pp=pr.get("pointer")
                        if not pr.get("direct") and pp and pp.get("kind")=="packed":
                            add(f"packedInline{stage.upper()}ProgramRef",mapname,fam,pp["raw"],pp.get("block"),pp.get("offset"),
                                {**base,"programBytes":pr["bytes"],"shaderName":sh.get("name")})
                    vd=pa["children"]["vertexDecl"]
                    if vd["kind"]=="packed":
                        add("packedVertexDeclRef",mapname,fam,vd["raw"],vd.get("block"),vd.get("offset"),base)
                    ar=pa["children"]["args"]
                    if ar["kind"]=="packed":
                        add("packedArgsRef",mapname,fam,ar["raw"],ar.get("block"),ar.get("offset"),{**base,"argCount":pa["argCount"]})

    legacy=totals["packedTechniqueRef"]+totals["packedVSObjectRef"]+totals["packedPSObjectRef"]
    if legacy!=956:raise SystemExit(f"legacy packed reference denominator {legacy} != 956")
    if totals["packedTechniqueRef"]!=277 or totals["packedVSObjectRef"]+totals["packedPSObjectRef"]!=679:
        raise SystemExit(f"legacy topology split drift {dict(totals)}")
    total_all=sum(totals.values())
    summary={
      "specialTechniqueSetCount":len(family),"specialTechniqueSetOccurrenceCount":occurrences,
      "legacyPackedTechniqueAndShaderObjectReferenceCount":legacy,
      "packedTechniqueRefCount":totals["packedTechniqueRef"],
      "packedShaderObjectRefCount":totals["packedVSObjectRef"]+totals["packedPSObjectRef"],
      "allEnumeratedPackedDependencyReferenceCount":total_all,
      "additionalPackedDependencyReferenceCountBeyondLegacy956":total_all-legacy,
      "referenceCounts":dict(sorted(totals.items())),
      "uniqueMapBlockOffsetRawIdentityCounts":{k:len(v) for k,v in sorted(identities.items())},
    }
    doc={
      "format":FORMAT,
      "sources":{"familyManifest":str(a.family_manifest),"parser":str(a.parser),"helper":str(a.helper),
        "expandedWorlds":{m:{"file":cfg["rel"],"sha256":cfg["sha"]} for m,cfg in parser.MAPS.items()}},
      "summary":summary,
      "familyReferenceCounts":{f:dict(sorted(c.items())) for f,c in sorted(byfam.items())},
      "mapReferenceCounts":{m:dict(sorted(c.items())) for m,c in sorted(bymap.items())},
      "rowSetSha256":digest(rows),"rows":rows,
      "proofBoundary":"Topology census only. Every row is an exact packed pointer decoded by the retained T6 zone-pointer helper from a structurally closed special TechniqueSet occurrence. The legacy 956 denominator is reproduced exactly before additional packed name/program/vertex-decl/argument dependencies are counted. No packed pointer is dereferenced, aliased, resolved by adjacency, or assigned from names in this proof."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
