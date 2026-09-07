#!/usr/bin/env python3
"""Extract directly retained DXBC programs for one exact T6 special world family.

This is a byte-retention tool, not a semantic classifier. Family membership is
consumed from the committed five-world special Material/TechniqueSet census.
TechniqueSet serialization is replayed with the already validated retained-byte
parser. Only physically inline FOLLOW/INSERT shader programs are emitted.
Packed/reused shader/technique pointers remain explicit unresolved references.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(root: Path, special_manifest: Path, parser_path: Path, helper_path: Path, family: str, out_dir: Path) -> dict:
    parser = load(parser_path, 'special_payload_parser')
    helper = load(helper_path, 'world_helper')
    manifest = json.loads(special_manifest.read_text())
    wanted = {r['techniqueSet'] for r in manifest['specialTechniqueSets'] if r['family'] == family}
    if not wanted:
        raise ValueError(f'family {family!r} has no TechniqueSets in special manifest')

    out_dir.mkdir(parents=True, exist_ok=True)
    programs: dict[tuple[str, str], dict] = {}
    occurrences = []
    packed = []
    structural = []

    for map_name, cfg in parser.MAPS.items():
        path = root / cfg['rel']
        data = path.read_bytes()
        got = sha(data)
        if got != cfg['sha']:
            raise ValueError(f'{map_name}: expanded SHA mismatch {got}')
        front = helper.parse_front(data)
        blocks = front['blockSizes']
        rows = helper.scan_techsets(data, blocks, before=cfg['world'])[-(cfg['q1'] - cfg['q0'] + 1):]
        if len(rows) != cfg['q1'] - cfg['q0'] + 1:
            raise ValueError(f'{map_name}: TechniqueSet block count mismatch')
        for i, row in enumerate(rows):
            row['xassetIndex'] = cfg['q0'] + i

        parsed = []
        for i, row in enumerate(rows):
            nxt = rows[i + 1]['fixedStart'] if i + 1 < len(rows) else cfg['world']
            parsed.append(parser.parse_techset(data, row, nxt, blocks, helper))
        if parsed[-1]['end'] != cfg['world']:
            raise ValueError(f'{map_name}: TechniqueSet block does not end at GfxWorld')
        structural.append({
            'map': map_name,
            'techniqueSetCount': len(parsed),
            'end': parsed[-1]['end'],
            'gfxWorldStart': cfg['world'],
        })

        for ts in parsed:
            if ts['name'] not in wanted:
                continue
            occ = {'map': map_name, 'techniqueSet': ts['name'], 'xassetIndex': ts['xassetIndex'], 'directPrograms': [], 'packedReferences': []}
            for ref in ts['techniqueRefs']:
                if ref['kind'] == 'packed':
                    rec = {'map': map_name, 'techniqueSet': ts['name'], 'techniqueSlot': ref['slot'], 'kind': 'packed-technique', 'raw': ref['raw']}
                    packed.append(rec); occ['packedReferences'].append(rec)
                    continue
                tech = ref.get('inlineTechnique')
                if not tech:
                    continue
                for pass_row in tech['passes']:
                    for field, stage in (('vertexShader', 'vs'), ('pixelShader', 'ps')):
                        child = pass_row['children'][field]
                        if child['kind'] == 'packed':
                            rec = {
                                'map': map_name, 'techniqueSet': ts['name'], 'techniqueSlot': ref['slot'],
                                'technique': tech['name'], 'passIndex': pass_row['passIndex'], 'stage': stage,
                                'kind': 'packed-shader', 'raw': child['raw'],
                            }
                            packed.append(rec); occ['packedReferences'].append(rec)
                            continue
                        shader = child.get('inline')
                        if not shader or not shader['program']['direct']:
                            continue
                        start = int(shader['program']['start'])
                        size = int(shader['program']['bytes'])
                        blob = data[start:start + size]
                        if len(blob) != size or blob[:4] != b'DXBC':
                            raise ValueError(f'{map_name}/{ts["name"]}: invalid direct {stage} bytes')
                        digest = sha(blob)
                        if digest != shader['program']['sha256']:
                            raise ValueError(f'{map_name}/{ts["name"]}: parser/direct {stage} SHA disagreement')
                        key = (stage, digest)
                        filename = f'{stage}_{digest}.cso'
                        target = out_dir / filename
                        if key not in programs:
                            target.write_bytes(blob)
                            programs[key] = {
                                'stage': stage, 'sha256': digest, 'bytes': size, 'file': filename,
                                'names': [], 'uses': [],
                            }
                        else:
                            if target.read_bytes() != blob:
                                raise ValueError('SHA collision/different retained shader bytes')
                        prog = programs[key]
                        if shader.get('name') not in prog['names']:
                            prog['names'].append(shader.get('name'))
                        use = {
                            'map': map_name, 'techniqueSet': ts['name'], 'techniqueSlot': ref['slot'],
                            'technique': tech['name'], 'passIndex': pass_row['passIndex'], 'stage': stage,
                            'sourceStart': start,
                        }
                        prog['uses'].append(use)
                        occ['directPrograms'].append({'stage': stage, 'sha256': digest, 'name': shader.get('name'), **use})
            occurrences.append(occ)

    rows = sorted(programs.values(), key=lambda r: (r['stage'], r['sha256']))
    for r in rows:
        r['names'] = sorted(x for x in r['names'] if x)
        r['uses'] = sorted(r['uses'], key=lambda x: (x['map'], x['techniqueSet'], x['techniqueSlot'], x['passIndex']))
    summary = {
        'family': family,
        'techniqueSetCount': len(wanted),
        'occurrenceCount': len(occurrences),
        'uniqueDirectVertexShaderCount': sum(r['stage'] == 'vs' for r in rows),
        'uniqueDirectPixelShaderCount': sum(r['stage'] == 'ps' for r in rows),
        'directProgramUseCount': sum(len(r['uses']) for r in rows),
        'packedReferenceCount': len(packed),
        'structuralFailureCount': 0,
    }
    return {
        'format': 't6-retail-special-family-dxbc-extract-v1',
        'family': family,
        'sources': {
            'specialManifest': special_manifest.name,
            'parser': parser_path.name,
            'helper': helper_path.name,
        },
        'techniqueSets': sorted(wanted),
        'programs': rows,
        'occurrences': occurrences,
        'packedReferences': packed,
        'structuralValidation': structural,
        'summary': summary,
        'proofBoundary': 'Exact bytes only for physically inline FOLLOW/INSERT DXBC programs in the five SHA-pinned expanded worlds. Family membership comes from the committed special-family census. Packed technique/shader references are retained unresolved and are never assigned by adjacency, names, or cross-map similarity.',
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--family', default='unlit')
    ap.add_argument('--special-manifest', type=Path, default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'))
    ap.add_argument('--parser', type=Path, default=Path('tools/t6_retail_special_shader_payload_census_v1.py'))
    ap.add_argument('--helper', type=Path, default=Path('tools/t6_retail_world_formats_45_proof_v1.py'))
    ap.add_argument('--program-dir', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    doc = build(a.root, a.special_manifest, a.parser, a.helper, a.family, a.program_dir)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
    print(json.dumps(doc['summary'], indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
