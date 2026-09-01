#!/usr/bin/env python3
"""Synthetic regression for t6_world_vertex_audit_v2.

This does NOT count as retail byte proof. It exists only to exercise every
declared T6 world vertex format/stride through the generic audit machinery.
"""
from __future__ import annotations

import json
import struct
import tempfile
from pathlib import Path

from t6_world_vertex_audit_v2 import audit
from t6_zone_core import WORLD_VERTEX_FORMATS, MaterialWorldVertexFormat


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = 0x4000
        vertex_count = 4

        surfaces = []
        materials = []
        catalog = []
        prefix = []
        vd0 = bytearray()
        vd1 = bytearray()

        for fmt in range(9):
            name = f"synthetic/material_{fmt}"
            pointer = 0x10000000 + fmt * 0x100
            ai = len(prefix)
            prefix.append(
                {
                    "type": "techniqueset",
                    "name": f"synthetic/techset_{fmt}",
                    "details": {"worldVertFormat": fmt},
                }
            )
            materials.append(
                {
                    "name": name,
                    "techniqueSet": {
                        "pointer": {
                            "kind": "offset",
                            "block": 5,
                            "offset": base + 4 + 8 * ai,
                        }
                    },
                }
            )
            catalog.append(
                {
                    "name": name,
                    "surfacePointerHex": f"0x{pointer:08x}",
                }
            )

            off0 = len(vd0)
            spec = WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(fmt)]
            off1 = len(vd1)
            surfaces.append(
                {
                    "index": fmt,
                    "vertexDataOffset0": off0,
                    "vertexDataOffset1": off1,
                    "vertexCount": vertex_count,
                    "materialPointerRaw": f"0x{pointer:08x}",
                    "lightmapIndex": fmt % 2,
                }
            )

            for vi in range(vertex_count):
                row = bytearray(36)
                struct.pack_into("<3f", row, 0, float(fmt), float(vi), float(fmt + vi))
                struct.pack_into("<f", row, 12, -1.0 if vi & 1 else 1.0)
                row[16:20] = bytes((255, vi * 20, fmt * 20, 255))
                struct.pack_into("<2e", row, 20, vi / 4.0, fmt / 8.0)
                struct.pack_into("<I", row, 24, 0x12340000 + fmt * 16 + vi)
                struct.pack_into("<I", row, 28, 0x56780000 + fmt * 16 + vi)
                struct.pack_into("<HH", row, 32, vi * 1000, fmt * 1000)
                vd0.extend(row)

                for field_index, field in enumerate(spec.vd1_fields):
                    if field.startswith("uv"):
                        vd1.extend(struct.pack("<2e", float(vi), float(field_index)))
                    else:
                        vd1.extend(
                            struct.pack(
                                "<I",
                                0xA0000000 + fmt * 0x100 + vi * 4 + field_index,
                            )
                        )

        surfaces_path = root / "surfaces.json"
        vd0_path = root / "vd0.bin"
        vd1_path = root / "vd1.bin"
        materials_path = root / "materials.json"
        catalog_path = root / "catalog.json"
        prefix_path = root / "prefix.json"

        _write_json(surfaces_path, {"surfaces": surfaces})
        vd0_path.write_bytes(vd0)
        vd1_path.write_bytes(vd1)
        _write_json(materials_path, {"materials": materials})
        _write_json(catalog_path, {"materials": catalog})
        _write_json(prefix_path, {"walkedAssets": prefix})

        report = audit(
            map_name="synthetic_all_world_formats",
            surfaces_path=surfaces_path,
            vd0_path=vd0_path,
            vd1_path=vd1_path,
            materials_path=materials_path,
            catalog_path=catalog_path,
            prefix_path=prefix_path,
            asset_pointer_array_virtual_base=base,
        )

        assert report["badGroupCount"] == 0, report["badGroups"]
        assert report["uniqueVertexGroups"] == 9
        assert report["surfaceCount"] == 9
        assert report["observedFormatGroupCounts"] == {str(i): 1 for i in range(9)}
        assert sum(int(r["vertexCount"]) for r in report["groups"]) == 36
        for row in report["groups"]:
            fmt = int(row["worldVertFormat"])
            spec = WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(fmt)]
            assert row["vd1Stride"] == spec.vd1_stride
            assert row["vd1Fields"] == list(spec.vd1_fields)
            assert len(row["samples"]) == 3
            for sample in row["samples"]:
                for field in spec.vd1_fields:
                    key = field if field.startswith("uv") else field + "Packed"
                    assert key in sample

        print("PASS t6_world_vertex_audit_v2 synthetic all-formats regression")
        print(json.dumps(report["observedFormatGroupCounts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
