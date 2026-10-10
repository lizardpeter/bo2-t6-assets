#!/usr/bin/env python3
"""Generate reproducible, PDB-aware AI C++ reconstruction worklists for T6.

This plans work only; it does not claim LLM execution, compilation or parity.
Consumes the functions.jsonl emitted by t6_preserve_ghidra_corpus.py and the
per-shard references.tsv inside the permanent archives.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, io, json, re, subprocess, tarfile
from pathlib import Path

def normalize_address(value):
    try:
        return int(value.strip().removeprefix("0x"),16)
    except (ValueError,AttributeError):
        return None

def read_tar_member(archive, member_name):
    proc=subprocess.Popen(["zstd","-dc",str(archive)],stdout=subprocess.PIPE)
    result=None
    try:
        with tarfile.open(fileobj=proc.stdout,mode="r|") as tar:
            for member in tar:
                if member.name==member_name:
                    entry=tar.extractfile(member)
                    result=entry.read() if entry else None
        status=proc.wait()
        if status:
            raise RuntimeError(f"zstd failed: {archive}")
        return result
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

def owner(name):
    if name.startswith(("FUN_","thunk_FUN_")):
        return "unknown"
    if "::" in name:
        return name.split("::",1)[0]
    if "_" in name:
        return name.split("_",1)[0]
    return "unclassified"

def plan(corpus, output, batch_size, type_revision, per_shard_ids):
    manifest=json.loads((corpus/"manifest.json").read_text())
    rows=[json.loads(line) for line in (corpus/"functions.jsonl").read_text().splitlines()]
    if len(rows)!=manifest["functions"]:
        raise ValueError("Function count does not match archive manifest")
    if manifest["build"]=="server":
        sidecar=corpus/manifest["sidecar"]["archive"]
        pdb=read_tar_member(sidecar,"pdb/functions.tsv")
        symbols=read_tar_member(sidecar,"map/CoDMPServer_PC.symbols.csv.gz")
        if pdb is None or symbols is None:
            raise ValueError("Complete PDB/MAP data required for server reconstruction")
        pdb_by_va={}
        for item in csv.DictReader(io.StringIO(pdb.decode("utf-8")),delimiter="\\t"):
            pdb_by_va[normalize_address(item["entry_va"])]=item
        map_by_va={}
        for item in csv.DictReader(io.StringIO(gzip.decompress(symbols).decode("utf-8"))):
            if item["is_function"]!="True":
                continue
            va=int(item["va"])
            if va not in map_by_va or (item.get("object") and not map_by_va[va].get("object")):
                map_by_va[va]=item
        for row in rows:
            va=normalize_address(row["address"])
            pdb_row=pdb_by_va.get(va,{})
            map_row=map_by_va.get(va,{})
            row["pdb_name"]=pdb_row.get("qualified_name","")
            row["pdb_signature"]=pdb_row.get("function_signature","")
            row["pdb_source"]=pdb_row.get("symbol_source","")
            row["map_object"]=map_row.get("object","")
            row["map_library"]=map_row.get("library","")
    by_id={r["id"]:r for r in rows}
    if len(by_id)!=len(rows):
        raise ValueError("Duplicated function IDs")
    address_to_id={normalize_address(r["address"]):r["id"] for r in rows}
    incoming=collections.Counter()
    callees=collections.defaultdict(set)
    calls_processed=0
    for shard in manifest["shards"]:
        archive=corpus/shard["archive"]
        if not archive.exists():
            raise ValueError(f"Missing durable evidence: {archive}")
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=shard["sha256"]:
            raise ValueError(f"SHA mismatch: {archive}")
        raw=read_tar_member(archive,"references.tsv")
        if raw is None:
            raise ValueError(f"Missing function references: {archive}")
        for ref in csv.DictReader(io.StringIO(raw.decode("utf-8")),delimiter="\t"):
            if "CALL" not in ref["reference_type"].upper():
                continue
            src=ref["function_id"]
            dst=address_to_id.get(normalize_address(ref["to_address"]))
            if src not in by_id or dst is None or src==dst:
                continue
            if dst not in callees[src]:
                callees[src].add(dst)
                incoming[dst]+=1
            calls_processed+=1
    groups=collections.defaultdict(list)
    for row in rows:
        if not row["decompiled"]:
            continue
        row["owner"]=row.get("map_object") or owner(row.get("pdb_name") or row["ghidra_name"])
        groups[row["owner"]].append(row)
    tasks=[]
    for subsystem,functions in groups.items():
        functions.sort(key=lambda r:(-incoming[r["id"]],r["bytes"],r["id"]))
        for start in range(0,len(functions),batch_size):
            chunk=functions[start:start+batch_size]
            ids={r["id"] for r in chunk}
            external=sorted(set().union(*(callees.get(r["id"],set()) for r in chunk))-ids)
            inputs=[{"id":r["id"],"address":r["address"],"pseudocode_sha256":r["sha256"],
                     "ghidra_name":r["ghidra_name"],"bytes":r["bytes"],\n                     "pdb_name":r.get("pdb_name",""),"pdb_signature":r.get("pdb_signature",""),\n                     "pdb_source":r.get("pdb_source",""),"map_object":r.get("map_object",""),
                     "source_archive":next(s["archive"] for s in manifest["shards"]
                         if r["id"] in per_shard_ids[s["archive"]])}
                    for r in chunk]
            # No model output can be accepted solely on successful generation.
            key=hashlib.sha256(json.dumps({"inputs":inputs,"type_revision":type_revision},
                           sort_keys=True).encode()).hexdigest()
            tasks.append({"task_id":key[:24],"cache_key":key,
                          "source_binary_sha256":manifest["binary_sha256"],
                          "type_revision":type_revision,"subsystem":subsystem,
                          "stage":"ai_cpp_candidate","status":"queued",
                          "functions":inputs,"dependency_function_ids":external[:256],
                          "dependency_count":len(external),
                          "required_outputs":["cpp_patch","type_hypotheses_with_evidence",
                                              "missing_dependencies","tests"],
                          "acceptance_gates":["compiler","ABI","differential_behavior"],
                          "priority_score":sum(incoming[r["id"]] for r in chunk)
                            +sum(not r["ghidra_name"].startswith("FUN_") for r in chunk)*5})
    tasks.sort(key=lambda x:(-x["priority_score"],x["subsystem"],x["task_id"]))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task,sort_keys=True)+"\n")
    result={"tasks":len(tasks),"functions_queued":sum(len(t["functions"]) for t in tasks),
            "decompilation_failures":manifest["failed"],"direct_calls_parsed":calls_processed,
            "average_functions_per_batch":round(sum(len(t["functions"]) for t in tasks)/max(1,len(tasks)),1)}
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--batch-size",type=int,default=32)
    p.add_argument("--type-revision",required=True)
    args=p.parse_args()
    if args.batch_size<1 or args.batch_size>64:
        p.error("Batch size must be between 1 and 64")
    # One initial pass builds membership without decompressing the whole corpus.
    manifest=json.loads((args.corpus/"manifest.json").read_text())
    rows=[json.loads(s) for s in (args.corpus/"functions.jsonl").read_text().splitlines()]
    per_shard_ids={}
    for shard in manifest["shards"]:
        contents=read_tar_member(args.corpus/shard["archive"],"results.tsv")
        if contents is None: raise ValueError("Missing shard function inventory")
        per_shard_ids[shard["archive"]]={r["function_id"] for r in
             csv.DictReader(io.StringIO(contents.decode("utf-8")),delimiter="\t")}
    plan(args.corpus,args.output,args.batch_size,args.type_revision,per_shard_ids)
