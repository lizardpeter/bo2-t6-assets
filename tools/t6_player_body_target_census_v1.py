#!/usr/bin/env python3
"""Generate fail-closed multiplayer full-body XModel discovery targets from retail viewhands prefixes.

The generated names are search candidates, not retail body identity proof.
Only direct XModel corpus hits may promote them later.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

FORMAT="t6-player-body-target-census-v1"

def load(path:Path):
    d=json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(d,dict): raise ValueError("seed must be a JSON object")
    return d

def sha256(path:Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def build(seed:dict):
    if seed.get("format")!="t6-player-faction-prefix-seeds-v1":
        raise ValueError("unsupported seed format")
    classes=seed.get("classes")
    if not isinstance(classes,list) or not classes or any(not isinstance(x,str) or not x for x in classes):
        raise ValueError("classes must be a non-empty string list")
    if len(set(classes))!=len(classes): raise ValueError("duplicate class")
    factions=seed.get("factions")
    if not isinstance(factions,list) or not factions: raise ValueError("factions missing")
    generated={}
    faction_rows=[]
    seen_prefixes=set()
    for row in factions:
        if not isinstance(row,dict): raise ValueError("invalid faction row")
        faction=row.get("faction"); prefix=row.get("prefix"); vh=row.get("viewhandsEvidence")
        if not isinstance(faction,str) or not faction or not isinstance(prefix,str) or not prefix:
            raise ValueError("faction/prefix missing")
        if prefix in seen_prefixes: raise ValueError(f"duplicate prefix: {prefix}")
        seen_prefixes.add(prefix)
        if not isinstance(vh,list) or not vh: raise ValueError(f"{faction}: viewhandsEvidence missing")
        for name in vh:
            if not isinstance(name,str) or not name.startswith(prefix+"_") or not name.endswith("_viewhands"):
                raise ValueError(f"{faction}: viewhands identity does not support prefix: {name!r}")
        faction_rows.append({"faction":faction,"prefix":prefix,"viewhandsEvidence":list(vh)})
        for cls in classes:
            name=f"{prefix}_{cls}_fb"
            if name in generated: raise ValueError(f"generated duplicate: {name}")
            generated[name]={"faction":faction,"prefix":prefix,"bodyClass":cls,"viewhandsEvidence":list(vh)}
    independent=seed.get("independentlyEnumeratedBodyNames") or []
    if not isinstance(independent,list) or any(not isinstance(x,str) for x in independent):
        raise ValueError("independentlyEnumeratedBodyNames must be a string list")
    if len(set(independent))!=len(independent): raise ValueError("duplicate independently enumerated body")
    unknown=sorted(set(independent)-set(generated))
    if unknown: raise ValueError(f"independently enumerated body outside generated universe: {unknown}")
    independent=set(independent)
    models=[]
    for name in sorted(generated,key=str.casefold):
        g=generated[name]; stronger=name in independent
        models.append({
            "name":name,
            "role":"third-person-player-body",
            "required":False,
            "expectedClass":"multiplayer-full-player-body",
            "faction":g["faction"],
            "bodyClass":g["bodyClass"],
            "prefix":g["prefix"],
            "viewhandsEvidence":g["viewhandsEvidence"],
            "nameEvidence":"independently-enumerated-discovery-target" if stronger else "derived-from-retail-viewhands-prefix-and-class-convention",
            "retailIdentityStatus":"unresolved-until-exact-xmodel-corpus-hit",
            "notes":"Discovery target only. Do not promote this body identity, skeleton, or animation compatibility without an exact retail XModel definition."
        })
    return {
        "format":FORMAT,
        "authority":"candidate-name generation from retained retail multiplayer viewhands prefixes; direct retail XModel proof required for promotion",
        "sourceSeedFormat":seed.get("format"),
        "classes":list(classes),
        "factions":faction_rows,
        "summary":{
            "factionPrefixes":len(faction_rows),
            "viewhandsEvidenceIdentities":sum(len(x["viewhandsEvidence"]) for x in faction_rows),
            "candidateBodies":len(models),
            "independentlyEnumeratedDiscoveryTargets":sum(m["nameEvidence"]=="independently-enumerated-discovery-target" for m in models),
            "derivedOnlyCandidates":sum(m["nameEvidence"]!="independently-enumerated-discovery-target" for m in models),
            "requiredTargets":sum(bool(m["required"]) for m in models),
            "retailResolvedBodies":0
        },
        "models":models,
        "proofBoundary":"Every generated body is non-required and unresolved. Viewhands prove only the faction prefix; the five-class _fb naming convention is a discovery mechanism. Independently enumerated names are still discovery evidence, not retail XModel proof. Promotion requires an exact validated XModel corpus hit."
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    seed=load(a.seeds); out=build(seed)
    out["sourceSeed"]={"path":str(a.seeds),"sha256":sha256(a.seeds)}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
    return 0
if __name__=="__main__": raise SystemExit(main())
