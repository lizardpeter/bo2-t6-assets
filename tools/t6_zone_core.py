from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct
from typing import Iterable

POINTER_BITS = 32
OFFSET_BLOCK_BITS = 3
OFFSET_BITS = POINTER_BITS - OFFSET_BLOCK_BITS
OFFSET_MASK = (1 << OFFSET_BITS) - 1
BLOCK_SHIFT = OFFSET_BITS
FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE

class XFileBlock(IntEnum):
    TEMP = 0
    RUNTIME_VIRTUAL = 1
    RUNTIME_PHYSICAL = 2
    DELAY_VIRTUAL = 3
    DELAY_PHYSICAL = 4
    VIRTUAL = 5
    PHYSICAL = 6
    STREAMER_RESERVE = 7

BLOCK_NAMES = {
    XFileBlock.TEMP: "temp",
    XFileBlock.RUNTIME_VIRTUAL: "runtime_virtual",
    XFileBlock.RUNTIME_PHYSICAL: "runtime_physical",
    XFileBlock.DELAY_VIRTUAL: "delay_virtual",
    XFileBlock.DELAY_PHYSICAL: "delay_physical",
    XFileBlock.VIRTUAL: "virtual",
    XFileBlock.PHYSICAL: "physical",
    XFileBlock.STREAMER_RESERVE: "streamer_reserve",
}

@dataclass(frozen=True)
class ZonePointer:
    raw: int
    kind: str
    block: int | None = None
    offset: int | None = None

    @property
    def block_name(self) -> str | None:
        if self.block is None:
            return None
        try:
            return BLOCK_NAMES[XFileBlock(self.block)]
        except Exception:
            return None

    def to_dict(self) -> dict:
        return {
            "raw": self.raw,
            "rawHex": f"0x{self.raw:08x}",
            "kind": self.kind,
            "block": self.block,
            "blockName": self.block_name,
            "offset": self.offset,
        }


def decode_zone_pointer32(raw: int) -> ZonePointer:
    raw &= 0xFFFFFFFF
    if raw == 0:
        return ZonePointer(raw, "null")
    if raw == FOLLOWING:
        return ZonePointer(raw, "following")
    if raw == INSERT:
        return ZonePointer(raw, "insert")
    shifted = (raw - 1) & 0xFFFFFFFF
    return ZonePointer(raw, "offset", (shifted >> BLOCK_SHIFT) & 0x7, shifted & OFFSET_MASK)


def encode_zone_offset32(block: int, offset: int) -> int:
    if not (0 <= block <= 7):
        raise ValueError(block)
    if not (0 <= offset <= OFFSET_MASK):
        raise ValueError(offset)
    return (((block & 7) << BLOCK_SHIFT) | (offset & OFFSET_MASK)) + 1


def align_up(value: int, alignment: int) -> int:
    if alignment <= 1:
        return value
    return (value + alignment - 1) // alignment * alignment


class MaterialWorldVertexFormat(IntEnum):
    TEX_1_NRM_1 = 0
    TEX_2_NRM_1 = 1
    TEX_2_NRM_2 = 2
    TEX_3_NRM_1 = 3
    TEX_3_NRM_2 = 4
    TEX_3_NRM_3 = 5
    TEX_4_NRM_1 = 6
    TEX_4_NRM_2 = 7
    TEX_4_NRM_3 = 8

@dataclass(frozen=True)
class WorldVertexFormatSpec:
    uv_count: int
    normal_count: int
    vd1_stride: int
    vd1_fields: tuple[str, ...]

