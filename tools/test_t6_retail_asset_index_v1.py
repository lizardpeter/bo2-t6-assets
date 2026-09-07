#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from t6_asset_types_v1 import IMAGE, MATERIAL, TECHNIQUE_SET, XANIMPARTS, XMODEL
from t6_retail_asset_index_v1 import (
    AmbiguousAssetError,
    AssetDefinition,
    AssetReference,
    MissingAssetError,
    RetailAssetIndex,
    StaleIndexError,
    ZoneFingerprint,
)


def definition(asset_type: str, name: str, zone: str, body: bytes, start: int = 10):
    return AssetDefinition(
        asset_type=asset_type,
        name=name,
        zone=zone,
        start=start,
        end=start + len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        metadata={"fixture": True},
    )


class RetailAssetIndexTests(unittest.TestCase):
    def test_canonical_t6_asset_ids(self):
        self.assertEqual((XANIMPARTS, XMODEL, MATERIAL, TECHNIQUE_SET, IMAGE), (4, 5, 6, 7, 8))

    def test_handle_reference_does_not_become_definition(self):
        idx = RetailAssetIndex()
        zone = b"faction-zone"
        idx.add_zone(ZoneFingerprint.from_bytes("faction", zone))
        idx.add_reference(
            AssetReference(
                asset_type="material",
                name="mc/shared",
                source_zone="faction",
                source_asset="c_usa_mp_seal6_smg_fb",
                owner_start=1234,
            )
        )
        self.assertEqual(len(idx.references_for("material", "mc/shared")), 1)
        with self.assertRaises(MissingAssetError):
            idx.resolve("material", "mc/shared")

    def test_identical_dependency_definitions_are_not_ambiguous(self):
        idx = RetailAssetIndex()
        for zone in ("common_mp", "patch_mp"):
            idx.add_zone(ZoneFingerprint.from_bytes(zone, zone.encode()))
            idx.add_definition(definition("material", "mc/shared", zone, b"same-body"))
        self.assertEqual(idx.resolve("material", "mc/shared").zone, "common_mp")
        self.assertEqual(
            idx.resolve("material", "mc/shared", ["patch_mp", "common_mp"]).zone,
            "patch_mp",
        )

    def test_conflicting_definitions_require_dependency_order(self):
        idx = RetailAssetIndex()
        idx.add_zone(ZoneFingerprint.from_bytes("common_mp", b"common"))
        idx.add_zone(ZoneFingerprint.from_bytes("faction", b"faction"))
        idx.add_definition(definition("material", "mc/foo", "common_mp", b"A"))
        idx.add_definition(definition("material", "mc/foo", "faction", b"B"))
        with self.assertRaises(AmbiguousAssetError):
            idx.resolve("material", "mc/foo")
        self.assertEqual(idx.resolve("material", "mc/foo", ["faction", "common_mp"]).zone, "faction")

    def test_dependency_closure_excludes_outside_definition(self):
        idx = RetailAssetIndex()
        idx.add_zone(ZoneFingerprint.from_bytes("common_mp", b"common"))
        idx.add_definition(definition("material", "mc/foo", "common_mp", b"A"))
        with self.assertRaises(MissingAssetError):
            idx.resolve("material", "mc/foo", ["faction"])

    def test_zone_fingerprint_invalidates_cache(self):
        idx = RetailAssetIndex()
        idx.add_zone(ZoneFingerprint.from_bytes("common_mp", b"retail"))
        idx.verify_zone_bytes("common_mp", b"retail")
        with self.assertRaises(StaleIndexError):
            idx.verify_zone_bytes("common_mp", b"mutated")

    def test_walk_adapter_hashes_exact_serialized_extent(self):
        expanded = bytearray(b"\x00" * 256)
        expanded[100:120] = b"M" * 20
        expanded[160:176] = b"T" * 16
        expanded = bytes(expanded)
        report = {
            "format": "t6-material-techset-top-level-walk-v1",
            "expandedSha256": hashlib.sha256(expanded).hexdigest(),
            "rows": [
                {
                    "xassetIndex": 7,
                    "xassetType": MATERIAL,
                    "sourceStart": 100,
                    "sourceEnd": 120,
                    "name": {"value": "mc/material"},
                    "textureCount": 2,
                    "constantCount": 3,
                    "stateBitsCount": 1,
                    "techniqueSetPointer": {"kind": "packed", "block": 1, "offset": 12},
                    "nestedTechniqueSet": None,
                },
                {
                    "xassetIndex": 8,
                    "xassetType": TECHNIQUE_SET,
                    "sourceStart": 160,
                    "sourceEnd": 176,
                    "name": {"value": "mc/techset"},
                    "worldVertFormat": 1,
                    "techniqueRefs": [],
                },
            ],
        }
        idx = RetailAssetIndex()
        made = idx.ingest_material_techset_walk("common_mp", report, expanded)
        self.assertEqual(len(made), 2)
        mat = idx.resolve("material", "mc/material")
        self.assertEqual(mat.start, 100)
        self.assertEqual(mat.end, 120)
        self.assertEqual(mat.sha256, hashlib.sha256(b"M" * 20).hexdigest())
        self.assertEqual(mat.metadata["textureCount"], 2)
        self.assertEqual(idx.resolve("material_technique_set", "mc/techset").start, 160)

    def test_walk_adapter_rejects_xmodel_type_as_material(self):
        expanded = b"x" * 64
        report = {
            "format": "t6-material-techset-top-level-walk-v1",
            "expandedSha256": hashlib.sha256(expanded).hexdigest(),
            "rows": [{
                "xassetIndex": 1, "xassetType": XMODEL,
                "sourceStart": 1, "sourceEnd": 2,
                "name": {"value": "must_not_be_material"},
            }],
        }
        with self.assertRaises(Exception):
            RetailAssetIndex().ingest_material_techset_walk("fixture", report, expanded)

    def test_walk_adapter_rejects_wrong_zone_bytes(self):
        report = {
            "format": "t6-material-techset-top-level-walk-v1",
            "expandedSha256": hashlib.sha256(b"expected").hexdigest(),
            "rows": [],
        }
        with self.assertRaises(StaleIndexError):
            RetailAssetIndex().ingest_material_techset_walk("common_mp", report, b"different")

    def test_json_roundtrip_preserves_reference_and_definition_provenance(self):
        idx = RetailAssetIndex()
        zone_bytes = b"common"
        idx.add_zone(ZoneFingerprint.from_bytes("common_mp", zone_bytes))
        idx.add_definition(definition("material", "mc/foo", "common_mp", b"body"))
        idx.add_reference(
            AssetReference(
                asset_type="material",
                name="mc/foo",
                source_zone="common_mp",
                source_asset="xmodel/test",
                owner_start=22,
                proof={"kind": "packed-alias"},
            )
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "index.json"
            idx.save(path)
            again = RetailAssetIndex.load(path)
        self.assertEqual(again.resolve("material", "mc/foo").zone, "common_mp")
        refs = again.references_for("material", "mc/foo")
        self.assertEqual(refs[0].source_asset, "xmodel/test")
        self.assertEqual(refs[0].proof["kind"], "packed-alias")


if __name__ == "__main__":
    unittest.main(verbosity=2)
