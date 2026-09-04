#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, signal, struct, subprocess, sys, time
from pathlib import Path

COUNT = 2992
NEEDLE = b"mp_nuketown_2020"


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


def u32(fd,addr):
    b=pread(fd,addr,4); return struct.unpack('<I',b)[0] if b else None

def i32(fd,addr):
    b=pread(fd,addr,4); return struct.unpack('<i',b)[0] if b else None

def ptr(fd,addr): return u32(fd,addr)

def f32(fd,addr):
    b=pread(fd,addr,4); return struct.unpack('<f',b)[0] if b else None

def cstr(fd,addr,limit=256):
    if not addr: return None
    b=pread(fd,addr,limit)
    if b is None:
        # String may be close to a mapping boundary; try a shorter read.
        for n in (128,64,32):
            b=pread(fd,addr,n)
            if b is not None: break
    if b is None: return None
    z=b.find(b'\0')
    if z<=0: return None
    s=b[:z]
    if any(c<0x20 or c>0x7e for c in s): return None
    try: return s.decode('ascii')
    except UnicodeDecodeError: return None


def vec3_from(blob:bytes,off:int): return list(struct.unpack_from('<3f',blob,off))


def region_contains(regions,addr,n=1):
    for lo,hi,perms,_ in regions:
        if lo<=addr and addr+n<=hi and 'r' in perms: return True
        if addr<lo: return False
    return False


def find_count_addresses(fd:int,regions,needle=COUNT):
    pat=struct.pack('<I',needle)
    chunk=4*1024*1024
    for lo,hi,perms,path in regions:
        # Typed zone objects live in writable mappings; omit executable and tiny regions.
        if 'r' not in perms or 'w' not in perms or hi-lo<4096: continue
        pos=lo
        tail=b''
        while pos<hi:
            n=min(chunk,hi-pos)
            try: b=os.pread(fd,n,pos)
            except OSError: break
            if not b: break
            data=tail+b
            base=pos-len(tail)
            at=0
            while True:
                j=data.find(pat,at)
                if j<0: break
                a=base+j
                if a%4==0: yield a,path
                at=j+1
            tail=data[-3:]
            pos+=len(b)
            if len(b)<n: break


def validate_candidate(fd:int,regions,world:int,L:dict,diag:dict):
    W=L['GfxWorld']; D=L['GfxWorldDpvsStatic']; SD=L['GfxStaticModelDrawInst']
    dp=world+W['dpvs']
    if u32(fd,dp+D['smodelCount'])!=COUNT: return None
    np=ptr(fd,world+W['name']); name=cstr(fd,np) if np else None
    if name: diag.setdefault('candidateNames',[]).append(name)
    if not name or 'mp_nuketown_2020' not in name: return None
    surf=i32(fd,world+W['surfaceCount'])
    if surf is None or not (1000<=surf<=10000): return None
    ip=ptr(fd,dp+D['smodelInsts']); dpn=ptr(fd,dp+D['smodelDrawInsts'])
    if not ip or not dpn: return None
    if not region_contains(regions,ip,L['GfxStaticModelInst']['size']*COUNT): return None
    if not region_contains(regions,dpn,SD['size']*COUNT): return None
    good=0; sample=[]
    for i in range(min(COUNT,64)):
        mp=ptr(fd,dpn+i*SD['size']+SD['model'])
        mn=cstr(fd,ptr(fd,mp+L['XModel']['name'])) if mp and region_contains(regions,mp,4) else None
        if mn:
            good+=1
            if len(sample)<12: sample.append(mn)
    if good<16: return None
    return {'world':world,'worldName':name,'surfaceCount':surf,'insts':ip,'draws':dpn,'goodSampleNames':good,'sampleModelNames':sample}


def find_world(pid:int,fd:int,L:dict,deadline:float,diag:dict):
    count_off=L['GfxWorld']['dpvs']+L['GfxWorldDpvsStatic']['smodelCount']
    passes=0
    while time.monotonic()<deadline:
        if not Path(f'/proc/{pid}').exists(): break
        regions=maps_for(pid)
        if not regions: break
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


