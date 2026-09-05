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

import t6_oat_external_gfxworld_texture_scan as base

EXPECTED_SMODELS = 2992


def static_model_snapshot(fd, W, X, world):
    GW = W['GfxWorld']; DP = W['GfxWorldDpvsStatic']; D = X['GfxStaticModelDrawInst']; XM = X['XModel']
    draws = base.ptr(fd, world + GW['dpvs'] + DP['smodelDrawInsts'])
    if not draws:
        return None
    out = []
    for i in range(EXPECTED_SMODELS):
        xp = base.ptr(fd, draws + i * D['size'] + D['model'])
        if not xp:
            return None
        name = base.cstr(fd, base.ptr(fd, xp + XM['name']))
        ns = base.u8(fd, xp + XM['numsurfs'])
        mh = base.ptr(fd, xp + XM['materialHandles'])
        if not name or ns is None or ns > 128 or (ns and not mh):
            return None
        handles = []
        for j in range(ns):
            mp = base.ptr(fd, mh + j * 4)
            if not mp:
                return None
            handles.append(mp)
        out.append((xp, name, ns, tuple(handles)))
    return tuple(out)


def wait_static_ready(fd, W, X, world, deadline, diag):
    attempts = 0
    while time.monotonic() < deadline:
        first = static_model_snapshot(fd, W, X, world)
        if first is not None:
            time.sleep(0.01)
            second = static_model_snapshot(fd, W, X, world)
            if second == first:
                diag['staticReadiness'] = {
                    'drawInstanceCount': len(first),
                    'nonNullModelPointers': len(first),
                    'distinctModelPointers': len({r[0] for r in first}),
                    'distinctModelNames': len({r[1] for r in first}),
                    'materialHandleReferences': sum(r[2] for r in first),
                    'stableConsecutiveSnapshots': 2,
                }
                return first
        attempts += 1
        time.sleep(0.01)
    diag['staticReadinessAttempts'] = attempts
    return None


def scan_image(fd, T, ip):
    I = T['GfxImage']; SP = T['GfxStreamedPartInfo']
    iname = base.cstr(fd, base.ptr(fd, ip + I['name']))
    if not iname:
        raise RuntimeError(f'unresolved GfxImage name {ip:#x}')
    ih = base.u32(fd, ip + I['hash'])
    w = base.u16(fd, ip + I['width']); h = base.u16(fd, ip + I['height']); d = base.u16(fd, ip + I['depth'])
    streaming = base.u8(fd, ip + I['streaming']); part_count = base.u8(fd, ip + I['streamedPartCount'])
    if None in (ih, w, h, d, streaming, part_count):
        raise RuntimeError(f'{iname}: truncated GfxImage')
    calc = base.rhash(iname)
    runtime_code = ih == 0 and iname.startswith(',')
    if ih == 0 and not runtime_code:
        raise RuntimeError(f'{iname}: zero GfxImage.hash outside runtime/code namespace')
    if not runtime_code and ih != calc:
        raise RuntimeError(f'{iname}: GfxImage.hash {ih:08x} != R_HashString {calc:08x}')
    part = None
    if part_count:
        sp = ip + I['streamedParts']
        ph = base.u32(fd, sp + SP['hash']); pw = base.u16(fd, sp + SP['width']); phh = base.u16(fd, sp + SP['height'])
        if None in (ph, pw, phh):
            raise RuntimeError(f'{iname}: unreadable streamed part')
        part = {'hash': ph, 'hash29': ph & 0x1fffffff, 'width': pw, 'height': phh}
    return {
        'image': iname, 'imagePointerRuntime': f'0x{ip:08x}', 'imageHash': ih,
        'computedRHashString': calc,
        'identityClass': 'runtime-code-hash-zero' if runtime_code else 'retail-name-hash-validated',
        'hashValidation': 'runtime-code-zero-hash-separated' if runtime_code else 'R_HashString-exact',
        'width': w, 'height': h, 'depth': d, 'streaming': streaming,
        'streamedPartCountRaw': part_count, 'streamedPart0': part,
    }


