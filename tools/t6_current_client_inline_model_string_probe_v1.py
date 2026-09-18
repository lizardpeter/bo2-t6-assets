#!/usr/bin/env python3
"""Find exact current-client ASCII strings relevant to inline brush-model parsing.

Current-client only. String presence does not source-name functions or establish
historical-retail equivalence.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path

CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def sections(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];coff=p+4
    n=struct.unpack_from("<H",raw,coff+2)[0];os=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+os;out=[]
    for i in range(n):
        q=so+i*40
        name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        out.append((name,ib+rva,vs,ro,rs))
    return ib,out

def fileoff_to_va(off,secs):
    for name,va,vs,ro,rs in secs:
        if ro<=off<ro+rs:
            return name,va+(off-ro)
    return None,None

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=CLIENT: raise SystemExit(f"unexpected client {sha}")
    ib,secs=sections(raw)
    strings=[]
    for m in re.finditer(rb"[\x20-\x7e]{4,}",raw):
        s=m.group().decode("ascii","replace")
        low=s.lower()
        if any(k in low for k in ["inlinemodel","inline model","bad number","brush model","submodel","numsubmodel"]):
            sec,va=fileoff_to_va(m.start(),secs)
            strings.append({"text":s,"fileOffset":m.start(),"virtualAddress":f"0x{va:08x}" if va is not None else None,"section":sec})
    out={"format":"t6-current-client-inline-model-string-probe-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"sha256":sha,"bytes":len(raw),"imageBaseHex":f"0x{ib:08x}"},"matches":strings,"summary":{"matchCount":len(strings)},"proofBoundary":"Exact ASCII-string presence only. Text does not source-name nearby code, prove *N semantics, or establish historical-retail equivalence."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
    for x in strings: print(x)
if __name__=="__main__":main()
