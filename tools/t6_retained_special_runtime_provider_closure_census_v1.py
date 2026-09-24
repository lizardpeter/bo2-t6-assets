#!/usr/bin/env python3
"""Fail-closed closure census for retained-special runtime input providers.

The denominator is the exact 37-input static identity proof. A provider is counted
closed only if an explicitly registered proof exists, has the expected format,
names the same accessor/enum, and states current-client provider closure.

Historical-retail equivalence is a separate authority column and is never implied.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-retained-special-runtime-provider-closure-census-v1"
DEN_FMT="t6-retail-special-omitted-code-input-static-identity-v1"
REGISTRY={
 "materialColor":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_MATERIAL_COLOR_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-material-color-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
 },
 "gameTime":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_GAMETIME_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-gametime-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
 },
 "renderTargetSize":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_RENDER_TARGET_SIZE_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-render-target-size-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
 },
 "scriptVector0":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_SCRIPT_VECTOR0_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-script-vector0-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
 },
 "postFxControl6":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_POSTFX_CONTROL6_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-postfx-control6-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
 },
 "viewProjectionMatrix":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_VIEWPROJECTION_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-viewprojection-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
 },
 "worldMatrix":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_WORLDMATRIX_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-worldmatrix-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
 },
 "worldViewProjectionMatrix":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_WORLDVIEWPROJECTION_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-worldviewprojection-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
 },
 "shadowLookupMatrix":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_SHADOWLOOKUP_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-shadowlookup-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
 },
 "lightPosition":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightDiffuse":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightSpotDir":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightSpotFactors":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightFallOffA":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightFallOffB":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightSpotMatrix0":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightSpotMatrix1":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightSpotMatrix2":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightSpotAABB":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightConeControl1":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "lightSpotCookieSlideControl":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_LIGHT_BLOCK_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-light-block-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "shadowmapSamplerSpot":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_SHADOW_SPOT_ATTENUATION_SAMPLER_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-shadow-spot-attenuation-sampler-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "attenuationSampler":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_SHADOW_SPOT_ATTENUATION_SAMPLER_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-shadow-spot-attenuation-sampler-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputsList":True,
 },
 "floatZSampler":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_FLOATZ_SAMPLER_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-floatz-sampler-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputSingle":True,
 },
 "debugPerformance":{
   "path":"proof/current_client/T6_CURRENT_CLIENT_DEBUG_PERFORMANCE_PROVIDER_SEMANTICS_V1.json",
   "format":"t6-current-client-debug-performance-provider-semantics-v1",
   "summaryFlag":"currentClientProviderClosed",
   "runtimeInputSingle":True,
 }
}
def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--denominator",type=Path,required=True);ap.add_argument("--repo-root",type=Path,default=Path("."));ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.denominator.read_text())
    if d.get("format")!=DEN_FMT:raise SystemExit("denominator format drift")
    rows=[]
    for src in d["rows"]:
      acc=src["accessor"];reg=REGISTRY.get(acc);proof=None;status="unresolved";boundary=None
      if reg:
        p=a.repo_root/reg["path"]
        if not p.is_file():raise SystemExit(f"{acc}: registered provider proof missing: {p}")
        proof=json.loads(p.read_text())
        if proof.get("format")!=reg["format"]:raise SystemExit(f"{acc}: provider proof format drift")
        if reg.get("runtimeInputsList"):
          members=[x for x in proof.get("runtimeInputs",[]) if x.get("accessor")==acc]
          if len(members)!=1:
            raise SystemExit(f"{acc}: provider family member count {len(members)}")
          r=members[0]
        else:
          r=proof.get("runtimeInput",{})
        if r.get("accessor")!=acc or int(r.get("enumValue",-1))!=int(src["enumValue"]):
          raise SystemExit(f"{acc}: provider proof identity mismatch")
        if proof.get("summary",{}).get(reg["summaryFlag"]) is not True:
          raise SystemExit(f"{acc}: provider closure flag absent")
        status="current-client-provider-closed"
        boundary=proof.get("proofBoundary")
        proof={"path":reg["path"],"sha256":sha(p),"format":proof["format"]}
      rows.append({
        "accessor":acc,"enumSymbol":src["enumSymbol"],"enumValue":src["enumValue"],
        "sourceClass":src["sourceClass"],"updateFrequency":src["updateFrequency"],
        "totalOccurrences":src["totalOccurrences"],"pixelOccurrences":src["pixelOccurrences"],"vertexOccurrences":src["vertexOccurrences"],
        "providerStatus":status,"providerProof":proof,"providerProofBoundary":boundary,
        "historicalRetailEquivalent":False,
      })
    cc=[x for x in rows if x["providerStatus"]=="current-client-provider-closed"]
    unresolved=[x for x in rows if x["providerStatus"]=="unresolved"]
    summary={
      "runtimeInputAccessorCount":len(rows),
      "currentClientProviderClosedCount":len(cc),
      "unresolvedProviderCount":len(unresolved),
      "currentClientProviderClosurePercent":100.0*len(cc)/len(rows) if rows else 0.0,
      "runtimeInputOccurrenceCount":sum(int(x["totalOccurrences"]) for x in rows),
      "currentClientProviderClosedOccurrenceCount":sum(int(x["totalOccurrences"]) for x in cc),
      "unresolvedProviderOccurrenceCount":sum(int(x["totalOccurrences"]) for x in unresolved),
      "currentClientClosedConstantCount":sum(x["sourceClass"]=="constant" for x in cc),
      "currentClientClosedSamplerCount":sum(x["sourceClass"]=="sampler" for x in cc),
      "historicalRetailEquivalentProviderCount":sum(bool(x["historicalRetailEquivalent"]) for x in rows),
    }
    doc={
      "format":FORMAT,
      "authority":"exact retained-special 37-input denominator + explicitly registered fail-closed provider proofs",
      "denominator":{"path":str(a.denominator),"sha256":sha(a.denominator),"format":d["format"]},
      "summary":summary,"rows":rows,
      "proofBoundary":"A current-client provider closure means the SHA-classified current client exact dataflow/provider semantics are proven for that accessor. It does not imply historical-retail executable equivalence, universal draw-time values, or target-corpus framebuffer equivalence. Unregistered or locator-only evidence remains unresolved."
    }
    if len(rows)!=37:raise SystemExit(f"expected 37 runtime inputs, got {len(rows)}")
    if len(cc)+len(unresolved)!=37:raise SystemExit("closure partition drift")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
