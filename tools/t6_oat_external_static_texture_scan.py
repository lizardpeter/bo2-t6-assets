#!/usr/bin/env python3
"""Recover exact live T6 texture identities for the 297 playable Nuketown static XModels.

The retained playable-static proof supplies only the allowed XModel/material identity set.
All texture/image facts are read from the frozen OAT process after pointer fixups:

  GfxWorld.smodelDrawInsts -> XModel -> Material** materialHandles
  -> MaterialTextureDef -> GfxImage -> GfxStreamedPartInfo

The same frozen process also emits the authoritative 2,992 GfxWorld static placements,
so placement and texture evidence cannot come from different runtime states.

LOD0 material order is independently checked against the retained proof before any
texture identity is emitted. Ordinary GfxImage.hash values must exactly equal T6
R_HashString(name). No material-name or texture-name fuzzy matching is used.
"""
from __future__ import annotations

import argparse
import base64
import collections
import hashlib
import json
import os
import signal
import struct
import subprocess
import time
import zlib
from pathlib import Path

import t6_oat_external_gfxworld_texture_scan as live
import t6_oat_external_gfxworld_scan as placement_scan

EXPECTED_SMODELS = 2992
EXPECTED_PLAYABLE_MODELS = 297
EXPECTED_PLAYABLE_MATERIALS = 344


def load_proof(path: Path) -> dict:
    if path.name.endswith('.zlib.b64'):
        return json.loads(zlib.decompress(base64.b64decode(path.read_text().strip())).decode())
    return json.loads(path.read_text())


def proof_rows(doc: dict) -> dict[str, dict]:
    rows = doc.get('models') or []
    out: dict[str, dict] = {}
    for row in rows:
        name = row.get('xmodelName')
        if not isinstance(name, str) or not name:
            raise RuntimeError('static proof contains model without xmodelName')
        if name in out:
            raise RuntimeError(f'duplicate proof XModel {name}')
        mats = row.get('materials')
        if not isinstance(mats, list) or not all(isinstance(x, str) and x for x in mats):
            raise RuntimeError(f'{name}: invalid proof material list')
        out[name] = row
    if len(out) != EXPECTED_PLAYABLE_MODELS:
        raise RuntimeError(f'proof model count {len(out)} != {EXPECTED_PLAYABLE_MODELS}')
    names = {m for row in rows for m in row.get('materials', [])}
    if len(names) != EXPECTED_PLAYABLE_MATERIALS:
        raise RuntimeError(f'proof material identity count {len(names)} != {EXPECTED_PLAYABLE_MATERIALS}')
    return out


def model_snapshot(fd: int, W: dict, world: int, proof: dict[str, dict]):
    DP = W['GfxWorldDpvsStatic']
    DI = W['GfxStaticModelDrawInst']
    XM = W['XModel']
    LI = W['XModelLodInfo']
    MI = W['MaterialInfo']

    draw = live.ptr(fd, world + W['GfxWorld']['dpvs'] + DP['smodelDrawInsts'])
    if not draw:
        return None
    found: dict[str, int] = {}
    for i in range(EXPECTED_SMODELS):
        xp = live.ptr(fd, draw + i * DI['size'] + DI['model'])
        if not xp:
            return None
        name = live.cstr(fd, live.ptr(fd, xp + XM['name']))
        if not name:
            return None
        if name in proof:
            old = found.setdefault(name, xp)
            if old != xp:
                raise RuntimeError(f'{name}: multiple live XModel pointers {old:#x}/{xp:#x}')
    if set(found) != set(proof):
        return None

    signature = []
    for name in sorted(found):
        xp = found[name]
        handles = live.ptr(fd, xp + XM['materialHandles'])
        if not handles:
            return None
        lod = xp + XM['lodInfo']
        n = live.u16(fd, lod + LI['numsurfs'])
        start = live.u16(fd, lod + LI['surfIndex'])
        total = live.u8(fd, xp + XM['numsurfs'])
        if None in (n, start, total) or n <= 0 or start + n > total:
            return None
        names = []
        ptrs = []
        for j in range(n):
            mp = live.ptr(fd, handles + 4 * (start + j))
            if not mp:
                return None
            mname = live.cstr(fd, live.ptr(fd, mp + MI['name']))
            if not mname:
                return None
            names.append(mname)
            ptrs.append(mp)
        expected = proof[name]['materials']
        if names != expected:
            raise RuntimeError(
                f'{name}: live LOD0 material order differs from retained proof\n'
                f'live={names}\nproof={expected}'
            )
        signature.append((name, xp, n, start, tuple(ptrs), tuple(names)))
    return tuple(signature)


