#!/usr/bin/env python3
"""Non-authoritative current-Plutonium comparison probe for T6 XAsset precedence.

This intentionally does NOT establish historical retail behavior. It inventories the
same strings/constants as the exact-retail probe in a separately SHA-recorded current
client so future retail work can test lineage continuity without nearest-match claims.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

RETAIL_BYTES=12_850_328
RETAIL_SHA256='11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1'
TARGET_STRINGS=(b'common\x00',b'patch\x00',b'_mp\x00',b'mp_nuketown_2020\x00')
IMMEDIATES=(0x3fffffff,0x17ffffff,0x80,0x02,0x8000)
class E(Exception): pass

def pe(raw):
    if raw[:2]!=b'MZ': raise E('not MZ')
    po=struct.unpack_from('<I',raw,0x3c)[0]
    if raw[po:po+4]!=b'PE\0\0': raise E('not PE')
    coff=po+4; machine,nsec,_,_,_,optsz,_=struct.unpack_from('<HHIIIHH',raw,coff)
    if machine!=0x14c: raise E(f'not i386: {machine:#x}')
    opt=coff+20
    if struct.unpack_from('<H',raw,opt)[0]!=0x10b: raise E('not PE32')
    base=struct.unpack_from('<I',raw,opt+28)[0]
    sec=opt+optsz; out=[]
    for i in range(nsec):
        o=sec+i*40; name=raw[o:o+8].split(b'\0',1)[0].decode('ascii','replace')
        vs,rva,rs,ro=struct.unpack_from('<IIII',raw,o+8); ch=struct.unpack_from('<I',raw,o+36)[0]
        out.append(dict(name=name,va=base+rva,vsize=vs,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,out

def occ(raw,n):
    p=0; out=[]
    while True:
        p=raw.find(n,p)
        if p<0:return out
        out.append(p);p+=1

def offva(secs,off):
    for s in secs:
        if s['rawOffset']<=off<s['rawOffset']+s['rawSize']: return s['va']+off-s['rawOffset']

def window(raw,secs,off,r=40):
    s=next((x for x in secs if x['executable'] and x['rawOffset']<=off<x['rawOffset']+x['rawSize']),None)
    if not s:return []
    a=max(s['rawOffset'],off-r); b=min(s['rawOffset']+s['rawSize'],off+r); va=s['va']+a-s['rawOffset']
    md=Cs(CS_ARCH_X86,CS_MODE_32)
    return [dict(address=f'0x{i.address:08x}',bytes=i.bytes.hex(),mnemonic=i.mnemonic,opStr=i.op_str) for i in md.disasm(raw[a:b],va)]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('exe',type=Path); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--revision',required=True); a=ap.parse_args()
    raw=a.exe.read_bytes(); sha=hashlib.sha256(raw).hexdigest(); base,secs=pe(raw)
    exact=(len(raw)==RETAIL_BYTES and sha==RETAIL_SHA256)
    strings=[]
    for st in TARGET_STRINGS:
        for off in occ(raw,st):
            va=offva(secs,off); strings.append(dict(text=st[:-1].decode(),fileOffset=off,vaHex=f'0x{va:08x}' if va else None))
    refs=[]
    for row in strings:
        if not row['vaHex']:continue
        for off in occ(raw,struct.pack('<I',int(row['vaHex'],16))):
            if any(s['executable'] and s['rawOffset']<=off<s['rawOffset']+s['rawSize'] for s in secs):
                refs.append(dict(target=row['text'],targetVa=row['vaHex'],referenceVa=f'0x{offva(secs,off):08x}',fileOffset=off,window=window(raw,secs,off)))
    imm=[]
    for v in IMMEDIATES:
        hits=[]
        for off in occ(raw,struct.pack('<I',v)):
            if any(s['executable'] and s['rawOffset']<=off<s['rawOffset']+s['rawSize'] for s in secs): hits.append(dict(vaHex=f'0x{offva(secs,off):08x}',fileOffset=off,window=window(raw,secs,off,32)))
        imm.append(dict(valueHex=f'0x{v:08x}',executableHitCount=len(hits),hits=hits))
    r=dict(format='t6-current-client-xasset-precedence-comparison-v1',authority='current Plutonium CDN object only; not historical retail authority',client=dict(revision=a.revision,bytes=len(raw),sha256=sha,imageBaseHex=f'0x{base:08x}',exactPinnedRetail=exact),sections=secs,strings=strings,stringExecutableReferences=refs,immediateInventory=imm,status='comparative_discovery_only_no_winner_promoted',proofBoundary='Current-client exact-byte inventory only. String/immediate similarity, adjacency, ordering, and nearest-match behavior do not prove historical retail function identity or duplicate precedence.')
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n'); print(json.dumps({'client':r['client'],'refs':len(refs),'immediates':{x['valueHex']:x['executableHitCount'] for x in imm}},indent=2))
if __name__=='__main__': main()
