#!/usr/bin/env python3
"""Focused current-client caller/string probe for the entity field parser at 0x005c2280."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-entity-field-caller-probe-v1"
RANGES=[
 ("clusterA",0x005c4100,0x005c4680),
 ("clusterB",0x0067d080,0x0067d1c0),
]
STRINGS={
 "spawnEntitiesNoEntities":0x00c25359,
 "parseSpawnVarsMax":0x00bcd4f5,
 "parseSpawnVarsExpectedOpen":0x00c16739,
 "parseSpawnVarsCloseWithoutData":0x00c4b3dd,
 "parseSpawnVarsEofWithoutClose":0x00c5f0d9,
 "mapentsFmt":0x00c2a890,
 "mapentsMpFmt":0x00c41d00,
}
class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"executable":bool(ch&0x20000000)})
    return ib,secs
def locate(secs,va,n=1):
    for s in secs:
        if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:return s,s["rawOffset"]+(va-s["va"])
    raise E(f"VA 0x{va:x}+{n} not raw-backed")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def dis(raw,secs,label,a,b):
    s,o=locate(secs,a,b-a);blob=raw[o:o+b-a];md=Cs(CS_ARCH_X86,CS_MODE_32)
    ins=[row(i) for i in md.disasm(blob,a)]
    return {"label":label,"startVa":f"0x{a:08x}","endVaExclusive":f"0x{b:08x}","section":s["name"],
            "sha256":hashlib.sha256(blob).hexdigest(),"instructions":ins}
def raw_ptr_hits(raw,secs,target):
    p=struct.pack("<I",target);out=[]
    for s in secs:
        if not s["executable"]:continue
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];pos=0
        while True:
            i=blob.find(p,pos)
            if i<0:break
            va=s["va"]+i
            lo=max(0,i-24);hi=min(len(blob),i+28)
            out.append({"vaIfAligned":f"0x{va:08x}","section":s["name"],"bytesAround":blob[lo:hi].hex(),
                        "windowStartVa":f"0x{s['va']+lo:08x}"})
            pos=i+1
    return out
def cstr(raw,secs,va):
    s,o=locate(secs,va);end=min(o+256,s["rawOffset"]+s["rawSize"]);z=raw.find(b"\0",o,end);req(z>=0,"unterminated")
    return raw[o:z].decode("ascii","replace")
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw)
    lits={k:{"va":f"0x{v:08x}","text":cstr(raw,secs,v),"rawExecutablePointerHits":raw_ptr_hits(raw,secs,v)} for k,v in STRINGS.items()}
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
         "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
         "ranges":[dis(raw,secs,*r) for r in RANGES],"stringReferences":lits,
         "proofBoundary":"Exact bounded current-client disassembly and exact raw executable occurrences of mapped string pointers only. Raw pointer hits are locators until the surrounding instruction boundary is separately validated. Investigation range labels are not source symbols. No MapEnt->SpawnVar or ClipMap indexing semantic is promoted here."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"ranges":{x["label"]:len(x["instructions"]) for x in doc["ranges"]},
      "stringHitCounts":{k:len(v["rawExecutablePointerHits"]) for k,v in lits.items()}},indent=2,sort_keys=True))
if __name__=="__main__":main()
