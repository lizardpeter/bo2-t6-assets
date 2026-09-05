#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import zlib
from pathlib import Path


def load_json(path: Path) -> dict:
    if path.name.endswith('.zlib.b64'):
        return json.loads(zlib.decompress(base64.b64decode(path.read_text().strip())))
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(ipak_path: Path, targets_path: Path, alias_bank_path: Path, texture_tool_path: Path, out_dir: Path, expected_exact: int) -> dict:
    targets = load_json(targets_path)
    bank = load_json(alias_bank_path)
    bindings = targets.get('bindings', [])
    if targets.get('remainingBindingCount') != len(bindings):
        raise ValueError('target binding count mismatch')
    target_by_name = {}
    for row in bindings:
        name = row['image']
        identity = (int(row['aliasHash']), int(row['aliasDataHash']))
        prior = target_by_name.get(name)
        if prior is not None and prior != identity:
            raise ValueError(f'conflicting target identity {name}')
        target_by_name[name] = identity
    if len(target_by_name) != int(targets['remainingUniqueImageCount']):
        raise ValueError('target unique image count mismatch')

    aliases = {a['name']: a for a in bank.get('aliases', [])}
    if len(aliases) != 81 or bank.get('conflictCount') != 0:
        raise ValueError('unexpected alias bank boundary')
    for name, identity in target_by_name.items():
        a = aliases.get(name)
        if a is None or (int(a['hash']), int(a['dataHash'])) != identity:
            raise ValueError(f'{name}: target/alias-bank identity mismatch')

    spec = importlib.util.spec_from_file_location('t6_static_tex', texture_tool_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    data, data_sec, by_pair, by_name, by_data, lzo = mod.read_ipak(ipak_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    validated = name_only = data_only = absent = 0
    for ordinal, name in enumerate(sorted(target_by_name)):
        nh, dh = target_by_name[name]
        alias = aliases[name]
        exact = by_pair.get((nh, dh))
        name_hits = by_name.get(nh, [])
        data_hits = by_data.get(dh, [])
        row = {
            'name': name, 'hash': nh, 'dataHash': dh,
            'semantic': int(alias['semantic']), 'slot': int(alias['slot']),
            'width': int(alias['width']), 'height': int(alias['height']), 'depth': int(alias['depth']),
            'nameHashEntryCount': len(name_hits),
            'nameHashAvailableDataHashes': sorted({int(e[0]) for e in name_hits}),
            'dataHashEntryCount': len(data_hits),
            'dataHashAvailableNameHashes': sorted({int(e[1]) for e in data_hits}),
        }
        if exact is None:
            if name_hits:
                row['status'] = 'name-hash-only'; name_only += 1
            elif data_hits:
                row['status'] = 'data-hash-only'; data_only += 1
            else:
                row['status'] = 'absent'; absent += 1
            rows.append(row)
            continue
        iwi = mod.extract_entry(data, data_sec, exact, lzo)
        fmt, flags, width, height, depth, gamma, _sizes = mod.base.parse_iwi27(iwi)
        expected_dims = (row['width'], row['height'], row['depth'])
        if (width, height, depth) != expected_dims:
            raise ValueError(f'{name}: IWI dimensions {(width,height,depth)} != {expected_dims}')
        png, meta = mod.iwi_top_png(iwi, normal_semantic=(int(alias['semantic']) == 5))
        safe = f"{ordinal:03d}_{name.replace('/', '__').replace('~', '_tilde_')}"
        iwi_path = out_dir / f'{safe}.iwi'
        png_path = out_dir / f'{safe}.png'
        iwi_path.write_bytes(iwi)
        png_path.write_bytes(png)
        row.update({
            'status': 'validated', 'ipakEntry': list(exact),
            'format': fmt, 'flags': flags, 'gamma': gamma,
            'iwiFile': iwi_path.name, 'iwiBytes': len(iwi), 'iwiSha256': hashlib.sha256(iwi).hexdigest(),
            'pngFile': png_path.name, 'pngBytes': len(png), 'pngSha256': hashlib.sha256(png).hexdigest(),
            'crc29Validated': True, 'iwi27Validated': True, 'dimensionsValidated': True,
            'decoder': meta.get('decoder'),
        })
        validated += 1
        rows.append(row)

    if validated != expected_exact:
        raise ValueError(f'validated exact targets {validated} != expected {expected_exact}')
    report = {
        'format': 't6-local-ipak-exact-target-extraction-v1',
        'sourceIpak': {'file': ipak_path.name, 'bytes': ipak_path.stat().st_size, 'sha256': sha256_file(ipak_path)},
        'targets': {'file': targets_path.name, 'sha256': sha256_file(targets_path), 'bindings': len(bindings), 'uniqueImages': len(target_by_name)},
        'aliasBank': {'file': alias_bank_path.name, 'sha256': sha256_file(alias_bank_path)},
        'summary': {'targetImages': len(target_by_name), 'validated': validated, 'nameHashOnly': name_only, 'dataHashOnly': data_only, 'absent': absent},
        'rows': rows,
        'proofBoundary': 'Payload promotion requires one exact current (nameHash,dataHash) IPAK index entry, decompressed CRC29 equality, IWI27 parse, and exact retained alias-bank dimensions. Name-hash-only and data-hash-only rows are never extracted or promoted.'
    }
    out = out_dir / 'LOCAL_IPAK_EXACT_TARGETS_V1.json'
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--ipak', type=Path, required=True)
    ap.add_argument('--targets', type=Path, required=True)
    ap.add_argument('--alias-bank', type=Path, required=True)
    ap.add_argument('--texture-tool', type=Path, default=Path('tools/t6_nuketown_static_xmodel_texture_apply_v2.py'))
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--expected-exact', type=int, required=True)
    args = ap.parse_args()
    report = build(args.ipak, args.targets, args.alias_bank, args.texture_tool, args.out_dir, args.expected_exact)
    print(json.dumps(report['summary'], indent=2))
    for row in report['rows']:
        if row['status'] != 'validated':
            print(row['status'].upper(), row['name'], row.get('nameHashAvailableDataHashes', []))


if __name__ == '__main__':
    main()
