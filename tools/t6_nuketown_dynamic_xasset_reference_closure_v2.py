#!/usr/bin/env python3
"""Close Nuketown's remaining external MapEnt FX alias using direct retail script + typed XAsset proof.

The v1 dynamic-reference proof treated fxanim_fx_* values as direct FX asset names and
therefore left fx_water_fire_sprinkler_thin unresolved. Exact retail script decompilation
proves that alias key maps to loadfx("water/fx_water_fire_sprinkler_thin"). An independent
typed five-root XAsset join proves exactly one FX owner for that qualified target.
This overlay promotes only that exact three-way relation.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,re
from pathlib import Path

V1="t6-nuketown-dynamic-xasset-reference-closure-v1"
SCRIPT="t6-nuketown-sprinkler-fx-decompile-proof-v1"
TYPED="t6-exact-typed-xasset-name-root-join-v1"
FORMAT="t6-nuketown-dynamic-xasset-reference-closure-v2"
ALIAS="fx_water_fire_sprinkler_thin"
QUALIFIED="water/fx_water_fire_sprinkler_thin"
LINE_RE=re.compile(r'^level\._effect\["fx_water_fire_sprinkler_thin"\]\s*=\s*loadfx\(\s*"water/fx_water_fire_sprinkler_thin"\s*\);$')
class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--v1",type=Path,required=True)
    ap.add_argument("--script",type=Path,required=True)
    ap.add_argument("--typed",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    v1=json.loads(a.v1.read_text());sc=json.loads(a.script.read_text());ty=json.loads(a.typed.read_text())
    req(v1.get("format")==V1,"v1 format drift")
    req(sc.get("format")==SCRIPT,"script format drift")
    req(ty.get("format")==TYPED,"typed proof format drift")
    absent=[r for r in v1.get("rows",[]) if r.get("status")=="absent-from-supplied-roots"]
    req(len(absent)==1,"expected exactly one v1 external absence")
    ar=absent[0]
    req(ar.get("kind")=="fx" and ar.get("expectedAssetType")=="FX" and ar.get("name")==ALIAS,"v1 unresolved row changed")
    req(int(sc.get("explicitSameLineMappingCount",-1))==1,"script explicit mapping count drift")
    lines=[x for x in sc.get("sprinklerLines",[]) if LINE_RE.fullmatch(str(x.get("text") or "").strip())]
    req(len(lines)==1,"exact script alias/loadfx expression absent or ambiguous")
    q=ty.get("query",{})
    req(q.get("name")==QUALIFIED and q.get("expectedAssetType")=="FX","typed query drift")
    ts=ty.get("summary",{})
    req(int(ts.get("typedMatchCount",-1))==1 and int(ts.get("sameNameOtherTypeMatchCount",-1))==0,"qualified typed ownership not unique")
    matches=ty.get("typedMatches",[])
    req(len(matches)==1 and matches[0].get("assetTypeName")=="FX" and matches[0].get("name")==QUALIFIED,"typed match drift")

    rows=[]
    for r in v1.get("rows",[]):
        x=copy.deepcopy(r)
        if x.get("status")=="absent-from-supplied-roots":
            x.update({
              "status":"resolved-via-retail-script-loadfx-alias",
              "scriptAlias":ALIAS,
              "qualifiedAssetName":QUALIFIED,
              "scriptMapping":{
                "line":int(lines[0]["line"]),
                "text":lines[0]["text"],
                "scriptBinarySha256":sc["scriptBinary"]["sha256"],
                "decompiledSha256":sc["decompiledSha256"]
              },
              "matches":[copy.deepcopy(matches[0])],
              "sameNameOtherAssetTypes":[]
            })
        rows.append(x)

    direct=sum(r.get("status")=="resolved" for r in rows)
    alias=sum(r.get("status")=="resolved-via-retail-script-loadfx-alias" for r in rows)
    inline=sum(r.get("status")=="inline-brush-model-token" for r in rows)
    unresolved=sum(r.get("status")=="absent-from-supplied-roots" for r in rows)
    external=direct+alias+unresolved
    summary={
      "referenceIdentityCount":len(rows),
      "directTypedXAssetResolvedCount":direct,
      "retailScriptAliasResolvedCount":alias,
      "externalXAssetReferenceCount":external,
      "externalXAssetResolvedCount":direct+alias,
      "unresolvedExternalXAssetReferenceCount":unresolved,
      "inlineBrushModelTokenCount":inline,
      "allExternalXAssetReferencesResolved":unresolved==0
    }
    req(len(rows)==251 and direct==67 and alias==1 and inline==183 and unresolved==0,"closure population drift")
    doc={
      "format":FORMAT,
      "sources":{
        "v1":{"path":str(a.v1),"sha256":sha(a.v1)},
        "scriptAlias":{"path":str(a.script),"sha256":sha(a.script)},
        "qualifiedTypedOwnership":{"path":str(a.typed),"sha256":sha(a.typed)}
      },
      "summary":summary,
      "rows":rows,
      "proofBoundary":"All external MapEnt model/destructible/FX references in the v1 Nuketown reference universe now resolve either by exact typed five-root identity or, for exactly one sprinkler alias, by an explicit exact retail ScriptParseTree decompile alias-to-loadfx expression plus an independent exact typed FX owner for the qualified target. The 183 star-decimal model tokens remain classified as inline brush-model tokens; this proof does not validate their BSP submodel indices or turn them into XMODEL assets."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
