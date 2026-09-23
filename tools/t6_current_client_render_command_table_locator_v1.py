#!/usr/bin/env python3
"""Locate the current-client 33-entry renderer command tables and dispatcher.

The exact current-client command-name table is discovered from all 33 C-string
pointers. Candidate function tables must have 33 dwords, entry0==0, entries1..32
inside executable sections, and the exact duplicate topology observed in T6
lineage (3==4 and 19==20). Candidate tables are then strengthened only by exact
indexed indirect-call operands that address the table.

No source symbol is assigned solely from ordering or adjacency.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-render-command-table-locator-v1"
NAMES=[
"RC_END_OF_LIST","RC_SET_CUSTOM_CONSTANT","RC_SET_MATERIAL_COLOR","RC_SAVE_SCREEN",
"RC_SAVE_SCREEN_SECTION","RC_CLEAR_SCREEN","RC_BEGIN_VIEW","RC_SET_VIEWPORT","RC_SET_SCISSOR",
"RC_RESOLVE_COMPOSITE","RC_PC_COPY_IMAGE_GEN_MIP","RC_STRETCH_PIC","RC_STRETCH_PIC_FLIP_ST",
"RC_STRETCH_PIC_ROTATE_XY","RC_STRETCH_PIC_ROTATE_ST","RC_DRAW_QUAD_PIC",
"RC_DRAW_FULL_SCREEN_COLORED_QUAD","RC_DRAW_TEXT_2D","RC_DRAW_TEXT_3D",
"RC_BLEND_SAVED_SCREEN_BLURRED","RC_BLEND_SAVED_SCREEN_FLASHED","RC_DRAW_POINTS","RC_DRAW_LINES",
"RC_DRAW_UI_QUADS","RC_DRAW_UI_QUADS_REPLACE_IMAGE","RC_DRAW_UI_TRIANGLES","RC_DRAW_TRIANGLES",
"RC_DRAW_QUADLIST_2D","RC_DRAW_EMBLEM_LAYER","RC_STRETCH_COMPOSITE","RC_PROJECTION_SET",
"RC_DRAW_FRAMED","RC_CONSTANT_SET"]
COUNT=len(NAMES)

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
def raw_to_va(secs,off):
    for s in secs:
      if s["rawOffset"]<=off< s["rawOffset"]+s["rawSize"]:return s["va"]+off-s["rawOffset"],s
    return None,None
def va_to_raw(secs,va,n=1):
    for s in secs:
      if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:return s["rawOffset"]+va-s["va"],s
    return None,None
def exact_string_vas(raw,secs,text):
    needle=text.encode()+b"\0";out=[];pos=0
    while True:
      i=raw.find(needle,pos)
      if i<0:break
      va,s=raw_to_va(secs,i)
      if va is not None:out.append({"va":va,"vaHex":f"0x{va:08x}","rawOffset":i,"section":s["name"]})
      pos=i+1
    return out
def is_exec_va(secs,va):
    return any(s["exec"] and s["va"]<=va<s["va"]+s["rawSize"] for s in secs)
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw)
    strings={name:exact_string_vas(raw,secs,name) for name in NAMES}
    req(all(len(v)>=1 for v in strings.values()),"not all 33 command strings found")
    # Exact full name table candidates: choose one occurrence for each name by matching 33 consecutive pointers.
    name_tables=[]
    first_vas={x["va"] for x in strings[NAMES[0]]}
    for s in secs:
      for off in range(s["rawOffset"],s["rawOffset"]+s["rawSize"]-COUNT*4+1,4):
        vals=struct.unpack_from("<"+("I"*COUNT),raw,off)
        if vals[0] not in first_vas:continue
        if all(any(z["va"]==vals[i] for z in strings[name]) for i,name in enumerate(NAMES)):
          va=s["va"]+off-s["rawOffset"]
          name_tables.append({"tableVa":f"0x{va:08x}","rawOffset":off,"section":s["name"],"pointers":[f"0x{x:08x}" for x in vals]})
    # Function table candidates.
    func_tables=[]
    for s in secs:
      for off in range(s["rawOffset"],s["rawOffset"]+s["rawSize"]-COUNT*4+1,4):
        vals=struct.unpack_from("<"+("I"*COUNT),raw,off)
        if vals[0]!=0:continue
        if not all(is_exec_va(secs,x) for x in vals[1:]):continue
        if vals[3]!=vals[4] or vals[19]!=vals[20]:continue
        va=s["va"]+off-s["rawOffset"]
        func_tables.append({"tableVa":va,"tableVaHex":f"0x{va:08x}","rawOffset":off,"section":s["name"],
          "handlers":[{"index":i,"name":NAMES[i],"va":f"0x{x:08x}"} for i,x in enumerate(vals)]})
    # Exact decoded indexed-memory references to candidate function table bases.
    refs=[]
    bases={x["tableVa"] for x in func_tables}
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
      ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
      for n,i in enumerate(ins):
        for op in i.operands:
          if op.type!=X86_OP_MEM or op.mem.index==0:continue
          disp=int(op.mem.disp)&0xffffffff
          if disp not in bases:continue
          lo=max(0,n-20);hi=min(len(ins),n+21)
          refs.append({"tableVa":f"0x{disp:08x}","instruction":row(i),"section":s["name"],
            "scale":op.mem.scale,"indexRegisterId":op.mem.index,"baseRegisterId":op.mem.base,
            "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]})
    bybase={}
    for r in refs:bybase.setdefault(r["tableVa"],[]).append(r)
    for t in func_tables:t["indexedReferences"]=bybase.get(t["tableVaHex"],[])
    doc={"format":FORMAT,"authority":"SHA-classified current client exact strings, pointer tables and decoded indexed-memory operands",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"allCommandStringsFound":True,"nameTableCandidateCount":len(name_tables),"functionTableCandidateCount":len(func_tables),
        "functionTableCandidateWithIndexedReferenceCount":sum(bool(x["indexedReferences"]) for x in func_tables),
        "indexedFunctionTableReferenceCount":len(refs)},
      "commandStringOccurrences":strings,"nameTableCandidates":name_tables,"functionTableCandidates":func_tables,
      "proofBoundary":"Command strings/name-table bytes and function-pointer table bytes are exact current-client evidence. The 33-entry size and duplicate topology are T6 lineage locators only. A candidate gains dispatcher significance only from exact indexed executable references; individual handler source-symbol semantics remain unpromoted until handler dataflow independently matches."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for t in func_tables:
      if t["indexedReferences"]:print("FUNC",t["tableVaHex"],"mat",t["handlers"][2]["va"],"refs",len(t["indexedReferences"]))
    for t in name_tables:print("NAMES",t["tableVa"])
if __name__=="__main__":main()