def scan_material(fd, W, T, mp):
    MI = W['MaterialInfo']; M = T['Material']; TD = T['MaterialTextureDef']
    name = base.cstr(fd, base.ptr(fd, mp + M['info'] + MI['name']))
    if not name:
        raise RuntimeError(f'unresolved Material name {mp:#x}')
    tc = base.u8(fd, mp + M['textureCount']); table = base.ptr(fd, mp + M['textureTable'])
    if tc is None or tc > 64:
        raise RuntimeError(f'{name}: invalid textureCount {tc}')
    if tc and not table:
        raise RuntimeError(f'{name}: null textureTable')
    textures = []
    for slot in range(tc):
        a = table + slot * TD['size']
        raw = base.pread(fd, a, TD['size'])
        if raw is None:
            raise RuntimeError(f'{name}: unreadable texture def {slot}')
        ip = struct.unpack_from('<I', raw, TD['image'])[0]
        if not ip:
            raise RuntimeError(f'{name}: null image pointer at slot {slot}')
        rec = {
            'slot': slot, 'nameHash': struct.unpack_from('<I', raw, TD['nameHash'])[0],
            'nameStart': raw[TD['nameStart']], 'nameEnd': raw[TD['nameEnd']],
            'samplerState': raw[TD['samplerState']], 'semantic': raw[TD['semantic']],
            'isMatureContent': bool(raw[TD['isMatureContent']]),
        }
        rec.update(scan_image(fd, T, ip)); textures.append(rec)
    first = {}
    for t in textures:
        if t['semantic'] in (2, 5) and str(t['semantic']) not in first:
            first[str(t['semantic'])] = t
    return {'name': name, 'runtimePointer': f'0x{mp:08x}', 'textureCount': tc, 'textures': textures, 'firstSemantic': first}


