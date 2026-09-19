#!/usr/bin/env python3
"""Bind exact generated-surface runtime sampler resources to exact retail payload hashes.

Consumes the already-closed per-surface runtime sampler resource proof and the
independent inline payload proofs for Nuketown secondary lightmaps/reflection probes.
No decoding/color/channel semantics are inferred here.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path

BIND_FMT="t6-nuketown-generated-runtime-sampler-surface-binding-v1"
LM_FMT="t6-nuketown-lightmap-inline-payload-proof-v1"
RP_FMT="t6-nuketown-reflection-inline-payload-probe-v1"
COV_FMT="t6-nuketown-production-texture-payload-coverage-v2"
FORMAT="t6-nuketown-generated-runtime-sampler-payload-binding-v1"
class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
def load(p):return json.loads(Path(p).read_text())
def sh(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def provider_maps(lm,rp):
    lm_by={}
    for r in lm.get("payloads",[]):
        n=str(r["image"]);req(n not in lm_by,f"duplicate lightmap payload {n}")
        lm_by[n]={
          "providerKind":"serialized-inline-lightmap",
          "payloadSha256":r["payloadSha256"],"payloadBytes":int(r["resourceSize"]),
          "width":int(r["width"]),"height":int(r["height"]),"depth":int(r["depth"]),
          "loadDefFormat":int(r["loadDefFormat"]),"serializedDataStart":int(r["dataStart"]),
        }
    rp_by={}
    for r in rp.get("rows",[]):
        n=str(r["image"]);c=r.get("candidates",[])
        req(int(r.get("serializedGfxImageCandidateCount",-1))==1 and len(c)==1,f"{n}: reflection payload not uniquely closed")
        x=c[0]
        req(n not in rp_by,f"duplicate reflection payload {n}")
        rp_by[n]={
          "providerKind":"serialized-inline-reflection",
          "payloadSha256":x["payloadSha256"],"payloadBytes":int(x["resourceSize"]),
          "serializedDataStart":int(x["dataStart"]),"serializedDataEnd":int(x["dataEnd"]),
          "serializedGfxImageFixedStart":int(x["fixedStart"]),
        }
    return lm_by,rp_by

def exact_coverage_set(cov):
    names=set()
    # V2 carries prior exact providers plus new exact providers.
    for key in ("exactProviders","priorExactProviders","newExactProviders"):
        for r in cov.get(key,[]) or []:
            n=r.get("image")
            if n:names.add(str(n))
    # Some revisions retain the canonical list directly.
    for n in cov.get("coveredProductionImages",[]) or []: names.add(str(n))
    return names

def build(bind,lm,rp,cov):
    req(bind.get("format")==BIND_FMT,f"binding format {bind.get('format')!r}")
    req(lm.get("format")==LM_FMT,f"lightmap payload format {lm.get('format')!r}")
    req(rp.get("format")==RP_FMT,f"reflection payload format {rp.get('format')!r}")
    req(cov.get("format")==COV_FMT,f"coverage format {cov.get('format')!r}")
    req(bind.get("summary",{}).get("allSampledRuntimeResourceIdentitiesResolved") is True,"resource identity proof not closed")
    lm_by,rp_by=provider_maps(lm,rp)
    coverage=exact_coverage_set(cov)
    resources={};rows=[];kind_counts=collections.Counter();bind_count=0
    for s in bind.get("surfaces",[]):
        br=[]
        for b in s.get("runtimeSamplerBindings",[]):
            req(b.get("status")=="resolved",f"surface {s.get('surfaceIndex')}: unresolved upstream binding")
            res=str(b["resource"]);img=str(b["image"])
            if res=="lightmapSamplerSecondary":
                p=lm_by.get(img);kind="lightmapSamplerSecondary"
            elif res=="reflectionProbeSampler":
                p=rp_by.get(img);kind="reflectionProbeSampler"
            else: raise E(f"surface {s.get('surfaceIndex')}: unexpected runtime sampler {res!r}")
            req(p is not None,f"{res}/{img}: no exact inline payload provider")
            req(img in coverage,f"{res}/{img}: absent from production exact-payload coverage v2")
            prior=resources.setdefault(img,{"image":img,**p})
            req(prior["payloadSha256"]==p["payloadSha256"],f"{img}: payload provider disagreement")
            br.append({
              "resource":res,"image":img,"payloadSha256":p["payloadSha256"],
              "payloadBytes":p["payloadBytes"],"providerKind":p["providerKind"],
              "selector":b["selector"],
            })
            kind_counts[kind]+=1;bind_count+=1
        rows.append({
          "surfaceIndex":int(s["surfaceIndex"]),"material":s["material"],
          "techniqueSet":s["techniqueSet"],"pixelShaderSha256":s["pixelShaderSha256"],
          "payloadBindings":br
        })
    used_lm={n for n,r in resources.items() if r["providerKind"]=="serialized-inline-lightmap"}
    used_rp={n for n,r in resources.items() if r["providerKind"]=="serialized-inline-reflection"}
    summary={
      "generatedSurfaceCount":len(rows),
      "surfaceSamplerPayloadBindingCount":bind_count,
      "secondaryLightmapPayloadBindingCount":kind_counts["lightmapSamplerSecondary"],
      "reflectionProbePayloadBindingCount":kind_counts["reflectionProbeSampler"],
      "uniquePayloadResourceCount":len(resources),
      "uniqueSecondaryLightmapPayloadResourceCount":len(used_lm),
      "uniqueReflectionProbePayloadResourceCount":len(used_rp),
      "allRuntimeSamplerPayloadsExact":True,
    }
    req(len(rows)==int(bind["summary"]["generatedSurfaceCount"]),"surface count drift")
    req(kind_counts["lightmapSamplerSecondary"]==int(bind["summary"]["resolvedSecondaryLightmapSurfaceBindingCount"]),"lightmap binding count drift")
    req(kind_counts["reflectionProbeSampler"]==int(bind["summary"]["resolvedReflectionProbeSurfaceBindingCount"]),"reflection binding count drift")
    return {
      "format":FORMAT,
      "authority":"exact generated per-surface code-sampler resource identity joined to independent exact serialized inline payload proofs and production exact-payload coverage v2",
      "summary":summary,
      "resources":[resources[k] for k in sorted(resources)],
      "surfaces":rows,
      "proofBoundary":"This proves exact retail payload byte identity for every resolved generated-surface lightmapSamplerSecondary/reflectionProbeSampler resource use. It does not assign channel/color meaning, decode BC formats, prove GPU upload/sampler state, choose reflection coordinates/LOD beyond separately retained shader evidence, or resolve hdrControl0 runtime value."
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--binding",type=Path,required=True);ap.add_argument("--lightmap-payload",type=Path,required=True)
    ap.add_argument("--reflection-payload",type=Path,required=True);ap.add_argument("--coverage",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    bind,lm,rp,cov=[load(x) for x in (a.binding,a.lightmap_payload,a.reflection_payload,a.coverage)]
    d=build(bind,lm,rp,cov)
    d["sources"]={
      "binding":{"path":str(a.binding),"sha256":sh(a.binding)},
      "lightmapPayload":{"path":str(a.lightmap_payload),"sha256":sh(a.lightmap_payload)},
      "reflectionPayload":{"path":str(a.reflection_payload),"sha256":sh(a.reflection_payload)},
      "productionCoverage":{"path":str(a.coverage),"sha256":sh(a.coverage)},
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps(d["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
