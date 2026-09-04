#!/usr/bin/env python3
"""Retained-byte closure for the final 15 mixed-writer TEMP reflection normals.

The earlier surface-normal verifier deliberately required the three raw-vector
components to share one writer. Exactly 15 reflectionProbeSampler fetches fall
outside that structural form: their normalized formula-A vector is sourced from
a TEMP whose x/y/z logical components have different retained writers.

This verifier selects those 15 fetches from the *exhaustive* reflection corpus by
formula shape, then proves per component that:

  rawNormal = float3(X, Y, 1.0)
  surfaceNormal = normalize(rawNormal)

For X/Y, all non-constant value origins must reduce to exactly the expected pair
of reflected normal textures plus exactly one cb2 control vector. For Z, the
writer must be an exact MOV of IEEE-754 float32 1.0 (0x3f800000). The opposing
reflect vector must independently be normalize(TEXCOORD1.xyz) or
normalize(TEXCOORD3.xyz), with the two retained families fixed at 6 and 9
fetches respectively.

This stage does not assign camera/view semantics to the opposing TEXCOORD. It
proves only the surface-normal side of the reflect equation from retained SM4
and RDEF evidence.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
EXPECTED_SHADERS = 5868
EXPECTED_FETCHES = 5888
EXPECTED_TARGETS = 15
TYPE_TEMP = 0
TYPE_INPUT = 1
TYPE_IMM32 = 4
TYPE_RESOURCE = 7
TYPE_CB = 8
OP_MOV = 54
ONE_BITS = 1065353216
FAMILIES = {'TEXCOORD1': {'count': 6, 'textures': {'normalMap00', 'normalMap01'}, 'cb': (2, 10), 'allowedMaps': {'mp_raid', 'zm_tomb'}}, 'TEXCOORD3': {'count': 9, 'textures': {'normalMapHi', 'normalMapLo'}, 'cb': (2, 6), 'allowedMaps': {'zm_prison'}}}
EXPECTED_STORAGE = {'xyz': 14, 'yzw': 1}

def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod

def jhash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def resource_name(guard, resources, rr: int):
    names = sorted({r['name'] for r in resources if r['inputType'] == guard.INPUT_TEXTURE and r['bindPoint'] == rr})
    if len(names) != 1:
        raise ValueError(f't{rr}: reflected texture names {names}')
    return names[0]

def effective_component(weight, src, dest, dch):
    try:
        eff = weight.eff(src, dest['comps'])
        pos = dest['comps'].index(dch)
        return [eff[pos]]
    except (ValueError, IndexError):
        return list(src.get('comps') or 'x')

def immediate_bits(shared, w, src, dest=None, dch=None, weight=None):
    vals = shared.raw_imms(w, src)
    if vals is None:
        return None
    if len(vals) == 1:
        return vals[0]
    if len(vals) != 4:
        raise ValueError(f'unsupported immediate width {len(vals)}')
    if dest is None or dch is None or weight is None:
        return tuple(vals)
    lanes = effective_component(weight, src, dest, dch)
    if len(lanes) != 1:
        raise ValueError(f'immediate lane selection {lanes}')
    return vals['xyzw'.index(lanes[0])]

def prove_exact_one_mov(shared, weight, w, latest, before, reg, ch):
    wr = latest(before, reg, ch)
    if wr is None:
        raise ValueError(f'r{reg}.{ch}: no writer')
    wi, p, op, dest, operands = wr
    if op != OP_MOV or len(operands) != 2:
        raise ValueError(f'r{reg}.{ch}: z writer op={op} arity={len(operands)} not MOV')
    bits = immediate_bits(shared, w, operands[1], dest, ch, weight)
    if bits != ONE_BITS:
        raise ValueError(f'r{reg}.{ch}: MOV immediate {bits!r} != 0x{ONE_BITS:08x}')
    return {'writerInstructionIndex': wi, 'writerOpcode': op, 'immediateBits': f'{bits:08x}'}

def variable_leaves(coord, weight, guard, resources, inst, parsed, latest, before, reg, ch, cache, depth=0):
    key = (before, reg, ch)
    if key in cache:
        return cache[key]
    if depth > 100:
        raise ValueError('variable ancestry recursion depth exceeded')
    wr = latest(before, reg, ch)
    if wr is None:
        out = {('unwritten', reg, ch)}
        cache[key] = out
        return out
    wi, p, op, dest, operands = wr
    if op in coord.SAMPLE_OPS:
        if len(operands) < 4:
            raise ValueError(f'sample arity at {wi}')
        res = operands[2]
        if res['type'] != TYPE_RESOURCE or len(res['idx']) != 1:
            raise ValueError(f'sample resource at {wi} is not direct t#')
        rr = res['idx'][0]
        out = {('sample', resource_name(guard, resources, rr), rr, ch, coord.SAMPLE_OPS[op])}
        cache[key] = out
        return out
    dest_count = 0
    for d in weight.writer_dests(op, operands):
        if d['type'] == TYPE_TEMP:
            dest_count += 1
    if dest_count != 1:
        raise ValueError(f'writer {wi} op={op}: destination count {dest_count}')
    out = set()
    sources = operands[1:]
    for src in sources:
        typ = src['type']
        if typ == TYPE_IMM32:
            continue
        if typ == TYPE_CB:
            if len(src['idx']) != 2 or not all((isinstance(x, int) for x in src['idx'])):
                raise ValueError(f"writer {wi}: unresolved CB operand {src['idx']}")
            lanes = list(src['comps'][:weight.DP_WIDTH[op]]) if op in weight.DP_WIDTH else effective_component(weight, src, dest, ch)
            for lane in lanes:
                out.add(('cb', src['idx'][0], src['idx'][1], lane))
            continue
        if typ == TYPE_INPUT:
            if len(src['idx']) != 1:
                raise ValueError(f"writer {wi}: unresolved INPUT operand {src['idx']}")
            lanes = list(src['comps'][:weight.DP_WIDTH[op]]) if op in weight.DP_WIDTH else effective_component(weight, src, dest, ch)
            for lane in lanes:
                out.add(('input', src['idx'][0], lane))
            continue
        if typ == TYPE_TEMP:
            if len(src['idx']) != 1 or not isinstance(src['idx'][0], int):
                raise ValueError(f"writer {wi}: unresolved TEMP operand {src['idx']}")
            lanes = list(src['comps'][:weight.DP_WIDTH[op]]) if op in weight.DP_WIDTH else effective_component(weight, src, dest, ch)
            for lane in set(lanes):
                out |= variable_leaves(coord, weight, guard, resources, inst, parsed, latest, wi, src['idx'][0], lane, cache, depth + 1)
            continue
        raise ValueError(f'writer {wi} op={op}: unsupported variable source type {typ}')
    cache[key] = out
    return out

def classify_opp(surf, sig, B):
    if B is None:
        return None
    raw = B['raw']
    if raw['type'] != TYPE_INPUT or len(raw['idx']) != 1 or B['rawComponents'] != 'xyz':
        return None
    sem = sig.get(raw['idx'][0])
    if sem not in (('TEXCOORD', 1), ('TEXCOORD', 3)):
        return None
    return f'TEXCOORD{sem[1]}'

def prove_target(coord, weight, shared, surf, guard, blob, resources, si, p, op):
    sig = surf.input_signature(blob)
    w = coord.get_program_words(blob)
    inst = list(coord.walk(w))
    parsed, latest, _ = shared.prep_shader(coord, weight, w, inst)
    roles = surf.formula_roles(coord, w, inst, latest, si, p, op)
    if roles is None:
        return None
    A = surf.normalized_raw(coord, w, inst, latest, roles['dotIndex'], roles['A'])
    B = surf.normalized_raw(coord, w, inst, latest, roles['dotIndex'], roles['B'])
    if A is None or B is None:
        return None
    opp = classify_opp(surf, sig, B)
    if opp not in FAMILIES:
        return None
    raw = A['raw']
    storage = A['rawComponents']
    if raw['type'] != TYPE_TEMP or len(raw['idx']) != 1 or len(storage) != 3:
        return None
    writers = [latest(A['normWriter'], raw['idx'][0], ch) for ch in storage]
    if any((x is None for x in writers)):
        return None
    if len({x[0] for x in writers}) == 1:
        return None
    family = FAMILIES[opp]
    cache = {}
    xleaves = variable_leaves(coord, weight, guard, resources, inst, parsed, latest, A['normWriter'], raw['idx'][0], storage[0], cache)
    yleaves = variable_leaves(coord, weight, guard, resources, inst, parsed, latest, A['normWriter'], raw['idx'][0], storage[1], cache)
    leaves = xleaves | yleaves
    samples = {x for x in leaves if x[0] == 'sample'}
    cbs = {x for x in leaves if x[0] == 'cb'}
    other = leaves - samples - cbs
    if other:
        raise ValueError(f'unexpected x/y variable leaves {sorted(other)}')
    names = {x[1] for x in samples}
    binds = {x[2] for x in samples}
    if names != family['textures']:
        raise ValueError(f'{opp}: normal texture leaves {sorted(names)}')
    if binds != {0, 1}:
        raise ValueError(f'{opp}: texture bind points {sorted(binds)} != [0,1]')
    cbids = {(x[1], x[2]) for x in cbs}
    if cbids != {family['cb']}:
        raise ValueError(f"{opp}: CB leaves {sorted(cbids)} != {[family['cb']]}")
    z = prove_exact_one_mov(shared, weight, w, latest, A['normWriter'], raw['idx'][0], storage[2])
    return {'opposingSemantic': opp, 'rawStorageComponents': storage, 'rawRegister': raw['idx'][0], 'normalXVariableLeaves': [list(x) for x in sorted(xleaves)], 'normalYVariableLeaves': [list(x) for x in sorted(yleaves)], 'normalTextureNames': sorted(names), 'normalTextureBindPoints': sorted(binds), 'controlCBuffer': {'slot': family['cb'][0], 'vectorIndex': family['cb'][1]}, 'rawZ': z}

def build(root: Path, coordinate_verifier: Path, weight_verifier: Path, shared_verifier: Path, surface_verifier: Path, guard_path: Path):
    coord = load(coordinate_verifier, 'temp15_coord')
    weight = load(weight_verifier, 'temp15_weight')
    shared = load(shared_verifier, 'temp15_shared')
    surf = load(surface_verifier, 'temp15_surface')
    guard = load(guard_path, 'temp15_guard')
    all_ref = {}
    map_rows = []
    for mapname, (rel, expected_sha) in guard.SOURCES.items():
        path = root / rel
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected_sha:
            raise ValueError(f'{mapname}: expanded SHA mismatch {actual}')
        valid, _ = guard.scan_map(path)
        local = 0
        for hh, (blob, resources) in valid.items():
            if any((x['name'] == 'reflectionProbeSampler' for x in resources)):
                local += 1
                old = all_ref.setdefault(hh, (blob, resources, set()))
                if old[0] != blob:
                    raise ValueError('reflection shader SHA collision')
                old[2].add(mapname)
        map_rows.append({'map': mapname, 'validDxbcCount': len(valid), 'reflectionProbeShaderCount': local})
    if len(all_ref) != EXPECTED_SHADERS:
        raise ValueError(f'reflection shader count {len(all_ref)}')
    total = 0
    rows = []
    family_counts = collections.Counter()
    storage_counts = collections.Counter()
    resource_rows = collections.Counter()
    cb_rows = collections.Counter()
    for hh, (blob, resources, maps) in sorted(all_ref.items()):
        w = coord.get_program_words(blob)
        inst = list(coord.walk(w))
        for si, (p, op, ln, tok) in enumerate(inst):
            if op not in coord.SAMPLE_OPS:
                continue
            O, _ = coord.parse_sample(w, p, op)
            rr, ss = (O[2], O[3])
            if not (rr['type'] == 7 and ss['type'] == 6 and (rr['idx'] == [15]) and (ss['idx'] == [15])):
                continue
            total += 1
            q = prove_target(coord, weight, shared, surf, guard, blob, resources, si, p, op)
            if q is None:
                continue
            allowed = FAMILIES[q['opposingSemantic']]['allowedMaps']
            if not maps or not maps <= allowed:
                raise ValueError(f"{hh}: {q['opposingSemantic']} maps {sorted(maps)} outside {sorted(allowed)}")
            family_counts[q['opposingSemantic']] += 1
            storage_counts[q['rawStorageComponents']] += 1
            for z in q['normalXVariableLeaves'] + q['normalYVariableLeaves']:
                if z[0] == 'sample':
                    resource_rows[tuple(z[1:])] += 1
                elif z[0] == 'cb':
                    cb_rows[tuple(z[1:])] += 1
            rows.append({'sha256': hh, 'maps': sorted(maps), 'sampleInstructionIndex': si, **q})
    if total != EXPECTED_FETCHES:
        raise ValueError(f'reflection fetch count {total}')
    if len(rows) != EXPECTED_TARGETS:
        raise ValueError(f'mixed-writer TEMP target count {len(rows)}')
    expected_family = {k: v['count'] for k, v in FAMILIES.items()}
    if dict(family_counts) != expected_family:
        raise ValueError(f'family counts {family_counts}')
    if dict(storage_counts) != EXPECTED_STORAGE:
        raise ValueError(f'raw storage counts {storage_counts}')
    map_union = {m for r in rows for m in r['maps']}
    if not {'mp_raid', 'zm_tomb', 'zm_prison'} <= map_union:
        raise ValueError(f'target map union {sorted(map_union)}')
    resource_summary = [{'resourceName': k[0], 'resourceRegister': k[1], 'channel': k[2], 'opcode': k[3], 'ancestryOccurrenceCount': v} for k, v in sorted(resource_rows.items())]
    cb_summary = [{'cbufferSlot': k[0], 'vectorIndex': k[1], 'component': k[2], 'ancestryOccurrenceCount': v} for k, v in sorted(cb_rows.items())]
    summary = {'retainedMapCount': len(guard.SOURCES), 'uniqueReflectionProbeShaderCount': len(all_ref), 'reflectionCubeFetchCount': total, 'targetShaderCount': len({r['sha256'] for r in rows}), 'targetFetchCount': len(rows), 'opposingSemanticCounts': dict(sorted(family_counts.items())), 'rawStorageComponentCounts': dict(sorted(storage_counts.items())), 'exactOneRawZCheckCount': len(rows), 'normalTextureOnlyXYCheckCount': len(rows), 'controlCBufferCheckCount': len(rows), 'shaderRowsSha256': jhash(rows), 'resourceRowsSha256': jhash(resource_summary), 'cbufferRowsSha256': jhash(cb_summary), 'mapRowsSha256': jhash(map_rows)}
    return {'format': 't6-retail-reflection-probe-temp-component-normal-v1', 'producer': 'tools/t6_retail_reflection_probe_temp_component_normal_v1.py', 'sources': {'surfaceNormalCensus': 'manifests/render/T6_RETAIL_REFLECTION_PROBE_SURFACE_NORMAL_V1.json', 'priorScratchManifestSha256': '481a750d41b755f644b368e3b33145eaf5739f1f7a57594fdcee1b662023370d', 'expandedRetailMaps': {n: {'file': rel, 'sha256': sha} for n, (rel, sha) in sorted(guard.SOURCES.items())}}, 'equations': {'surfaceNormal': 'N=normalize(float3(X,Y,1.0))', 'reflection': 'cubeCoord=B-2*N*dot(N,B)'}, 'familySemantics': {'TEXCOORD1': 'X/Y variable origins are normalMap00 + normalMap01 + cb2[10]', 'TEXCOORD3': 'X/Y variable origins are normalMapHi + normalMapLo + cb2[6]'}, 'resourceAncestry': resource_summary, 'controlCBufferAncestry': cb_summary, 'rows': rows, 'summary': summary, 'proofBoundary': 'Exhaustive retained-DXBC/RDEF component-level proof of the 15 reflectionProbeSampler fetches whose formula-A normalized raw vector is a mixed-writer TEMP and whose opposing normalized vector is TEXCOORD1.xyz or TEXCOORD3.xyz. For all 15, logical raw X/Y have no non-constant value origins beyond the exact family-specific pair of normal-named textures at t0/t1 and one exact cb2 control vector (cb2[10] or cb2[6]); logical raw Z is written by MOV immediate float32 1.0 (0x3f800000); and formula-A is independently proved by the retained reflect parser to be normalized before dot/reflection use. Fourteen raw vectors occupy xyz and one occupies yzw. This promotes formula-A to a surface normal for these 15 fetches only. The opposing TEXCOORD remains a mathematical incident/view candidate here.'}

def main():
    a = argparse.ArgumentParser()
    a.add_argument('--root', type=Path, required=True)
    a.add_argument('--coordinate-verifier', type=Path, default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'))
    a.add_argument('--weight-verifier', type=Path, default=Path('tools/t6_retail_reflection_probe_weight_v1.py'))
    a.add_argument('--shared-verifier', type=Path, default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'))
    a.add_argument('--surface-verifier', type=Path, default=Path('tools/t6_retail_reflection_probe_surface_normal_v1.py'))
    a.add_argument('--guard', type=Path, default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
    a.add_argument('--out', type=Path, required=True)
    q = a.parse_args()
    d = build(q.root, q.coordinate_verifier, q.weight_verifier, q.shared_verifier, q.surface_verifier, q.guard)
    q.out.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    print(json.dumps(d['summary'], indent=2, sort_keys=True))
if __name__ == '__main__':
    main()
