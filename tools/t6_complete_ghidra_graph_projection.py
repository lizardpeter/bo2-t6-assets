#!/usr/bin/env python3
"""Produce bounded, full-text uregraph Cypher projections from durable T6 Ghidra archives.

All original C-like pseudocode is stored as source text or as ordered source
chunks. Unreviewed Ghidra output is NEVER promoted to reconstructed C++.
Original builds remain distinct; cross-build identity is not inferred here.
This tool generates queries but does NOT automatically execute graph writes.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, re, subprocess, tarfile
from pathlib import Path

BUILD_ID = {
    "retail": "urn:ure:t6:re_Build:current-client-sha77031817",
    "server": "urn:ure:t6:re_Build:urn_ure_t6_core_Project_black-ops-2_fd2705692f16c05f_pc-server-2013-03-11:4ee9a1fac7aa9195",
}
FUNC_RE = re.compile(r"([0-9a-fA-F]{8})$")

def q(value):
    return json.dumps(value, ensure_ascii=True)

def cmap(item):
    return "{" + ",".join(f"{key}:{q(value)}" for key,value in item.items()) + "}"

def hash_file(path):
    d = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1<<20), b""):
            d.update(part)
    return d.hexdigest()

def stream_tar(archive):
    process = subprocess.Popen(["zstd","-dc",str(archive)],stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout,mode="r|") as tf:
            for member in tf:
                if not member.isfile():
                    continue
                f = tf.extractfile(member)
                if f is not None:
                    yield member.name, f.read()
        if process.wait() != 0:
            raise RuntimeError(f"zstd failed on {archive}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

def canonical_function(build, va):
    stem = "current-client" if build=="retail" else "server-2013-03-11"
    return f"urn:ure:t6:occ:function:{stem}:{va}"

def flush(output, number, rows, kind="functions"):
    if not rows:
        return number
    p=output/f"{kind}_{number:05d}.cypher"
    payload="["+",".join(map(cmap,rows))+"]"
    if kind=="functions":
        query=f"""WITH {payload} AS rows
UNWIND rows AS row
MERGE (f:KGNode {{id:row.id}})
ON CREATE SET f.kind='re:FunctionOccurrence', f.namespace='t6'
SET f.build_id=row.build_id,
    f.address_start=row.address_start,
    f.source_export_id=row.export_id,
    f.ghidra_name=row.ghidra_name,
    f.ghidra_decompile_completed=row.success,
    f.ghidra_evidence_state=CASE WHEN row.success THEN 'generated-unreviewed-completed' ELSE 'generated-unreviewed-failed' END,
    f.ghidra_pseudocode_sha256=CASE WHEN row.success THEN row.source_sha256 ELSE f.ghidra_pseudocode_sha256 END
WITH f,row
FOREACH (_ IN CASE WHEN row.success THEN [1] ELSE [] END |
    MERGE (r:KGNode {{id:row.rep_id}})
    ON CREATE SET r.kind='core:Representation', r.namespace='t6'
    SET r.representation_type='pseudocode:c:ghidra',
        r.language='c-like',
        r.producer='Ghidra',
        r.producer_version='12.1.3',
        r.build_id=row.build_id,
        r.subject_id=row.id,
        r.content_sha256=row.source_sha256,
        r.size_bytes=row.source_bytes,
        r.source_text=CASE WHEN row.chunked THEN coalesce(r.source_text,'') ELSE row.source_text END,
        r.source_chunked=row.chunked,
        r.git_repo=row.git_repo,
        r.git_archive_path=row.archive_path,
        r.git_archive_member=row.archive_member,
        r.generated_unreviewed=true
    MERGE (f)-[:\x60core:HAS_REPRESENTATION\x60]->(r)
)
"""
    else:
        query=f"""WITH {payload} AS rows
UNWIND rows AS row
MATCH (r:KGNode {{id:row.rep_id}})
MERGE (c:KGNode {{id:row.chunk_id}})
ON CREATE SET c.kind='re:SourceChunk', c.namespace='t6'
SET c.sequence=row.sequence,
    c.source_text=row.source_text,
    c.content_sha256=row.sha256,
    c.parent_representation_id=row.rep_id
