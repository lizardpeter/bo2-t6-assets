#!/usr/bin/env python3
"""Bind exact retail textures to the repaired 1943-static Nuketown GLB.

Input texture identity comes only from t6_oat_external_static_texture_scan.py.
Streamed images require exact equality of the live T6 pair
(GfxImage.hash, GfxImage.streamedParts[0].hash29) with one map-IPAK entry,
followed by decompressed CRC29 and exact dimension validation.

Only the first semantic-2 slot may bind baseColorTexture and only the first
semantic-5 slot may bind normalTexture. $identitynormalmap is accepted only as
an exact live non-streamed semantic-5 identity. No same-name fallback exists.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
from pathlib import Path

from PIL import Image

import t6_nuketown_ipak_partial_texture_export_v2 as base
import t6_nuketown_static_xmodel_texture_apply_v2 as tex

SEM_COLOR = 2
SEM_NORMAL = 5
IDENTITY = '$identitynormalmap'
IDENTITY_HASH = 45285053


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_semantic(row: dict, semantic: int):
    return next((t for t in row.get('textures', []) if int(t.get('semantic', -1)) == semantic), None)


def identity_png() -> bytes:
    im = Image.new('RGBA', (1, 1), (128, 128, 255, 255))
    b = io.BytesIO()
    im.save(b, format='PNG', optimize=False)
    return b.getvalue()


def sampler_for(js: dict, sampler_state: int, cache: dict[tuple[bool, bool], int]) -> int:
    # T6 MaterialTextureDef sampler-state clamp bits, retained from the live material.
    clamp_u = bool(sampler_state & 0x20)
    clamp_v = bool(sampler_state & 0x40)
    key = (clamp_u, clamp_v)
    if key in cache:
        return cache[key]
    desired = {
        'magFilter': 9729,
        'minFilter': 9987,
        'wrapS': 33071 if clamp_u else 10497,
        'wrapT': 33071 if clamp_v else 10497,
    }
    js.setdefault('samplers', []).append(desired)
    idx = len(js['samplers']) - 1
    cache[key] = idx
    return idx


def append_png(js: dict, binbuf: bytearray, payload: bytes, name: str, sampler_state: int,
               extras: dict, sampler_cache: dict, texture_cache: dict) -> int:
    key = (name, hashlib.sha256(payload).hexdigest(), sampler_state)
    if key in texture_cache:
        return texture_cache[key]
    while len(binbuf) % 4:
        binbuf.append(0)
    off = len(binbuf)
    binbuf.extend(payload)
    bvs = js.setdefault('bufferViews', [])
    bvs.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(payload), 'name': f'T6_{name}_static_live_exact_PNG'})
    bvi = len(bvs) - 1
    images = js.setdefault('images', [])
    images.append({'name': name, 'bufferView': bvi, 'mimeType': 'image/png', 'extras': {'T6': extras}})
    ii = len(images) - 1
    si = sampler_for(js, sampler_state, sampler_cache)
    textures = js.setdefault('textures', [])
    textures.append({'name': name, 'sampler': si, 'source': ii})
    ti = len(textures) - 1
    texture_cache[key] = ti
    return ti


def build(glb: Path, catalog_path: Path, ipak_path: Path, out: Path, manifest_path: Path):
    catalog = json.loads(catalog_path.read_text())
    if catalog.get('playableStaticModelCount') != 297 or catalog.get('materialCount') != 344:
        raise ValueError('live static catalog identity counts changed')
    by_material = {m['name']: m for m in catalog.get('materials', [])}
    if len(by_material) != 344:
        raise ValueError('live static catalog has duplicate material names')

    js, binbuf = base.read_glb(glb)
    if js.get('images') or js.get('textures'):
        raise ValueError('repaired static input unexpectedly already contains image/texture objects')
    for i, m in enumerate(js.get('materials', [])):
        pbr = m.get('pbrMetallicRoughness') or {}
        if pbr.get('baseColorTexture') is not None or m.get('normalTexture') is not None:
            raise ValueError(f'static material {i}:{m.get("name")} already carries an unproven texture binding')

    data, data_sec, by_pair, by_name, by_data, lzo = tex.read_ipak(ipak_path)
    sampler_cache = {}
    texture_cache = {}
    promotions = []
    misses = collections.Counter()
    wrong_name_variants = []
    identity_bindings = 0

    glb_name_indices = collections.defaultdict(list)
    for i, m in enumerate(js.get('materials', [])):
        glb_name_indices[m.get('name')].append(i)

    for name, src in sorted(by_material.items()):
        indices = glb_name_indices.get(name, [])
        if not indices:
            # Catalog is the complete retail playable material set, but only materials represented
            # by the repaired OAT scene can be bound here. Missing names remain explicit evidence.
            misses[('material', 'absent-from-glb') ] += 1
            continue
        if len(indices) != 1:
            raise ValueError(f'{name}: duplicate exact GLB material identities {indices}')
        mi = indices[0]
        m = js['materials'][mi]
        for semantic, kind in ((SEM_COLOR, 'color'), (SEM_NORMAL, 'normal')):
            t = first_semantic(src, semantic)
            if t is None:
                misses[(kind, 'semantic-absent')] += 1
                continue
            im = t.get('image') or {}
            iname = im.get('name')
            if not isinstance(iname, str) or not iname:
                raise ValueError(f'{name} {kind}: live GfxImage has no name')
            if int(im.get('hash', -1)) != base.r_hash_string(iname):
                raise ValueError(f'{name} {kind}: live image hash validation lost for {iname}')

            if semantic == SEM_NORMAL and iname == IDENTITY:
                if int(im.get('hash')) != IDENTITY_HASH:
                    raise ValueError(f'{name}: identity-normal hash changed')
                if (int(im.get('width', 0)), int(im.get('height', 0)), int(im.get('depth', 0))) != (1, 1, 1):
                    raise ValueError(f'{name}: identity-normal dimensions changed')
                if int(im.get('streamedPartCountRaw', 0)) != 0:
                    raise ValueError(f'{name}: identity normal unexpectedly streamed')
                png = identity_png()
                ti = append_png(
                    js, binbuf, png, IDENTITY, int(t.get('samplerState', 0)),
                    {
                        'identityResolution': 'live-retail-gfximage-identity',
                        'sourceCatalog': catalog_path.name,
                        'imageHash': IDENTITY_HASH,
                        'width': 1, 'height': 1, 'depth': 1,
                        'semantic': SEM_NORMAL,
                        'pngSha256': hashlib.sha256(png).hexdigest(),
                    },
                    sampler_cache, texture_cache,
                )
                m['normalTexture'] = {'index': ti, 'texCoord': 0, 'scale': 1.0}
                identity_bindings += 1
                promotions.append({
                    'materialIndex': mi, 'material': name, 'kind': kind, 'semantic': semantic,
                    'image': IDENTITY, 'textureIndex': ti,
                    'identityResolution': 'live-retail-gfximage-identity',
                })
                continue

            part = im.get('streamedPart0')
            if not part:
                misses[(kind, 'nonstreamed-unresolved')] += 1
                continue
            name_hash = int(im['hash'])
            data_hash = int(part['hash29'])
            entry = by_pair.get((name_hash, data_hash))
            if entry is None:
                if by_name.get(name_hash):
                    wrong_name_variants.append({
                        'material': name, 'kind': kind, 'image': iname,
                        'nameHash': name_hash, 'expectedDataHash': data_hash,
                        'availableDataHashes': sorted({int(x[0]) for x in by_name[name_hash]}),
                    })
                misses[(kind, 'exact-pair-missing')] += 1
                continue

            iwi = tex.extract_entry(data, data_sec, entry, lzo)
            fmt, flags, w, h, d, gamma, sizes = base.parse_iwi27(iwi)
            expected_dims = (int(im['width']), int(im['height']), int(im['depth']))
            if (w, h, d) != expected_dims:
                raise ValueError(f'{name}/{iname}: exact pair dimensions {(w,h,d)} != live {expected_dims}')
            png, meta = tex.iwi_top_png(iwi, normal_semantic=(semantic == SEM_NORMAL))
            ti = append_png(
                js, binbuf, png, iname, int(t.get('samplerState', 0)),
                {
                    'source': ipak_path.name,
                    'identityResolution': 'ipak-exact-live-name+data-hash',
                    'ipakDataHash': int(entry[0]),
                    'ipakNameHash': int(entry[1]),
                    'liveImageHash': name_hash,
                    'liveStreamedDataHash': data_hash,
                    'semantic': semantic,
                    'iwiSha256': hashlib.sha256(iwi).hexdigest(),
                    'pngSha256': hashlib.sha256(png).hexdigest(),
                    **meta,
                },
                sampler_cache, texture_cache,
            )
            if semantic == SEM_COLOR:
                pbr = m.setdefault('pbrMetallicRoughness', {})
                pbr['baseColorTexture'] = {'index': ti, 'texCoord': 0}
                pbr['baseColorFactor'] = [1.0, 1.0, 1.0, 1.0]
            elif semantic == SEM_NORMAL:
                m['normalTexture'] = {'index': ti, 'texCoord': 0, 'scale': 1.0}
            else:
                raise AssertionError('semantic dispatch')
            promotions.append({
                'materialIndex': mi, 'material': name, 'kind': kind, 'semantic': semantic,
                'image': iname, 'textureIndex': ti,
                'identityResolution': 'ipak-exact-live-name+data-hash',
                'ipakNameHash': int(entry[1]), 'ipakDataHash': int(entry[0]),
                'iwiSha256': hashlib.sha256(iwi).hexdigest(),
                'pngSha256': hashlib.sha256(png).hexdigest(),
            })

    color_promotions = sum(p['semantic'] == SEM_COLOR for p in promotions)
    normal_promotions = sum(p['semantic'] == SEM_NORMAL for p in promotions)
    if any(p['kind'] == 'color' and p['semantic'] != SEM_COLOR for p in promotions):
        raise ValueError('semantic audit: non-color texture bound as base color')
    if any(p['kind'] == 'normal' and p['semantic'] != SEM_NORMAL for p in promotions):
        raise ValueError('semantic audit: non-normal texture bound as normal')

    js.setdefault('extras', {}).setdefault('T6', {})['staticLiveExactTextureApplyV1'] = {
        'sourceCatalog': catalog_path.name,
        'sourceIpak': ipak_path.name,
        'promotionCount': len(promotions),
        'colorPromotions': color_promotions,
        'normalPromotions': normal_promotions,
        'identityNormalBindings': identity_bindings,
        'sameNameWrongDataVariantRejected': len(wrong_name_variants),
        'proofBoundary': (
            'Static texture roles come from live MaterialTextureDef semantic values. '
            'Streamed images require exact live GfxImage nameHash+streamed dataHash equality with the map IPAK, '
            'then decompressed CRC29 and dimensions. $identitynormalmap is accepted only as the exact live 1x1 '
            'non-streamed semantic-5 identity. No same-name or unique-name fallback is used.'
        ),
    }
    base.write_glb(out, js, binbuf)
    j2, b2 = base.read_glb(out)
    if j2['buffers'][0]['byteLength'] != len(b2):
        raise ValueError('output buffer byteLength mismatch')

    summary = {
        'catalogMaterials': len(by_material),
        'glbMaterials': len(js.get('materials', [])),
        'promotionCount': len(promotions),
        'colorPromotions': color_promotions,
        'normalPromotions': normal_promotions,
        'identityNormalBindings': identity_bindings,
        'uniqueEmbeddedTextures': len(js.get('textures', [])),
        'uniqueEmbeddedImages': len(js.get('images', [])),
        'sameNameWrongDataVariantRejected': len(wrong_name_variants),
        'misses': {f'{k[0]}:{k[1]}': v for k, v in sorted(misses.items())},
    }
    manifest = {
        'format': 't6-nuketown-static-live-exact-texture-apply-v1',
        'inputGlb': {'file': glb.name, 'bytes': glb.stat().st_size, 'sha256': sha(glb)},
        'catalog': {'file': catalog_path.name, 'bytes': catalog_path.stat().st_size, 'sha256': sha(catalog_path)},
        'ipak': {'file': ipak_path.name, 'bytes': ipak_path.stat().st_size, 'sha256': sha(ipak_path)},
        'outputGlb': {'file': out.name, 'bytes': out.stat().st_size, 'sha256': sha(out)},
        'summary': summary,
        'promotions': promotions,
        'sameNameWrongDataVariantsRejected': wrong_name_variants,
        'validation': {
            'liveCatalogCounts': 'pass',
            'exactPairOnly': 'pass',
            'crc29AndDimensions': 'pass',
            'semantic2OnlyBaseColor': 'pass',
            'semantic5OnlyNormal': 'pass',
            'glbReparse': 'pass',
            'bufferByteLengthMatches': 'pass',
        },
        'proofBoundary': js['extras']['T6']['staticLiveExactTextureApplyV1']['proofBoundary'],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(manifest['outputGlb'], indent=2, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--glb', type=Path, required=True)
    ap.add_argument('--catalog', type=Path, required=True)
    ap.add_argument('--ipak', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, required=True)
    a = ap.parse_args()
    build(a.glb, a.catalog, a.ipak, a.out, a.manifest)


if __name__ == '__main__':
    main()
