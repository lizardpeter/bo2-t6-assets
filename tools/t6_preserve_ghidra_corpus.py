#!/usr/bin/env python3
"""Preserve complete T6 Ghidra function output as verified, Git-sized shards.

Input dirs are ExportT6*Batch results: results.tsv, references.tsv and
unreviewed/<function>.c. Missing or duplicated functions fail the entire job.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, re, subprocess, tarfile, tempfile
from pathlib import Path

ID = re.compile(r"^[A-Za-z0-9._:-]+$")
SHA = re.compile(r"^[0-9a-f]{64}$")

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def pack(paths, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "payload.tar"
        with tarfile.open(src, "w", format=tarfile.PAX_FORMAT) as archive:
            for path, name in sorted(paths, key=lambda x: x[1]):
                body = path.read_bytes()
                info = tarfile.TarInfo(name)
                info.size, info.mtime, info.uid, info.gid = len(body), 0, 0, 0
                info.uname, info.gname, info.mode = "", "", 0o644
                archive.addfile(info, io.BytesIO(body))
        subprocess.run(["zstd","-q","-f","-19","-T0",str(src),"-o",str(output)],check=True)
    return digest(output)

def archive_shard(shard, out, with_asm):
    with (shard/"results.tsv").open(encoding="utf-8",newline="") as f:
        rows = list(csv.DictReader(f,delimiter="\t"))
    if not rows:
        raise ValueError(f"Empty results: {shard}")
    included = [(shard/"results.tsv","results.tsv")]
    for optional in ("references.tsv","summary.json","selection.tsv"):
        path = shard/optional
        if path.is_file():
            included.append((path,optional))
    seen, index = set(), []
    for row in rows:
        fid = row["function_id"]
        if not ID.fullmatch(fid) or fid in seen:
            raise ValueError(f"Unsafe or duplicated ID: {fid}")
        seen.add(fid)
        name = fid.rsplit(":",1)[-1]
        src = shard/"unreviewed"/(name+".c")
        if not src.is_file():
            raise ValueError(f"Missing pseudocode: {src}")
        code = src.read_bytes()
        complete = row["decompile_completed"]=="true"
        if complete and (int(row["c_bytes"])<=0 or
                         b"decompile_completed: true" not in code or
                         len(code)<int(row["c_bytes"])):
            raise ValueError(f"Missing/truncated successful decompilation: {fid}")
        included.append((src,"unreviewed/"+name+".c"))
        asm = shard/"disassembly"/(name+".asm")
        if with_asm and asm.is_file():
            included.append((asm,"disassembly/"+name+".asm"))
        index.append({"id":fid,"address":row["requested_va"],"decompiled":complete,
                      "sha256":hashlib.sha256(code).hexdigest(),"bytes":len(code),
                      "ghidra_name":row["ghidra_name"]})
    output = out/(shard.name+".tar.zst")
    sha = pack(included,output)
    completed = sum(x["decompiled"] for x in index)
    return ({"name":shard.name,"functions":len(rows),"completed":completed,
             "failed":len(rows)-completed,"archive":output.name,
             "sha256":sha,"bytes":output.stat().st_size},index)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-root",required=True,type=Path)
    p.add_argument("--output-root",required=True,type=Path)
    p.add_argument("--build",required=True,choices=("retail","server"))
    p.add_argument("--binary-sha256",required=True)
    p.add_argument("--expected-functions",required=True,type=int)
    p.add_argument("--expected-completed",required=True,type=int)
    p.add_argument("--sidecar-root",type=Path)
    p.add_argument("--include-assembly",action="store_true")
    a=p.parse_args()
    if not SHA.fullmatch(a.binary_sha256):
        p.error("Invalid original binary SHA256")
    shards=sorted(x for x in a.input_root.iterdir() if x.is_dir() and x.name.startswith("shard-"))
    if len(shards)!=8:
        raise ValueError(f"Expected 8 shards, got {len(shards)}")
    output=a.output_root/a.build
    output.mkdir(parents=True,exist_ok=True)
    summaries, indexes, seen = [], [], set()
    for shard in shards:
        summary, rows = archive_shard(shard,output,a.include_assembly)
        if any(row["id"] in seen for row in rows):
            raise ValueError(f"Duplicate function across shards: {shard}")
        seen.update(row["id"] for row in rows)
        summaries.append(summary)
        indexes.extend(rows)
    completed=sum(s["completed"] for s in summaries)
    if len(indexes)!=a.expected_functions or completed!=a.expected_completed:
        raise ValueError(f"Coverage mismatch: {len(indexes)}/{completed} vs "
                         f"{a.expected_functions}/{a.expected_completed}")
    manifest={"format":"t6-durable-ghidra-corpus-v1","build":a.build,
              "binary_sha256":a.binary_sha256,"functions":len(indexes),
              "completed":completed,"failed":len(indexes)-completed,
              "shards":summaries,
              "classification":"Unreviewed Ghidra output, not verified source"}
    if a.sidecar_root:
        sidefiles=sorted(f for f in a.sidecar_root.rglob("*") if f.is_file())
        if not sidefiles:
            raise ValueError("Missing PDB/MAP sidecar")
        dst=output/"pdb-map-and-type-evidence.tar.zst"
        sha=pack([(f,f.relative_to(a.sidecar_root).as_posix()) for f in sidefiles],dst)
        manifest["sidecar"]={"files":len(sidefiles),"archive":dst.name,
                             "sha256":sha,"bytes":dst.stat().st_size}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    with (output/"functions.jsonl").open("w",encoding="utf-8") as f:
        for row in sorted(indexes,key=lambda x:x["id"]):
            f.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
    print(json.dumps({"build":a.build,"functions":len(indexes),"completed":completed},indent=2))

if __name__=="__main__":
    main()
