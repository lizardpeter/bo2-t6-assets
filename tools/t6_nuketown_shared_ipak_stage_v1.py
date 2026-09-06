#!/usr/bin/env python3
"""Stage exact Nuketown packed-GfxImage payloads from the retained shared-IPAK census.

The census is the proof/identity layer. This tool is only a deterministic byte
materializer: each resolved alias must reproduce its retained payload SHA-256,
CRC29 (inside the IPAK reader), IWI27 identity and dimensions. Payloads are
stored once by SHA-256 and aliases point to that immutable file.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import zlib
from pathlib import Path

from t6_ipak_http_range_v2 import open_ipak
from t6_nuketown_shared_ipak_alias_census_v1 import iwi_identity


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_census(path: Path) -> tuple[dict, bytes]:
    stored = path.read_bytes().strip()
    raw = zlib.decompress(base64.b64decode(stored))
    doc = json.loads(raw)
    if doc.get('format') != 't6-nuketown-shared-ipak-packed-image-alias-census-v1':
        raise ValueError(f"unexpected census format {doc.get('format')!r}")
    s = doc.get('summary') or {}
    if int(s.get('conflict', -1)) != 0:
        raise ValueError('census contains conflicts')
    if int(s.get('resolved', -1)) + int(s.get('missing', -1)) != int(s.get('aliasCount', -1)):
        raise ValueError('census summary does not balance')
    return doc, raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('urls', nargs='+')
    a = ap.parse_args()

    census, census_raw = load_census(a.census)
    ipaks = {x.url: x for x in (open_ipak(u) for u in a.urls)}
    a.out_dir.mkdir(parents=True, exist_ok=True)
    payload_rows = {}
    aliases = []

    for row in census['aliases']:
        if row['status'] != 'resolved':
            aliases.append({
                'aliasIndex': row['aliasIndex'], 'name': row['name'], 'status': row['status'],
                'payload': None, 'reason': row.get('reason')
            })
            continue

        expected_sha = row['payloadSha256']
        matches = row.get('matches') or []
        if not matches:
            raise ValueError(f"alias {row['aliasIndex']} resolved without matches")

        # All census matches were already proven byte-identical. Use the first
        # exact recorded container/entry and independently reproduce the bytes.
        m = matches[0]
        ipak = ipaks.get(m['container'])
        if ipak is None:
            raise ValueError(f"census container not supplied: {m['container']}")
        e0 = m['entry']
        e = ipak.entry_exact(int(e0['nameHash']), int(e0['dataHash']))
        if e is None:
            raise ValueError(f"recorded exact IPAK entry disappeared for alias {row['aliasIndex']}")
        if list(e) != [int(e0['dataHash']), int(e0['nameHash']), int(e0['offset']), int(e0['rawSize'])]:
            raise ValueError(f"recorded IPAK tuple drift for alias {row['aliasIndex']}")

        raw = ipak.extract_entry(e)
        got_sha = sha256(raw)
        if got_sha != expected_sha or got_sha != m['sha256']:
            raise ValueError(f"payload SHA drift for alias {row['aliasIndex']}: {got_sha} != {expected_sha}")
        ident = iwi_identity(raw)
        dims = row['retainedDimensions']
        if (ident['width'], ident['height'], ident['depth']) != (int(dims['width']), int(dims['height']), int(dims['depth'])):
            raise ValueError(f"IWI dimension drift for alias {row['aliasIndex']}")

        rel = f"payloads/{got_sha}.iwi"
        p = a.out_dir / f'{got_sha}.iwi'
        if p.exists():
            if p.read_bytes() != raw:
                raise ValueError(f"same SHA path contains different bytes: {p}")
        else:
            p.write_bytes(raw)
        payload_rows.setdefault(got_sha, {
            'sha256': got_sha,
            'bytes': len(raw),
            'file': rel,
            'iwi': ident,
            'dataHash': int(e[0]),
            'sourceContainers': set(),
            'aliases': [],
        })['sourceContainers'].add(m['container'])
        payload_rows[got_sha]['aliases'].append(int(row['aliasIndex']))
        aliases.append({
            'aliasIndex': int(row['aliasIndex']),
            'block': int(row['block']),
            'virtualOffset': int(row['virtualOffset']),
            'name': row['name'],
            'nameHash': int(row['nameHash']),
            'dataHash': int(row['dataHash']),
            'semantic': int(row['semantic']),
            'samplerState': int(row['samplerState']),
            'status': 'resolved',
            'payload': rel,
            'payloadSha256': got_sha,
            'iwi': ident,
        })

    payloads = []
    for k in sorted(payload_rows):
        r = payload_rows[k]
        r['sourceContainers'] = sorted(r['sourceContainers'])
        r['aliases'] = sorted(r['aliases'])
        payloads.append(r)

    resolved = sum(1 for x in aliases if x['status'] == 'resolved')
    missing = len(aliases) - resolved
    manifest = {
        'format': 't6-nuketown-shared-ipak-staged-payloads-v1',
        'map': 'mp_nuketown_2020',
        'sourceCensus': {
            'path': str(a.census),
            'rawBytes': len(census_raw),
            'rawSha256': sha256(census_raw),
        },
        'summary': {
            'aliasCount': len(aliases),
            'resolvedAliasCount': resolved,
            'unresolvedAliasCount': missing,
            'uniquePayloadCount': len(payloads),
            'payloadBytes': sum(int(x['bytes']) for x in payloads),
        },
        'payloads': payloads,
        'aliases': aliases,
        'proofBoundary': 'Materialization only from exact entries already retained by the six-IPAK census. Every byte range is re-read, retail-decompressed, CRC29 checked by the v2 range reader, SHA-256 checked against the census, parsed as IWI27, and dimension checked. No new identity inference occurs here.',
    }
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps(manifest['summary'], indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
