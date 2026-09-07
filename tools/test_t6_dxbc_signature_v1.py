#!/usr/bin/env python3
from __future__ import annotations

import struct
import unittest

import t6_dxbc_signature_v1 as sig


def signature_payload(rows):
    table = bytearray()
    strings = bytearray()
    base = 8 + 24 * len(rows)
    offsets = {}
    for row in rows:
        name = row[0]
        if name not in offsets:
            offsets[name] = base + len(strings)
            strings.extend(name.encode("ascii") + b"\0")
        semantic_index, system_value, component_type, register, mask, rw = row[1:]
        table.extend(
            struct.pack(
                "<6I",
                offsets[name],
                semantic_index,
                system_value,
                component_type,
                register,
                mask | (rw << 8),
            )
        )
    return struct.pack("<II", len(rows), 8) + table + strings


class DxbcSignatureTests(unittest.TestCase):
    def test_sm4_signature_decodes_component_masks(self):
        payload = signature_payload([
            ("POSITION", 0, 0, 3, 0, 0xF, 0xF),
            ("TEXCOORD", 0, 0, 3, 2, 0x3, 0x3),
            ("NORMAL", 0, 0, 3, 3, 0x7, 0x7),
        ])
        rows = sig.parse_signature_payload(payload)
        self.assertEqual([r["semanticKey"] for r in rows], ["POSITION0", "TEXCOORD0", "NORMAL0"])
        self.assertEqual(rows[1]["components"], "xy")
        self.assertEqual(rows[2]["components"], "xyz")
        self.assertEqual(rows[0]["componentType"], "float32")

    def test_exact_car01_opaque_route_shape(self):
        payload = signature_payload([
            ("POSITION", 0, 0, 3, 0, 0xF, 0xF),
            ("COLOR", 0, 0, 3, 1, 0xF, 0xF),
            ("TEXCOORD", 0, 0, 3, 2, 0x3, 0x3),
            ("NORMAL", 0, 0, 3, 3, 0x7, 0x7),
            ("TEXCOORD", 2, 0, 3, 4, 0x7, 0x7),
        ])
        routes = [
            {"destination": "position", "source": "position"},
            {"destination": "color[0]", "source": "color"},
            {"destination": "texcoord[0]", "source": "texcoord[0]"},
            {"destination": "normal", "source": "normal"},
            {"destination": "texcoord[2]", "source": "tangent"},
        ]
        rows = sig.bind_vertex_routes(sig.parse_signature_payload(payload), routes)
        self.assertEqual([r["t6Source"] for r in rows], [
            "position", "color", "texcoord[0]", "normal", "tangent"
        ])
        self.assertEqual(rows[4]["semanticKey"], "TEXCOORD2")
        self.assertEqual(rows[4]["t6Source"], "tangent")

    def test_route_join_fails_closed(self):
        payload = signature_payload([
            ("TEXCOORD", 2, 0, 3, 4, 0x7, 0x7),
        ])
        with self.assertRaises(sig.DxbcSignatureError):
            sig.bind_vertex_routes(sig.parse_signature_payload(payload), [])


if __name__ == "__main__":
    unittest.main()
