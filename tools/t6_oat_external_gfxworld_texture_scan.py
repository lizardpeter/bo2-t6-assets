#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import signal
import struct
import subprocess
import time
from pathlib import Path

EXPECTED_SMODELS=2992
EXPECTED_SURFACES=5614
EXPECTED_WORLD_MATERIALS=327
EXPECTED_UNIQUE_IMAGES=423


def pread(fd,addr,n):
    try:
        b=os.pread(fd,n,addr)
        return b if len(b)==n else None
    except OSError:
        return None


def u8(fd,a):
    b=pread(fd,a,1); return b[0] if b else None

def u16(fd,a):
    b=pread(fd,a,2); return struct.unpack('<H',b)[0] if b else None

def u32(fd,a):
    b=pread(fd,a,4); return struct.unpack('<I',b)[0] if b else None

def i32(fd,a):
    b=pread(fd,a,4); return struct.unpack('<i',b)[0] if b else None

def ptr(fd,a): return u32(fd,a)


def cstr(fd,addr,limit=512):
    if not addr:return None
    for n in (limit,256,128,64,32):
        b=pread(fd,addr,n)
        if b is None:continue
        z=b.find(b'\0')
        if z<=0:continue
        raw=b[:z]
        if any(c<0x20 or c>0x7e for c in raw):return None
        try:return raw.decode('ascii')
        except UnicodeDecodeError:return None
    return None


def rhash(s:str,h=0):
    for c in s.encode('latin1'):
        h=((33*h)^(c|0x20))&0xffffffff
    return h


def maps_for(pid):
    out=[]
    try:text=Path(f'/proc/{pid}/maps').read_text()
    except (FileNotFoundError,ProcessLookupError):return out
    for line in text.splitlines():
        p=line.split(maxsplit=5); lo,hi=(int(x,16) for x in p[0].split('-'))
        out.append((lo,hi,p[1],p[5] if len(p)>5 else ''))
    return out


def find_count_addresses(fd,regions,needle=EXPECTED_SMODELS):
    pat=struct.pack('<I',needle); chunk=4*1024*1024
    for lo,hi,perms,path in regions:
        if 'r' not in perms or 'w' not in perms or hi-lo<4096:continue
        pos=lo; tail=b''
        while pos<hi:
            n=min(chunk,hi-pos)
            try:b=os.pread(fd,n,pos)
            except OSError:break
            if not b:break
            data=tail+b;base=pos-len(tail);at=0
            while True:
                j=data.find(pat,at)
                if j<0:break
                a=base+j
                if a%4==0:yield a,path
                at=j+1
            tail=data[-3:];pos+=len(b)
            if len(b)<n:break


def surface_material_snapshot(fd,W,world):
    GW=W['GfxWorld']; DP=W['GfxWorldDpvsStatic']; S=W['GfxSurface']
    surfaces=ptr(fd,world+GW['dpvs']+DP['surfaces'])
    if not surfaces:return None
    out=[]
    for si in range(EXPECTED_SURFACES):
        mp=ptr(fd,surfaces+si*S['size']+S['material'])
        if not mp:return None
        out.append(mp)
    return tuple(out)


def find_world(pid,fd,W,deadline,diag):
    count_off=W['GfxWorld']['dpvs']+W['GfxWorldDpvsStatic']['smodelCount']
    passes=0
    while time.monotonic()<deadline:
        if not Path(f'/proc/{pid}').exists():break
        regions=maps_for(pid); raw=0
        for q,path in find_count_addresses(fd,regions):
            raw+=1
            if q<count_off:continue
            world=q-count_off
            if u32(fd,world+count_off)!=EXPECTED_SMODELS:continue
            name=cstr(fd,ptr(fd,world+W['GfxWorld']['name']))
            if not name or 'mp_nuketown_2020' not in name:continue
            if i32(fd,world+W['GfxWorld']['surfaceCount'])!=EXPECTED_SURFACES:continue

            first=surface_material_snapshot(fd,W,world)
            if first is None:continue
            distinct=len(set(first))
            if distinct!=EXPECTED_WORLD_MATERIALS:continue
            time.sleep(0.01)
            second=surface_material_snapshot(fd,W,world)
            if second is None or second!=first:continue

            diag.update({
                'passes':passes+1,
                'raw2992HitsLastPass':raw,
                'candidateMapping':path,
                'worldName':name,
                'surfaceMaterialReadiness':{
                    'surfaceCount':len(first),
                    'nonNullMaterialPointers':len(first),
                    'distinctMaterialPointers':distinct,
                    'stableConsecutiveSnapshots':2,
                },
            })
            return world
        passes+=1;diag.update({'passes':passes,'raw2992HitsLastPass':raw});time.sleep(0.01)
    return None


