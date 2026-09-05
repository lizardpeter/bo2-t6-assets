#!/usr/bin/env python3
from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from t6_image_resolver_v1 import T6IpakSource, T6StreamedImageResolver
from t6_ipak_core import IpakEntry, T6Ipak
from t6_material_image_resolver_v1 import (
    normalize_packed_identity_map,
    resolve_materials,
)


def crc29(payload: bytes) -> int:
    return zlib.crc32(payload) & 0x1FFFFFFF


def make_ipak(path: Path, name_hash: int, payload: bytes) -> IpakEntry:
    dh = crc29(payload)
    block = bytearray(128)
    struct.pack_into('<I', block, 0, (1 << 24) | 0)
    struct.pack_into('<I', block, 4, len(payload))
    blob = bytes(block) + payload
    total = 0x800
    out = bytearray(total)
    struct.pack_into('<4sIII', out, 0, b'KAPI', 0x50000, total, 2)
    struct.pack_into('<IIII', out, 16, 1, 0x100, 16, 1)
    struct.pack_into('<IIII', out, 32, 2, 0x200, total - 0x200, 0)
    entry = IpakEntry(dh, name_hash, 0, len(blob))
    struct.pack_into('<IIII', out, 0x100, *entry.as_tuple())
    out[0x200:0x200 + len(blob)] = blob
    path.write_bytes(out)
    return entry


class TestT6MaterialImageResolverV1(unittest.TestCase):
    def _resolver(self, root: Path, name_hash: int, payload: bytes):
        path = root / 'fixture.ipak'
        entry = make_ipak(path, name_hash, payload)
        resolver = T6StreamedImageResolver([
            T6IpakSource('fixture', 1, T6Ipak.open_file(path), 'fixture')
        ])
        return resolver, entry

    def test_world_and_xmodel_materials_use_identical_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            name_hash = 0x44556677
            payload = b'retail-image-payload'
            resolver, entry = self._resolver(root, name_hash, payload)
            image = {
                'inline': True,
                'name': 'shared_image',
                'hash': name_hash,
                'streaming': True,
                'streamedPartCount': 1,
                'streamedPart0Hash29': entry.data_hash,
                'width': 64,
                'height': 64,
                'depth': 1,
            }
            world = [{'name': 'world/material', 'textures': [{'semantic': 2, 'image': image}]}]
            xmodel = [{'name': 'model/material', 'textures': [{'semantic': 2, 'image': image}]}]
            wr = resolve_materials(world, image_resolver=resolver)
            xr = resolve_materials(xmodel, image_resolver=resolver)
            wd = wr['materials'][0]['dependencies'][0]
            xd = xr['materials'][0]['dependencies'][0]
            self.assertEqual(wd['state'], 'resolved')
            self.assertEqual(xd['state'], 'resolved')
            self.assertEqual(wd['nameHash'], xd['nameHash'])
            self.assertEqual(wd['dataHash29'], xd['dataHash29'])
            self.assertEqual(wd['resolution']['winner'], xd['resolution']['winner'])

    def test_missing_retained_hash_is_not_filename_inferred(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolver, entry = self._resolver(root, 0x12345678, b'payload')
            materials = [{
                'name': 'model/material',
                'textures': [{
                    'semantic': 2,
                    'image': {
                        'inline': True,
                        'name': 'looks_hashable_but_is_not_proof',
                        'streaming': True,
                        'streamedPartCount': 1,
                        'streamedPart0Hash29': entry.data_hash,
                    },
                }],
            }]
            result = resolve_materials(materials, image_resolver=resolver)
            dep = result['materials'][0]['dependencies'][0]
            self.assertEqual(dep['state'], 'identity-incomplete')
            self.assertIn('filename hashing is not proof', dep['reason'])

    def test_packed_pointer_requires_then_uses_exact_identity_proof(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            name_hash = 0x0A0B0C0D
            payload = b'packed-image-payload'
            resolver, entry = self._resolver(root, name_hash, payload)
            materials = [{
                'name': 'world/layered',
                'textures': [{
                    'semantic': 5,
                    'image': {
                        'inline': False,
                        'pointer': {'kind': 'offset', 'block': 5, 'offset': 1234},
                    },
                }],
            }]
            unresolved = resolve_materials(materials, image_resolver=resolver)
            self.assertEqual(
                unresolved['materials'][0]['dependencies'][0]['state'],
                'packed-pointer-unresolved',
            )
            packed = normalize_packed_identity_map([{
                'block': 5,
                'offset': 1234,
                'imageIdentity': {
                    'name': 'packed_exact',
                    'hash': name_hash,
                    'streamedPart0Hash29': entry.data_hash,
                    'width': 8,
                    'height': 8,
                    'depth': 1,
                },
            }])
            resolved = resolve_materials(
                materials,
                image_resolver=resolver,
                packed_identities=packed,
            )
            dep = resolved['materials'][0]['dependencies'][0]
            self.assertEqual(dep['state'], 'resolved')
            self.assertEqual(dep['identityProvenance'], 'retained-packed-pointer-proof')
            self.assertEqual(dep['pointer'], [5, 1234])

    def test_runtime_image_never_hits_ipak(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolver, _ = self._resolver(root, 0x01010101, b'unrelated')
            materials = [{
                'name': 'world/shadow',
                'textures': [{
                    'semantic': 10,
                    'image': {
                        'inline': True,
                        'name': ',shadow',
                        'hash': 0,
                        'streaming': False,
                        'streamedPartCount': 0,
                        'width': 1,
                        'height': 1,
                        'depth': 1,
                    },
                }],
            }]
            result = resolve_materials(
                materials,
                image_resolver=resolver,
                runtime_images={',shadow'},
            )
            dep = result['materials'][0]['dependencies'][0]
            self.assertEqual(dep['state'], 'non-streamed')
            self.assertTrue(dep['runtimeCodeImage'])
            self.assertEqual(result['stats']['streamedResolvedDependencyCount'], 0)


if __name__ == '__main__':
    unittest.main()
