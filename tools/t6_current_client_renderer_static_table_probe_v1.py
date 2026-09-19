#!/usr/bin/env python3
"""Locate current-client static renderer tables that own known sampler/constant strings.

The prior exact string probe found no executable direct references to the relevant
string VAs, strongly suggesting table indirection. This probe therefore:
  1. gates the exact current-client SHA;
  2. scans all raw-backed PE sections for dword pointers to selected exact strings;
  3. records bounded raw dword neighborhoods around every pointer occurrence;
  4. clusters nearby pointer occurrences into candidate static tables;
  5. records executable absolute/immediate references into/near those clusters.

The output is a locator. Row meanings/strides and runtime semantics are not promoted
until a later exact consumer/dataflow proof.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-renderer-static-table-probe-v1"
TARGETS={
 "hdrControl0":0x00D2F7A4,
 "hdrControl1":0x00D2F798,
 "reflectionProbeSampler":0x00D301E4,
 "lightmapSamplerSecondary":0x00D30264,
 "lightmapSamplerPrimary":0x00D30280,
 "dlightAttenuationSampler":0x00D30298,
 "attenuationSampler":0x00D302B4,
}
NEIGHBOR_DWORDS=24
CLUSTER_GAP=0x200
XREF_NEAR=0x100

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)

def parse_pe(raw:bytes):
    pe=struct.unpack_from("<I",raw,0x3c)[0];req(raw[pe:pe+4]==b"PE\0\0","bad PE")
    coff=pe+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;req(struct.unpack_from("<H",raw,opt)[0]==0x10b,"not PE32")
    ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);chars=struct.unpack_from("<I",raw,q+36)[0]
        secs.append({"name":name,"va":ib+rva,"virtualSize":vs,"rawSize":rs,"rawOffset":ro,"characteristics":chars})
    return ib,secs

def va_to_raw(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]:
            return s["rawOffset"]+(va-s["va"]),s
    return None,None

def raw_to_va(sec,off): return sec["va"]+(off-sec["rawOffset"])

def dword_neighbors(raw,sec,off):
    lo=max(sec["rawOffset"],off-NEIGHBOR_DWORDS*4)
    hi=min(sec["rawOffset"]+sec["rawSize"],off+(NEIGHBOR_DWORDS+1)*4)
    lo-= (lo-sec["rawOffset"])%4
    rows=[]
    for p in range(lo,hi,4):
        if p+4>len(raw):break
        v=struct.unpack_from("<I",raw,p)[0]
        rows.append({"va":f"0x{raw_to_va(sec,p):08x}","rawOffset":p,"value":v,"valueHex":f"0x{v:08x}"})
    return rows

def pointer_occurrences(raw,secs):
    rev={v:k for k,v in TARGETS.items()};out=[]
    for s in secs:
        start=s["rawOffset"];end=start+s["rawSize"]
        blob=raw[start:end]
        for rel in range(0,max(0,len(blob)-3),4):
            v=struct.unpack_from("<I",blob,rel)[0]
            if v not in rev:continue
            off=start+rel
            out.append({
              "target":rev[v],"targetVa":f"0x{v:08x}",
              "pointerVa":f"0x{raw_to_va(s,off):08x}","rawOffset":off,
              "section":s["name"],"neighbors":dword_neighbors(raw,s,off),
            })
    return sorted(out,key=lambda r:int(r["pointerVa"],16))

def cluster_occurrences(occ):
    if not occ:return []
    groups=[];cur=[occ[0]]
    for r in occ[1:]:
        if int(r["pointerVa"],16)-int(cur[-1]["pointerVa"],16)<=CLUSTER_GAP:
            cur.append(r)
        else:
            groups.append(cur);cur=[r]
    groups.append(cur)
    out=[]
    for i,g in enumerate(groups):
        vas=[int(r["pointerVa"],16) for r in g]
        out.append({
          "clusterIndex":i,"startVa":f"0x{min(vas):08x}","endVa":f"0x{max(vas)+4:08x}",
          "pointerCount":len(g),"targets":[r["target"] for r in g],
          "uniqueTargetCount":len({r["target"] for r in g}),
        })
    return out

def insrow(i):
    return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def exec_refs(raw,secs,clusters):
    if not clusters:return []
    ranges=[]
    for c in clusters:
        a=int(c["startVa"],16);b=int(c["endVa"],16)
        ranges.append((c["clusterIndex"],max(0,a-XREF_NEAR),b+XREF_NEAR,a,b))
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;refs=[]
    for s in secs:
        if not (s["characteristics"]&0x20000000):continue
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];ins=list(md.disasm(blob,s["va"]))
        for n,i in enumerate(ins):
            vals=[]
            for op in i.operands:
                if op.type==X86_OP_IMM: vals.append(int(op.imm)&0xffffffff)
                elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0: vals.append(int(op.mem.disp)&0xffffffff)
            hits=[]
            for v in vals:
                for ci,near0,near1,exact0,exact1 in ranges:
                    if near0<=v<near1:
                        hits.append({"clusterIndex":ci,"operandValueHex":f"0x{v:08x}","insidePointerSpan":exact0<=v<exact1})
            if not hits:continue
            lo=max(0,n-20);hi=min(len(ins),n+21)
            refs.append({"instruction":insrow(i),"section":s["name"],"hits":hits,
                         "contextBefore":[insrow(z) for z in ins[lo:n]],
                         "contextAfter":[insrow(z) for z in ins[n+1:hi]]})
    return refs

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"client SHA drift {digest}")
    ib,secs=parse_pe(raw);occ=pointer_occurrences(raw,secs);clusters=cluster_occurrences(occ);refs=exec_refs(raw,secs,clusters)
    bytarget={k:0 for k in TARGETS}
    for r in occ:bytarget[r["target"]]+=1
    doc={
      "format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "targets":{k:f"0x{v:08x}" for k,v in TARGETS.items()},
      "summary":{"pointerOccurrenceCount":len(occ),"pointerOccurrenceCountsByTarget":bytarget,
                 "clusterCount":len(clusters),"executableNearClusterReferenceCount":len(refs)},
      "pointerOccurrences":occ,"clusters":clusters,"executableNearClusterReferences":refs,
      "proofBoundary":"Exact current-client pointer bytes and executable operand references only. Candidate clusters are proximity groupings, not proven tables; neighboring dwords are uninterpreted. No table stride/row type, sampler descriptor, code-constant provider, API call, or historical-retail equivalence is promoted here."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
