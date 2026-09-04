#!/usr/bin/env python3
"""Retail-byte proof for Nuketown block-5 image alias 514620 -> $identitynormalmap.

This verifier is intentionally fail-closed. It replays the T6 PC32 loader's
source cursor and XFILE_BLOCK_VIRTUAL destination cursor from the XAssetList
front matter through the first TechniqueSet and nt_2020_air_vent XModel. The
claim is promoted only if the derived MaterialTextureDef[1].image field is
exactly block 5 / 514620 and the corresponding inline GfxImage is named
$identitynormalmap.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
BLOCK_SHIFT = 29
OFFSET_MASK = (1 << BLOCK_SHIFT) - 1
EXPECTED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
EXPECTED_SCRIPT_STRINGS = 546
EXPECTED_ASSETS = 840
EXPECTED_TARGET_ASSET_INDEX = 836
EXPECTED_TARGET_BLOCK = 5
EXPECTED_TARGET_OFFSET = 514620
EXPECTED_MATERIAL = "mc/paris_plaster_interiorwall_white"
EXPECTED_IMAGE = "$identitynormalmap"


def align_up(value: int, alignment: int) -> int:
    if alignment <= 0 or alignment & (alignment - 1):
        raise ValueError(f"alignment must be a power of two: {alignment}")
    return (value + alignment - 1) & ~(alignment - 1)


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def i16(data: bytes, off: int) -> int:
    return struct.unpack_from("<h", data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def cstring(data: bytes, off: int) -> tuple[str, int]:
    end = data.find(b"\0", off)
    if end < 0:
        raise ValueError(f"unterminated string at {off}")
    return data[off:end].decode("latin1"), end + 1


def decode_packed(value: int) -> tuple[int, int]:
    if value in (0, FOLLOWING, INSERT):
        raise ValueError(f"not a packed pointer: 0x{value:08X}")
    encoded = (value - 1) & 0xFFFFFFFF
    return encoded >> BLOCK_SHIFT, encoded & OFFSET_MASK


@dataclass
class Cursor:
    data: bytes
    source: int
    virtual: int
    padding: list[dict] = field(default_factory=list)

    def source_only(self, size: int, label: str) -> int:
        start = self.source
        self.source += size
        if self.source > len(self.data):
            raise ValueError(f"{label}: source overrun")
        return start

    def alloc(self, size: int, alignment: int, label: str) -> tuple[int, int]:
        before = self.virtual
        self.virtual = align_up(self.virtual, alignment)
        if self.virtual != before:
            self.padding.append({
                "label": label,
                "before": before,
                "after": self.virtual,
                "bytes": self.virtual - before,
            })
        source_start = self.source
        virtual_start = self.virtual
        self.source += size
        self.virtual += size
        if self.source > len(self.data):
            raise ValueError(f"{label}: source overrun")
        return source_start, virtual_start

    def string(self, label: str) -> str:
        text, end = cstring(self.data, self.source)
        self.alloc(end - self.source, 1, label)
        return text


def parse_front(data: bytes) -> dict:
    if len(data) < 64:
        raise ValueError("stream too short")
    declared_size, external_size = struct.unpack_from("<II", data, 0)
    blocks = list(struct.unpack_from("<8I", data, 8))
    sc, sp, dc, dp, ac, ap = struct.unpack_from("<6I", data, 40)
    if sc != EXPECTED_SCRIPT_STRINGS or ac != EXPECTED_ASSETS:
        raise ValueError(f"unexpected front counts: scriptStrings={sc}, assets={ac}")
    if sp != FOLLOWING or ap != FOLLOWING or dc != 0 or dp != 0:
        raise ValueError("unexpected XAssetList pointer topology")

    source = 64
    virtual = 0
    virtual = align_up(virtual, 4)
    ptrs = struct.unpack_from(f"<{sc}I", data, source)
    source += sc * 4
    virtual += sc * 4
    inline_strings = 0
    for ptr in ptrs:
        if ptr == FOLLOWING:
            _, end = cstring(data, source)
            n = end - source
            source = end
            virtual += n
            inline_strings += 1
        elif ptr != 0:
            decode_packed(ptr)

    asset_array_source = source
    virtual = align_up(virtual, 4)
    asset_array_virtual = virtual
    assets = []
    for i in range(ac):
        typ, ptr = struct.unpack_from("<II", data, source + 8 * i)
        assets.append((typ, ptr))
    source += ac * 8
    virtual += ac * 8

    if source != 20253 or virtual != 20192:
        raise ValueError(f"front replay drift: source={source}, virtual={virtual}")
    if [assets[i][0] for i in range(5)] != [49, 54, 42, 7, 5]:
        raise ValueError(f"unexpected first five asset types: {[assets[i][0] for i in range(5)]}")
    if any(assets[i][1] != FOLLOWING for i in range(5)):
        raise ValueError("first five XAssets are not inline definitions")

    target_type, target_ptr = assets[EXPECTED_TARGET_ASSET_INDEX]
    if target_type != 8:
        raise ValueError(f"XAsset {EXPECTED_TARGET_ASSET_INDEX} is not IMAGE: type={target_type}")
    target_block, target_offset = decode_packed(target_ptr)
    if (target_block, target_offset) != (EXPECTED_TARGET_BLOCK, EXPECTED_TARGET_OFFSET):
        raise ValueError(
            f"XAsset {EXPECTED_TARGET_ASSET_INDEX} pointer drift: "
            f"block={target_block}, offset={target_offset}"
        )

    return {
        "declaredZoneSize": declared_size,
        "declaredExternalSize": external_size,
        "blockSizes": blocks,
        "scriptStringCount": sc,
        "inlineScriptStringCount": inline_strings,
        "assetCount": ac,
        "assetArraySource": asset_array_source,
        "assetArrayVirtual": asset_array_virtual,
        "assetBodySource": source,
        "assetBodyVirtual": virtual,
        "assets": assets,
        "targetXAssetRawPointer": f"0x{target_ptr:08X}",
    }


def replay_assets_0_to_2(data: bytes, source: int, virtual: int) -> tuple[Cursor, dict]:
    r = Cursor(data, source, virtual)

    a0 = r.source_only(12, "KeyValuePairs.fixed")
    if u32(data, a0) != FOLLOWING or u32(data, a0 + 8) != FOLLOWING:
        raise ValueError("KeyValuePairs topology drift")
    kv_count = u32(data, a0 + 4)
    if kv_count != 8:
        raise ValueError(f"KeyValuePairs count drift: {kv_count}")
    if r.string("KeyValuePairs.name") != "mp_nuketown_2020":
        raise ValueError("KeyValuePairs name drift")
    kv_source, _ = r.alloc(kv_count * 12, 4, "KeyValuePairs.entries")
    for i in range(kv_count):
        value_ptr = u32(data, kv_source + i * 12 + 8)
        if value_ptr == FOLLOWING:
            r.string(f"KeyValuePairs.entries[{i}].value")
        elif value_ptr not in (0, INSERT):
            decode_packed(value_ptr)
    if r.source != 20424:
        raise ValueError(f"KeyValuePairs source boundary drift: {r.source}")

    a1 = r.source_only(8, "SkinnedVertsDef.fixed")
    if u32(data, a1) != FOLLOWING:
        raise ValueError("SkinnedVertsDef name is not inline")
    if r.string("SkinnedVertsDef.name") != "skinnedverts":
        raise ValueError("SkinnedVertsDef name drift")
    if r.source != 20445:
        raise ValueError(f"SkinnedVertsDef source boundary drift: {r.source}")

    a2 = r.source_only(20, "StringTable.fixed")
    if u32(data, a2) != FOLLOWING or u32(data, a2 + 12) != FOLLOWING or u32(data, a2 + 16) != FOLLOWING:
        raise ValueError("StringTable topology drift")
    columns = u32(data, a2 + 4)
    rows = u32(data, a2 + 8)
    cell_count = columns * rows
    if (columns, rows, cell_count) != (1, 6596, 6596):
        raise ValueError(f"StringTable dimensions drift: {columns}x{rows}")
    if r.string("StringTable.name") != "mp/configstrings/configstrings_mp_nuketown_2020.csv":
        raise ValueError("StringTable name drift")
    cells_source, _ = r.alloc(cell_count * 8, 4, "StringTable.values")
    inline_cell_strings = 0
    for i in range(cell_count):
        string_ptr = u32(data, cells_source + i * 8)
        if string_ptr == FOLLOWING:
            r.string(f"StringTable.values[{i}].string")
            inline_cell_strings += 1
        elif string_ptr not in (0, INSERT):
            decode_packed(string_ptr)
    r.alloc(cell_count * 2, 2, "StringTable.cellIndex")
    if inline_cell_strings != 1715:
        raise ValueError(f"StringTable inline string count drift: {inline_cell_strings}")
    if (r.source, r.virtual) != (125632, 125536):
        raise ValueError(f"asset0-2 replay drift: source={r.source}, virtual={r.virtual}")

    return r, {
        "endSource": r.source,
        "endVirtual": r.virtual,
        "inlineStringTableCells": inline_cell_strings,
        "destinationPaddingBytes": sum(x["bytes"] for x in r.padding),
    }


def replay_technique_set(data: bytes, source: int, virtual: int) -> tuple[Cursor, dict]:
    fixed = source
    if u32(data, fixed) != FOLLOWING:
        raise ValueError("TechniqueSet name is not inline")
    technique_ptrs = [u32(data, fixed + 8 + 4 * i) for i in range(36)]
    inline_count = sum(p == FOLLOWING for p in technique_ptrs)
    if inline_count != 28:
        raise ValueError(f"TechniqueSet inline technique count drift: {inline_count}")

    r = Cursor(data, fixed + 152, virtual)
    techset_name = r.string("TechniqueSet.name")
    if techset_name != "mc_lit_sm_r0c0s0_986ezzjq":
        raise ValueError(f"TechniqueSet name drift: {techset_name}")

    def load_shader(label: str) -> None:
        shader_source, _ = r.alloc(16, 4, label + ".fixed")
        name_ptr = u32(data, shader_source)
        program_ptr = u32(data, shader_source + 8)
        program_size = u32(data, shader_source + 12)
        if name_ptr == FOLLOWING:
            r.string(label + ".name")
        elif name_ptr not in (0, INSERT):
            decode_packed(name_ptr)
        if program_ptr == FOLLOWING:
            r.alloc(program_size, 1, label + ".program")
        elif program_ptr not in (0, INSERT):
            decode_packed(program_ptr)

    def load_vdecl(label: str) -> None:
        r.alloc(116, 4, label + ".fixed")

    def load_args(pass_source: int, count: int, label: str) -> None:
        args_ptr = u32(data, pass_source + 20)
        if not count:
            if args_ptr not in (0,):
                raise ValueError(f"{label}: zero args with non-null pointer 0x{args_ptr:08X}")
            return
        if args_ptr == FOLLOWING:
            args_source, _ = r.alloc(count * 12, 4, label + ".fixed")
            for i in range(count):
                arg = args_source + i * 12
                arg_type = u16(data, arg)
                value_ptr = u32(data, arg + 8)
                if arg_type in (1, 7) and value_ptr == FOLLOWING:
                    r.alloc(16, 4, f"{label}[{i}].literalConst")
        elif args_ptr not in (0, INSERT):
            decode_packed(args_ptr)

    technique_rows = []
    for technique_index, ptr in enumerate(technique_ptrs):
        if ptr != FOLLOWING:
            if ptr not in (0, INSERT):
                decode_packed(ptr)
            continue
        pass_count = u16(data, r.source + 6)
        if not 1 <= pass_count <= 64:
            raise ValueError(f"Technique {technique_index}: implausible passCount={pass_count}")
        tech_source, _ = r.alloc(8 + 24 * pass_count, 4, f"Technique[{technique_index}].fixed")
        name_ptr = u32(data, tech_source)
        for pass_index in range(pass_count):
            p = tech_source + 8 + 24 * pass_index
            vertex_decl = u32(data, p)
            vertex_shader = u32(data, p + 4)
            pixel_shader = u32(data, p + 8)
            arg_count = data[p + 12] + data[p + 13] + data[p + 14]
            if vertex_shader == FOLLOWING:
                load_shader(f"Technique[{technique_index}].pass[{pass_index}].vs")
            elif vertex_shader not in (0, INSERT):
                decode_packed(vertex_shader)
            if vertex_decl == FOLLOWING:
                load_vdecl(f"Technique[{technique_index}].pass[{pass_index}].vdecl")
            elif vertex_decl not in (0, INSERT):
                decode_packed(vertex_decl)
            if pixel_shader == FOLLOWING:
                load_shader(f"Technique[{technique_index}].pass[{pass_index}].ps")
            elif pixel_shader not in (0, INSERT):
                decode_packed(pixel_shader)
            load_args(p, arg_count, f"Technique[{technique_index}].pass[{pass_index}].args")
        technique_name = r.string(f"Technique[{technique_index}].name") if name_ptr == FOLLOWING else None
        technique_rows.append({"index": technique_index, "passCount": pass_count, "name": technique_name})

    if (r.source, r.virtual) != (499456, 499317):
        raise ValueError(f"TechniqueSet replay drift: source={r.source}, virtual={r.virtual}")
    return r, {
        "fixedSource": fixed,
        "name": techset_name,
        "inlineTechniqueCount": inline_count,
        "endSource": r.source,
        "endVirtual": r.virtual,
        "destinationPaddingBytes": sum(x["bytes"] for x in r.padding),
        "techniques": technique_rows,
    }


def replay_vent_to_texture_table(data: bytes, source: int, virtual: int, node_alignment: int = 16) -> tuple[Cursor, dict]:
    r = Cursor(data, source, virtual)
    xmodel = r.source_only(248, "XModel.fixed")
    if u32(data, xmodel) != FOLLOWING:
        raise ValueError("XModel name is not inline")
    num_bones = data[xmodel + 4]
    num_root_bones = data[xmodel + 5]
    num_surfs = data[xmodel + 6]
    if (num_bones, num_root_bones, num_surfs) != (1, 1, 1):
        raise ValueError(f"nt_2020_air_vent counts drift: {(num_bones, num_root_bones, num_surfs)}")
    if r.string("XModel.name") != "nt_2020_air_vent":
        raise ValueError("XModel name drift")

    if u32(data, xmodel + 8) == FOLLOWING:
        r.alloc(num_bones * 2, 2, "XModel.boneNames")
    non_root = num_bones - num_root_bones
    if u32(data, xmodel + 12) == FOLLOWING:
        r.alloc(non_root, 1, "XModel.parentList")
    if u32(data, xmodel + 16) == FOLLOWING:
        r.alloc(non_root * 8, 2, "XModel.quats")
    if u32(data, xmodel + 20) == FOLLOWING:
        r.alloc(non_root * 16, 4, "XModel.trans")
    if u32(data, xmodel + 24) == FOLLOWING:
        r.alloc(num_bones, 1, "XModel.partClassification")
    if u32(data, xmodel + 28) == FOLLOWING:
        r.alloc(num_bones * 32, 4, "XModel.baseMat")

    if u32(data, xmodel + 32) != FOLLOWING:
        raise ValueError("XModel.surfs is not inline")
    surfaces_source, _ = r.alloc(num_surfs * 80, 16, "XModel.surfs.fixed")
    for surface_index in range(num_surfs):
        surf = surfaces_source + surface_index * 80
        vert_list_count = data[surf + 1]
        flags = u16(data, surf + 2)
        vert_count = u16(data, surf + 4)
        tri_count = u16(data, surf + 6)
        if (vert_list_count, vert_count, tri_count) != (1, 416, 212):
            raise ValueError(f"XSurface counts drift: {(vert_list_count, vert_count, tri_count)}")
        tri_ptr = u32(data, surf + 12)
        blend_counts = [i16(data, surf + 16 + 2 * i) for i in range(4)]
        blend_ptr = u32(data, surf + 24)
        tension_ptr = u32(data, surf + 28)
        verts_ptr = u32(data, surf + 32)
        vert_list_ptr = u32(data, surf + 40)
        blend_count = blend_counts[0] + 3 * blend_counts[1] + 5 * blend_counts[2] + 7 * blend_counts[3]
        if blend_ptr == FOLLOWING:
            r.alloc(blend_count * 2, 2, "XSurface.vertInfo.vertsBlend")
        if tension_ptr == FOLLOWING:
            r.alloc(sum(blend_counts) * 4, 4, "XSurface.vertInfo.tensionData")
        if not (flags & 1) and verts_ptr == FOLLOWING:
            r.alloc(vert_count * 32, 16, "XSurface.verts0")
        if vert_list_ptr == FOLLOWING:
            lists_source, _ = r.alloc(vert_list_count * 12, 4, "XSurface.vertList.fixed")
            for list_index in range(vert_list_count):
                rigid = lists_source + list_index * 12
                tree_ptr = u32(data, rigid + 8)
                if tree_ptr == FOLLOWING:
                    tree_source, _ = r.alloc(40, 4, "XSurface.collisionTree.fixed")
                    node_count = u32(data, tree_source + 24)
                    nodes_ptr = u32(data, tree_source + 28)
                    leaf_count = u32(data, tree_source + 32)
                    leafs_ptr = u32(data, tree_source + 36)
                    if (node_count, leaf_count) != (14, 106):
                        raise ValueError(f"collision tree counts drift: {(node_count, leaf_count)}")
                    if nodes_ptr == FOLLOWING:
                        r.alloc(node_count * 16, node_alignment, "XSurface.collisionTree.nodes")
                    if leafs_ptr == FOLLOWING:
                        r.alloc(leaf_count * 2, 2, "XSurface.collisionTree.leafs")
        if tri_ptr == FOLLOWING:
            r.alloc(tri_count * 6, 16, "XSurface.triIndices")

    if r.source != 514908:
        raise ValueError(f"XSurface source end drift: {r.source}")
    if u32(data, xmodel + 36) != FOLLOWING:
        raise ValueError("XModel.materialHandles is not inline")
    material_handles_source, _ = r.alloc(num_surfs * 4, 4, "XModel.materialHandles")
    if u32(data, material_handles_source) != FOLLOWING:
        raise ValueError("air vent material is not an inline definition")
    if (r.source, r.virtual) != (514912, 514556 if node_alignment == 16 else 514540):
        raise ValueError(f"pre-material cursor drift: source={r.source}, virtual={r.virtual}")

    material = r.source_only(112, "Material.fixed")
    texture_count = data[material + 80]
    texture_table_ptr = u32(data, material + 96)
    if texture_count != 3 or texture_table_ptr != FOLLOWING:
        raise ValueError(f"material texture table drift: count={texture_count}, ptr=0x{texture_table_ptr:08X}")
    material_name = r.string("Material.name")
    if material_name != EXPECTED_MATERIAL:
        raise ValueError(f"material name drift: {material_name}")

    texture_source, texture_virtual = r.alloc(texture_count * 16, 4, "Material.textureTable")
    semantics = [data[texture_source + i * 16 + 7] for i in range(texture_count)]
    image_ptrs = [u32(data, texture_source + i * 16 + 12) for i in range(texture_count)]
    if semantics != [8, 5, 2]:
        raise ValueError(f"texture semantics drift: {semantics}")
    if image_ptrs != [FOLLOWING, FOLLOWING, FOLLOWING]:
        raise ValueError(f"texture image topology drift: {[hex(x) for x in image_ptrs]}")

    slot1_field = texture_virtual + 16 + 12
    return r, {
        "xmodelFixedSource": xmodel,
        "materialFixedSource": material,
        "materialName": material_name,
        "textureCount": texture_count,
        "textureTableSource": texture_source,
        "textureTableVirtual": texture_virtual,
        "textureSemantics": semantics,
        "slotImageFieldVirtualOffsets": [texture_virtual + i * 16 + 12 for i in range(texture_count)],
        "slot1ImageFieldVirtual": slot1_field,
        "destinationPaddingBytes": sum(x["bytes"] for x in r.padding),
        "padding": r.padding,
    }


def walk_inline_gfximage(data: bytes, source: int, expected_name: str) -> tuple[int, dict]:
    fixed = source
    if fixed + 80 > len(data):
        raise ValueError("truncated GfxImage")
    load_def_ptr = u32(data, fixed)
    name_ptr = u32(data, fixed + 72)
    if name_ptr != FOLLOWING:
        raise ValueError(f"GfxImage {expected_name}: name is not inline")
    source += 80
    name, source = cstring(data, source)
    if name != expected_name:
        raise ValueError(f"GfxImage name drift: expected {expected_name!r}, got {name!r}")
    resource_size = None
    if load_def_ptr in (FOLLOWING, INSERT):
        if source + 12 > len(data):
            raise ValueError("truncated GfxImageLoadDef")
        resource_size = u32(data, source + 8)
        source += 12 + resource_size
    elif load_def_ptr != 0:
        decode_packed(load_def_ptr)
    return source, {
        "fixedSource": fixed,
        "name": name,
        "loadDefPointer": f"0x{load_def_ptr:08X}",
        "resourceSize": resource_size,
        "endSource": source,
    }


def build(stream: Path) -> dict:
    data = stream.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"wrong retail stream SHA256: {digest}")

    front = parse_front(data)
    a02_cursor, a02 = replay_assets_0_to_2(data, front["assetBodySource"], front["assetBodyVirtual"])
    tech_cursor, tech = replay_technique_set(data, a02_cursor.source, a02_cursor.virtual)
    vent_cursor, vent = replay_vent_to_texture_table(data, tech_cursor.source, tech_cursor.virtual, 16)

    if vent["textureTableVirtual"] != 514592:
        raise ValueError(f"texture table virtual base drift: {vent['textureTableVirtual']}")
    if vent["slot1ImageFieldVirtual"] != EXPECTED_TARGET_OFFSET:
        raise ValueError(f"slot1 image field drift: {vent['slot1ImageFieldVirtual']}")

    image_source = vent_cursor.source
    image_source, image0 = walk_inline_gfximage(data, image_source, "~~-gplaster_interiorwall_pain~1b5a3ea4")
    image_source, image1 = walk_inline_gfximage(data, image_source, EXPECTED_IMAGE)
    if image1["fixedSource"] != 515239:
        raise ValueError(f"identity normal GfxImage fixed source drift: {image1['fixedSource']}")
    if image1["resourceSize"] != 4:
        raise ValueError(f"identity normal resource size drift: {image1['resourceSize']}")
    if data[image1["endSource"] - 4:image1["endSource"]] != bytes((0x80, 0x80, 0xFF, 0x80)):
        raise ValueError("identity normal embedded pixel drift")

    _, wrong = replay_vent_to_texture_table(data, tech_cursor.source, tech_cursor.virtual, 4)
    if wrong["slot1ImageFieldVirtual"] != EXPECTED_TARGET_OFFSET - 16:
        raise ValueError("alignment sensitivity regression changed")

    return {
        "format": "t6-nuketown-identitynormalmap-block5-proof-v1",
        "map": "mp_nuketown_2020",
        "verifier": {
            "file": Path(__file__).name,
            "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "source": {
            "file": stream.name,
            "sha256": digest,
            "bytes": len(data),
        },
        "frontReplay": {k: v for k, v in front.items() if k != "assets"},
        "assets0To2Replay": a02,
        "techniqueSetReplay": tech,
        "airVentMaterialReplay": vent,
        "identityImage": image1,
        "alignmentControl": {
            "correctCollisionNodeAlignment": 16,
            "correctSlot1VirtualOffset": vent["slot1ImageFieldVirtual"],
            "wrongAlignmentControl": 4,
            "wrongAlignmentSlot1VirtualOffset": wrong["slot1ImageFieldVirtual"],
            "deltaBytes": vent["slot1ImageFieldVirtual"] - wrong["slot1ImageFieldVirtual"],
        },
        "promotion": {
            "xassetIndex": EXPECTED_TARGET_ASSET_INDEX,
            "xassetType": "IMAGE",
            "block": EXPECTED_TARGET_BLOCK,
            "virtualOffset": EXPECTED_TARGET_OFFSET,
            "image": EXPECTED_IMAGE,
            "material": EXPECTED_MATERIAL,
            "textureSlot": 1,
            "semantic": 5,
            "proof": "direct T6 PC32 loader destination-cursor replay plus inline GfxImage name/pixel validation",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    doc = build(args.stream)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(json.dumps(doc["promotion"], indent=2, sort_keys=True))
    print(json.dumps(doc["alignmentControl"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
