#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import struct
import subprocess
import time
from pathlib import Path

EXPECTED_SMODELS = 2992
EXPECTED_SURFACES = 5614
EXPECTED_VERTICES = 146764
EXPECTED_VD0 = 5285088
EXPECTED_VD1 = 33764
EXPECTED_INDICES = 300840


def maps_for(pid: int):
    out=[]
    try:
        text=Path(f'/proc/{pid}/maps').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return out
    for line in text.splitlines():
        parts=line.split(maxsplit=5)
        lo,hi=(int(x,16) for x in parts[0].split('-'))
        perms=parts[1]
        path=parts[5] if len(parts)>5 else ''
        out.append((lo,hi,perms,path))
    return out


def pread(fd:int, addr:int, n:int):
    try:
        b=os.pread(fd,n,addr)
        return b if len(b)==n else None
    except OSError:
        return None


def u16(fd,addr):
    b=pread(fd,addr,2); return struct.unpack('<H',b)[0] if b else None

def u32(fd,addr):
    b=pread(fd,addr,4); return struct.unpack('<I',b)[0] if b else None

def i32(fd,addr):
    b=pread(fd,addr,4); return struct.unpack('<i',b)[0] if b else None

def ptr(fd,addr): return u32(fd,addr)


def cstr(fd,addr,limit=512):
    if not addr: return None
    for n in (limit,256,128,64,32):
        b=pread(fd,addr,n)
        if b is None: continue
        z=b.find(b'\0')
        if z<=0: continue
        raw=b[:z]
        if any(c<0x20 or c>0x7e for c in raw): return None
        try: return raw.decode('ascii')
        except UnicodeDecodeError: return None
    return None


def region_contains(regions,addr,n=1):
    for lo,hi,perms,_ in regions:
        if lo<=addr and addr+n<=hi and 'r' in perms: return True
        if addr<lo: return False
    return False


def find_count_addresses(fd:int,regions,needle=EXPECTED_SMODELS):
    pat=struct.pack('<I',needle)
    chunk=4*1024*1024
    for lo,hi,perms,path in regions:
        if 'r' not in perms or 'w' not in perms or hi-lo<4096: continue
        pos=lo; tail=b''
        while pos<hi:
            n=min(chunk,hi-pos)
            try: b=os.pread(fd,n,pos)
            except OSError: break
            if not b: break
            data=tail+b; base=pos-len(tail); at=0
            while True:
                j=data.find(pat,at)
                if j<0: break
                a=base+j
                if a%4==0: yield a,path
                at=j+1
            tail=data[-3:]; pos+=len(b)
            if len(b)<n: break


def validate_candidate(fd:int,regions,world:int,L:dict,diag:dict):
    W=L['GfxWorld']; DP=L['GfxWorldDpvsStatic']; D=L['GfxWorldDraw']; V0=L['GfxWorldVertexData0']; V1=L['GfxWorldVertexData1']
    dp=world+W['dpvs']; draw=world+W['draw']
    if u32(fd,dp+DP['smodelCount'])!=EXPECTED_SMODELS: return None
    name=cstr(fd,ptr(fd,world+W['name']))
    if name: diag.setdefault('candidateNames',[]).append(name)
    if not name or 'mp_nuketown_2020' not in name: return None
    vals={
        'surfaceCount':i32(fd,world+W['surfaceCount']),
        'vertexCount':u32(fd,draw+D['vertexCount']),
        'vd0Bytes':u32(fd,draw+D['vertexDataSize0']),
        'vd1Bytes':u32(fd,draw+D['vertexDataSize1']),
        'indexCount':i32(fd,draw+D['indexCount']),
    }
    expected={
        'surfaceCount':EXPECTED_SURFACES,'vertexCount':EXPECTED_VERTICES,
        'vd0Bytes':EXPECTED_VD0,'vd1Bytes':EXPECTED_VD1,'indexCount':EXPECTED_INDICES,
    }
    if vals!=expected: return None
    surfaces=ptr(fd,dp+DP['surfaces'])
    vd0=ptr(fd,draw+D['vd0']+V0['data'])
    vd1=ptr(fd,draw+D['vd1']+V1['data'])
    indices=ptr(fd,draw+D['indices'])
    sizes={
        'surfaces':L['GfxSurface']['size']*EXPECTED_SURFACES,
        'vd0':EXPECTED_VD0,
        'vd1':EXPECTED_VD1,
        'indices':EXPECTED_INDICES*2,
    }
    ptrs={'surfaces':surfaces,'vd0':vd0,'vd1':vd1,'indices':indices}
    if any(not ptrs[k] or not region_contains(regions,ptrs[k],sizes[k]) for k in ptrs): return None
    return {'world':world,'worldName':name,'draw':draw,'dpvs':dp,**vals,**ptrs}


