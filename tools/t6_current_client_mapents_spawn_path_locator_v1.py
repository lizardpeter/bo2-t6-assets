#!/usr/bin/env python3
"""Current-client locator for MapEnt -> spawnVar -> entity model parsing."""
from __future__ import annotations
import argparse,hashlib,json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-mapents-spawn-path-locator-v1"
KEYWORDS=("g_spawn","spawnentities","spawnvar","mapent","entitystring","brushmodel","clipmap","parseentityfield","parseentityfields")
CTX=28
CALL_TARGETS=(0x005c2280,0x005c23f0)

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from('<I',raw,0x3c)[0];req(raw[p:p+4]==b'PE\0\0','bad PE')
    coff=p+4;n=struct.unpack_from('<H',raw,coff+2)[0];optsz=struct.unpack_from('<H',raw,coff+16)[0]
    opt=coff+20;req(struct.unpack_from('<H',raw,opt)[0]==0x10b,'not PE32')
    ib=struct.unpack_from('<I',raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b'\0',1)[0].decode('ascii','replace')
        vs,rva,rs,ro=struct.unpack_from('<IIII',raw,q+8);ch=struct.unpack_from('<I',raw,q+36)[0]
        secs.append({'name':name,'va':ib+rva,'rawSize':rs,'rawOffset':ro,'executable':bool(ch&0x20000000)})
    return ib,secs
def off_to_va(secs,off):
    for s in secs:
        if s['rawOffset']<=off<s['rawOffset']+s['rawSize']:return s['va']+off-s['rawOffset'],s
    return None,None
def strings(raw,secs):
    out=[]
    for m in re.finditer(rb'[\x20-\x7e]{4,}\x00',raw):
        b=m.group()[:-1]
        try:t=b.decode('ascii')
        except:continue
        lo=t.lower()
        if not any(k in lo for k in KEYWORDS):continue
        va,s=off_to_va(secs,m.start())
        if va is not None:out.append({'text':t,'va':va,'vaHex':f'0x{va:08x}','rawOffset':m.start(),'section':s['name']})
    return out
def row(i):return {'address':f'0x{i.address:08x}','bytes':i.bytes.hex(),'mnemonic':i.mnemonic,'opStr':i.op_str}
def decoded_xrefs(raw,secs,strs):
    targets={x['va']:x['text'] for x in strs};md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;out=[]
    for s in secs:
        if not s['executable']:continue
        blob=raw[s['rawOffset']:s['rawOffset']+s['rawSize']];ins=list(md.disasm(blob,s['va']))
        for n,i in enumerate(ins):
            hits=[]
            for op in i.operands:
                if op.type==X86_OP_IMM and (int(op.imm)&0xffffffff) in targets:hits.append(int(op.imm)&0xffffffff)
                elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0 and (int(op.mem.disp)&0xffffffff) in targets:hits.append(int(op.mem.disp)&0xffffffff)
            if hits:
                lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
                out.append({'instruction':row(i),'section':s['name'],'targetStrings':[targets[x] for x in sorted(set(hits))],
                    'contextBefore':[row(z) for z in ins[lo:n]],'contextAfter':[row(z) for z in ins[n+1:hi]]})
    return out
def raw_rel32_calls(raw,secs,target):
    out=[]
    for s in secs:
        if not s['executable']:continue
        b=raw[s['rawOffset']:s['rawOffset']+s['rawSize']]
        for p in range(0,max(0,len(b)-5)):
            if b[p]!=0xe8:continue
            disp=struct.unpack_from('<i',b,p+1)[0];va=s['va']+p;t=(va+5+disp)&0xffffffff
            if t==target:out.append({'callVa':f'0x{va:08x}','targetVa':f'0x{target:08x}','bytes':b[p:p+5].hex(),'section':s['name']})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('--revision',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f'SHA drift {digest}')
    ib,secs=pe(raw);ss=strings(raw,secs);xr=decoded_xrefs(raw,secs,ss)
    calls={f'0x{t:08x}':raw_rel32_calls(raw,secs,t) for t in CALL_TARGETS}
    summary={'relevantStringCount':len(ss),'decodedStringXrefCount':len(xr),'rawDirectCallCounts':{k:len(v) for k,v in calls.items()}}
    doc={'format':FORMAT,'authority':'SHA-classified current Plutonium client only','client':{'revision':a.revision,'bytes':len(raw),'sha256':digest,'imageBaseHex':f'0x{ib:08x}'},
      'keywords':KEYWORDS,'summary':summary,'strings':ss,'decodedStringXrefs':xr,'rawRel32CallsToCandidateAddresses':calls,
      'proofBoundary':'Exact current-client printable strings, decoded operand xrefs, and raw rel32 call encodings only. String text and source-file names are locators; they are not sufficient alone to promote MapEnt ownership, SpawnVar semantics, parser identity, ClipMap indexing, or historical-retail equivalence.'}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
