#!/usr/bin/env python3
"""Comparative-only probe for T6 current-client DB zone-priority machinery.

This deliberately does NOT promote current Plutonium client behavior to historical
retail authority.  It searches executable sections for structural instruction
signatures independently proved in the exact PC dedicated-server build, while
allowing relocation-sensitive absolute addresses to differ.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

SERVER_SHA256='f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d'
CURRENT_EXPECTED_SHA256='770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf'

def pe(raw):
    peoff=struct.unpack_from('<I',raw,0x3c)[0]
    assert raw[peoff:peoff+4]==b'PE\0\0'
    n=struct.unpack_from('<H',raw,peoff+6)[0]; opt=peoff+24
    base=struct.unpack_from('<I',raw,opt+28)[0]; sec=opt+struct.unpack_from('<H',raw,peoff+20)[0]
    out=[]
    for i in range(n):
        o=sec+i*40; name=raw[o:o+8].split(b'\0')[0].decode('ascii','replace')
        vs,va,rs,rp=struct.unpack_from('<IIII',raw,o+8)
        chars=struct.unpack_from('<I',raw,o+36)[0]
        if chars & 0x20000000: out.append((name,rp,min(rs,len(raw)-rp),base+va))
    return base,out

def windows(raw, sections, pattern, label):
    md=Cs(CS_ARCH_X86,CS_MODE_32); hits=[]
    for sn,rp,sz,va in sections:
        blob=raw[rp:rp+sz]; p=0
        while True:
            j=blob.find(pattern,p)
            if j<0: break
            lo=max(0,j-48); hi=min(len(blob),j+len(pattern)+96)
            ins=[]
            for x in md.disasm(blob[lo:hi],va+lo):
                ins.append({'address':f'0x{x.address:08x}','bytes':x.bytes.hex(),'mnemonic':x.mnemonic,'opStr':x.op_str})
            hits.append({'section':sn,'fileOffset':rp+j,'vaHex':f'0x{va+j:08x}','label':label,'window':ins})
            p=j+1
    return hits

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('exe'); ap.add_argument('--revision',default='unknown'); ap.add_argument('--out',required=True); a=ap.parse_args()
    raw=Path(a.exe).read_bytes(); sha=hashlib.sha256(raw).hexdigest()
    if sha != CURRENT_EXPECTED_SHA256: raise SystemExit(f'fail closed: expected current-client sha256 {CURRENT_EXPECTED_SHA256}, got {sha}')
    base,secs=pe(raw)
    # Address-free fragments from exact server proof.  These encode the two explicit
    # priority branches and the stored-zone flag mask, not guessed function names.
    sigs=[
      ('priority_explicit_0x80_branch',bytes.fromhex('3d8000000074203d0001000074123d00020000')),
      ('priority_return_0x80_54',bytes.fromhex('b8360000005dc3')),
      ('priority_explicit_0x8000_branch',bytes.fromhex('3d00800000741c3d00000100740e3d00000200')),
      ('priority_return_0x8000_57',bytes.fromhex('b8390000005dc3')),
      ('stored_flag_mask_and_eax',bytes.fromhex('25ffffff3f')),
      ('stored_flag_mask_and_ecx',bytes.fromhex('81e1ffffff3f')),
    ]
    found={k:windows(raw,secs,v,k) for k,v in sigs}
    exact={k:len(v) for k,v in found.items()}
    out={'format':'t6-current-client-db-priority-signature-probe-v1','status':'comparative_discovery_only_no_retail_winner_promoted','authority':'current Plutonium CDN client only; NOT historical retail authority','client':{'revision':str(a.revision),'bytes':len(raw),'sha256':sha,'imageBaseHex':f'0x{base:08x}'},'serverReference':{'sha256':SERVER_SHA256,'authority':'exact PC dedicated-server proof only'},'exactAddressFreeSignatureHitCounts':exact,'hits':found,'proofBoundary':'Exact byte matches here may establish code conservation between the SHA-pinned current client and exact server for the matched address-free fragment only. Absence does not disprove semantic conservation. Presence does not establish historical retail t6mp.exe behavior, function identity outside the matched bytes, zone ownership, or any winner among the 58 retail Technique conflicts.'}
    Path(a.out).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'sha256':sha,'hits':exact},indent=2))
if __name__=='__main__': main()
