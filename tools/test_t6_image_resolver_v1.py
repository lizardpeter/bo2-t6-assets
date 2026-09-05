#!/usr/bin/env python3
from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from t6_image_resolver_v1 import (
    T6ImageIdentity,
    T6ImageResolverError,
    T6IpakSource,
    T6StreamedImageResolver,
)
from t6_ipak_core import IpakEntry, T6Ipak


def crc29(payload: bytes) -> int:
    return zlib.crc32(payload) & 0x1FFFFFFF


def raw_block(payload: bytes) -> bytes:
    header = bytearray(128)
    struct.pack_into('<I', header, 0, (1 << 24) | 0)
    struct.pack_into('<I', header, 4, len(payload))
    return bytes(header) + payload


def make_ipak(path: Path, entries: list[tuple[int, int, bytes]]) -> list[IpakEntry]:
    index_off = 0x100
    data_off = 0x400
    stride = 0x200
    total = data_off + stride * max(1, len(entries)) + 0x100
    out = bytearray(total)
    struct.pack_into('<4sIII', out, 0, b'KAPI', 0x50000, total, 2)
    struct.pack_into('<IIII', out, 16, 1, index_off, 16 * len(entries), len(entries))
    struct.pack_into('<IIII', out, 32, 2, data_off, total - data_off, 0)
    result = []
    for i, (name_hash, data_hash, payload) in enumerate(entries):
        if crc29(payload) != data_hash:
            raise AssertionError('fixture data hash mismatch')
        blob = raw_block(payload)
        rel = i * stride
        entry = IpakEntry(data_hash, name_hash, rel, len(blob))
        result.append(entry)
        struct.pack_into('<IIII', out, index_off + 16 * i, *entry.as_tuple())
        out[data_off + rel:data_off + rel + len(blob)] = blob
    path.write_bytes(out)
    return result


def probe(payload: bytes) -> dict:
    # Fixture payload begins with three unsigned 16-bit dimensions.
    w, h, d = struct.unpack_from('<HHH', payload, 0)
    return {'width': w, 'height': h, 'depth': d}


class TestT6ImageResolverV1(unittest.TestCase):
    def test_exact_pair_highest_precedence_wins(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = struct.pack('<HHH', 64, 32, 1) + b'exact-retail-payload'
            dh = crc29(payload)
            nh = 0x2468ACE0
            p0 = root / 'base.ipak'
            p1 = root / 'map.ipak'
            make_ipak(p0, [(nh, dh, payload)])
            make_ipak(p1, [(nh, dh, payload)])
            resolver = T6StreamedImageResolver([
                T6IpakSource('base', 10, T6Ipak.open_file(p0), 'base'),
                T6IpakSource('map', 40, T6Ipak.open_file(p1), 'map'),
            ])
            image = T6ImageIdentity('fixture', nh, dh, 64, 32, 1)
            result = resolver.resolve(image, payload_probe=probe)
            self.assertEqual(result['state'], 'resolved')
            self.assertEqual(result['resolution'], 'exact-pair')
            self.assertEqual(result['winner']['source'], 'map')
            self.assertEqual([x['source'] for x in result['shadowedAdmissibleMatches']], ['base'])
            self.assertEqual(result['payload'], payload)

    def test_exact_pair_beats_higher_priority_unique_data(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = struct.pack('<HHH', 8, 8, 1) + b'identity'
            dh = crc29(payload)
            expected_nh = 0x11111111
            alien_nh = 0x22222222
            exact_path = root / 'common.ipak'
            alien_path = root / 'patch.ipak'
            make_ipak(exact_path, [(expected_nh, dh, payload)])
            make_ipak(alien_path, [(alien_nh, dh, payload)])
            resolver = T6StreamedImageResolver([
                T6IpakSource('common', 20, T6Ipak.open_file(exact_path), 'common'),
                T6IpakSource('patch', 90, T6Ipak.open_file(alien_path), 'patch'),
            ], allow_unique_data_hash=True)
            result = resolver.resolve(T6ImageIdentity('fixture', expected_nh, dh, 8, 8, 1), payload_probe=probe)
            self.assertEqual(result['resolution'], 'exact-pair')
            self.assertEqual(result['winner']['source'], 'common')

    def test_unique_data_hash_requires_explicit_policy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = struct.pack('<HHH', 4, 4, 1) + b'unique'
            dh = crc29(payload)
            retained_nh = 0xAAAA0001
            stored_nh = 0xBBBB0002
            path = root / 'base.ipak'
            make_ipak(path, [(stored_nh, dh, payload)])
            source = T6IpakSource('base', 10, T6Ipak.open_file(path), 'base')
            strict = T6StreamedImageResolver([source], allow_unique_data_hash=False)
            self.assertEqual(strict.resolve(T6ImageIdentity('fixture', retained_nh, dh))['state'], 'unresolved')
            permitted = T6StreamedImageResolver([source], allow_unique_data_hash=True)
            result = permitted.resolve(T6ImageIdentity('fixture', retained_nh, dh))
            self.assertEqual(result['state'], 'resolved')
            self.assertEqual(result['resolution'], 'unique-data-hash')

    def test_same_name_wrong_data_is_diagnostic_not_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wrong_payload = struct.pack('<HHH', 2, 2, 1) + b'wrong'
            wanted_payload = struct.pack('<HHH', 2, 2, 1) + b'wanted-but-absent'
            wrong_dh = crc29(wrong_payload)
            wanted_dh = crc29(wanted_payload)
            nh = 0x13572468
            path = root / 'map.ipak'
            make_ipak(path, [(nh, wrong_dh, wrong_payload)])
            resolver = T6StreamedImageResolver([
                T6IpakSource('map', 40, T6Ipak.open_file(path), 'map')
            ])
            result = resolver.resolve(T6ImageIdentity('fixture', nh, wanted_dh))
            self.assertEqual(result['state'], 'unresolved')
            self.assertEqual(result['sourceDiagnostics'][0]['sameNameWrongDataHashes'], [wrong_dh])

    def test_dimension_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = struct.pack('<HHH', 16, 8, 1) + b'dimensions'
            dh = crc29(payload)
            nh = 0x01020304
            path = root / 'map.ipak'
            make_ipak(path, [(nh, dh, payload)])
            resolver = T6StreamedImageResolver([
                T6IpakSource('map', 1, T6Ipak.open_file(path), 'map')
            ])
            with self.assertRaises(T6ImageResolverError):
                resolver.resolve(T6ImageIdentity('fixture', nh, dh, 32, 8, 1), payload_probe=probe)


if __name__ == '__main__':
    unittest.main()