def wait_static_ready(pid: int, fd: int, W: dict, world: int, proof: dict[str, dict], deadline: float):
    passes = 0
    while time.monotonic() < deadline and Path(f'/proc/{pid}').exists():
        a = model_snapshot(fd, W, world, proof)
        if a is not None:
            time.sleep(0.01)
            b = model_snapshot(fd, W, world, proof)
            if b == a:
                return a, passes + 1
        passes += 1
        time.sleep(0.01)
    return None, passes


def scan_texture(fd: int, T: dict, mp: int, mname: str):
    M = T['Material']
    TD = T['MaterialTextureDef']
    I = T['GfxImage']
    SP = T['GfxStreamedPartInfo']
    tc = live.u8(fd, mp + M['textureCount'])
    table = live.ptr(fd, mp + M['textureTable'])
    if tc is None or tc > 64:
        raise RuntimeError(f'{mname}: invalid textureCount {tc}')
    if tc and not table:
        raise RuntimeError(f'{mname}: null textureTable with count {tc}')
    textures = []
    for slot in range(tc):
        a = table + slot * TD['size']
        raw = live.pread(fd, a, TD['size'])
        if raw is None:
            raise RuntimeError(f'{mname}: unreadable texture def {slot}')
        name_hash = struct.unpack_from('<I', raw, TD['nameHash'])[0]
        name_start = raw[TD['nameStart']]
        name_end = raw[TD['nameEnd']]
        sampler = raw[TD['samplerState']]
        semantic = raw[TD['semantic']]
        mature = bool(raw[TD['isMatureContent']])
        ip = struct.unpack_from('<I', raw, TD['image'])[0]
        if not ip:
            raise RuntimeError(f'{mname} slot {slot}: null GfxImage pointer')
        iname = live.cstr(fd, live.ptr(fd, ip + I['name']))
        if not iname:
            raise RuntimeError(f'{mname} slot {slot}: unresolved GfxImage name {ip:#x}')
        ih = live.u32(fd, ip + I['hash'])
        w = live.u16(fd, ip + I['width'])
        h = live.u16(fd, ip + I['height'])
        d = live.u16(fd, ip + I['depth'])
        streaming = live.u8(fd, ip + I['streaming'])
        part_count = live.u8(fd, ip + I['streamedPartCount'])
        if None in (ih, w, h, d, streaming, part_count):
            raise RuntimeError(f'{iname}: truncated GfxImage')
        calc = live.rhash(iname)
        runtime_code = ih == 0 and iname.startswith(',')
        if ih == 0 and not runtime_code:
            raise RuntimeError(f'{iname}: zero GfxImage.hash outside runtime/code namespace')
        if not runtime_code and ih != calc:
            raise RuntimeError(f'{iname}: GfxImage.hash {ih:08x} != R_HashString {calc:08x}')
        part = None
        if part_count:
            sp = ip + I['streamedParts']
            ph = live.u32(fd, sp + SP['hash'])
            pw = live.u16(fd, sp + SP['width'])
            phh = live.u16(fd, sp + SP['height'])
            if None in (ph, pw, phh):
                raise RuntimeError(f'{iname}: unreadable streamed part')
            part = {'hash': ph, 'hash29': ph & 0x1FFFFFFF, 'width': pw, 'height': phh}
        image = {
            'name': iname,
            'hash': ih,
            'computedRHashString': calc,
            'identityClass': 'runtime-code-hash-zero' if runtime_code else 'retail-name-hash-validated',
            'width': w,
            'height': h,
            'depth': d,
            'streaming': streaming,
            'streamedPartCountRaw': part_count,
            'streamedPart0': part,
        }
        textures.append({
            'slot': slot,
            'nameHash': name_hash,
            'nameStart': name_start,
            'nameEnd': name_end,
            'samplerState': sampler,
            'semantic': semantic,
            'isMatureContent': mature,
            'imagePointerRuntime': f'0x{ip:08X}',
            'image': image,
        })
    return textures


