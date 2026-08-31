#!/usr/bin/env python3
"""T6 ClipMap normalized collision exporter v7.

Extends v6 with exact DynEntityDef asset identity resolution.

For live/destroyed XModel and destroy-FX references, packed VIRTUAL pointers are
accepted as top-level XAsset references only when they exactly address an
XAsset header slot:
    xAssetVirtualBase + assetIndex * 8 + 4
and the addressed XAsset has the expected type.

DynEnt PhysPreset pointers are classified more carefully: some retail pointers
address top-level PHYSPRESET XAssets, while others address reusable nested
PhysPreset allocations owned by XModels. v7 preserves that distinction instead
of forcing every packed PhysPreset pointer into the XAsset table.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from t6_clipmap_normalize_v1 import normalize as normalize_v1
from t6_clipmap_normalize_v2 import resolve_planes
from t6_clipmap_normalize_v3 import resolve_leafbrushes
from t6_clipmap_normalize_v4 import decode_static_models, decode_constraints
from t6_clipmap_normalize_v5 import parse_top_level_xasset_table, resolve_static_xmodel_assets
from t6_clipmap_normalize_v6 import resolve_static_xmodel_names, walk_map_prefix_stringtable, scan_required_xmodels

ASSET_TYPE_PHYSPRESET = 1
ASSET_TYPE_XMODEL = 5
ASSET_TYPE_FX = 33


def _slot_asset_index(pointer: dict, base: int, entries: list[dict], expected_type: int, *, required: bool, field: str) -> int | None:
    kind = pointer.get('kind')
    if kind == 'null':
        return None
    if kind != 'packed' or pointer.get('block') != 5:
        if required:
            raise ValueError(f'{field}: expected packed VIRTUAL XAsset reference, got {pointer}')
        return None
    delta = int(pointer['offset']) - int(base) - 4
    if delta < 0 or delta % 8:
        if required:
            raise ValueError(f'{field}: pointer does not address an XAsset header slot: {pointer}; base={base}')
        return None
    idx = delta // 8
    if idx >= len(entries) or entries[idx]['type'] != expected_type:
        if required:
            typ = entries[idx]['type'] if 0 <= idx < len(entries) else None
            raise ValueError(f'{field}: XAsset slot {idx} has type {typ}, expected {expected_type}')
        return None
    return idx


def resolve_dynent_assets(out: dict, data: bytes) -> dict:
    if 'staticModelXModelAssetResolution' not in out:
        raise ValueError('v7 DynEnt resolution requires static XAsset-base resolution first')
    base = int(out['staticModelXModelAssetResolution']['xAssetVirtualBase'])
    table = parse_top_level_xasset_table(data)
    entries = table['entries']

    live = Counter()
    destroyed = Counter()
    fx = Counter()
    phys_top = Counter()
    phys_inline = Counter()
    phys_reusable = Counter()

    for row in out.get('dynEntDefs', []):
        i = _slot_asset_index(row['xModel'], base, entries, ASSET_TYPE_XMODEL, required=True, field=f"dynEnt[{row['index']}].xModel") if row['xModel']['kind'] != 'null' else None
        j = _slot_asset_index(row['destroyedXModel'], base, entries, ASSET_TYPE_XMODEL, required=True, field=f"dynEnt[{row['index']}].destroyedXModel") if row['destroyedXModel']['kind'] != 'null' else None
        f = _slot_asset_index(row['destroyFx'], base, entries, ASSET_TYPE_FX, required=True, field=f"dynEnt[{row['index']}].destroyFx") if row['destroyFx']['kind'] != 'null' else None
        p = _slot_asset_index(row['physPreset'], base, entries, ASSET_TYPE_PHYSPRESET, required=False, field=f"dynEnt[{row['index']}].physPreset") if row['physPreset']['kind'] != 'null' else None

        row['xModelAssetIndex'] = i
        row['destroyedXModelAssetIndex'] = j
        row['destroyFxAssetIndex'] = f
        if i is not None: live[i] += 1
        if j is not None: destroyed[j] += 1
        if f is not None: fx[f] += 1
        if row['physPreset']['kind'] == 'null':
            row['physPresetResolution'] = {'kind': 'null'}
        elif row['physPreset']['kind'] in ('following', 'insert'):
            row['physPresetResolution'] = {'kind': 'inline_serialized_phys_preset', 'pointer': row['physPreset']}
            phys_inline[row['physPreset']['kind']] += 1
        elif p is not None:
            row['physPresetResolution'] = {'kind': 'top_level_xasset', 'assetIndex': p}
            phys_top[p] += 1
        else:
            row['physPresetResolution'] = {'kind': 'reusable_non_xasset_allocation', 'pointer': row['physPreset']}
            phys_reusable[(row['physPreset']['block'], row['physPreset']['offset'])] += 1

    targets = sorted(set(live) | set(destroyed))
    if targets:
        max_target = max(targets)
        required_indices = [i for i, ent in enumerate(entries) if ent['type'] == ASSET_TYPE_XMODEL and i <= max_target]
        prefix = walk_map_prefix_stringtable(data, table)
        records = scan_required_xmodels(data, prefix['sourceEnd'], len(required_indices), prefix['logicalToText'])
        if len(records) != len(required_indices):
            raise AssertionError('DynEnt XModel record/index cardinality mismatch')
        by_asset = {idx: rec for idx, rec in zip(required_indices, records)}
    else:
        required_indices = []
        prefix = None
        by_asset = {}

    for row in out.get('dynEntDefs', []):
        for stem in ('xModel', 'destroyedXModel'):
            idx = row.get(stem + 'AssetIndex')
            if idx is None:
                row[stem + 'AssetName'] = None
                row[stem + 'FixedSourceStart'] = None
                continue
            rec = by_asset.get(idx)
            if rec is None:
                raise ValueError(f'{stem}: no serialized XModel record for asset {idx}')
            row[stem + 'AssetName'] = rec['name']
            row[stem + 'FixedSourceStart'] = rec['fixedSourceStart']
            row[stem + 'NamePointer'] = rec['namePointer']

    unique_targets = []
    for idx in targets:
        rec = by_asset[idx]
        unique_targets.append({
            'assetIndex': idx,
            'name': rec['name'],
            'fixedSourceStart': rec['fixedSourceStart'],
            'liveUseCount': live[idx],
            'destroyedUseCount': destroyed[idx],
            'numBones': rec['numBones'],
            'numSurfs': rec['numSurfs'],
            'numCollSurfs': rec['numCollSurfs'],
            'numCollmaps': rec['numCollmaps'],
            'physPresetPointer': rec['physPresetPointer'],
            'physConstraintsPointer': rec['physConstraintsPointer'],
        })

    result = {
        'status': 'resolved_from_xasset_header_slots_and_serialized_xmodel_records',
        'xAssetVirtualBase': base,
        'dynEntDefCount': len(out.get('dynEntDefs', [])),
        'nonNullLiveXModelRefs': sum(live.values()),
        'nonNullDestroyedXModelRefs': sum(destroyed.values()),
        'uniqueXModelTargetCount': len(targets),
        'maxXModelTargetAssetIndex': max(targets) if targets else None,
        'requiredTopLevelXModelsThroughMaxTarget': len(required_indices),
        'destroyFx': {'referenceCount': sum(fx.values()), 'uniqueAssetCount': len(fx), 'assetUseCounts': {str(k): v for k, v in sorted(fx.items())}},
        'physPreset': {
            'topLevelXAssetReferenceCount': sum(phys_top.values()),
            'topLevelUniqueAssetCount': len(phys_top),
            'topLevelAssetUseCounts': {str(k): v for k, v in sorted(phys_top.items())},
            'inlineSerializedReferenceCount': sum(phys_inline.values()),
            'inlineSerializedPointerKindCounts': dict(sorted(phys_inline.items())),
            'reusableNestedReferenceCount': sum(phys_reusable.values()),
            'reusableNestedUniqueAllocationCount': len(phys_reusable),
            'reusableNestedAllocationUseCounts': {f'{k[0]}:{k[1]}': v for k, v in sorted(phys_reusable.items())},
        },
        'stringTableProof': prefix['assets']['stringTable'] if prefix else None,
        'uniqueXModelTargets': unique_targets,
    }
    out['dynEntAssetResolution'] = result
    out['format'] = 't6-clipmap-normalized-v7'
    out['normalizationStatus']['dynEntXModelAssetsResolved'] = True
    out['normalizationStatus']['dynEntDestroyedXModelAssetsResolved'] = True
    out['normalizationStatus']['dynEntDestroyFxAssetsResolved'] = True
    out['normalizationStatus']['dynEntPhysPresetReferencesClassified'] = True
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path)
    ap.add_argument('--asset-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--gfxworld-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--plane-source-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    out, walk = normalize_v1(data, args.asset_start)
    resolve_planes(out, data, gfxworld_start=args.gfxworld_start, plane_source_start=args.plane_source_start)
    resolve_leafbrushes(out, walk, data)
    decode_static_models(out, walk, data)
    decode_constraints(out, walk, data)
    resolve_static_xmodel_assets(out, data)
    resolve_static_xmodel_names(out, data)
    dyn = resolve_dynent_assets(out, data)
    out['expandedSha256'] = hashlib.sha256(data).hexdigest()
    out['normalizationStatus']['unexpandedOwnedSections'] = sorted(out['unexpandedSections'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({
        'out': str(args.out),
        'bytes': args.out.stat().st_size,
        'sha256': hashlib.sha256(args.out.read_bytes()).hexdigest(),
        'dynEntDefCount': dyn['dynEntDefCount'],
        'liveXModelRefs': dyn['nonNullLiveXModelRefs'],
        'destroyedXModelRefs': dyn['nonNullDestroyedXModelRefs'],
        'uniqueDynamicXModels': dyn['uniqueXModelTargetCount'],
        'destroyFxRefs': dyn['destroyFx']['referenceCount'],
        'physPresetTopLevelRefs': dyn['physPreset']['topLevelXAssetReferenceCount'],
        'physPresetInlineRefs': dyn['physPreset']['inlineSerializedReferenceCount'],
        'physPresetReusableNestedRefs': dyn['physPreset']['reusableNestedReferenceCount'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
