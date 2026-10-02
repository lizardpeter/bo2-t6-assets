#!/usr/bin/env python3
"""Parse the pinned CoDMPServer_PC MSVC linker MAP into function-start evidence.

This intentionally emits only the fields needed by the conservative
current-client -> server anchor-call propagation. The MAP remains cross-build
evidence only; this script never assigns retail semantic identity.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
from collections import defaultdict
from pathlib import Path

FORMAT="t6-msvc-map-function-symbols-v1"

SECTION_RE=re.compile(
    r"^\s*(?P<segment>[0-9A-Fa-f]{4}):(?P<offset>[0-9A-Fa-f]{8})\s+"
    r"(?P<length>[0-9A-Fa-f]{8})H\s+(?P<name>\S+)\s+(?P<class>\S+)\s*$"
)
SYMBOL_RE=re.compile(
    r"^\s*(?P<segment>[0-9A-Fa-f]{4}):(?P<offset>[0-9A-Fa-f]{8})\s+"
    r"(?P<name>\S+)\s+(?P<va>[0-9A-Fa-f]{8})\s*(?P<trailer>.*)$"
)

def split_origin(origin:str)->tuple[str,str]:
    if not origin or origin.startswith("<"):
        return "",origin
    if ":" in origin:
        lib,obj=origin.split(":",1)
        return lib.strip(),obj.strip()
    return "",origin.strip()

def parse(path:Path):
    lines=path.read_text(encoding="latin-1").splitlines()
    table=None
    sections=[]
    symbols=[]
    preferred=None
    for line_no,line in enumerate(lines,1):
        stripped=line.strip()
        if stripped.startswith("Preferred load address is "):
            preferred=int(stripped.rsplit(" ",1)[-1],16)
            continue
        if "Publics by Value" in line:
            table="public"
            continue
        if stripped=="Static symbols":
            table="static"
            continue
        if table is None:
            m=SECTION_RE.match(line)
            if m:
                off=int(m.group("offset"),16)
                length=int(m.group("length"),16)
                sections.append({
                    "segment":int(m.group("segment"),16),
                    "offset":off,
                    "end_offset":off+length,
                    "name":m.group("name"),
                    "class":m.group("class"),
                })
            continue
        m=SYMBOL_RE.match(line)
        if not m:
            continue
        toks=m.group("trailer").split()
        is_function=bool(toks and toks[0]=="f")
        if is_function:
            toks.pop(0)
        is_inline=bool(toks and toks[0]=="i")
        if is_inline:
            toks.pop(0)
        origin=" ".join(toks)
        library,obj=split_origin(origin)
        symbols.append({
            "table":table,
            "segment":int(m.group("segment"),16),
            "offset":int(m.group("offset"),16),
            "va":int(m.group("va"),16),
            "decorated_name":m.group("name"),
            "is_function":is_function,
            "is_inline":is_inline,
            "origin":origin,
            "library":library,
            "object":obj,
            "map_line":line_no,
        })

    segment_ends=defaultdict(int)
    for s in sections:
        segment_ends[s["segment"]]=max(segment_ends[s["segment"]],s["end_offset"])
    offsets=defaultdict(list)
    for s in symbols:
        if s["segment"]:
            offsets[s["segment"]].append(s["offset"])
    next_off={}
    for seg,vals in offsets.items():
        ordered=sorted(set(vals))
        for i,off in enumerate(ordered):
            if i+1<len(ordered):
                next_off[(seg,off)]=ordered[i+1]
            elif segment_ends.get(seg,0)>off:
                next_off[(seg,off)]=segment_ends[seg]
    for s in symbols:
        upper=next_off.get((s["segment"],s["offset"]))
        s["span_upper_bound"]=max(0,upper-s["offset"]) if upper else None
    return preferred,sections,symbols

def write_gzip_csv(path:Path,rows:list[dict]):
    fields=[
        "table","segment","offset","va","decorated_name","is_function","is_inline",
        "span_upper_bound","origin","library","object","map_line"
    ]
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw,mode="wb",mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8",newline="") as text:
                w=csv.DictWriter(text,fieldnames=fields)
                w.writeheader()
                w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--map",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--summary",type=Path,required=True)
    ap.add_argument("--expected-sha256")
    a=ap.parse_args()

    raw=a.map.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if a.expected_sha256 and sha.lower()!=a.expected_sha256.lower():
        raise SystemExit(f"MAP SHA-256 mismatch: expected {a.expected_sha256}, got {sha}")

    preferred,sections,symbols=parse(a.map)
    funcs=[x for x in symbols if x["is_function"]]
    write_gzip_csv(a.out,symbols)
    summary={
        "format":FORMAT,
        "input_name":a.map.name,
        "input_size_bytes":len(raw),
        "input_sha256":sha,
        "preferred_load_address":preferred,
        "section_count":len(sections),
        "symbol_rows":len(symbols),
        "function_symbol_rows":len(funcs),
        "function_start_addresses":len({x["va"] for x in funcs}),
        "public_function_rows":sum(x["table"]=="public" for x in funcs),
        "static_function_rows":sum(x["table"]=="static" for x in funcs),
        "proof_boundary":"Server linker MAP evidence only; no server symbol is retail-authoritative without independent cross-build proof."
    }
    a.summary.parent.mkdir(parents=True,exist_ok=True)
    a.summary.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
