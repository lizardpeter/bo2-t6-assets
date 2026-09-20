#!/usr/bin/env python3
"""Corpus-wide runtime-input census for retained T6 special TechniqueSets.

Pinned OAT has already performed native T6 pointer resolution. This tool walks
every exact special TechniqueSet occurrence from the five-world family census,
parses each dumped pixel-shader argument block, and joins the shader destination
to exact DXBC RDEF metadata.

Source classes come only from OAT's emitted grammar:
  constant.* -> code constant
  sampler.*  -> code sampler
  material.* -> material constant/sampler
  float4(*)  -> literal
Anything else remains 'other'. RDEF resources/variables with no emitted
assignment remain unresolved because OAT intentionally omits assignments when
source and destination accessors are identical.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,re
from pathlib import Path

FORMAT="t6-retail-special-runtime-input-census-v1"
FAMILY_FORMAT="t6-retail-special-material-family-census-v1"

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def loadmod(path:Path,name:str):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def roots(values):
    out={}
    for x in values:
        if "=" not in x:raise E(f"bad root {x!r}")
        k,v=x.split("=",1);p=Path(v).resolve()
        req(k and k not in out and p.is_dir(),f"bad/duplicate root {x!r}")
        out[k]=p
    return out
def dest_base(dest:str):
    m=re.fullmatch(r"([^\[]+)(?:\[(\d+)\])?",dest)
    if not m:return None,None
    return m.group(1),None if m.group(2) is None else int(m.group(2))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--family-census",type=Path,required=True)
    ap.add_argument("--root",action="append",required=True)
    ap.add_argument("--oat-parser",type=Path,default=Path("tools/t6_oat_techset_binding_manifest_v1.py"))
    ap.add_argument("--rdef-tool",type=Path,default=Path("tools/t6_dxbc_rdef_v1.py"))
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    fam=json.loads(a.family_census.read_text());req(fam.get("format")==FAMILY_FORMAT,"family format drift")
    rr=roots(a.root);oat=loadmod(a.oat_parser,"special_oat_parser");rdef=loadmod(a.rdef_tool,"special_rdef")
    expected_maps={x["map"] for x in fam.get("maps",[])}
    req(set(rr)==expected_maps,f"root map set {sorted(rr)} != {sorted(expected_maps)}")
    specials=fam.get("specialTechniqueSets",[]);req(len(specials)==31,f"special TS count {len(specials)} !=31")

    rows=[];source_counts=collections.Counter();resource_counts=collections.Counter();family_counts=collections.Counter()
    shader_hashes=set();unmatched_dest=[];unassigned_rdef=[];parse_errors=[];code_const=collections.Counter();code_sampler=collections.Counter()
    occurrence_count=0;pass_count=0;pixel_stage_count=0
    for tsrow in specials:
        ts=str(tsrow["techniqueSet"]);family=str(tsrow["family"])
        for mapn in sorted(tsrow.get("maps",{})):
            occurrence_count+=1;root=rr[mapn];tsp=root/"techsets"/f"{ts}.techset"
            if not tsp.is_file():
                parse_errors.append({"map":mapn,"techniqueSet":ts,"reason":"techset-absent"});continue
            bindings,errs=oat.parse_techset(tsp.read_text(encoding="utf-8",errors="strict"))
            if errs:
                parse_errors.append({"map":mapn,"techniqueSet":ts,"reason":"techset-parse","errors":errs});continue
            for b in bindings:
                tech=str(b["technique"]);tp=root/"techniques"/f"{tech}.tech"
                if not tp.is_file():
                    parse_errors.append({"map":mapn,"techniqueSet":ts,"technique":tech,"reason":"technique-absent"});continue
                rawpasses,errs=oat.split_top_level_passes(tp.read_text(encoding="utf-8",errors="strict"))
                if errs:
                    parse_errors.append({"map":mapn,"techniqueSet":ts,"technique":tech,"reason":"pass-split","errors":errs});continue
                for pi,rawp in enumerate(rawpasses):
                    pass_count+=1;prec,errs=oat.parse_pass(rawp,root)
                    if errs:
                        parse_errors.append({"map":mapn,"techniqueSet":ts,"technique":tech,"passIndex":pi,"reason":"pass-parse","errors":errs});continue
                    ps=[s for s in prec.get("shaders",[]) if s.get("kind")=="pixelShader"]
                    if not ps:continue
                    if len(ps)!=1:
                        parse_errors.append({"map":mapn,"techniqueSet":ts,"technique":tech,"passIndex":pi,"reason":"pixel-stage-count","count":len(ps)});continue
                    stage=ps[0];binary=stage.get("binary")
                    if not isinstance(binary,dict):
                        parse_errors.append({"map":mapn,"techniqueSet":ts,"technique":tech,"passIndex":pi,"reason":"pixel-binary-absent"});continue
                    bp=root/str(binary["path"]);hh=sha(bp)
                    if hh!=binary.get("sha256"):
                        raise E(f"{mapn}/{tech}/{pi}: PS SHA drift")
                    rd=rdef.parse_rdef(bp.read_bytes());pixel_stage_count+=1;shader_hashes.add(hh);family_counts[family]+=1
                    resources=rd["resources"];textures={x["name"]:x for x in resources if x["resourceType"]=="texture"}
                    samplers={x["name"]:x for x in resources if x["resourceType"]=="sampler"}
                    cbvars={}
                    for cb in rd["constantBuffers"]:
                        for v in cb["variables"]:
                            cbvars[v["name"]]=(cb,v)
                    args=[];assigned_texture_names=set();assigned_cb_names=set()
                    for ar in stage.get("arguments",[]):
                        dest=str(ar.get("destination") or "");src=str(ar.get("source") or "");klass=str(ar.get("sourceClass") or "other")
                        source_counts[klass]+=1;base,index=dest_base(dest);match_kind=None;match=None
                        if base in textures:
                            match_kind="texture";match=textures[base];assigned_texture_names.add(base);resource_counts["texture-assignment"]+=1
                            same_sampler=samplers.get(base)
                            if same_sampler is not None:resource_counts["same-name-sampler-paired"]+=1
                        elif base in cbvars:
                            match_kind="constant-variable";cb,v=cbvars[base];assigned_cb_names.add(base);resource_counts["constant-assignment"]+=1
                            match={"constantBuffer":cb["name"],"bufferRegister":cb.get("register"),"variable":v}
                        else:
                            unmatched_dest.append({"map":mapn,"family":family,"techniqueSet":ts,"technique":tech,"passIndex":pi,
                              "pixelShaderSha256":hh,"destination":dest,"source":src,"sourceClass":klass})
                        if klass=="constant":
                            acc=src[len("constant."):] if src.startswith("constant.") else src;code_const[acc]+=1
                        elif klass=="sampler":
                            acc=src[len("sampler."):] if src.startswith("sampler.") else src;code_sampler[acc]+=1
                        args.append({"destination":dest,"source":src,"sourceClass":klass,"rdefMatchKind":match_kind,"rdefMatch":match})
                    for name,x in textures.items():
                        if name not in assigned_texture_names:
                            unassigned_rdef.append({"map":mapn,"family":family,"techniqueSet":ts,"technique":tech,"passIndex":pi,
                              "pixelShaderSha256":hh,"kind":"texture","name":name,"register":x.get("register"),
                              "reason":"no-emitted-technique-assignment-identity-or-nonargument-unresolved"})
                    for name,(cb,v) in cbvars.items():
                        if name not in assigned_cb_names:
                            unassigned_rdef.append({"map":mapn,"family":family,"techniqueSet":ts,"technique":tech,"passIndex":pi,
                              "pixelShaderSha256":hh,"kind":"constant-variable","name":name,"buffer":cb["name"],"register":cb.get("register"),
                              "startOffset":v["startOffset"],"size":v["size"],
                              "reason":"no-emitted-technique-assignment-identity-or-nonargument-unresolved"})
                    rows.append({"map":mapn,"family":family,"techniqueSet":ts,"techniqueTypes":b["types"],"technique":tech,"passIndex":pi,
                      "pixelShader":{"asset":stage.get("name"),"sha256":hh,"relativeFile":binary["path"]},
                      "stateMap":prec.get("stateMap"),"arguments":args,
                      "rdef":{"resources":resources,"constantBuffers":rd["constantBuffers"]}})
    summary={
      "specialTechniqueSetIdentityCount":len(specials),
      "specialTechniqueSetMapOccurrenceCount":occurrence_count,
      "parsedPassCount":pass_count,
      "pixelShaderPassOccurrenceCount":pixel_stage_count,
      "uniquePixelShaderSha256Count":len(shader_hashes),
      "argumentCount":sum(source_counts.values()),
      "argumentSourceClassCounts":dict(sorted(source_counts.items())),
      "rdefAssignmentClassCounts":dict(sorted(resource_counts.items())),
      "uniqueCodeConstantAccessorCount":len(code_const),
      "codeConstantAccessorOccurrenceCount":sum(code_const.values()),
      "uniqueCodeSamplerAccessorCount":len(code_sampler),
      "codeSamplerAccessorOccurrenceCount":sum(code_sampler.values()),
      "unmatchedTechniqueDestinationCount":len(unmatched_dest),
      "unassignedRdefInputCount":len(unassigned_rdef),
      "parseErrorCount":len(parse_errors),
      "familyPixelShaderPassCounts":dict(sorted(family_counts.items())),
    }
    doc={"format":FORMAT,
      "authority":"exact retained special TechniqueSet/map denominator + same-world pinned-OAT native dumps + exact emitted pixel-shader argument grammar + direct DXBC RDEF metadata",
      "sources":{"familyCensus":{"path":str(a.family_census),"sha256":sha(a.family_census)},"oatRoots":{k:str(v) for k,v in sorted(rr.items())}},
      "summary":summary,
      "codeConstantAccessors":[{"accessor":k,"occurrenceCount":v} for k,v in sorted(code_const.items())],
      "codeSamplerAccessors":[{"accessor":k,"occurrenceCount":v} for k,v in sorted(code_sampler.items())],
      "unmatchedTechniqueDestinations":unmatched_dest,
      "unassignedRdefInputs":unassigned_rdef,
      "parseErrors":parse_errors,
      "rows":rows,
      "proofBoundary":"Census/identity join only. TechniqueSet occurrence, Technique/pass, pixel-shader bytes, emitted assignments, and RDEF ABI are exact same-world artifacts. Source classes are taken only from OAT's emitted grammar. An RDEF input with no emitted assignment is explicitly unresolved because OAT may omit identity assignments when source and destination accessors match. No unassigned input is promoted to engine/code/material ownership by name, register, family, or visual behavior. Runtime values and upload mechanics are outside this proof."
    }
    if parse_errors:raise SystemExit(f"native special input census parse errors: {len(parse_errors)}")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    print("CODE CONSTANTS",dict(sorted(code_const.items())))
    print("CODE SAMPLERS",dict(sorted(code_sampler.items())))
if __name__=="__main__":main()