def scan(fd,W,T,world):
    GW=W['GfxWorld']; DP=W['GfxWorldDpvsStatic']; S=W['GfxSurface']; MI=W['MaterialInfo']
    M=T['Material']; TD=T['MaterialTextureDef']; I=T['GfxImage']; SP=T['GfxStreamedPartInfo']
    surfaces=ptr(fd,world+GW['dpvs']+DP['surfaces'])
    if not surfaces:raise RuntimeError('null world surface pointer')

    mat_ptrs={}
    for si in range(EXPECTED_SURFACES):
        mp=ptr(fd,surfaces+si*S['size']+S['material'])
        if not mp:raise RuntimeError(f'surface {si}: null material')
        name=cstr(fd,ptr(fd,mp+M['info']+MI['name']))
        if not name:raise RuntimeError(f'surface {si}: unresolved material {mp:#x}')
        old=mat_ptrs.setdefault(name,mp)
        if old!=mp:raise RuntimeError(f'material {name}: multiple live pointers {old:#x}/{mp:#x}')
    if len(mat_ptrs)!=EXPECTED_WORLD_MATERIALS:
        raise RuntimeError(f'world material count {len(mat_ptrs)} != {EXPECTED_WORLD_MATERIALS}')

    mats=[]; images={}; texture_entries=0; runtime_code_images=set()
    for mname,mp in sorted(mat_ptrs.items()):
        tc=u8(fd,mp+M['textureCount']); table=ptr(fd,mp+M['textureTable'])
        if tc is None or tc>64:raise RuntimeError(f'{mname}: invalid textureCount {tc}')
        if tc and not table:raise RuntimeError(f'{mname}: null textureTable with count {tc}')
        tex=[]
        for slot in range(tc):
            a=table+slot*TD['size']
            raw=pread(fd,a,TD['size'])
            if raw is None:raise RuntimeError(f'{mname}: unreadable texture def {slot}')
            name_hash=struct.unpack_from('<I',raw,TD['nameHash'])[0]
            name_start=raw[TD['nameStart']]; name_end=raw[TD['nameEnd']]
            sampler=raw[TD['samplerState']]; semantic=raw[TD['semantic']]; mature=bool(raw[TD['isMatureContent']])
            ip=struct.unpack_from('<I',raw,TD['image'])[0]
            if not ip:raise RuntimeError(f'{mname} slot {slot}: null image pointer')
            iname=cstr(fd,ptr(fd,ip+I['name']))
            if not iname:raise RuntimeError(f'{mname} slot {slot}: unresolved GfxImage name {ip:#x}')
            ih=u32(fd,ip+I['hash']); w=u16(fd,ip+I['width']); h=u16(fd,ip+I['height']); d=u16(fd,ip+I['depth'])
            streaming=u8(fd,ip+I['streaming']); part_count=u8(fd,ip+I['streamedPartCount'])
            if None in (ih,w,h,d,streaming,part_count):raise RuntimeError(f'{iname}: truncated GfxImage')

            calc=rhash(iname)
            runtime_code=(ih==0 and iname.startswith(','))
            if ih==0 and not runtime_code:
                raise RuntimeError(f'{iname}: zero GfxImage.hash outside runtime/code namespace')
            if not runtime_code and ih!=calc:
                raise RuntimeError(f'{iname}: GfxImage.hash {ih:08x} != R_HashString {calc:08x}')
            if runtime_code:
                runtime_code_images.add(iname)

            part=None
            if part_count:
                sp=ip+I['streamedParts']
                ph=u32(fd,sp+SP['hash']); pw=u16(fd,sp+SP['width']); phh=u16(fd,sp+SP['height'])
                if None in (ph,pw,phh):raise RuntimeError(f'{iname}: unreadable streamed part')
                part={'hash':ph,'hash29':ph&0x1fffffff,'width':pw,'height':phh}

            rec={
                'slot':slot,'nameHash':name_hash,'nameStart':name_start,'nameEnd':name_end,
                'samplerState':sampler,'semantic':semantic,'isMatureContent':mature,
                'image':iname,'imagePointerRuntime':f'0x{ip:08x}','imageHash':ih,
                'computedRHashString':calc,
                'identityClass':'runtime-code-hash-zero' if runtime_code else 'retail-name-hash-validated',
                'hashValidation':'runtime-code-zero-hash-separated' if runtime_code else 'R_HashString-exact',
                'width':w,'height':h,'depth':d,'streaming':streaming,
                'streamedPartCountRaw':part_count,'streamedPart0':part,
            }
            tex.append(rec);texture_entries+=1
            prev=images.get(iname)
            image_rec={k:rec[k] for k in ('image','imageHash','computedRHashString','identityClass','hashValidation','width','height','depth','streaming','streamedPartCountRaw')}
            image_rec['streamedPart0']=part
            if prev is None:images[iname]=image_rec
            elif prev!=image_rec:raise RuntimeError(f'{iname}: conflicting live GfxImage metadata')
        mats.append({'name':mname,'runtimePointer':f'0x{mp:08x}','textureCount':tc,'textures':tex})

    if len(images)!=EXPECTED_UNIQUE_IMAGES:
        raise RuntimeError(f'unique world image count {len(images)} != {EXPECTED_UNIQUE_IMAGES}')
    semantic_counts=collections.Counter(t['semantic'] for m in mats for t in m['textures'])
    streaming_counts=collections.Counter(v['streaming'] for v in images.values())
    part_counts=collections.Counter(v['streamedPartCountRaw'] for v in images.values())
    ordinary_images=[v for v in images.values() if v['identityClass']=='retail-name-hash-validated']
    runtime_images=[images[k] for k in sorted(runtime_code_images)]
    if len(ordinary_images)+len(runtime_images)!=EXPECTED_UNIQUE_IMAGES:
        raise RuntimeError('image identity-class accounting mismatch')

    doc={
        'format':'t6-nuketown-live-world-material-texture-identities-v2',
        'map':'mp_nuketown_2020','materialCount':len(mats),'textureEntryCount':texture_entries,
        'uniqueImageCount':len(images),'ordinaryRetailImageCount':len(ordinary_images),
        'runtimeCodeImageCount':len(runtime_images),'runtimeCodeImages':runtime_images,
        'semanticEntryCounts':{str(k):v for k,v in sorted(semantic_counts.items())},
        'uniqueImageStreamingCounts':{str(k):v for k,v in sorted(streaming_counts.items())},
        'uniqueImageStreamedPartCounts':{str(k):v for k,v in sorted(part_counts.items())},
        'materials':mats,'images':[images[k] for k in sorted(images)],
        'proofBoundary':'Every record is read from the frozen retail GfxWorld surface Material pointer, its live MaterialTextureDef array and direct live GfxImage pointer. Ordinary retail GfxImages are still fail-closed: GfxImage.hash must exactly equal R_HashString(image name). Hash-zero comma-prefixed runtime/code images are explicitly classified and retained as runtime identities instead of being treated as streamed IPAK assets. Streamed payload identity for ordinary assets is the live streamedParts[0].hash, retained both full-width and CRC29/IPAK form.',
    }
    return doc


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world-layout',type=Path,required=True);ap.add_argument('--texture-layout',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--diag',type=Path,required=True);ap.add_argument('--timeout',type=float,default=30);ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args()
    cmd=a.command[1:] if a.command and a.command[0]=='--' else a.command
    if not cmd:ap.error('missing target command')
    W=json.loads(a.world_layout.read_text());T=json.loads(a.texture_layout.read_text())
    if W.get('ptrSize')!=4 or T.get('ptrSize')!=4:raise SystemExit('expected x86 layouts')
    log=a.out.with_suffix('.target.log').open('wb');p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
    diag={'format':'t6-oat-external-gfxworld-texture-scan-diagnostics-v2','pid':p.pid,'command':cmd};fd=None;frozen=False
    try:
        for _ in range(400):
            try:fd=os.open(f'/proc/{p.pid}/mem',os.O_RDONLY);break
            except OSError:
                if p.poll() is not None:break
                time.sleep(.005)
        if fd is None:raise RuntimeError('could not open child mem')
        world=find_world(p.pid,fd,W,time.monotonic()+a.timeout,diag)
        if world is None:raise RuntimeError(f'no validated Nuketown GfxWorld: {diag}')
        os.kill(p.pid,signal.SIGSTOP);_,status=os.waitpid(p.pid,os.WUNTRACED)
        if not os.WIFSTOPPED(status):raise RuntimeError('child did not freeze')
        frozen=True
        doc=scan(fd,W,T,world);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
        diag['summary']={k:doc[k] for k in ('materialCount','textureEntryCount','uniqueImageCount','ordinaryRetailImageCount','runtimeCodeImageCount','semanticEntryCounts','uniqueImageStreamingCounts','uniqueImageStreamedPartCounts')}
        diag['outputSha256']=hashlib.sha256(a.out.read_bytes()).hexdigest()
    finally:
        if fd is not None:os.close(fd)
        if frozen:
            try:os.kill(p.pid,signal.SIGCONT)
            except ProcessLookupError:pass
        try:rc=p.wait(timeout=30)
        except subprocess.TimeoutExpired:p.terminate();rc=p.wait(timeout=5)
        diag['targetFinalReturnCode']=rc;log.close();a.diag.write_text(json.dumps(diag,indent=2,sort_keys=True)+'\n')
    print(json.dumps(diag,indent=2,sort_keys=True))

if __name__=='__main__':main()
