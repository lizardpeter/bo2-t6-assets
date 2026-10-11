#!/usr/bin/env python3
"""Retrieve one exact Ghidra pseudocode body from a durable T6 Git archive.

Example:
 python3 tools/t6_retrieve_ghidra_function.py --corpus ./t6/ghidra-12.1.3/retail-77031817 --address 0x00401600
"""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys, tarfile
from pathlib import Path

def find_source(archive:Path, member_name:str):
    p=subprocess.Popen(["zstd","-dc",str(archive)],stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=p.stdout,mode="r|") as tf:
            for member in tf:
                if member.name!=member_name:
                    continue
                f=tf.extractfile(member)
                if f is None:
                    raise RuntimeError(f"Missing file data for {member_name}")
                body=f.read()
                # Drain the decompressor to allow its integrity check to finish.
                for _ in tf:
                    pass
                if p.wait()!=0:
                    raise RuntimeError("Failed to decompress original Ghidra archive")
                return body
        if p.wait()!=0:
            raise RuntimeError("Failed to decompress original Ghidra archive")
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
    raise FileNotFoundError(member_name)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus",type=Path,required=True)
    parser.add_argument("--address",required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    address=args.address.lower().removeprefix("0x")
    if not re.fullmatch("[0-9a-f]{1,8}",address):
        parser.error("Expected a 32-bit hexadecimal virtual address")
    address=address.zfill(8)
    manifest=json.loads((args.corpus/"manifest.json").read_text())
    stem="current-client" if manifest["build"]=="retail" else "pc-server"
    target=f"urn:ure:t6:occ:function:{stem}:{address}"
    rows=(json.loads(s) for s in (args.corpus/"functions.jsonl").read_text().splitlines())
    row=next((r for r in rows if r["id"]==target),None)
    if row is None:
        parser.error(f"Function {target} is not in the preserved corpus")
    archive=args.corpus/row["source_archive"]
    sha=hashlib.sha256(archive.read_bytes()).hexdigest()
    shard=next((s for s in manifest["shards"] if s["archive"]==row["source_archive"]),None)
    if shard is None or sha!=shard["sha256"]:
        raise ValueError("Permanent archive hash mismatch")
    data=find_source(archive,f"unreviewed/{address}.c")
    if hashlib.sha256(data).hexdigest()!=row["sha256"]:
        raise ValueError("Function pseudocode hash mismatch")
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(data)
    else:
        sys.stdout.buffer.write(data)
    print(json.dumps({"binary":manifest["build"],"function":target,"sha256":row["sha256"],
                      "decompilation_success":row["decompiled"],"archive":row["source_archive"]}),
          file=sys.stderr)

if __name__=="__main__":
    main()
