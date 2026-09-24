#!/usr/bin/env python3
"""Locate dynamic RC_SET_CUSTOM_CONSTANT-shaped record builders without assuming enum immediates.

A candidate is a bounded executable function/base-register pair that has 32-bit
destination writes to +4,+8,+12,+16,+20. The +4 source may be immediate,
register, or memory. Header writes at +0/+2 are retained separately.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-dynamic-custom-constant-record-builders-v1"
REQ={4,8,12,16,20}
CTX=18

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
      secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def split_functions(ins):
    out=[];cur=[]
    for i in ins:
      if i.mnemonic=="int3":
        if cur: out.append(cur);cur=[]
      else: cur.append(i)
    if cur:out.append(cur)
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);cands=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for body in split_functions(ins):
        if len(body)>5000:continue
        bybase=defaultdict(list)
        for n,i in enumerate(body):
          if not i.operands:continue
          op=i.operands[0]
          if op.type!=X86_OP_MEM or not op.mem.base or op.mem.index:continue
          if op.size!=4:continue
          if i.mnemonic in ("cmp","test"):continue
          disp=int(op.mem.disp)
          if disp not in (0,2,4,8,12,16,20):continue
          base=md.reg_name(op.mem.base)
          bybase[base].append((n,disp,i))
        for base,rows in bybase.items():
          offs={d for _,d,_ in rows}
          if not REQ.issubset(offs):continue
          # Split into local clusters, since a long function can reuse one register for unrelated objects.
          indices=sorted(n for n,_,_ in rows)
          clusters=[];cur=[indices[0]]
          for n in indices[1:]:
            if n-cur[-1] <= 90: cur.append(n)
            else: clusters.append(cur);cur=[n]
          clusters.append(cur)
          for cluster in clusters:
            crow=[x for x in rows if x[0] in set(cluster)]
            coffs={d for _,d,_ in crow}
            if not REQ.issubset(coffs):continue
            lo=max(0,min(cluster)-CTX);hi=min(len(body),max(cluster)+CTX+1)
            fields={}
            for n,d,i in crow: fields.setdefault(str(d),[]).append(rr(i))
            cands.append({
              "section":s["name"],"functionStartVa":f"0x{body[0].address:08x}",
              "functionEndVaExclusive":f"0x{body[-1].address+body[-1].size:08x}",
              "recordBaseRegister":base,"clusterFirstVa":f"0x{body[min(cluster)].address:08x}",
              "clusterLastVa":f"0x{body[max(cluster)].address:08x}",
              "destinationOffsets":sorted(coffs),
              "hasOffset0DwordWrite":0 in coffs,"hasOffset2DwordWrite":2 in coffs,
              "fieldWrites":fields,
              "enumFieldWrites":fields["4"],
              "context":[rr(x) for x in body[lo:hi]]
            })
    # stable de-dupe by function/base/cluster bounds
    uniq={}
    for c in cands:
      k=(c["functionStartVa"],c["recordBaseRegister"],c["clusterFirstVa"],c["clusterLastVa"])
      uniq[k]=c
    cands=list(uniq.values());cands.sort(key=lambda x:(x["functionStartVa"],x["clusterFirstVa"],x["recordBaseRegister"]))
    doc={"format":FORMAT,"authority":"SHA-classified exact 32-bit same-base record-field destination writes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "requiredShape":{"enumOffset":4,"floatPayloadOffsets":[8,12,16,20],"writeWidthBytes":4},
      "summary":{"candidateCount":len(cands),
        "withOffset0DwordWrite":sum(c["hasOffset0DwordWrite"] for c in cands),
        "withOffset2DwordWrite":sum(c["hasOffset2DwordWrite"] for c in cands)},
      "candidates":cands,
      "proofBoundary":"Structural locator only. Exact same-base 32-bit writes establish command-record shape candidates, but allocator/header/type identity, enum source semantics and backend reachability require subsequent joins."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in cands:
      print(c["functionStartVa"],c["recordBaseRegister"],c["clusterFirstVa"],c["clusterLastVa"],c["destinationOffsets"],c["enumFieldWrites"])
if __name__=="__main__":main()