# T6 vd0 always contains the first UV and first normal/tangent basis.
# vd1 appends 4-byte half2 UVs, then 4-byte packed normal-transform words.
WORLD_VERTEX_FORMATS: dict[MaterialWorldVertexFormat, WorldVertexFormatSpec] = {
    MaterialWorldVertexFormat.TEX_1_NRM_1: WorldVertexFormatSpec(1, 1, 0, ()),
    MaterialWorldVertexFormat.TEX_2_NRM_1: WorldVertexFormatSpec(2, 1, 4, ("uv1",)),
    MaterialWorldVertexFormat.TEX_2_NRM_2: WorldVertexFormatSpec(2, 2, 8, ("uv1", "normalTransform0")),
    MaterialWorldVertexFormat.TEX_3_NRM_1: WorldVertexFormatSpec(3, 1, 8, ("uv1", "uv2")),
    MaterialWorldVertexFormat.TEX_3_NRM_2: WorldVertexFormatSpec(3, 2, 12, ("uv1", "uv2", "normalTransform0")),
    MaterialWorldVertexFormat.TEX_3_NRM_3: WorldVertexFormatSpec(3, 3, 16, ("uv1", "uv2", "normalTransform0", "normalTransform1")),
    MaterialWorldVertexFormat.TEX_4_NRM_1: WorldVertexFormatSpec(4, 1, 12, ("uv1", "uv2", "uv3")),
    MaterialWorldVertexFormat.TEX_4_NRM_2: WorldVertexFormatSpec(4, 2, 16, ("uv1", "uv2", "uv3", "normalTransform0")),
    MaterialWorldVertexFormat.TEX_4_NRM_3: WorldVertexFormatSpec(4, 3, 20, ("uv1", "uv2", "uv3", "normalTransform0", "normalTransform1")),
}

GFX_PACKED_VERTEX_SIZE = 32
GFX_WORLD_VD0_STRIDE = 36


def unpack_half2(raw4: bytes) -> tuple[float, float]:
    if len(raw4) != 4:
        raise ValueError("half2 must be exactly 4 bytes")
    a, b = struct.unpack("<2e", raw4)
    return float(a), float(b)


def unpack_unorm16x2(raw4: bytes) -> tuple[float, float]:
    if len(raw4) != 4:
        raise ValueError("unorm16x2 must be exactly 4 bytes")
    a, b = struct.unpack("<HH", raw4)
    return a / 65535.0, b / 65535.0


def decode_world_vd0_vertex(raw36: bytes) -> dict:
    if len(raw36) != GFX_WORLD_VD0_STRIDE:
        raise ValueError("T6 world vd0 vertex must be exactly 36 bytes")
    xyz = struct.unpack_from("<3f", raw36, 0)
    binormal_sign = struct.unpack_from("<f", raw36, 12)[0]
    color = tuple(raw36[16:20])
    uv0 = unpack_half2(raw36[20:24])
    normal = struct.unpack_from("<I", raw36, 24)[0]
    tangent = struct.unpack_from("<I", raw36, 28)[0]
    lightmap_uv = unpack_unorm16x2(raw36[32:36])
    return {
        "position": list(xyz),
        "binormalSign": binormal_sign,
        "colorRGBA8": list(color),
        "uv0": list(uv0),
        "normalPacked": normal,
        "tangentPacked": tangent,
        "lightmapUV": list(lightmap_uv),
        "lightmapUVRaw": list(struct.unpack_from("<HH", raw36, 32)),
    }


def decode_world_vd1_vertex(raw: bytes, fmt: int | MaterialWorldVertexFormat) -> dict:
    fmt = MaterialWorldVertexFormat(int(fmt))
    spec = WORLD_VERTEX_FORMATS[fmt]
    if len(raw) != spec.vd1_stride:
        raise ValueError(f"format {int(fmt)} expects {spec.vd1_stride} vd1 bytes, got {len(raw)}")
    out: dict[str, object] = {}
    for i, field in enumerate(spec.vd1_fields):
        chunk = raw[i * 4 : i * 4 + 4]
        if field.startswith("uv"):
            out[field] = list(unpack_half2(chunk))
        else:
            out[field + "Packed"] = struct.unpack("<I", chunk)[0]
    return out


def expected_vd1_stride(fmt: int | MaterialWorldVertexFormat) -> int:
    return WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(int(fmt))].vd1_stride
