#!/usr/bin/env python3
"""Predict T6 layered-material world vertex format from source-closed engine rules.

Inherited Treyarch Material_RegisterLayeredTechniqueSet logic selects the base
world vertex format from layer count, then adds one format step for each normal
map beyond the first:

    2 layers -> TEX_2_NRM_1 (1)
    3 layers -> TEX_3_NRM_1 (3)
    4 layers -> TEX_4_NRM_1 (6)

    if normalMapCount > 1:
        worldVertFormat += normalMapCount - 1

The generated-name `n` marker is independently source-closed as the expected
Material_HasNormalMap state, so a T6 ``*...(...)`` identity is sufficient to
predict the corresponding worldVertFormat without guessing shader semantics.
"""
from __future__ import annotations

import argparse
import json

from t6_layered_material_name_v1 import parse_layered_material_name
from t6_zone_core import MaterialWorldVertexFormat, WORLD_VERTEX_FORMATS


class LayeredWorldFormatError(RuntimeError):
    pass


BASE_FORMAT_BY_LAYER_COUNT = {
    2: MaterialWorldVertexFormat.TEX_2_NRM_1,
    3: MaterialWorldVertexFormat.TEX_3_NRM_1,
    4: MaterialWorldVertexFormat.TEX_4_NRM_1,
}


def format_for_counts(layer_count: int, normal_map_count: int) -> MaterialWorldVertexFormat:
    if layer_count not in BASE_FORMAT_BY_LAYER_COUNT:
        raise LayeredWorldFormatError(
            f"layered world format requires 2..4 layers, got {layer_count}"
        )
    if normal_map_count < 0 or normal_map_count > layer_count:
        raise LayeredWorldFormatError(
            f"normalMapCount {normal_map_count} outside 0..{layer_count}"
        )
    base = int(BASE_FORMAT_BY_LAYER_COUNT[layer_count])
    value = base + max(0, normal_map_count - 1)
    try:
        result = MaterialWorldVertexFormat(value)
    except ValueError as exc:
        raise LayeredWorldFormatError(
            f"layerCount={layer_count}, normalMapCount={normal_map_count} produces invalid format {value}"
        ) from exc
    spec = WORLD_VERTEX_FORMATS[result]
    expected_normals = max(1, normal_map_count)
    if spec.uv_count != layer_count or spec.normal_count != expected_normals:
        raise LayeredWorldFormatError(
            f"format-table mismatch: {result.name} has uv={spec.uv_count}/nrm={spec.normal_count}, "
            f"expected uv={layer_count}/nrm={expected_normals}"
        )
    return result


def predict_from_name(name: str) -> dict:
    parsed = parse_layered_material_name(name)
    layer_count = int(parsed["layerCount"])
    normal_count = int(parsed["expectedNormalMapLayerCount"])
    fmt = format_for_counts(layer_count, normal_count)
    spec = WORLD_VERTEX_FORMATS[fmt]
    return {
        "format": "t6-layered-world-format-proof-v1",
        "material": name,
        "layerCount": layer_count,
        "normalMapCount": normal_count,
        "worldVertFormat": int(fmt),
        "formatName": fmt.name,
        "uvCount": spec.uv_count,
        "normalCount": spec.normal_count,
        "vd1Stride": spec.vd1_stride,
        "vd1Fields": list(spec.vd1_fields),
        "layers": parsed["layers"],
        "sourceRule": (
            "base format selected by layer count; add normalMapCount-1 when normalMapCount>1"
        ),
        "proofBoundary": (
            "format selection is source-closed; formats still require retail vd0/vd1 byte fixtures "
            "before being marked retail-byte-proven"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_name")
    args = parser.parse_args()
    print(json.dumps(predict_from_name(args.material_name), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
