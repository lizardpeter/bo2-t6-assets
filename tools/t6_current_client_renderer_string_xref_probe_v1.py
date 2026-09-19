#!/usr/bin/env python3
"""Current-client renderer string/xref probe for sampler/lightmap/reflection closure.

This is a locator, not a semantic promoter. It scans the exact SHA-classified T6 MP
client for printable ASCII strings containing renderer keywords, maps raw file offsets
to image VAs, then records exact executable references and bounded disassembly context.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32,CS_GRP_JUMP,CS_GRP_CALL
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-renderer-string-xref-probe-v1"
KEYWORDS=("reflection","lightmap","sampler","r_state","hdrcontrol","texture_src_code")
MINLEN=4
CTX=48

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)

def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;magic=struct.unpack_from("<H",raw,opt)[0];req(magic==0x10b,"not PE32")
    imagebase=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro,chars=struct.unpack_from("<IIIII",raw,q+8)
        secs.append({"name":name,"va":imagebase+rva,"virtualSize":vs,"rawSize":rs,"rawOffset":ro,"characteristics":chars})
    return imagebase,secs

def rawoff_to_va(secs,off):
    for s in secs:
        if s["rawOffset"]<=off<s["rawOffset"]+s["rawSize"]:
            return s["va"]+(off-s["rawOffset"]),s["name"]
    return None,None

def ascii_strings(raw):
    out=[]
    for m in re.finditer(rb"[\x20-\x7e]{4,}\x00",raw):
        b=m.group()[:-1]
        try:t=b.decode("ascii")
        except:continue
        lo=t.lower()
        if any(k in lo for k in KEYWORDS):
            out.append((m.start(),t))
    return out

def insrow(i):
    return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def xrefs(raw,secs,target_vas):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    rows=[]
    for s in secs:
        if not (s["characteristics"]&0x20000000):continue
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        ins=list(md.disasm(blob,s["va"]))
        byaddr={i.address:n for n,i in enumerate(ins)}
        for n,i in enumerate(ins):
            hits=set()
            for op in i.operands:
                if op.type==X86_OP_IMM and int(op.imm)&0xffffffff in target_vas:
                    hits.add(int(op.imm)&0xffffffff)
                elif op.type==X86_OP_MEM:
                    # Absolute disp references only. Base/index forms can coincidentally
                    # contain matching displacements and are not promoted.
                    if op.mem.base==0 and op.mem.index==0 and (int(op.mem.disp)&0xffffffff) in target_vas:
                        hits.add(int(op.mem.disp)&0xffffffff)
            if not hits:continue
            lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            rows.append({
              "instruction":insrow(i),"targetVas":[f"0x{x:08x}" for x in sorted(hits)],
              "section":s["name"],"contextBefore":[insrow(z) for z in ins[lo:n]],
              "contextAfter":[insrow(z) for z in ins[n+1:hi]],
            })
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"client SHA drift {digest}")
    ib,secs=pe(raw);strings=[]
    for off,t in ascii_strings(raw):
        va,sec=rawoff_to_va(secs,off)
        if va is None:continue
        strings.append({"text":t,"rawOffset":off,"va":f"0x{va:08x}","section":sec})
    # Deduplicate exact VA/text, preserving all relevant strings.
    uniq={(r["va"],r["text"]):r for r in strings};strings=sorted(uniq.values(),key=lambda r:(int(r["va"],16),r["text"]))
    vas={int(r["va"],16) for r in strings};refs=xrefs(raw,secs,vas)
    byva={r["va"]:r["text"] for r in strings}
    for r in refs:r["targetStrings"]=[byva.get(v) for v in r["targetVas"]]
    counts={k:sum(k in r["text"].lower() for r in strings) for k in KEYWORDS}
    docs={
      "format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"relevantAsciiStringCount":len(strings),"executableXrefCount":len(refs),"keywordStringCounts":counts},
      "strings":strings,"xrefs":refs,
      "proofBoundary":"Exact current-client string presence and executable operand references only. String text is a locator, not function-name or semantic authority. No historical-retail equivalence, sampler descriptor meaning, API-call identity, or renderer behavior is promoted by this probe alone."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(docs,indent=2,sort_keys=True)+"\n")
    print(json.dumps(docs["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
