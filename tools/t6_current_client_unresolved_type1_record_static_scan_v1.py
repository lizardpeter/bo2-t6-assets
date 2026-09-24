#!/usr/bin/env python3
"""Scan exact current-client PE bytes for structurally valid type-1 runtime records
for the six unresolved indirect-only constant enums.

A type-1 record is admitted only when:
  uint16(+0) is a sane aligned record size >= 0x18,
  uint8(+2) == 1,
  uint32(+4) is one target enum,
  the complete record lies inside one PE section.
This is a locator/provenance step, not provider promotion.
"""
from __future__ import annotations
import argparse,hashlib,json,math,struct
from pathlib import Path

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-unresolved-type1-record-static-scan-v1"
TARGETS={
 37:"shadowmapSwitchPartition",
 38:"sunShadowmapPixelSize",
 60:"spotShadowmapPixelAdjust",
 61:"dlightSpotShadowmapPixelAdjust",
 111:"postFxControl4",
 112:"postFxControl5",
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
        secs.append({"name":name,"va":ib+rva,"virtualSize":vs,"rawSize":rs,"rawOffset":ro,
                     "exec":bool(ch&0x20000000),"write":bool(ch&0x80000000),"read":bool(ch&0x40000000)})
    return ib,secs
def f32(raw,o):
    return struct.unpack_from("<f",raw,o)[0]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
        start=s["rawOffset"]; end=start+s["rawSize"]
        for o in range(start,max(start,end-0x18+1)):
            if raw[o+2]!=1:continue
            size=struct.unpack_from("<H",raw,o)[0]
            if size<0x18 or size>0x400 or size%4!=0 or o+size>end:continue
            enum=struct.unpack_from("<I",raw,o+4)[0]
            if enum not in TARGETS:continue
            lanes=[f32(raw,o+x) for x in (8,12,16,20)]
            hits.append({
              "accessor":TARGETS[enum],"enumValue":enum,"recordSize":size,
              "section":s["name"],"sectionExec":s["exec"],"sectionWrite":s["write"],
              "rawOffset":o,"va":f"0x{s['va']+(o-start):08x}",
              "headerHex":raw[o:o+min(size,0x40)].hex(),
              "lanes":[{"bits":f"0x{struct.unpack_from('<I',raw,o+x)[0]:08x}","float":lanes[k],"finite":math.isfinite(lanes[k])} for k,x in enumerate((8,12,16,20))]
            })
    summary={}
    for e,name in TARGETS.items():
        rs=[x for x in hits if x["enumValue"]==e]
        summary[name]={"enumValue":e,"candidateCount":len(rs),"sections":sorted({x["section"] for x in rs}),"vas":[x["va"] for x in rs]}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact PE byte scan constrained by independently proven type-1 runtime-record layout",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "recordContract":{"size":"uint16(+0), >=0x18, aligned, complete in section","typeByte":"uint8(+2)==1","enumValue":"uint32(+4)","lanes":"float32(+8,+0xC,+0x10,+0x14)"},
      "summary":summary,"hits":hits,
      "proofBoundary":"Static locator only. A hit is a byte-exact structure compatible with the proven type-1 record ABI; runtime reachability, ownership by one of the four dispatcher streams, mutability, historical-retail equivalence and framebuffer effect require separate joins. No hit means the enum is not present as a literal structurally valid type-1 record in the PE image, not that the runtime cannot construct it dynamically."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