def scan(fd, W, X, T, world, snapshot):
    models_by_ptr = {}; material_uses = collections.defaultdict(list)
    for draw_index, (xp, name, ns, handles) in enumerate(snapshot):
        row = models_by_ptr.get(xp); identity = (name, ns, handles)
        if row is None:
            row = {'name': name, 'runtimePointer': f'0x{xp:08x}', 'numsurfs': ns,
                   'materialPointers': [f'0x{x:08x}' for x in handles], 'drawIndices': []}
            models_by_ptr[xp] = row
        else:
            old = (row['name'], row['numsurfs'], tuple(int(x, 16) for x in row['materialPointers']))
            if old != identity: raise RuntimeError(f'XModel pointer {xp:#x}: inconsistent identity')
        row['drawIndices'].append(draw_index)
        for surf_index, mp in enumerate(handles):
            material_uses[mp].append({'model': name, 'drawIndex': draw_index, 'surfaceIndex': surf_index})

    mats = []; by_name = {}; image_meta = {}
    for mp in sorted(material_uses):
        m = scan_material(fd, W, T, mp); old = by_name.get(m['name'])
        if old is not None and old['runtimePointer'] != m['runtimePointer']:
            def sig(r):
                return [(t['semantic'], t['image'], t['imageHash'], (t.get('streamedPart0') or {}).get('hash29'),
                         t['width'], t['height'], t['depth']) for t in r['textures']]
            if sig(old) != sig(m): raise RuntimeError(f"material {m['name']}: conflicting runtime objects")
            old.setdefault('runtimePointerAliases', []).append(m['runtimePointer']); old['uses'].extend(material_uses[mp]); continue
        m['uses'] = material_uses[mp]; by_name[m['name']] = m; mats.append(m)
        for t in m['textures']:
            k = t['image']; im = {x:t[x] for x in ('image','imageHash','computedRHashString','identityClass','hashValidation','width','height','depth','streaming','streamedPartCountRaw')}; im['streamedPart0'] = t['streamedPart0']
            if k in image_meta and image_meta[k] != im: raise RuntimeError(f'{k}: conflicting static GfxImage metadata')
            image_meta[k] = im

    models = sorted(models_by_ptr.values(), key=lambda r:(r['name'], r['runtimePointer'])); mats.sort(key=lambda r:r['name'])
    sem = collections.Counter(t['semantic'] for m in mats for t in m['textures'])
    return {
        'format':'t6-nuketown-live-static-xmodel-material-texture-identities-v1', 'map':'mp_nuketown_2020',
        'staticDrawInstanceCount':len(snapshot), 'distinctStaticXModelPointers':len(models),
        'distinctStaticXModelNames':len({m['name'] for m in models}), 'distinctStaticMaterialNames':len(mats),
        'textureEntryCount':sum(len(m['textures']) for m in mats), 'uniqueImageCount':len(image_meta),
        'semanticEntryCounts':{str(k):v for k,v in sorted(sem.items())},
        'models':models, 'materials':mats, 'images':[image_meta[k] for k in sorted(image_meta)],
        'proofBoundary':'Every XModel is reached from the frozen retail GfxWorld smodelDrawInsts array. Every static Material is reached through the live XModel.materialHandles array, then every MaterialTextureDef and direct GfxImage pointer is read from that frozen process. Ordinary GfxImage.hash values must equal T6 R_HashString(name); streamed payload identity is retained from streamedParts[0].hash. No material-name, image-name, or same-name IPAK substitution is performed.'
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--world-layout',type=Path,required=True); ap.add_argument('--xmodel-layout',type=Path,required=True); ap.add_argument('--texture-layout',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--diag',type=Path,required=True); ap.add_argument('--timeout',type=float,default=30); ap.add_argument('command',nargs=argparse.REMAINDER); a=ap.parse_args()
    cmd=a.command[1:] if a.command and a.command[0]=='--' else a.command
    if not cmd: ap.error('missing target command')
    W=json.loads(a.world_layout.read_text()); X=json.loads(a.xmodel_layout.read_text()); T=json.loads(a.texture_layout.read_text())
    if W.get('ptrSize')!=4 or X.get('ptrSize')!=4 or T.get('ptrSize')!=4: raise SystemExit('expected x86 layouts')
    log=a.out.with_suffix('.target.log').open('wb'); p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
    diag={'format':'t6-oat-external-static-xmodel-texture-scan-diagnostics-v1','pid':p.pid,'command':cmd}; fd=None; frozen=False
    try:
        for _ in range(400):
            try: fd=os.open(f'/proc/{p.pid}/mem',os.O_RDONLY); break
            except OSError:
                if p.poll() is not None: break
                time.sleep(.005)
        if fd is None: raise RuntimeError('could not open child mem')
        world=base.find_world(p.pid,fd,W,time.monotonic()+a.timeout,diag)
        if world is None: raise RuntimeError(f'no validated Nuketown GfxWorld: {diag}')
        snapshot=wait_static_ready(fd,W,X,world,time.monotonic()+a.timeout,diag)
        if snapshot is None: raise RuntimeError(f'static XModels never reached stable readiness: {diag}')
        os.kill(p.pid,signal.SIGSTOP); _,status=os.waitpid(p.pid,os.WUNTRACED)
        if not os.WIFSTOPPED(status): raise RuntimeError('child did not freeze')
        frozen=True; doc=scan(fd,W,X,T,world,snapshot); a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
        diag['summary']={k:doc[k] for k in ('staticDrawInstanceCount','distinctStaticXModelPointers','distinctStaticXModelNames','distinctStaticMaterialNames','textureEntryCount','uniqueImageCount','semanticEntryCounts')}; diag['outputSha256']=hashlib.sha256(a.out.read_bytes()).hexdigest()
    finally:
        if fd is not None: os.close(fd)
        if frozen:
            try: os.kill(p.pid,signal.SIGCONT)
            except ProcessLookupError: pass
        try: rc=p.wait(timeout=30)
        except subprocess.TimeoutExpired: p.terminate(); rc=p.wait(timeout=5)
        diag['targetFinalReturnCode']=rc; log.close(); a.diag.write_text(json.dumps(diag,indent=2,sort_keys=True)+'\n')
    print(json.dumps(diag,indent=2,sort_keys=True))

if __name__=='__main__': main()
