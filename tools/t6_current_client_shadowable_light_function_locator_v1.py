#!/usr/bin/env python3
"""Locate the current-client shadowable-light constant writer by exact in-client evidence.

Open-engine lineage is used only to choose string keywords / enum numerics.
Promotion data in this proof is exclusively the SHA-classified current client:
- raw-backed printable strings matching shadowable-light concepts
- decoded code xrefs to those strings
- INT3-bounded candidate function bodies
- exact light code-constant immediates observed in each candidate

No source symbol is assigned here.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shadowable-light-function-locator-v1"
KEYWORDS=(
    "r_draw_shadowablelight","shadowablelight","shadowableLight",
    "spotShadow","light->radius","light->type","source->viewMode",
    "GFX_LIGHT_TYPE","R_SPOTSHADOW_TILE_COUNT","primary lights"
)
LIGHT_ENUMS={
 0:"lightPosition",1:"lightDiffuse",2:"lightSpotDir",3:"lightSpotFactors",
 5:"lightFallOffA",6:"lightFallOffB",7:"lightSpotMatrix0",8:"lightSpotMatrix1",
 9:"lightSpotMatrix2",11:"lightSpotAABB",12:"lightConeControl1",
 14:"lightSpotCookieSlideControl",60:"spotShadowmapPixelAdjust"
}

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0]; req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4; n=struct.unpack_from("<H",raw,coff+2)[0]; optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20; req(struct.unpack_from("<H",raw,opt)[0]==0x10b,"not PE32")
    ib=struct.unpack_from("<I",raw,opt+28)[0]; so=opt+optsz; secs=[]
    for i in range(n):
        q=so+i*40; name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8); ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def row(i): return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def off_to_va(secs,off):
    for s in secs:
        if s["rawOffset"]<=off<s["rawOffset"]+s["rawSize"]:
            return s["va"]+off-s["rawOffset"],s
    return None,None
def relevant_strings(raw,secs):
    out=[]
    for m in re.finditer(rb"[\x20-\x7e]{4,}\x00",raw):
        b=m.group()[:-1]
        try:t=b.decode("ascii")
        except Exception:continue
        lo=t.lower()
        if not any(k.lower() in lo for k in KEYWORDS):continue
        va,s=off_to_va(secs,m.start())
        if va is not None:
            out.append({"text":t,"va":va,"vaHex":f"0x{va:08x}","rawOffset":m.start(),"section":s["name"]})
    return out
def bounds(raw,s,va):
    o=s["rawOffset"]+va-s["va"]; base=s["rawOffset"]; end=s["rawOffset"]+s["rawSize"]
    lo=o
    while lo>base+4 and raw[lo-4:lo]!=b"\xcc"*4: lo-=1
    start=lo if lo>base and raw[lo-4:lo]==b"\xcc"*4 else max(base,o-4096)
    hi=o
    while hi<end-4 and raw[hi:hi+4]!=b"\xcc"*4: hi+=1
    stop=hi if hi<end-4 and raw[hi:hi+4]==b"\xcc"*4 else min(end,o+8192)
    return s["va"]+start-base,s["va"]+stop-base,start,stop
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("exe",type=Path); ap.add_argument("--revision",required=True); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    raw=a.exe.read_bytes(); dg=hashlib.sha256(raw).hexdigest(); req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw); strs=relevant_strings(raw,secs); tmap={x["va"]:x for x in strs}
    grouped={}
    for s in secs:
        if not s["exec"]: continue
        md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True; md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for i in ins:
            hits=set()
            for op in i.operands:
                if op.type==X86_OP_IMM:
                    v=int(op.imm)&0xffffffff
                    if v in tmap:hits.add(v)
                elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0:
                    v=int(op.mem.disp)&0xffffffff
                    if v in tmap:hits.add(v)
            if not hits:continue
            fs,fe,rs,re=bounds(raw,s,i.address); key=(fs,fe,s["name"],rs,re)
            g=grouped.setdefault(key,{"stringVas":set(),"xrefInstructions":[]})
            g["stringVas"].update(hits); g["xrefInstructions"].append(row(i))
    candidates=[]
    for (fs,fe,sec,rs,re),g in grouped.items():
        md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True; md.skipdata=True
        body=[i for i in md.disasm(raw[rs:re],fs) if i.id]
        enumHits=[]
        for i in body:
            vals=[]
            for op in i.operands:
                if op.type==X86_OP_IMM:
                    v=int(op.imm)&0xffffffff
                    if v in LIGHT_ENUMS: vals.append(v)
            if vals:
                enumHits.append({"instruction":row(i),"enumValues":vals,"accessors":[LIGHT_ENUMS[v] for v in vals]})
        stringRows=[tmap[v] for v in sorted(g["stringVas"])]
        candidates.append({
          "section":sec,"functionStartVa":f"0x{fs:08x}","functionEndVaExclusive":f"0x{fe:08x}",
          "bytes":re-rs,"sha256":hashlib.sha256(raw[rs:re]).hexdigest(),
          "referencedStrings":stringRows,"stringXrefs":g["xrefInstructions"],
          "lightEnumImmediateHits":enumHits,
          "distinctLightEnumValues":sorted({v for x in enumHits for v in x["enumValues"]}),
          "distinctLightAccessors":sorted({LIGHT_ENUMS[v] for x in enumHits for v in x["enumValues"]}),
          "instructionCount":len(body),"instructions":[row(i) for i in body]
        })
    candidates.sort(key=lambda x:(-len(x["distinctLightEnumValues"]),x["functionStartVa"]))
    doc={
      "format":FORMAT,"authority":"SHA-classified current-client raw strings + decoded xrefs + exact bounded function bytes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "locatorVocabulary":{"keywords":list(KEYWORDS),"lightEnums":[{"enumValue":k,"accessor":v} for k,v in sorted(LIGHT_ENUMS.items())]},
      "summary":{
        "relevantStringCount":len(strs),"candidateFunctionCount":len(candidates),
        "candidateFunctionsWithAtLeast4LightEnums":sum(len(x["distinctLightEnumValues"])>=4 for x in candidates),
        "maxDistinctLightEnumsInCandidate":max((len(x["distinctLightEnumValues"]) for x in candidates),default=0)
      },
      "strings":strs,"candidates":candidates,
      "proofBoundary":"Locator only. Source-lineage vocabulary selects strings/enums to search, but every persisted candidate/xref/function byte comes from the exact SHA-classified current client. A candidate is not promoted as R_SetLightProperties until an independent semantic projector proves argument/source offsets, formulas, enum destinations/versioning and relevant branch conditions."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in candidates[:20]:
        print(c["functionStartVa"],len(c["distinctLightEnumValues"]),c["distinctLightAccessors"],[x["text"] for x in c["referencedStrings"]])
if __name__=="__main__":main()
