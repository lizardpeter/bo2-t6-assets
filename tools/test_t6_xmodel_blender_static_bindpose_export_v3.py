#!/usr/bin/env python3
from __future__ import annotations

import math
import struct
import unittest

import t6_xmodel_blender_static_bindpose_export_v2 as v2
import t6_xmodel_blender_static_bindpose_export_v3 as v3
from t6_glb_parse_v1 import parse_glb


def fixture():
    verts = [
        {
            "position": [0.0, 0.0, 0.0],
            "normal": [0.0, 0.0, 1.0],
            "tangentXYZ": [1.0, 0.0, 0.0],
            "binormalSign": 1.0,
            "texcoord0": [0.0, 0.0],
            "colorRGBA": [1.0, 0.5, 0.25, 1.0],
        },
        {
            "position": [1.0, 0.0, 0.0],
            "normal": [0.0, 0.0, 1.0],
            "tangentXYZ": [0.0, 1.0, 0.0],
            "binormalSign": -1.0,
            "texcoord0": [1.0, 0.0],
            "colorRGBA": [1.0, 1.0, 1.0, 1.0],
        },
        {
            "position": [0.0, 1.0, 0.0],
            "normal": [0.0, 0.0, 1.0],
            "tangentXYZ": [0.0, 0.0, 1.0],
            "binormalSign": 1.0,
            "texcoord0": [0.0, 1.0],
            "colorRGBA": [1.0, 1.0, 1.0, 1.0],
        },
    ]
    return {
        "format": "t6-xmodel-mesh-normalized-v1",
        "identity": {"name": "test_tangent"},
        "xmodel": {
            "lods": [{"index": 0, "surfIndex": 0, "numSurfs": 1}],
        },
        "surfaces": [{
            "index": 0,
            "baseVertIndex": 0,
            "vertCount": 3,
            "triCount": 1,
            "vertices": verts,
            "triangles": [[0, 1, 2]],
        }],
    }


def accessor_values(doc, raw, index):
    a = doc["accessors"][index]
    view = doc["bufferViews"][a["bufferView"]]
    count = int(a["count"])
    typ = a["type"]
    width = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[typ]
    stride = int(view.get("byteStride", width * 4))
    start = int(view.get("byteOffset", 0)) + int(a.get("byteOffset", 0))
    rows = []
    for i in range(count):
        rows.append(struct.unpack_from("<" + "f" * width, raw, start + i * stride))
    return rows


class XModelBlenderV3Tests(unittest.TestCase):
    def test_v3_preserves_v2_prefix_and_exact_basis(self):
        mesh = fixture()
        v2_doc, v2_raw = parse_glb(v2.export(mesh, 0))
        v3_doc, v3_raw = parse_glb(v3.export(mesh, 0))
        self.assertEqual(v3_raw[:len(v2_raw)], v2_raw)
        self.assertGreater(len(v3_raw), len(v2_raw))

        a2 = v2_doc["meshes"][0]["primitives"][0]["attributes"]
        a3 = v3_doc["meshes"][0]["primitives"][0]["attributes"]
        self.assertNotIn("COLOR_0", a3)
        self.assertEqual(a3["_T6_COLOR_RGBA"], a2["_T6_COLOR_RGBA"])
        self.assertIn("TANGENT", a3)
        self.assertEqual(a3["_T6_XMODEL_NORMAL"], a3["NORMAL"])

        tangent = accessor_values(v3_doc, v3_raw, a3["TANGENT"])
        self.assertEqual(tangent[0], (1.0, 0.0, -0.0, 1.0))
        self.assertEqual(tangent[1], (0.0, 0.0, -1.0, -1.0))
        self.assertEqual(tangent[2], (0.0, 1.0, -0.0, 1.0))
        tangent_xyz = accessor_values(v3_doc, v3_raw, a3["_T6_XMODEL_TANGENT"])
        handedness = accessor_values(v3_doc, v3_raw, a3["_T6_TANGENT_HANDEDNESS"])
        for i in range(3):
            self.assertEqual(tangent_xyz[i], tangent[i][:3])
            self.assertEqual(handedness[i][0], tangent[i][3])

        contract = v3_doc["extras"]["T6"]["xmodelNormalBasisAttributes"]
        self.assertEqual(contract["format"], v3.FORMAT)
        self.assertTrue(contract["baseV2BinPrefixByteIdentical"])
        self.assertEqual(contract["baseV2BinBytes"], len(v2_raw))

    def test_bad_handedness_fails_closed(self):
        mesh = fixture()
        mesh["surfaces"][0]["vertices"][0]["binormalSign"] = 0.0
        with self.assertRaises(v3.XModelBlenderStaticV3Error):
            v3.export(mesh, 0)


if __name__ == "__main__":
    unittest.main()
