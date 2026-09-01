#!/usr/bin/env python3
"""Export normalized T6 GfxWorld geometry to self-contained glTF 2.0 / GLB.

Input must be `t6-world-mesh-normalized-v1`, produced by
`t6_world_mesh_normalize_v1.py` after a zero-error world-vertex byte audit.

The exporter keeps each T6 world vertex group once and emits one glTF mesh per
shared group, with one primitive per original GfxSurface. Native T6 local
uint16 surface indices therefore remain local instead of forcing vertex
replication per surface.

Coordinate conversion:
  T6 Z-up inches -> glTF Y-up meters
  (x, y, z) -> (x, z, -y) * 0.0254

Native UV0..UV3 are assigned to consecutive TEXCOORD sets. glTF requires
indexed TEXCOORD semantics to start at zero and remain consecutive, so the T6
lightmap UV is emitted as TEXCOORD_<uvCount> for each vertex group.

Decoded normals/tangents become standard NORMAL/TANGENT attributes. Original
packed normal/tangent words, raw lightmap UV words, and unresolved T6 normal
transform words are also preserved as application-specific `_T6_*` attributes.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import math
import struct
from pathlib import Path

T6_UNIT_TO_METERS = 0.0254
ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963


class ExportError(RuntimeError):
    pass


def _finite_rows(rows: list[list[float]], width: int, name: str) -> None:
    if any(len(row) != width for row in rows):
        raise ExportError(f"{name}: malformed row width")
    values = [float(value) for row in rows for value in row]
    if not all(math.isfinite(value) for value in values):
        raise ExportError(f"{name}: nonfinite value")


def _axis_position(value: list[float]) -> list[float]:
    return [
        float(value[0]) * T6_UNIT_TO_METERS,
        float(value[2]) * T6_UNIT_TO_METERS,
        -float(value[1]) * T6_UNIT_TO_METERS,
    ]


def _axis_direction(value: list[float]) -> list[float]:
    out = [float(value[0]), float(value[2]), -float(value[1])]
    length = math.sqrt(sum(component * component for component in out))
    if not math.isfinite(length) or length <= 1.0e-12:
        raise ExportError(f"zero/nonfinite direction {value}")
    return [component / length for component in out]


def _packed_u32_bytes(values: list[int]) -> list[list[int]]:
    rows: list[list[int]] = []
    for source in values:
        value = int(source) & 0xFFFFFFFF
        rows.append(
            [
                value & 0xFF,
                (value >> 8) & 0xFF,
                (value >> 16) & 0xFF,
                (value >> 24) & 0xFF,
            ]
        )
    return rows


class Builder:
    def __init__(self) -> None:
        self.raw = bytearray()
        self.views: list[dict] = []
        self.accessors: list[dict] = []

    def _align4(self) -> None:
        while len(self.raw) % 4:
            self.raw.append(0)

    def add(
        self,
        payload: bytes,
        component_type: int,
        count: int,
        accessor_type: str,
        name: str,
        *,
        target: int | None = None,
        normalized: bool | None = None,
        min_value: list | None = None,
        max_value: list | None = None,
    ) -> int:
        self._align4()
        offset = len(self.raw)
        self.raw.extend(payload)

        view_index = len(self.views)
        view = {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(payload),
            "name": name,
        }
        if target is not None:
            view["target"] = target
        self.views.append(view)

        accessor = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": count,
            "type": accessor_type,
            "name": name,
        }
        if normalized is not None:
            accessor["normalized"] = normalized
        if min_value is not None:
            accessor["min"] = min_value
        if max_value is not None:
            accessor["max"] = max_value

        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index

    def f32(
        self,
        rows: list[list[float]],
        width: int,
        accessor_type: str,
        name: str,
        *,
        target: int = ARRAY_BUFFER,
        bounds: bool = False,
    ) -> int:
        _finite_rows(rows, width, name)
        values = [float(value) for row in rows for value in row]
        payload = struct.pack("<" + "f" * len(values), *values)
        min_value = None
        max_value = None
        if bounds and rows:
            min_value = [min(float(row[i]) for row in rows) for i in range(width)]
            max_value = [max(float(row[i]) for row in rows) for i in range(width)]
        return self.add(
            payload,
            5126,
            len(rows),
            accessor_type,
            name,
            target=target,
            min_value=min_value,
            max_value=max_value,
        )

    def u8vec4(self, rows: list[list[int]], name: str, *, normalized: bool = False) -> int:
        if any(len(row) != 4 for row in rows):
            raise ExportError(f"{name}: malformed UBYTE VEC4")
        values = [int(value) for row in rows for value in row]
        if any(value < 0 or value > 255 for value in values):
            raise ExportError(f"{name}: UBYTE outside range")
        return self.add(
            bytes(values),
            5121,
            len(rows),
            "VEC4",
            name,
            target=ARRAY_BUFFER,
            normalized=normalized,
        )

    def u16vec2(self, rows: list[list[int]], name: str) -> int:
        if any(len(row) != 2 for row in rows):
            raise ExportError(f"{name}: malformed USHORT VEC2")
        values = [int(value) for row in rows for value in row]
        if any(value < 0 or value > 65535 for value in values):
            raise ExportError(f"{name}: USHORT outside range")
        return self.add(
            struct.pack("<" + "H" * len(values), *values),
            5123,
            len(rows),
            "VEC2",
            name,
            target=ARRAY_BUFFER,
            normalized=False,
        )

    def indices(self, values: list[int], name: str) -> int:
        indices = [int(value) for value in values]
        if not indices:
            raise ExportError(f"{name}: empty triangle index accessor")
        if any(value < 0 or value > 65535 for value in indices):
            raise ExportError(f"{name}: source local index outside uint16")

        lo = min(indices)
        hi = max(indices)
        # glTF forbids the maximum value of the selected index component type
        # because some graphics APIs treat it as primitive restart. If T6
        # legitimately references 0xffff, promote that accessor to uint32.
        if hi == 65535:
            payload = struct.pack("<" + "I" * len(indices), *indices)
            component_type = 5125
        else:
            payload = struct.pack("<" + "H" * len(indices), *indices)
            component_type = 5123

        return self.add(
            payload,
            component_type,
            len(indices),
            "SCALAR",
            name,
            target=ELEMENT_ARRAY_BUFFER,
            min_value=[lo],
            max_value=[hi],
        )


def _material_key(surface: dict) -> str:
    name = surface.get("material")
    if name:
        return str(name)
    material_index = surface.get("materialIndex")
    if material_index is not None:
        return f"__t6_material_{int(material_index)}"
    pointer = surface.get("materialPointerRaw")
    if pointer:
        return f"__t6_material_{pointer}"
    return "__t6_unresolved_material"


def export(world: dict) -> tuple[dict, bytes]:
    if world.get("format") != "t6-world-mesh-normalized-v1":
        raise ExportError(f"unsupported normalized world format {world.get('format')!r}")

    groups = world.get("groups", [])
    surfaces = world.get("surfaces", [])
    if not isinstance(groups, list) or not isinstance(surfaces, list):
        raise ExportError("missing groups/surfaces")
    if not groups or not surfaces:
        raise ExportError("world export requires nonempty groups and surfaces")

    builder = Builder()

    material_names: list[str] = []
    material_index: dict[str, int] = {}
    for surface in surfaces:
        key = _material_key(surface)
        if key not in material_index:
            material_index[key] = len(material_names)
            material_names.append(key)

    materials = [
        {
            "name": name,
            "pbrMetallicRoughness": {
                "metallicFactor": 0.0,
                "roughnessFactor": 1.0,
            },
            "extras": {"T6": {"sourceMaterial": name}},
        }
        for name in material_names
    ]

    by_group = {index: [] for index in range(len(groups))}
    for surface in surfaces:
        group_index = int(surface["groupIndex"])
        if group_index not in by_group:
            raise ExportError(
                f"surface {surface.get('index')} invalid groupIndex {group_index}"
            )
        by_group[group_index].append(surface)

    meshes: list[dict] = []
    nodes: list[dict] = []
    global_positions: list[list[float]] = []
    primitive_count = 0
    triangle_count = 0

    for group_index, group in enumerate(groups):
        if int(group.get("groupIndex", group_index)) != group_index:
            raise ExportError("groups must be dense/in order")

        attributes = group.get("attributes", {})
        vertex_count = int(group["vertexCount"])
        if vertex_count <= 0:
            raise ExportError(f"group {group_index}: nonpositive vertexCount {vertex_count}")

        def rows(key: str) -> list:
            values = attributes.get(key)
            if not isinstance(values, list) or len(values) != vertex_count:
                raise ExportError(f"group {group_index}: {key} count mismatch")
            return values

        positions = [_axis_position(value) for value in rows("position")]
        normals = [_axis_direction(value) for value in rows("normal")]
        tangent_xyz = [_axis_direction(value) for value in rows("tangent")]
        binormal_signs = rows("binormalSign")
        global_positions.extend(positions)

        tangents: list[list[float]] = []
        for vertex_index, (tangent, sign_source) in enumerate(
            zip(tangent_xyz, binormal_signs)
        ):
            sign = float(sign_source)
            if not math.isfinite(sign) or abs(abs(sign) - 1.0) > 1.0e-4:
                raise ExportError(
                    f"group {group_index} vertex {vertex_index}: "
                    f"invalid binormalSign {sign}"
                )
            tangents.append(tangent + [1.0 if sign >= 0.0 else -1.0])

        gltf_attributes: dict[str, int] = {
            "POSITION": builder.f32(
                positions,
                3,
                "VEC3",
                f"group{group_index}:POSITION",
                bounds=True,
            ),
            "NORMAL": builder.f32(
                normals,
                3,
                "VEC3",
                f"group{group_index}:NORMAL",
            ),
            "TANGENT": builder.f32(
                tangents,
                4,
                "VEC4",
                f"group{group_index}:TANGENT",
            ),
            "COLOR_0": builder.u8vec4(
                rows("colorRGBA8"),
                f"group{group_index}:COLOR_0",
                normalized=True,
            ),
            "TEXCOORD_0": builder.f32(
                rows("uv0"),
                2,
                "VEC2",
                f"group{group_index}:TEXCOORD_0",
            ),
        }

        for uv_index in (1, 2, 3):
            key = f"uv{uv_index}"
            if key in attributes:
                gltf_attributes[f"TEXCOORD_{uv_index}"] = builder.f32(
                    rows(key),
                    2,
                    "VEC2",
                    f"group{group_index}:TEXCOORD_{uv_index}",
                )

        uv_count = int(group.get("uvCount", 1))
        if uv_count < 1 or uv_count > 4:
            raise ExportError(f"group {group_index}: invalid T6 uvCount {uv_count}")

        expected_native_uv_keys = {f"TEXCOORD_{i}" for i in range(uv_count)}
        actual_native_uv_keys = {
            key for key in gltf_attributes if key.startswith("TEXCOORD_")
        }
        if actual_native_uv_keys != expected_native_uv_keys:
            raise ExportError(
                f"group {group_index}: native UV attributes {sorted(actual_native_uv_keys)} "
                f"do not match uvCount={uv_count}"
            )

        # Indexed attribute semantics in glTF must be consecutive. Native T6
        # UV0..UV3 therefore occupy the first sets, and lightmap UV follows.
        lightmap_texcoord = uv_count
        gltf_attributes[f"TEXCOORD_{lightmap_texcoord}"] = builder.f32(
            rows("lightmapUV"),
            2,
            "VEC2",
            f"group{group_index}:TEXCOORD_{lightmap_texcoord}_lightmap",
        )

        gltf_attributes["_T6_NORMAL_PACKED"] = builder.u8vec4(
            _packed_u32_bytes(rows("normalPacked")),
            f"group{group_index}:_T6_NORMAL_PACKED",
        )
        gltf_attributes["_T6_TANGENT_PACKED"] = builder.u8vec4(
            _packed_u32_bytes(rows("tangentPacked")),
            f"group{group_index}:_T6_TANGENT_PACKED",
        )
        gltf_attributes["_T6_LIGHTMAP_UV_RAW"] = builder.u16vec2(
            rows("lightmapUVRaw"),
            f"group{group_index}:_T6_LIGHTMAP_UV_RAW",
        )

        for normal_transform_index in (0, 1):
            key = f"normalTransform{normal_transform_index}Packed"
            if key in attributes:
                gltf_attributes[
                    f"_T6_NORMAL_TRANSFORM_{normal_transform_index}"
                ] = builder.u8vec4(
                    _packed_u32_bytes(rows(key)),
                    f"group{group_index}:_T6_NORMAL_TRANSFORM_{normal_transform_index}",
                )

        primitives: list[dict] = []
        for surface in by_group[group_index]:
            indices = [int(value) for value in surface.get("indices", [])]
            surface_triangles = int(surface["triCount"])
            if surface_triangles <= 0:
                raise ExportError(
                    f"surface {surface.get('index')}: "
                    f"nonpositive triCount {surface_triangles}"
                )
            if len(indices) != surface_triangles * 3:
                raise ExportError(
                    f"surface {surface.get('index')}: tri/index mismatch"
                )
            if indices and max(indices) >= vertex_count:
                raise ExportError(
                    f"surface {surface.get('index')}: local index outside group"
                )

            index_accessor = builder.indices(
                indices,
                f"surface{int(surface['index'])}:INDICES",
            )
            t6_surface = {
                key: surface.get(key)
                for key in (
                    "index",
                    "groupIndex",
                    "baseIndex",
                    "triCount",
                    "firstVertex",
                    "storedVertexCount",
                    "material",
                    "materialIndex",
                    "materialPointerRaw",
                    "lightmapIndex",
                    "reflectionProbeIndex",
                    "primaryLightIndex",
                    "flags",
                    "bounds",
                )
            }
            primitives.append(
                {
                    "attributes": dict(gltf_attributes),
                    "indices": index_accessor,
                    "material": material_index[_material_key(surface)],
                    "mode": 4,
                    "extras": {"T6": t6_surface},
                }
            )
            primitive_count += 1
            triangle_count += surface_triangles

        texcoord_mapping = {
            f"TEXCOORD_{i}": f"uv{i}" for i in range(uv_count)
        }
        texcoord_mapping[f"TEXCOORD_{lightmap_texcoord}"] = "lightmapUV"

        mesh = {
            "name": f"world_group_{group_index:04d}_{group.get('formatName', 'FMT')}",
            "primitives": primitives,
            "extras": {
                "T6": {
                    "groupIndex": group_index,
                    "firstVertex": int(group["firstVertex"]),
                    "vd0Offset": int(group["vd0Offset"]),
                    "vd1Offset": int(group["vd1Offset"]),
                    "vertexCount": vertex_count,
                    "worldVertFormat": int(group["worldVertFormat"]),
                    "formatName": group.get("formatName"),
                    "uvCount": group.get("uvCount"),
                    "normalCount": group.get("normalCount"),
                    "vd1Stride": group.get("vd1Stride"),
                    "vd1Fields": group.get("vd1Fields"),
                    "texCoordMapping": texcoord_mapping,
                    "lightmapTexCoord": lightmap_texcoord,
                }
            },
        }
        mesh_index = len(meshes)
        meshes.append(mesh)
        nodes.append({"name": mesh["name"], "mesh": mesh_index})

    if not global_positions:
        raise ExportError("world contains no vertices")

    global_min = [min(row[i] for row in global_positions) for i in range(3)]
    global_max = [max(row[i] for row in global_positions) for i in range(3)]
    export_stats = {
        "groupCount": len(groups),
        "primitiveCount": primitive_count,
        "materialCount": len(materials),
        "vertexCount": sum(int(group["vertexCount"]) for group in groups),
        "triangleCount": triangle_count,
        "boundsMeters": {"min": global_min, "max": global_max},
    }

    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "bo2-t6-assets t6_world_gltf_export_v1.py",
        },
        "scene": 0,
        "scenes": [
            {
                "name": str(world.get("map") or "T6 World"),
                "nodes": list(range(len(nodes))),
            }
        ],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "bufferViews": builder.views,
        "accessors": builder.accessors,
        "buffers": [{"byteLength": len(builder.raw)}],
        "extras": {
            "T6": {
                "sourceFormat": world.get("format"),
                "map": world.get("map"),
                "unitScaleMetersPerT6Unit": T6_UNIT_TO_METERS,
                "axisConversion": "(x,y,z)->(x,z,-y)",
                "windingPolicy": "unchanged; axis transform determinant is +1",
                "normalTangentPolicy": (
                    "decode T6 third-based PackedUnitVec, rotate axes, renormalize"
                ),
                "tangentHandedness": "T6 binormalSign -> glTF TANGENT.w",
                "lightmapTexCoordPolicy": (
                    "TEXCOORD_uvCount (consecutive after native T6 UV sets)"
                ),
                "normalTransformPolicy": world.get("normalTransformPolicy"),
                "sourceStats": copy.deepcopy(world.get("stats", {})),
                "exportStats": export_stats,
            }
        },
    }
    validate(gltf, bytes(builder.raw))
    return gltf, bytes(builder.raw)


def _component_size(component_type: int) -> int:
    return {
        5120: 1,
        5121: 1,
        5122: 2,
        5123: 2,
        5125: 4,
        5126: 4,
    }[component_type]


def _type_width(accessor_type: str) -> int:
    return {
        "SCALAR": 1,
        "VEC2": 2,
        "VEC3": 3,
        "VEC4": 4,
        "MAT2": 4,
        "MAT3": 9,
        "MAT4": 16,
    }[accessor_type]


def validate(gltf: dict, raw: bytes) -> bool:
    if gltf.get("asset", {}).get("version") != "2.0":
        raise ExportError("not glTF 2.0")
    if gltf.get("buffers") != [{"byteLength": len(raw)}]:
        raise ExportError("buffer length mismatch")

    views = gltf.get("bufferViews", [])
    accessors = gltf.get("accessors", [])
    for index, view in enumerate(views):
        offset = int(view.get("byteOffset", 0))
        length = int(view["byteLength"])
        if offset < 0 or length < 0 or offset + length > len(raw):
            raise ExportError(f"bufferView {index} outside buffer")
        if offset % 4:
            raise ExportError(f"bufferView {index} is not 4-byte aligned")

    for index, accessor in enumerate(accessors):
        view_index = int(accessor["bufferView"])
        if view_index < 0 or view_index >= len(views):
            raise ExportError(f"accessor {index} bad bufferView")
        needed = (
            int(accessor["count"])
            * _component_size(int(accessor["componentType"]))
            * _type_width(accessor["type"])
        )
        if needed > int(views[view_index]["byteLength"]):
            raise ExportError(f"accessor {index} exceeds bufferView")

    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            attributes = primitive.get("attributes", {})
            counts = {
                int(accessors[accessor_index]["count"])
                for accessor_index in attributes.values()
            }
            if len(counts) != 1:
                raise ExportError(f"primitive attribute counts differ {counts}")

            texcoords = sorted(
                int(key.split("_", 1)[1])
                for key in attributes
                if key.startswith("TEXCOORD_")
            )
            if texcoords != list(range(len(texcoords))):
                raise ExportError(f"nonconsecutive TEXCOORD sets {texcoords}")

            vertex_count = next(iter(counts))
            index_accessor = accessors[int(primitive["indices"])]
            component_type = int(index_accessor["componentType"])
            if index_accessor["type"] != "SCALAR" or component_type not in (
                5121,
                5123,
                5125,
            ):
                raise ExportError("bad index accessor")
            if int(index_accessor["count"]) <= 0 or int(index_accessor["count"]) % 3:
                raise ExportError("triangle indices not positive multiple of 3")

            index_max = int(index_accessor.get("max", [0])[0])
            if index_max >= vertex_count:
                raise ExportError("index accessor max outside vertices")
            component_max = {
                5121: 255,
                5123: 65535,
                5125: 4294967295,
            }[component_type]
            if index_max == component_max:
                raise ExportError("index accessor uses reserved component maximum")

    return True


def gltf_bytes(gltf: dict, raw: bytes) -> bytes:
    document = copy.deepcopy(gltf)
    document["buffers"][0]["uri"] = (
        "data:application/octet-stream;base64," + base64.b64encode(raw).decode("ascii")
    )
    return (
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def glb_bytes(gltf: dict, raw: bytes) -> bytes:
    document = copy.deepcopy(gltf)
    document["buffers"][0].pop("uri", None)
    json_chunk = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    json_chunk += b" " * ((-len(json_chunk)) % 4)
    bin_chunk = bytes(raw) + b"\0" * ((-len(raw)) % 4)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    return (
        b"glTF"
        + struct.pack("<II", 2, total_length)
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
        + struct.pack("<II", len(bin_chunk), 0x004E4942)
        + bin_chunk
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("world_json", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    world = json.loads(args.world_json.read_text(encoding="utf-8"))
    gltf, raw = export(world)
    suffix = args.output.suffix.lower()
    if suffix == ".gltf":
        payload = gltf_bytes(gltf, raw)
    elif suffix == ".glb":
        payload = glb_bytes(gltf, raw)
    else:
        raise SystemExit("output must end in .gltf or .glb")

    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "out": str(args.output),
                "bytes": len(payload),
                "bufferBytes": len(raw),
                **gltf["extras"]["T6"]["exportStats"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
