#!/usr/bin/env python3
"""Smoke-test durable Ghidra archiving and reject missing function bodies."""
from __future__ import annotations
import csv, json, subprocess, sys, tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("t6_preserve_ghidra_corpus.py")

def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for i in range(8):
            p = root/"input"/f"shard-{i}"
            (p/"unreviewed").mkdir(parents=True)
            fid = f"urn:ure:t6:occ:function:current-client:{i+1:08x}"
            (p/"unreviewed"/f"{i+1:08x}.c").write_text(
                "/* GENERATED/UNREVIEWED GHIDRA OUTPUT\n"
                " * decompile_completed: true\n */\nvoid f() {}\n")
            (p/"references.tsv").write_text("function_id\tfrom_address\tmnemonic\toperand_index\treference_type\tto_address\ttarget_symbol\ttarget_data_type\n")
            with (p/"results.tsv").open("w",newline="") as f:
                fields = ["function_id","requested_va","decompile_completed","c_bytes","ghidra_name"]
                writer=csv.DictWriter(f,fieldnames=fields,delimiter="\t")
                writer.writeheader()
                writer.writerow({"function_id":fid,"requested_va":f"0x{i+1:08x}",
                                 "decompile_completed":"true","c_bytes":11,
                                 "ghidra_name":f"FUN_{i:08x}"})
        cmd=[sys.executable,str(SCRIPT),"--input-root",str(root/"input"),
             "--output-root",str(root/"out"),"--build","retail",
             "--binary-sha256","a"*64,"--expected-functions","8",
             "--expected-completed","8"]
        good=subprocess.run(cmd,capture_output=True,text=True)
        if good.returncode:
            raise AssertionError(good.stderr)
        m=json.loads((root/"out/retail/manifest.json").read_text())
        assert m["functions"]==8 and m["completed"]==8
        assert len(list((root/"out/retail").glob("shard-*.tar.zst")))==8
        def run_checked(command):
            result=subprocess.run(command,capture_output=True,text=True)
            assert result.returncode==0,(command,result.stdout,result.stderr)
            return result
        run_checked([sys.executable,str(Path(__file__).with_name("t6_reconstruction_worklist.py")),
                     "--corpus",str(root/"out/retail"),"--output",str(root/"jobs.jsonl"),
                     "--type-revision","fixture-types-v1"])
        jobs=[json.loads(s) for s in (root/"jobs.jsonl").read_text().splitlines()]
        assert sum(len(x["functions"]) for x in jobs)==8
        run_checked([sys.executable,str(Path(__file__).with_name("t6_complete_ghidra_graph_projection.py")),
                     "--corpus",str(root/"out/retail"),"--output",str(root/"graph"),
                     "--git-repo","fixture/private","--git-prefix","t6/retail"])
        gm=json.loads((root/"graph/manifest.json").read_text())
        assert gm["functions"]==8 and gm["completed"]==8 and not gm["graph_writes_executed"]
        fetched=run_checked([sys.executable,str(Path(__file__).with_name("t6_retrieve_ghidra_function.py")),
                     "--corpus",str(root/"out/retail"),"--address","0x00000001"])
        assert "void f()" in fetched.stdout
        (root/"input/shard-7/unreviewed/00000008.c").unlink()
        bad=subprocess.run(cmd,capture_output=True,text=True)
        assert bad.returncode!=0,"Missing successful pseudocode did not fail"
        print("PASS: eight shards preserved; missing source rejected")

if __name__=="__main__":
    main()