def dump_world(fd:int,L:dict,hit:dict,out:Path):
    I=L['GfxStaticModelInst']; D=L['GfxStaticModelDrawInst']; P=L['GfxPackedPlacement']; X=L['XModel']
    rows=[]
    for i in range(COUNT):
        ib=pread(fd,hit['insts']+i*I['size'],I['size'])
        db=pread(fd,hit['draws']+i*D['size'],D['size'])
        if ib is None or db is None: raise RuntimeError(f'failed to read frozen static row {i}')
        po=D['placement']
        model_ptr=struct.unpack_from('<I',db,D['model'])[0]
        name_ptr=u32(fd,model_ptr+X['name']) if model_ptr else None
        model=cstr(fd,name_ptr) if name_ptr else None
        axis_off=po+P['axis']
        rows.append({
            'index':i,
            'model':model,
            'cullDist':struct.unpack_from('<f',db,D['cullDist'])[0],
            'origin':vec3_from(db,po+P['origin']),
            'axis':[vec3_from(db,axis_off+j*12) for j in range(3)],
            'scale':struct.unpack_from('<f',db,po+P['scale'])[0],
            'flags':struct.unpack_from('<i',db,D['flags'])[0],
            'mins':vec3_from(ib,I['mins']),
            'maxs':vec3_from(ib,I['maxs']),
            'lightingOrigin':vec3_from(ib,I['lightingOrigin']),
            'lightingHandle':struct.unpack_from('<H',db,D['lightingHandle'])[0],
            'colorsIndex':struct.unpack_from('<H',db,D['colorsIndex'])[0],
            'primaryLightIndex':struct.unpack_from('<b',db,D['primaryLightIndex'])[0],
            'visibility':struct.unpack_from('<b',db,D['visibility'])[0],
            'reflectionProbeIndex':struct.unpack_from('<b',db,D['reflectionProbeIndex'])[0],
            'smid':struct.unpack_from('<I',db,D['smid'])[0],
        })
    obj={
        'format':'t6-gfxworld-static-placement-external-v1',
        'worldName':hit['worldName'],
        'surfaceCount':hit['surfaceCount'],
        'smodelCount':COUNT,
        'layout':L,
        'placements':rows,
    }
    out.write_text(json.dumps(obj,separators=(',',':'))+'\n')
    return obj


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--layout',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--diag',type=Path,required=True)
    ap.add_argument('--timeout',type=float,default=15.0)
    ap.add_argument('command',nargs=argparse.REMAINDER)
    a=ap.parse_args()
    cmd=a.command[1:] if a.command and a.command[0]=='--' else a.command
    if not cmd: ap.error('missing target command after --')
    L=json.loads(a.layout.read_text())
    if L.get('ptrSize')!=4: raise SystemExit(f'expected x86 pointer size 4, got {L.get("ptrSize")}')
    log=Path('oat-external-scan-target.log').open('wb')
    p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
    diag={'format':'t6-oat-external-gfxworld-scan-diagnostics-v1','pid':p.pid,'command':cmd}
    fd=None; frozen=False
    try:
        # As the direct parent, this scanner is allowed to read /proc/PID/mem under ptrace_scope=1.
        for _ in range(200):
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
        diag['validatedWorld']={k:v for k,v in hit.items() if k not in ('insts','draws')}
        os.kill(p.pid,signal.SIGSTOP)
        # Ensure the child is actually stopped before copying any arrays.
        _,status=os.waitpid(p.pid,os.WUNTRACED)
        if not os.WIFSTOPPED(status): raise RuntimeError(f'child did not stop cleanly: status={status}')
        frozen=True
        obj=dump_world(fd,L,hit,a.out)
        diag['dumpRows']=len(obj['placements'])
        diag['nullModelNames']=sum(r['model'] is None for r in obj['placements'])
    finally:
        if fd is not None: os.close(fd)
        if frozen:
            try: os.kill(p.pid,signal.SIGCONT)
            except ProcessLookupError: pass
        try: rc=p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.terminate()
            try: rc=p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill(); rc=p.wait()
        diag['targetFinalReturnCode']=rc
        log.close()
        a.diag.write_text(json.dumps(diag,indent=2)+'\n')
    print(json.dumps(diag,indent=2))

if __name__=='__main__': main()
