#!/usr/bin/env python3
"""Bind generated Nuketown final-output code samplers to exact per-surface GfxWorld resources.

This is a renderer-resource identity proof, not an engine upload-mechanism proof.
It joins:
  exact v3 GfxSurface -> exact Material identity ->
  exact generated final-output runtime-input census ->
  exact GfxWorld lightmap/reflection catalogs.

No resource is synthesized for lightmapIndex 31. Any sampled code resource whose
surface selector cannot resolve exactly is retained as a blocker and strict mode
fails closed.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path

SURF_FMT="t6-gfxworld-surfaces-source-sidecar-v3"
CAT_FMT="t6-world-surface-material-catalog-source-v3"
RUNTIME_FMT="t6-nuketown-generated-final-output-runtime-input-census-v1"
LM_FMT="t6-gfxworld-lightmap-catalog-v1"
RP_FMT="t6-gfxworld-reflection-probe-catalog-v1"
FORMAT="t6-nuketown-generated-runtime-sampler-surface-binding-v1"

class BindError(RuntimeError): pass
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path)->dict:return json.loads(p.read_text())
def req(c,m): 
    if not c: raise BindError(m)
def index_unique(rows,key,label):
    out={}
    for r in rows:
        v=str(r.get(key) or "")
        req(v,f"{label}: empty {key}")
        req(v not in out,f"{label}: duplicate {v!r}")
        out[v]=r
    return out

def build(surfaces,catalog,runtime,lightmaps,probes):
    req(surfaces.get("format")==SURF_FMT,f"surface format {surfaces.get('format')!r}")
    req(catalog.get("format")==CAT_FMT,f"catalog format {catalog.get('format')!r}")
    req(runtime.get("format")==RUNTIME_FMT,f"runtime format {runtime.get('format')!r}")
    req(lightmaps.get("format")==LM_FMT,f"lightmap format {lightmaps.get('format')!r}")
    req(probes.get("format")==RP_FMT,f"reflection format {probes.get('format')!r}")

    by_ptr={}
    for m in catalog.get("materials",[]):
        raw=str(m.get("surfacePointerHex") or "")
        req(raw and raw not in by_ptr,f"invalid/duplicate material pointer {raw!r}")
        by_ptr[raw]=m
    rt=index_unique(runtime.get("materials",[]),"material","runtime material")
    lm={int(x["index"]):x for x in lightmaps.get("lightmaps",[])}
    rp={int(x["index"]):x for x in probes.get("reflectionProbes",[])}
    req(len(lm)==int(lightmaps.get("lightmapCount",-1)),"lightmap count mismatch")
    req(len(rp)==int(probes.get("reflectionProbeCount",-1)),"reflection count mismatch")

    rows=[]; status=collections.Counter(); materials=collections.Counter()
    lm_use=collections.Counter(); rp_use=collections.Counter()
    for s in surfaces.get("surfaces",[]):
        idx=int(s["index"]); ptr=str(s["materialPointerRaw"])
        m=by_ptr.get(ptr); req(m is not None,f"surface {idx}: material pointer {ptr} absent")
        name=str(m["name"])
        rr=rt.get(name)
        if rr is None: continue
        materials[name]+=1
        dyn={str(x.get("resource")):x for x in rr.get("textureInputs",[]) if x.get("kind")=="t6CodeSamplerDynamic"}
        unexpected=set(dyn)-{"lightmapSamplerSecondary","reflectionProbeSampler"}
        req(not unexpected,f"{name}: unexpected dynamic code samplers {sorted(unexpected)}")
        bind=[]
        if "lightmapSamplerSecondary" in dyn:
            li=int(s["lightmapIndex"])
            if li==31:
                b={"resource":"lightmapSamplerSecondary","selector":{"field":"GfxSurface.lightmapIndex","value":li},
                   "status":"unresolved-lightmap-sentinel-31","image":None}
                status[b["status"]]+=1
            else:
                rec=lm.get(li)
                if rec is None:
                    b={"resource":"lightmapSamplerSecondary","selector":{"field":"GfxSurface.lightmapIndex","value":li},
                       "status":"unresolved-lightmap-index","image":None}
                    status[b["status"]]+=1
                else:
                    image=rec.get("secondaryImage")
                    if image is None:
                        b={"resource":"lightmapSamplerSecondary","selector":{"field":"GfxSurface.lightmapIndex","value":li},
                           "status":"unresolved-null-secondary-image","image":None}
                        status[b["status"]]+=1
                    else:
                        b={"resource":"lightmapSamplerSecondary","selector":{"field":"GfxSurface.lightmapIndex","value":li},
                           "status":"resolved","image":image}
                        status["resolved-lightmap"]+=1;lm_use[li]+=1
            bind.append(b)
        if "reflectionProbeSampler" in dyn:
            pi=int(s["reflectionProbeIndex"]); rec=rp.get(pi)
            if rec is None:
                b={"resource":"reflectionProbeSampler","selector":{"field":"GfxSurface.reflectionProbeIndex","value":pi},
                   "status":"unresolved-reflection-index","image":None}
                status[b["status"]]+=1
            else:
                image=rec.get("reflectionImage")
                if image is None:
                    b={"resource":"reflectionProbeSampler","selector":{"field":"GfxSurface.reflectionProbeIndex","value":pi},
                       "status":"unresolved-null-reflection-image","image":None}
                    status[b["status"]]+=1
                else:
                    b={"resource":"reflectionProbeSampler","selector":{"field":"GfxSurface.reflectionProbeIndex","value":pi},
                       "status":"resolved","image":image,"probeOrigin":rec.get("origin"),"mipLodBias":rec.get("mipLodBias")}
                    status["resolved-reflection"]+=1;rp_use[pi]+=1
            bind.append(b)
        rows.append({
          "surfaceIndex":idx,"material":name,"materialIndex":int(m["materialIndex"]),
          "techniqueSet":rr["techniqueSet"],"pixelShaderSha256":rr["pixelShaderSha256"],
          "lightmapIndex":int(s["lightmapIndex"]),"reflectionProbeIndex":int(s["reflectionProbeIndex"]),
          "runtimeSamplerBindings":bind
        })
    generated=set(rt)
    req(set(materials)==generated,f"generated material surface coverage mismatch: used={len(materials)} expected={len(generated)} missing={sorted(generated-set(materials))[:8]}")
    blockers={k:v for k,v in sorted(status.items()) if k.startswith("unresolved-") and v}
    summary={
      "generatedMaterialCount":len(generated),
      "generatedSurfaceCount":len(rows),
      "generatedMaterialSurfaceCoverageCount":len(materials),
      "resolvedSecondaryLightmapSurfaceBindingCount":status["resolved-lightmap"],
      "resolvedReflectionProbeSurfaceBindingCount":status["resolved-reflection"],
      "runtimeSamplerBlockerCounts":blockers,
      "secondaryLightmapUseCounts":{str(k):v for k,v in sorted(lm_use.items())},
      "reflectionProbeUseCounts":{str(k):v for k,v in sorted(rp_use.items())},
      "distinctSecondaryLightmapIndicesResolved":len(lm_use),
      "distinctReflectionProbeIndicesResolved":len(rp_use),
      "allSampledRuntimeResourceIdentitiesResolved":not blockers,
    }
    return {
      "format":FORMAT,
      "authority":"exact canonical Nuketown v3 GfxSurface/Material ownership + exact generated final-output runtime-input census + exact GfxWorld lightmap/reflection catalogs",
      "summary":summary,"surfaces":rows,
      "proofBoundary":"Per-draw resource identity only. A resolved row proves which exact GfxImage identity is selected by the surface-owned lightmapIndex/reflectionProbeIndex for a generated shader that samples that exact T6 code sampler. It does not prove the client API call/upload mechanism, sampler filtering/addressing state, hdrControl0 runtime value, reflection coordinate arithmetic, or final framebuffer behavior. Sentinel/null/unmapped selectors remain blockers and are never substituted."
    }

def main():
    ap=argparse.ArgumentParser()
    for n in ("surfaces","catalog","runtime","lightmaps","probes"):ap.add_argument(f"--{n}",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True);ap.add_argument("--strict",action="store_true")
    a=ap.parse_args()
    docs={n:load(getattr(a,n)) for n in ("surfaces","catalog","runtime","lightmaps","probes")}
    d=build(**docs)
    d["sources"]={n:{"path":str(getattr(a,n)),"sha256":sha(getattr(a,n))} for n in docs}
    if a.strict and not d["summary"]["allSampledRuntimeResourceIdentitiesResolved"]:
        raise SystemExit(f"fail-closed runtime sampler blockers: {d['summary']['runtimeSamplerBlockerCounts']}")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps(d["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
