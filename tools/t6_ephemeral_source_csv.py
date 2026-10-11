#!/usr/bin/env python3
"""Export exact existing T6 Ghidra artifacts into temporary private-transfer CSVs.

No original executable is imported. Every pseudocode row is tied to its exact
binary, function entry and SHA256; failures are tracked in manifest counts.
"""
import argparse,csv,hashlib,json,os,pathlib,subprocess,tarfile,zipfile
from collections import defaultdict

RETAIL_BUILD="urn:ure:t6:re_Build:current-client-sha77031817"
SERVER_BUILD="urn:ure:t6:re_Build:urn_ure_t6_core_Project_black-ops-2_fd2705692f16c05f_pc-server-2013-03-11:4ee9a1fac7aa9195"
EXE={
"retail":"770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf",
"server":"f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d",
}
FIELDS=["subject_id","rep_id","build_id","address_start","ghidra_name",
        "content_sha256","size_bytes","source_text","source_chunked","exe_sha256"]
CHUNK_FIELDS=["rep_id","chunk_id","sequence","source_text","content_sha256"]

def read_tsv(path):
    with path.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f,delimiter="\t"))

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

class CSVWriter:
    def __init__(self,root,kind,build,fields,max_rows):
        self.root=root
        self.kind=kind
        self.build=build
        self.fields=fields
        self.max_rows=max_rows
        self.file=None
        self.writer=None
        self.written=0
        self.total=0
        self.files=[]
    def emit(self,data):
        if self.file is None or self.written>=self.max_rows:
            if self.file:
                self.file.close()
            path=self.root/self.build/f"{self.kind}-{len(self.files):04d}.csv"
            path.parent.mkdir(parents=True,exist_ok=True)
            self.file=path.open("w",encoding="utf-8",newline="")
            self.writer=csv.DictWriter(self.file,fieldnames=self.fields,lineterminator="\n")
            self.writer.writeheader()
            self.files.append(path)
            self.written=0
        self.writer.writerow(data)
        self.written+=1
        self.total+=1
    def finish(self):
        if self.file:
            self.file.close()
        return self.files

def run(retail_root,server_root,out,rows_per_file,limit):
    out.mkdir(parents=True,exist_ok=True)
    manifest=[]
    all_summary={}
    for build,root in (("retail",retail_root),("server",server_root)):
        writer=CSVWriter(out,"functions",build,FIELDS,rows_per_file)
        chunks=CSVWriter(out,"chunks",build,CHUNK_FIELDS,rows_per_file*4)
        seen=set()
        selected=0
        success=0
        failures=[]
        num_shards=0
        expected_shards=[str(i) for i in range(8)] if build=="retail" else [f"{i:02d}" for i in range(8)]
        for i in expected_shards:
            name=("t6-enriched-full-v1-shard-"+i if build=="retail" else "t6-full-pc-ghidra-decompile-"+i)
            p=root/name
            assert p.is_dir(),f"Missing artifact {p}"
            if build=="retail":
                tarball=p/"bundle.tar.zst"
                assert tarball.is_file()
                expected=(p/"bundle.sha256").read_text().split()[0]
                assert sha(tarball.read_bytes())==expected
                expanded=out/"_source"/name
                expanded.mkdir(parents=True,exist_ok=True)
                subprocess.run(["tar","-I","zstd","-xf",str(tarball),"-C",str(expanded)],check=True)
                data=expanded/"batch"
                assert data.is_dir()
            else:
                data=p
            rows=read_tsv(data/"results.tsv")
            num_shards+=1
            for row in rows:
                selected+=1
                va=row["requested_va"].lower().removeprefix("0x").zfill(8)
                assert len(va)==8 and va not in seen,(build,va)
                seen.add(va)
                ok=row["decompile_completed"]=="true"
                if not ok:
                    failures.append({"address":va,"name":row.get("ghidra_name",""),"error":row.get("decompiler_message","")})
                    continue
                source=data/"unreviewed"/(va+".c")
                assert source.is_file(),f"Missing pseudocode {source}"
                raw=source.read_bytes()
                text=raw.decode("utf-8")
                assert raw and "GENERATED/UNREVIEWED GHIDRA OUTPUT" in text
                assert "decompile_completed: true" in text
                assert len(raw)>=int(row["c_bytes"])
                h=sha(raw)
                subject=f"urn:ure:t6:occ:function:{'current-client' if build=='retail' else 'server-2013-03-11'}:{va}"
                rep=f"urn:ure:t6:representation:pseudocode:c:ghidra:{build}:{va}:{h}"
                chunked=len(text)>12000
                writer.emit({
                    "subject_id":subject,"rep_id":rep,
                    "build_id":RETAIL_BUILD if build=="retail" else SERVER_BUILD,
                    "address_start":"0x"+va,"ghidra_name":row["ghidra_name"],
                    "content_sha256":h,"size_bytes":len(raw),
                    "source_text":"" if chunked else text,
                    "source_chunked":"true" if chunked else "false",
                    "exe_sha256":EXE[build],
                })
                if chunked:
                    for index,start in enumerate(range(0,len(text),12000)):
                        segment=text[start:start+12000]
                        chunks.emit({"rep_id":rep,"chunk_id":rep+":chunk:"+str(index),
                            "sequence":index,"source_text":segment,
                            "content_sha256":sha(segment.encode("utf-8"))})
                success+=1
                if limit and selected>=limit:
                    break
            if limit and selected>=limit:
                break
        files=writer.finish()+chunks.finish()
        expected=(24617,24612) if build=="retail" else (27734,27730)
        if not limit:
            assert (selected,success)==expected,(build,selected,success,expected)
        all_summary[build]={"selected":selected,"success":success,"failures":failures,
                            "file_count":len(files),"chunks":chunks.total}
        for path in files:
            rel=path.relative_to(out).as_posix()
            manifest.append({"path":rel,"build":build,
                             "kind":"chunk" if "/chunks-" in rel else "function",
                             "rows":sum(1 for _ in csv.DictReader(path.open(encoding="utf-8",newline=""))),
                             "sha256":sha(path.read_bytes())})
        print(json.dumps({"build":build,"total":selected,"successful":success,"csv_files":len(files)}),flush=True)
    with (out/"index.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["path","build","kind","rows","sha256"])
        w.writeheader();w.writerows(manifest)
    (out/"summary.json").write_text(json.dumps(all_summary,indent=2)+"\n",encoding="utf-8")
    return all_summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--retail",type=pathlib.Path,required=True)
    p.add_argument("--server",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    p.add_argument("--rows-per-file",type=int,default=200)
    p.add_argument("--limit",type=int,default=0)
    a=p.parse_args()
    run(a.retail,a.server,a.out,a.rows_per_file,a.limit)
