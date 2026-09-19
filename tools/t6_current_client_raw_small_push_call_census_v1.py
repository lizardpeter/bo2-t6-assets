#!/usr/bin/env python3
"""Raw executable census of immediate-push followed by direct-call patterns.

This intentionally avoids whole-section disassembly. It scans executable section
bytes for:
  6A vv E8 rel32
  68 vv 00 00 00 E8 rel32
where vv is a small nonnegative value. Targets receiving many distinct values
are useful generic-call locators. Values are not promoted as XAssetType without
independent argument-order/dataflow proof.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-raw-small-push-call-census-v1"
MAX_SMALL=60
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
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw);grouped=collections.defaultdict(list);total=0
    for s in secs:
        if not s["executable"]:continue
        b=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        for i in range(len(b)-10):
            value=None;calloff=None;encoding=None
            if b[i]==0x6a and b[i+2]==0xe8:
                value=b[i+1];calloff=i+2;encoding="push-imm8"
            elif b[i]==0x68 and b[i+5]==0xe8:
                value=struct.unpack_from("<I",b,i+1)[0];calloff=i+5;encoding="push-imm32"
            if value is None or value>MAX_SMALL:continue
            callva=s["va"]+calloff
            disp=struct.unpack_from("<i",b,calloff+1)[0];target=(callva+5+disp)&0xffffffff
            siteva=s["va"]+i
            lo=max(0,i-24);hi=min(len(b),calloff+5+24)
            rec={"pushVa":f"0x{siteva:08x}","callVa":f"0x{callva:08x}","targetVa":f"0x{target:08x}",
                 "value":value,"encoding":encoding,"section":s["name"],
                 "windowStartVa":f"0x{s['va']+lo:08x}","bytesAround":b[lo:hi].hex()}
            grouped[target].append(rec);total+=1
    targets=[]
    for target,sites in grouped.items():
        vals=sorted({x["value"] for x in sites})
        if len(vals)<3:continue
        targets.append({"targetVa":f"0x{target:08x}","siteCount":len(sites),
          "distinctSmallValues":vals,"distinctSmallValueCount":len(vals),
          "value16SiteCount":sum(x["value"]==16 for x in sites),
          "value16Sites":[x for x in sites if x["value"]==16],
          "sites":sites if len(sites)<=120 else []})
    targets.sort(key=lambda x:(-x["distinctSmallValueCount"],-x["siteCount"],x["targetVa"]))
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"rawPatternSiteCount":total,"candidateTargetCount":len(targets),
        "candidateWithValue16Count":sum(x["value16SiteCount"]>0 for x in targets),
        "maxDistinctSmallValueCount":max([x["distinctSmallValueCount"] for x in targets],default=0)},
      "targets":targets,
      "proofBoundary":"Raw executable byte-pattern locator only. Matching bytes are not assumed to be instruction-aligned absent focused decode. Small immediate values are not assigned as XAssetType and targets are not named by calling-pattern similarity. Candidates require independent bounded disassembly and argument/dataflow proof."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
