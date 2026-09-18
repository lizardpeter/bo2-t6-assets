#!/usr/bin/env python3
"""Static discovery probe for duplicate-XAsset precedence in exact retail T6 t6mp.exe.

This is intentionally a *discovery* probe, not a winner oracle.  It SHA/size/PE32
pins the historical retail client, inventories exact constants/strings relevant
to the independently proved PC-server DB path, and emits bounded Capstone
windows around executable references.  No server address, priority value, load
ordering, or nearest-match result is promoted to client authority.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXPECTED_BYTES=12_850_328
EXPECTED_SHA256="11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
IMAGE_BASE=0x400000
TARGET_STRINGS=(b"common\x00",b"patch\x00",b"_mp\x00",b"mp_nuketown_2020\x00")
IMMEDIATES=(0x3fffffff,0x17ffffff,0x80,0x02,0x8000)

class E(Exception): pass

def pe(raw:bytes):
    if raw[:2]!=b'MZ': raise E('not MZ')
    po=struct.unpack_from('<I',raw,0x3c)[0]
    if raw[po:po+4]!=b'PE\0\0': raise E('not PE')
    coff=po+4; machine,nsec,_,_,_,optsz,_=struct.unpack_from('<HHIIIHH',raw,coff)
    if machine!=0x14c: raise E(f'not i386: {machine:#x}')
    opt=coff+20
    if struct.unpack_from('<H',raw,opt)[0]!=0x10b: raise E('not PE32')
    base=struct.unpack_from('<I',raw,opt+28)[0]
    if base!=IMAGE_BASE: raise E(f'image base {base:#x}')
    sec=opt+optsz; out=[]
    for i in range(nsec):
        o=sec+i*40; name=raw[o:o+8].split(b'\0',1)[0].decode('ascii','replace')
        vs,rva,rs,ro=struct.unpack_from('<IIII',raw,o+8)
        out.append(dict(name=name,va=base+rva,vsize=vs,rawSize=rs,rawOffset=ro,executable=bool(struct.unpack_from('<I',raw,o+36)[0]&0x20000000)))
    return out

def off_to_va(secs,off):
    for s in secs:
        if s['rawOffset']<=off<s['rawOffset']+s['rawSize']:
            return s['va']+(off-s['rawOffset'])
    return None

def occurrences(raw,needle):
    p=0; out=[]
    while True:
        p=raw.find(needle,p)
        if p<0:return out
        out.append(p);p+=1

def disasm_window(raw,secs,off,radius=48):
    s=next((x for x in secs if x['executable'] and x['rawOffset']<=off<x['rawOffset']+x['rawSize']),None)
    if not s:return []
    a=max(s['rawOffset'],off-radius); b=min(s['rawOffset']+s['rawSize'],off+radius)
    va=s['va']+(a-s['rawOffset']); md=Cs(CS_ARCH_X86,CS_MODE_32)
    return [dict(address=f"0x{i.address:08x}",bytes=i.bytes.hex(),mnemonic=i.mnemonic,opStr=i.op_str) for i in md.disasm(raw[a:b],va)]

def build(path:Path):
    raw=path.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
    if len(raw)!=EXPECTED_BYTES: raise E(f'bytes {len(raw)} != {EXPECTED_BYTES}')
    if sha!=EXPECTED_SHA256: raise E(f'SHA {sha} != {EXPECTED_SHA256}')
    secs=pe(raw)
    strings=[]
    for st in TARGET_STRINGS:
        for off in occurrences(raw,st): strings.append(dict(text=st[:-1].decode(),fileOffset=off,vaHex=(f"0x{off_to_va(secs,off):08x}" if off_to_va(secs,off) else None)))
    refs=[]
    # Absolute little-endian references to each physically mapped target string.
    for row in strings:
        if not row['vaHex']: continue
        va=int(row['vaHex'],16); needle=struct.pack('<I',va)
        for off in occurrences(raw,needle):
            sec=next((s for s in secs if s['executable'] and s['rawOffset']<=off<s['rawOffset']+s['rawSize']),None)
            if sec: refs.append(dict(target=row['text'],targetVa=row['vaHex'],referenceVa=f"0x{off_to_va(secs,off):08x}",fileOffset=off,window=disasm_window(raw,secs,off)))
    imm=[]
    for value in IMMEDIATES:
        needle=struct.pack('<I',value)
        hits=[]
        for off in occurrences(raw,needle):
            sec=next((s for s in secs if s['executable'] and s['rawOffset']<=off<s['rawOffset']+s['rawSize']),None)
            if sec: hits.append(dict(vaHex=f"0x{off_to_va(secs,off):08x}",fileOffset=off,window=disasm_window(raw,secs,off,32)))
        imm.append(dict(valueHex=f"0x{value:08x}",executableHitCount=len(hits),hits=hits))
    return dict(format='t6-retail-client-xasset-precedence-discovery-v1',client=dict(bytes=len(raw),sha256=sha,imageBaseHex=f"0x{IMAGE_BASE:08x}"),sections=secs,strings=strings,stringExecutableReferences=refs,immediateInventory=imm,status='discovery_only_no_winner_promoted',proofBoundary='Exact SHA-pinned retail-client byte inventory only. Candidate references and immediate occurrences are discovery evidence, not function identity or duplicate precedence proof. Server semantics, adjacency, ordering, and nearest-match behavior are not promoted.')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    try:r=build(a.exe)
    except E as e: raise SystemExit(f'FAIL: {e}')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({k:r[k] for k in ('format','client','status')},indent=2))
if __name__=='__main__':main()