MERGE (r)-[:HAS_SOURCE_CHUNK]->(c)
"""
    p.write_text(query,encoding="utf-8")
    return number+1

def generate(corpus,out,git_repo,git_prefix,source_char_limit,byte_budget):
    manifest=json.loads((corpus/"manifest.json").read_text())
    build=manifest["build"]
    id_to_index={x["id"]:x for x in (json.loads(s) for s in
        (corpus/"functions.jsonl").read_text(encoding="utf-8").splitlines())}
    if len(id_to_index)!=manifest["functions"]:
        raise ValueError("Incomplete or duplicated function index")
    out.mkdir(parents=True,exist_ok=True)
    all_seen=set()
    total_completed=0
    total_chunks=0
    query_count=0
    manifests=[]
    for shard in manifest["shards"]:
        path=corpus/shard["archive"]
        if hash_file(path)!=shard["sha256"]:
            raise ValueError(f"Archive integrity failure: {path}")
        rows=[]
        chunks=[]
        batch_bytes=0
        chunk_bytes=0
        processed=0
        success=0
        evidence_id="urn:ure:t6:evidence:durable-ghidra:"+build+":"+shard["sha256"]
        corpus_query=(f"MERGE (e:KGNode {{id:{q(evidence_id)}}})\n"
                      f"SET e.kind='re:Evidence', e.namespace='t6',\n"
                      f"e.build_id={q(BUILD_ID[build])}, e.binary_sha256={q(manifest['binary_sha256'])},\n"
                      f"e.archive_sha256={q(shard['sha256'])}, e.archive_path={q(git_prefix+'/'+build+'/'+shard['archive'])},\n"
                      f"e.git_repo={q(git_repo)}, e.status='generated-unreviewed',\n"
                      f"e.complete_shard_count={shard['functions']},e.completed_shard_count={shard['completed']}\n")
        (out/("corpus_"+shard["name"]+".cypher")).write_text(corpus_query,encoding="utf-8")
        for name,raw in stream_tar(path):
            if not name.startswith("unreviewed/") or not name.endswith(".c"):
                continue
            va_match=FUNC_RE.search(Path(name).stem)
            if va_match is None:
                raise ValueError(f"Invalid pseudocode member: {name}")
            va=va_match.group(1).lower()
            export_id=(f"urn:ure:t6:occ:function:current-client:{va}" if build=="retail"
                       else f"urn:ure:t6:occ:function:pc-server:{va}")
            record=id_to_index.get(export_id)
            if record is None or export_id in all_seen:
                raise ValueError(f"Duplicate/unknown function: {export_id}")
            all_seen.add(export_id)
            text=raw.decode("utf-8")
            sha=hashlib.sha256(raw).hexdigest()
            if sha!=record["sha256"]:
                raise ValueError(f"Source content changed: {export_id}")
            success_flag=bool(record["decompiled"])
            success+=int(success_flag)
            processed+=1
            rep_id=(f"urn:ure:t6:representation:pseudocode:c:ghidra:{va}:{sha}"
                if build=="retail" else
                f"urn:ure:t6:representation:pseudocode:c:ghidra:server-2013-03-11:{va}:{sha}")
            chunked=success_flag and len(text)>source_char_limit
            row={
                "id":canonical_function(build,va),
                "export_id":export_id,
                "build_id":BUILD_ID[build],
                "address_start":"0x"+va.upper(),
                "ghidra_name":record["ghidra_name"],
                "success":success_flag,
                "rep_id":rep_id,
                "source_sha256":sha,
                "source_bytes":len(raw),
                "source_text":"" if chunked or not success_flag else text,
                "chunked":chunked,
                "git_repo":git_repo,
                "archive_path":git_prefix+"/"+shard["archive"],
                "archive_member":name
            }
            encoded=len(cmap(row).encode("utf-8"))
            if rows and (len(rows)>=12 or batch_bytes+encoded>byte_budget):
                query_count=flush(out,query_count,rows)
                rows=[]
                batch_bytes=0
            rows.append(row)
            batch_bytes+=encoded
            if chunked:
                for i in range(0,len(text),source_char_limit):
                    part=text[i:i+source_char_limit]
                    csha=hashlib.sha256(part.encode("utf-8")).hexdigest()
                    chunk={"rep_id":rep_id,"chunk_id":rep_id+":chunk:"+str(i//source_char_limit),
                           "sequence":i//source_char_limit,
                           "source_text":part,"sha256":csha}
                    encoded=len(cmap(chunk).encode("utf-8"))
                    if chunks and (len(chunks)>=8 or chunk_bytes+encoded>byte_budget):
                        query_count=flush(out,query_count,chunks,"chunks")
                        chunks=[]
                        chunk_bytes=0
                    chunks.append(chunk)
                    chunk_bytes+=encoded
                    total_chunks+=1
        query_count=flush(out,query_count,rows)
        query_count=flush(out,query_count,chunks,"chunks")
        if processed!=shard["functions"] or success!=shard["completed"]:
            raise ValueError(f"Incomplete shard {shard['name']}: {processed} / {success}")
        total_completed+=success
        manifests.append({"shard":shard["name"],"functions":processed,
                          "completed":success,"archive_sha256":shard["sha256"]})
    if len(all_seen)!=manifest["functions"] or total_completed!=manifest["completed"]:
        raise ValueError("Incomplete full-archive projection")
    summary={"format":"t6-full-corpus-uregraph-projection-v1","build":build,
        "functions":len(all_seen),"completed":total_completed,
        "source_chunks":total_chunks,"cypher_batches":query_count,
        "source_git_repo":git_repo,"source_git_prefix":git_prefix,
        "projection_only":True,"graph_writes_executed":False,
        "provenance":"Generated unreviewed pseudocode, not validated C++",
        "shards":manifests}
    (out/"manifest.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--git-repo",required=True)
    p.add_argument("--git-prefix",required=True)
    p.add_argument("--source-char-limit",type=int,default=12000)
    p.add_argument("--query-budget-bytes",type=int,default=100000)
    a=p.parse_args()
    if a.source_char_limit<1024 or a.source_char_limit>16000:
        p.error("source-char-limit must be between 1024 and 16000")
    if a.query_budget_bytes<32000 or a.query_budget_bytes>200000:
        p.error("query-budget-bytes must be between 32000 and 200000")
    generate(a.corpus,a.output,a.git_repo,a.git_prefix,
             a.source_char_limit,a.query_budget_bytes)

if __name__=="__main__":
    main()
