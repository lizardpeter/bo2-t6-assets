#!/usr/bin/env python3
"""Batch-close multiplayer T6 player bodies across a materialized faction corpus.

The batch is discovery-first and fail-closed:
1. generate the 30 candidate body names from the retained prefix seed;
2. scan every supplied expanded stream before promoting anything;
3. deduplicate byte-identical stream copies by SHA-256;
4. block a body if any stream gives an ambiguous inline XModel result;
5. block a body if it has exact definitions in multiple distinct streams;
6. pair a unique exact stream with exactly one hash-distinct retail .ff;
7. run t6_player_body_close_v3 for that body; and
8. regenerate the player-body identity registry from closed proofs only.

Any expanded-stream parse error blocks all promotion because an unread source
could contain a competing definition that changes source precedence.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

FORMAT="t6-player-body-faction-batch-v1"
KNOWN_FACTION_ZONES=[
    "faction_multiteam_sand_mp","faction_multiteam_snow_mp","faction_multiteam_wet_mp","faction_multiteam_mp",
    "faction_seals_snow_mp","faction_seals_wet_mp","faction_seals_mp","faction_isa_sand_mp","faction_isa_mp",
    "faction_pmc_snow_mp","faction_pmc_mp","faction_pla_wet_mp","faction_pla_mp","faction_cd_sand_mp","faction_cd_mp","faction_fbi_mp",
]

def load_module(path:Path,name:str):
    s=importlib.util.spec_from_file_location(name,path)
    if s is None or s.loader is None: raise RuntimeError(f"cannot import {path}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def sha(path:Path):
    h=hashlib.sha256();
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()
def dump(path:Path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return {"path":str(path),"bytes":path.stat().st_size,"sha256":sha(path)}
def collect(roots:list[Path],patterns:list[str]):
    out=[]
    for root in roots:
        if root.is_file(): out.append(root); continue
        if not root.is_dir(): raise FileNotFoundError(root)
        for pat in patterns: out.extend(p for p in root.rglob(pat) if p.is_file())
    return sorted(set(p.resolve() for p in out),key=lambda p:str(p).casefold())
def zone_name(path:Path):
    low=path.name.lower()
    for z in sorted(KNOWN_FACTION_ZONES,key=len,reverse=True):
        if z in low:return z
    n=path.name
    for suffix in (".ff.expanded",".expanded.bin",".expanded","_expanded.bin"):
        if n.lower().endswith(suffix): return n[:-len(suffix)]
    return path.stem
def safe_name(name:str): return re.sub(r"[^A-Za-z0-9_.-]+","_",name)

def default_modules(here:Path,raw_parser:Path):
    return SimpleNamespace(raw=load_module(raw_parser,"t6_body_batch_raw"),probe=load_module(here/"t6_xmodel_target_probe_v1.py","t6_body_batch_probe"),targets=load_module(here/"t6_player_body_target_census_v1.py","t6_body_batch_targets"),closer=load_module(here/"t6_player_body_close_v3.py","t6_body_batch_closer"),registry=load_module(here/"t6_player_body_identity_registry_v1.py","t6_body_batch_registry"))

def _dedupe_streams(paths:list[Path]):
    by_sha={}
    for p in paths:
        digest=sha(p); by_sha.setdefault(digest,[]).append(p)
    rows=[]
    for digest,ps in sorted(by_sha.items()):
        primary=sorted(ps,key=lambda x:str(x).casefold())[0]
        rows.append({"sha256":digest,"path":primary,"duplicates":[str(x) for x in sorted(ps,key=lambda x:str(x).casefold())[1:]],"bytes":primary.stat().st_size,"zoneName":zone_name(primary)})
    return rows

def _fastfile_index(paths:list[Path]):
    idx={}
    for p in paths:
        z=zone_name(p); idx.setdefault(z,{}).setdefault(sha(p),[]).append(p)
    return idx

def run_batch(*,seed_path:Path,expanded_paths:list[Path],fastfile_paths:list[Path],raw_parser_path:Path,out_dir:Path,modules=None):
    here=Path(__file__).resolve().parent; mods=modules or default_modules(here,raw_parser_path); out_dir.mkdir(parents=True,exist_ok=True)
    seed=json.loads(seed_path.read_text(encoding="utf-8-sig")); candidates=mods.targets.build(seed); models=candidates["models"]
    streams=_dedupe_streams(expanded_paths); ffidx=_fastfile_index(fastfile_paths)
    source_rows=[]; source_errors=[]; hits={m["name"]:[] for m in models}; ambiguous={m["name"]:[] for m in models}
    for s in streams:
        p=s["path"]
        try:
            data=p.read_bytes(); front=mods.raw.parse_front(data); blocks=[int(x["bytes"]) for x in front["block_sizes"]]
        except Exception as e:
            source_errors.append({"path":str(p),"sha256":s["sha256"],"zoneName":s["zoneName"],"error":str(e)}); continue
        found=0; amb=0
        for model in models:
            row=mods.probe.probe_name(data,{"name":model["name"],"required":False,"role":"multiplayer_full_body"},mods.raw,blocks)
            if row.get("status")=="exact_inline_xmodel":
                hits[model["name"]].append({"stream":s,"target":row}); found+=1
            elif row.get("status")=="ambiguous_inline_xmodel":
                ambiguous[model["name"]].append({"stream":s,"target":row}); amb+=1
        source_rows.append({"path":str(p),"sha256":s["sha256"],"bytes":s["bytes"],"zoneName":s["zoneName"],"duplicates":s["duplicates"],"exactBodyHits":found,"ambiguousBodyHits":amb})

    body_rows=[]; closed_proofs=[]
    for model in models:
        name=model["name"]; exact=hits[name]; amb=ambiguous[name]
        row={"name":name,"faction":model.get("faction"),"bodyClass":model.get("bodyClass"),"nameEvidence":model.get("nameEvidence"),"exactSourceCount":len(exact),"ambiguousSourceCount":len(amb)}
        if source_errors:
            row.update({"status":"blocked-source-corpus-errors","blocker":"one or more expanded streams could not be parsed, so unique source ownership cannot be proven"}); body_rows.append(row); continue
        if amb:
            row.update({"status":"blocked-ambiguous-inline-xmodel","sources":[{"path":str(x["stream"]["path"]),"sha256":x["stream"]["sha256"]} for x in amb]}); body_rows.append(row); continue
        if not exact:
            row.update({"status":"unresolved-no-inline-definition"}); body_rows.append(row); continue
        if len(exact)!=1:
            row.update({"status":"blocked-multiple-distinct-retail-streams","sources":[{"path":str(x["stream"]["path"]),"sha256":x["stream"]["sha256"],"zoneName":x["stream"]["zoneName"],"fixedRecordSha256":x["target"].get("fixedRecordSha256")} for x in exact]}); body_rows.append(row); continue
        hit=exact[0]; stream=hit["stream"]; z=stream["zoneName"]; ffsets=ffidx.get(z,{})
        if not ffsets:
            row.update({"status":"blocked-missing-fastfile","zoneName":z,"expandedPath":str(stream["path"]),"expandedSha256":stream["sha256"]}); body_rows.append(row); continue
        if len(ffsets)!=1:
            row.update({"status":"blocked-ambiguous-fastfile","zoneName":z,"fastfileHashes":sorted(ffsets)}); body_rows.append(row); continue
        ffsha,ffpaths=next(iter(ffsets.items())); ff=sorted(ffpaths,key=lambda p:str(p).casefold())[0]
        body_out=out_dir/"bodies"/safe_name(name)
        try:
            result=mods.closer.close_body(name=name,zone_name=z,fastfile=ff,expanded=stream["path"],raw_parser_path=raw_parser_path,out_dir=body_out)
        except Exception as e:
            row.update({"status":"blocked-closer-exception","zoneName":z,"error":str(e)}); body_rows.append(row); continue
        row.update({"zoneName":z,"expandedPath":str(stream["path"]),"expandedSha256":stream["sha256"],"fastfilePath":str(ff),"fastfileSha256":ffsha,"closureStatus":result.get("status"),"closureBlockerStage":result.get("blockerStage"),"closureBlocker":result.get("blocker"),"meshPath":result.get("meshPath"),"summary":result.get("summary")})
        proof=result.get("retailProof")
        if result.get("status")=="closed" and isinstance(proof,dict) and isinstance(proof.get("path"),str):
            row["status"]="closed-retail-proof"; row["retailProof"]=proof; closed_proofs.append(Path(proof["path"]))
        else: row["status"]="blocked-closure"
        body_rows.append(row)

    registry=mods.registry.build(candidates,closed_proofs); registry_art=dump(out_dir/"player_body_identity_registry_v1.json",registry)
    summary={
        "candidateBodies":len(models),"uniqueExpandedStreams":len(streams),"sourceErrors":len(source_errors),
        "closedRetailBodies":sum(r["status"]=="closed-retail-proof" for r in body_rows),
        "unresolvedNoInlineDefinition":sum(r["status"]=="unresolved-no-inline-definition" for r in body_rows),
        "multipleDistinctRetailStreams":sum(r["status"]=="blocked-multiple-distinct-retail-streams" for r in body_rows),
        "ambiguousInlineDefinitions":sum(r["status"]=="blocked-ambiguous-inline-xmodel" for r in body_rows),
        "closureBlocked":sum(r["status"]=="blocked-closure" for r in body_rows),
        "registryRetailProven":registry.get("summary",{}).get("retailProvenBodies"),"registryUnresolved":registry.get("summary",{}).get("unresolvedCandidates"),
    }
    out={"format":FORMAT,"authority":"direct scan of caller-supplied hash-distinct expanded retail streams; promotion only through closer-v3","seed":{"path":str(seed_path),"sha256":sha(seed_path)},"rules":{"allSourcesScannedBeforePromotion":True,"identicalExpandedCopiesDeduplicatedBySha256":True,"multipleDistinctSourceDefinitionsBlock":True,"sourceParseErrorBlocksAllPromotion":True,"noZonePrecedenceIsGuessed":True},"summary":summary,"sourceErrors":source_errors,"sources":source_rows,"bodies":body_rows,"registry":registry_art,"proofBoundary":"This batch proves only bodies that have one exact inline XModel definition across the supplied fully readable corpus and one unambiguous paired fastfile. Multiple distinct source definitions are retained as a precedence problem rather than collapsed."}
    dump(out_dir/"player_body_faction_batch_v1.json",out); return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds",type=Path,required=True); ap.add_argument("--expanded-root",type=Path,action="append",default=[]); ap.add_argument("--expanded",type=Path,action="append",default=[]); ap.add_argument("--fastfile-root",type=Path,action="append",default=[]); ap.add_argument("--fastfile",type=Path,action="append",default=[]); ap.add_argument("--raw-parser",type=Path,default=Path(__file__).with_name("t6_raw_xasset_inventory_v2.py")); ap.add_argument("--out-dir",type=Path,required=True); a=ap.parse_args()
    expanded=list(a.expanded)+collect(a.expanded_root,["*.expanded","*.expanded.bin","*_expanded.bin"]); fastfiles=list(a.fastfile)+collect(a.fastfile_root,["*.ff"])
    if not expanded: raise SystemExit("no expanded streams supplied");
    if not fastfiles: raise SystemExit("no source fastfiles supplied")
    out=run_batch(seed_path=a.seeds,expanded_paths=expanded,fastfile_paths=fastfiles,raw_parser_path=a.raw_parser,out_dir=a.out_dir)
    print(json.dumps(out["summary"],indent=2,sort_keys=True)); return 2 if out["summary"]["sourceErrors"] else 0
if __name__=="__main__": raise SystemExit(main())