def scan(fd: int, W: dict, T: dict, snapshot):
    MI = W['MaterialInfo']
    model_rows = []
    material_ptrs: dict[str, int] = {}
    for name, xp, n, start, ptrs, names in snapshot:
        model_rows.append({
            'xmodelName': name,
            'runtimePointer': f'0x{xp:08X}',
            'lod0SurfaceCount': n,
            'lod0SurfaceIndex': start,
            'materials': list(names),
        })
        for mname, mp in zip(names, ptrs):
            observed = live.cstr(fd, live.ptr(fd, mp + MI['name']))
            if observed != mname:
                raise RuntimeError(f'{name}: material pointer name changed {observed!r} != {mname!r}')
            old = material_ptrs.setdefault(mname, mp)
            if old != mp:
                raise RuntimeError(f'{mname}: multiple live Material pointers {old:#x}/{mp:#x}')
    if len(material_ptrs) != EXPECTED_PLAYABLE_MATERIALS:
        raise RuntimeError(f'live material count {len(material_ptrs)} != {EXPECTED_PLAYABLE_MATERIALS}')

    materials = []
    images: dict[str, dict] = {}
    semantic_counts = collections.Counter()
    for mname, mp in sorted(material_ptrs.items()):
        textures = scan_texture(fd, T, mp, mname)
        for t in textures:
            semantic_counts[t['semantic']] += 1
            im = t['image']
            prev = images.get(im['name'])
            if prev is None:
                images[im['name']] = im
            elif prev != im:
                raise RuntimeError(f"{im['name']}: conflicting live GfxImage metadata")
        materials.append({
            'name': mname,
            'status': 'located',
            'runtimePointer': f'0x{mp:08X}',
            'textureCount': len(textures),
            'textures': textures,
        })

    return {
        'format': 't6-nuketown-live-playable-static-material-texture-identities-v1',
        'map': 'mp_nuketown_2020',
        'playableStaticModelCount': len(model_rows),
        'materialCount': len(materials),
        'textureEntryCount': sum(len(m['textures']) for m in materials),
        'uniqueImageCount': len(images),
        'semanticEntryCounts': {str(k): v for k, v in sorted(semantic_counts.items())},
        'models': model_rows,
        'materials': materials,
        'images': [images[k] for k in sorted(images)],
        'validation': {
            'all297XModelsResolved': True,
            'allLod0MaterialOrdersMatchRetainedProof': True,
            'uniquePlayableMaterialIdentities': len(materials),
            'ordinaryImageNameHashesValidated': True,
        },
        'proofBoundary': (
            'The retained proof selects exactly 297 playable XModels and supplies their exact LOD0 material order. '
            'All emitted MaterialTextureDef/GfxImage identities are read from the frozen retail OAT process through '
            'the live XModel materialHandles pointers. Ordinary GfxImage.hash must equal T6 R_HashString(name); '
            'streamed payload identity is live streamedParts[0].hash. Placements are captured from the same frozen '
            'GfxWorld state. No filename similarity or material fallback is used.'
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--world-layout', type=Path, required=True)
    ap.add_argument('--texture-layout', type=Path, required=True)
    ap.add_argument('--proof', type=Path, required=True)
    ap.add_argument('--placements-out', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--diag', type=Path, required=True)
    ap.add_argument('--timeout', type=float, default=30)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.command[1:] if a.command and a.command[0] == '--' else a.command
    if not cmd:
        ap.error('missing target command')
    W = json.loads(a.world_layout.read_text())
    T = json.loads(a.texture_layout.read_text())
    if W.get('ptrSize') != 4 or T.get('ptrSize') != 4:
        raise SystemExit('expected x86 layouts')
    proof = proof_rows(load_proof(a.proof))

    log = a.out.with_suffix('.target.log').open('wb')
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    diag = {
        'format': 't6-oat-external-playable-static-texture-scan-diagnostics-v1',
        'pid': p.pid,
        'command': cmd,
    }
    fd = None
    frozen = False
    try:
        for _ in range(400):
            try:
                fd = os.open(f'/proc/{p.pid}/mem', os.O_RDONLY)
                break
            except OSError:
                if p.poll() is not None:
                    break
                time.sleep(0.005)
        if fd is None:
            raise RuntimeError('could not open child mem')
        deadline = time.monotonic() + a.timeout
        world = live.find_world(p.pid, fd, W, deadline, diag)
        if world is None:
            raise RuntimeError(f'no validated Nuketown GfxWorld: {diag}')
        snap, passes = wait_static_ready(p.pid, fd, W, world, proof, deadline)
        if snap is None:
            raise RuntimeError(f'playable static XModels never reached a stable proof-matching state after {passes} passes')
        diag['staticReadiness'] = {
            'passes': passes,
            'playableModelCount': len(snap),
            'stableConsecutiveSnapshots': 2,
        }
        os.kill(p.pid, signal.SIGSTOP)
        _, status = os.waitpid(p.pid, os.WUNTRACED)
        if not os.WIFSTOPPED(status):
            raise RuntimeError('child did not freeze')
        frozen = True

        doc = scan(fd, W, T, snap)
        a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')

        dp = world + W['GfxWorld']['dpvs']
        hit = {
            'insts': live.ptr(fd, dp + W['GfxWorldDpvsStatic']['smodelInsts']),
            'draws': live.ptr(fd, dp + W['GfxWorldDpvsStatic']['smodelDrawInsts']),
            'worldName': live.cstr(fd, live.ptr(fd, world + W['GfxWorld']['name'])),
            'surfaceCount': live.i32(fd, world + W['GfxWorld']['surfaceCount']),
        }
        if not hit['insts'] or not hit['draws'] or not hit['worldName']:
            raise RuntimeError(f'incomplete frozen placement roots: {hit}')
        placements = placement_scan.dump_world(fd, W, hit, a.placements_out)
        if placements.get('smodelCount') != EXPECTED_SMODELS or len(placements.get('placements', [])) != EXPECTED_SMODELS:
            raise RuntimeError('frozen placement count changed')

        diag['summary'] = {
            k: doc[k] for k in (
                'playableStaticModelCount', 'materialCount', 'textureEntryCount',
                'uniqueImageCount', 'semanticEntryCounts'
            )
        }
        diag['placementCount'] = len(placements['placements'])
        diag['outputSha256'] = hashlib.sha256(a.out.read_bytes()).hexdigest()
        diag['placementsSha256'] = hashlib.sha256(a.placements_out.read_bytes()).hexdigest()
    finally:
        if fd is not None:
            os.close(fd)
        if frozen:
            try:
                os.kill(p.pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
        try:
            rc = p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.terminate()
            rc = p.wait(timeout=5)
        diag['targetFinalReturnCode'] = rc
        log.close()
        a.diag.write_text(json.dumps(diag, indent=2, sort_keys=True) + '\n')
    print(json.dumps(diag, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