def find_world(pid:int,fd:int,L:dict,deadline:float,diag:dict):
    count_off=L['GfxWorld']['dpvs']+L['GfxWorldDpvsStatic']['smodelCount']
    passes=0
    while time.monotonic()<deadline:
        if not Path(f'/proc/{pid}').exists(): break
        regions=maps_for(pid)
        raw=0
        for q,path in find_count_addresses(fd,regions):
            raw+=1
            if q<count_off: continue
            hit=validate_candidate(fd,regions,q-count_off,L,diag)
            if hit:
                diag.update({'passes':passes+1,'raw2992HitsLastPass':raw,'countOffset':count_off,'candidateMapping':path})
                return hit
        passes+=1
        diag.update({'passes':passes,'raw2992HitsLastPass':raw,'countOffset':count_off})
        time.sleep(0.01)
    return None


def unpack_vec3(blob:bytes,off:int): return list(struct.unpack_from('<3f',blob,off))


def dump_world(fd:int,L:dict,hit:dict,out_dir:Path):
    out_dir.mkdir(parents=True,exist_ok=True)
    vd0=pread(fd,hit['vd0'],EXPECTED_VD0)
    vd1=pread(fd,hit['vd1'],EXPECTED_VD1)
    indices=pread(fd,hit['indices'],EXPECTED_INDICES*2)
    if vd0 is None or vd1 is None or indices is None: raise RuntimeError('failed frozen draw-buffer read')
    (out_dir/'gfxworld.vd0.bin').write_bytes(vd0)
    (out_dir/'gfxworld.vd1.bin').write_bytes(vd1)
    (out_dir/'gfxworld.indices.bin').write_bytes(indices)

    S=L['GfxSurface']; T=L['srfTriangles_t']; M=L['Material']; MI=L['MaterialInfo']; TS=L['MaterialTechniqueSet']
    rows=[]; materials={}
    null_materials=0; null_techsets=0
    for i in range(EXPECTED_SURFACES):
        sb=pread(fd,hit['surfaces']+i*S['size'],S['size'])
        if sb is None: raise RuntimeError(f'failed surface read {i}')
        toff=S['tris']
        mat_ptr=struct.unpack_from('<I',sb,S['material'])[0]
        mat_name=None; tech_name=None; fmt=None; tech_ptr=None
        if mat_ptr:
            mat_name=cstr(fd,ptr(fd,mat_ptr+M['info']+MI['name']))
            tech_ptr=ptr(fd,mat_ptr+M['techniqueSet'])
            if tech_ptr:
                tech_name=cstr(fd,ptr(fd,tech_ptr+TS['name']))
                raw=pread(fd,tech_ptr+TS['worldVertFormat'],4)
                fmt=struct.unpack('<I',raw)[0] if raw else None
            else:
                null_techsets+=1
        else:
            null_materials+=1
        if mat_name is None: raise RuntimeError(f'surface {i}: unresolved material name for pointer {mat_ptr:#x}')
        if fmt is None or not (0<=int(fmt)<=8): raise RuntimeError(f'surface {i}: invalid worldVertFormat {fmt} for {mat_name}')
        row={
            'index':i,
            'mins':unpack_vec3(sb,toff+T['mins']),
            'maxs':unpack_vec3(sb,toff+T['maxs']),
            'vertexDataOffset0':struct.unpack_from('<i',sb,toff+T['vertexDataOffset0'])[0],
            'vertexDataOffset1':struct.unpack_from('<i',sb,toff+T['vertexDataOffset1'])[0],
            'firstVertex':struct.unpack_from('<i',sb,toff+T['firstVertex'])[0],
            'himipRadiusInvSq':struct.unpack_from('<f',sb,toff+T['himipRadiusInvSq'])[0],
            'vertexCount':struct.unpack_from('<H',sb,toff+T['vertexCount'])[0],
            'triCount':struct.unpack_from('<H',sb,toff+T['triCount'])[0],
            'baseIndex':struct.unpack_from('<i',sb,toff+T['baseIndex'])[0],
            'material':mat_name,
            'materialPointerRuntime':f'0x{mat_ptr:08x}',
            'techniqueSet':tech_name,
            'techniqueSetPointerRuntime':f'0x{tech_ptr:08x}' if tech_ptr else None,
            'worldVertFormat':int(fmt),
        }
        rows.append(row)
        rec=materials.setdefault(mat_name,{'name':mat_name,'runtimePointer':f'0x{mat_ptr:08x}','techniqueSet':tech_name,'worldVertFormat':int(fmt),'surfaceCount':0})
        if rec['worldVertFormat']!=int(fmt) or rec['techniqueSet']!=tech_name:
            raise RuntimeError(f'material identity changed across surfaces: {mat_name}')
        rec['surfaceCount']+=1

    # Direct draw-contract sanity before writing proof sidecars.
    if any(r['triCount']<=0 for r in rows): raise RuntimeError('zero-triangle world surface')
    if any(r['baseIndex']<0 or r['baseIndex']+r['triCount']*3>EXPECTED_INDICES for r in rows):
        raise RuntimeError('surface index range outside global index buffer')
    if any(r['vertexDataOffset0']<0 or r['vertexDataOffset0']>=EXPECTED_VD0 for r in rows):
        raise RuntimeError('surface vd0 offset outside draw buffer')
    if any(r['vertexDataOffset1']<0 or r['vertexDataOffset1']>EXPECTED_VD1 for r in rows):
        raise RuntimeError('surface vd1 offset outside draw buffer')

    surface_doc={
        'format':'t6-gfxworld-live-surface-table-v1',
        'name':'mp_nuketown_2020',
        'worldName':hit['worldName'],
        'surfaceCount':EXPECTED_SURFACES,
        'vertexCount':EXPECTED_VERTICES,
        'vertexDataSize0':EXPECTED_VD0,
        'vertexDataSize1':EXPECTED_VD1,
        'indexCount':EXPECTED_INDICES,
        'surfaces':rows,
    }
    (out_dir/'gfxworld.surfaces.json').write_text(json.dumps(surface_doc,separators=(',',':'))+'\n')
    mat_doc={'format':'t6-gfxworld-live-material-format-table-v1','map':'mp_nuketown_2020','materialCount':len(materials),'materials':sorted(materials.values(),key=lambda x:x['name'])}
    (out_dir/'gfxworld.material_formats.json').write_text(json.dumps(mat_doc,indent=2,sort_keys=True)+'\n')
    summary={
        'format':'t6-gfxworld-live-world-stream-extraction-v1',
        'worldName':hit['worldName'],
        'surfaceCount':EXPECTED_SURFACES,
        'vertexCount':EXPECTED_VERTICES,
        'vd0Bytes':len(vd0),'vd0Sha256':hashlib.sha256(vd0).hexdigest(),
        'vd1Bytes':len(vd1),'vd1Sha256':hashlib.sha256(vd1).hexdigest(),
        'indexCount':EXPECTED_INDICES,'indexBytes':len(indices),'indicesSha256':hashlib.sha256(indices).hexdigest(),
        'surfaceTableSha256':hashlib.sha256((out_dir/'gfxworld.surfaces.json').read_bytes()).hexdigest(),
        'materialCount':len(materials),
        'nullMaterialPointers':null_materials,
        'nullTechniqueSets':null_techsets,
        'observedWorldVertFormats':sorted({r['worldVertFormat'] for r in rows}),
    }
    (out_dir/'GFXWORLD_WORLD_STREAM_EXTRACTION_V1.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    return summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--layout',type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    ap.add_argument('--diag',type=Path,required=True)
    ap.add_argument('--timeout',type=float,default=30.0)
    ap.add_argument('command',nargs=argparse.REMAINDER)
    a=ap.parse_args()
    cmd=a.command[1:] if a.command and a.command[0]=='--' else a.command
    if not cmd: ap.error('missing target command after --')
    L=json.loads(a.layout.read_text())
    if L.get('ptrSize')!=4: raise SystemExit(f'expected x86 pointer size 4, got {L.get("ptrSize")}')
    a.out_dir.mkdir(parents=True,exist_ok=True)
    log=(a.out_dir/'oat-world-scan-target.log').open('wb')
    p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
    diag={'format':'t6-oat-external-gfxworld-world-scan-diagnostics-v1','pid':p.pid,'command':cmd}
    fd=None; frozen=False
    try:
        for _ in range(400):
            try:
                fd=os.open(f'/proc/{p.pid}/mem',os.O_RDONLY); break
            except OSError:
                if p.poll() is not None: break
                time.sleep(0.005)
        if fd is None: raise RuntimeError('could not open child /proc/PID/mem')
        hit=find_world(p.pid,fd,L,time.monotonic()+a.timeout,diag)
        if not hit:
            diag['targetReturnCode']=p.poll()
            raise RuntimeError(f'no validated Nuketown GfxWorld found; diagnostics={diag}')
        diag['validatedWorld']={k:v for k,v in hit.items() if k not in ('world','draw','dpvs','surfaces','vd0','vd1','indices')}
        os.kill(p.pid,signal.SIGSTOP)
        _,status=os.waitpid(p.pid,os.WUNTRACED)
        if not os.WIFSTOPPED(status): raise RuntimeError(f'child did not stop cleanly: status={status}')
        frozen=True
        summary=dump_world(fd,L,hit,a.out_dir)
        diag['summary']=summary
    finally:
        if fd is not None: os.close(fd)
        if frozen:
            try: os.kill(p.pid,signal.SIGCONT)
            except ProcessLookupError: pass
        try: rc=p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.terminate()
            try: rc=p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill(); rc=p.wait()
        diag['targetFinalReturnCode']=rc
        log.close()
        a.diag.write_text(json.dumps(diag,indent=2,sort_keys=True)+'\n')
    print(json.dumps(diag,indent=2,sort_keys=True))

if __name__=='__main__': main()
