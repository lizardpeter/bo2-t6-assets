#!/usr/bin/env python3
"""General T6 PC32 serialized clipMap_t / CLIPMAP_PVS walker.

This module walks the serialized *source-byte* representation of a T6 clipMap_t
starting at a caller-provided fixed-record offset. It derives all subsequent
byte consumption from the fixed header counts, pointer sentinels, T6 native
PC32 structure sizes, and XBlock behavior.

It deliberately does not discover the top-level asset start; asset discovery is
a separate XAsset-stream concern. No map-specific offsets are embedded here.

Important T6 rule: XBlock alignment changes destination-memory offsets only.
It never pads the serialized source cursor. Runtime blocks are zero-filled by
the loader and consume zero serialized source bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE
BLOCK_SHIFT = 29
OFFSET_MASK = 0x1FFFFFFF
BLOCK_NAMES = [
    "TEMP", "RUNTIME_VIRTUAL", "RUNTIME_PHYSICAL", "DELAY_VIRTUAL",
    "DELAY_PHYSICAL", "VIRTUAL", "PHYSICAL", "STREAMER_RESERVE",
]

# T6 PC32 native fixed sizes. Native alignment affects destination memory; these
# are the actual bytes present when a fixed object/array is serialized.
SIZE = {
    "clipMap_t": 332,
    "ClipInfo": 72,
    "cplane_s": 20,
    "ClipMaterial": 12,
    "cbrushside_t": 12,
    "cLeafBrushNode_s": 20,
    "LeafBrush": 2,
    "vec3_t": 12,
    "uind": 2,
    "cbrush_t": 96,
    "Bounds": 24,
    "cStaticModel_s": 84,
    "cNode_t": 8,
    "cLeaf_s": 44,
    "triIndexTriplet": 6,
    "CollisionPartition": 16,
    "CollisionAabbTree": 32,
    "cmodel_t": 76,
    "MapEnts": 36,
    "TriggerModel": 8,
    "TriggerHull": 32,
    "TriggerSlab": 20,
    "DynEntityDef": 84,
    "XModelPieces": 12,
    "XModelPiece": 16,
    "PhysConstraint": 168,
    "DynEntityPose": 32,
    "DynEntityClient": 20,
    "DynEntityServer": 8,
    "DynEntityColl": 32,
}


class WalkError(RuntimeError):
    pass


def ptr_kind(value: int) -> dict:
    if value == 0:
        return {"raw": value, "rawHex": "0x00000000", "kind": "null"}
    if value == PTR_FOLLOWING:
        return {"raw": value, "rawHex": "0xFFFFFFFF", "kind": "following"}
    if value == PTR_INSERT:
        return {"raw": value, "rawHex": "0xFFFFFFFE", "kind": "insert"}
    encoded = (value - 1) & 0xFFFFFFFF
    block = encoded >> BLOCK_SHIFT
    off = encoded & OFFSET_MASK
    return {
        "raw": value,
        "rawHex": f"0x{value:08X}",
        "kind": "packed",
        "block": block,
        "blockName": BLOCK_NAMES[block] if block < len(BLOCK_NAMES) else None,
        "offset": off,
    }


def is_inline(value: int) -> bool:
    return value in (PTR_FOLLOWING, PTR_INSERT)


class Walker:
    def __init__(self, data: bytes, start: int):
        self.data = data
        self.start = start
        self.pos = start
        self.sections: list[dict] = []
        self.runtime_allocations: list[dict] = []
        self.blockers: list[dict] = []
        self.details: dict = {}

    def need(self, n: int, label: str):
        if n < 0 or self.pos + n > len(self.data):
            raise WalkError(
                f"{label}: need {n} bytes at {self.pos}, file has {len(self.data)}"
            )

    def take(self, n: int, label: str, *, meta=None) -> tuple[int, int]:
        self.need(n, label)
        a = self.pos
        self.pos += n
        rec = {
            "name": label,
            "start": a,
            "end": self.pos,
            "bytes": n,
            "sha256": hashlib.sha256(self.data[a:self.pos]).hexdigest(),
        }
        if meta:
            rec.update(meta)
        self.sections.append(rec)
        return a, self.pos

    def cstring(self, label: str) -> str:
        try:
            end = self.data.index(b"\0", self.pos)
        except ValueError as e:
            raise WalkError(f"{label}: unterminated string at {self.pos}") from e
        a = self.pos
        raw = self.data[a:end]
        self.pos = end + 1
        text = raw.decode("latin1", "replace")
        self.sections.append(
            {
                "name": label,
                "start": a,
                "end": self.pos,
                "bytes": self.pos - a,
                "sha256": hashlib.sha256(self.data[a:self.pos]).hexdigest(),
                "text": text,
            }
        )
        return text

    def u32at(self, base: int, off: int) -> int:
        return struct.unpack_from("<I", self.data, base + off)[0]

    def i32at(self, base: int, off: int) -> int:
        return struct.unpack_from("<i", self.data, base + off)[0]

    def u16at(self, base: int, off: int) -> int:
        return struct.unpack_from("<H", self.data, base + off)[0]

    def i16at(self, base: int, off: int) -> int:
        return struct.unpack_from("<h", self.data, base + off)[0]

    def runtime(self, name: str, ptr: int, count: int, elem_size: int):
        if ptr == 0 or count == 0:
            return
        if ptr not in (PTR_FOLLOWING, PTR_INSERT):
            self.blockers.append(
                {
                    "kind": "unexpected_runtime_pointer",
                    "field": name,
                    "pointer": ptr_kind(ptr),
                    "count": count,
                }
            )
            return
        self.runtime_allocations.append(
            {
                "name": name,
                "count": count,
                "recordBytes": elem_size,
                "destinationBytes": count * elem_size,
                "serializedSourceBytes": 0,
                "pointer": ptr_kind(ptr),
                "rule": (
                    "XBlock BLOCK_TYPE_RUNTIME is zero-filled and does not read "
                    "source bytes"
                ),
            }
        )

    def external_asset_ref(self, field: str, ptr: int, owner_index=None):
        # Packed/null refs consume no source bytes. An inline asset ref requires
        # dispatching the referenced XAsset loader, which belongs in the generic
        # XAsset walker rather than silently guessing here.
        if is_inline(ptr):
            self.blockers.append(
                {
                    "kind": "inline_external_asset_reference_requires_xasset_dispatch",
                    "field": field,
                    "ownerIndex": owner_index,
                    "pointer": ptr_kind(ptr),
                }
            )

    def walk_string_ptr(self, ptr: int, label: str):
        if is_inline(ptr):
            return self.cstring(label)
        return None

    def walk_plane_ptr(self, ptr: int, label: str):
        if is_inline(ptr):
            self.take(SIZE["cplane_s"], label)

    def walk_clipinfo_at_cursor(self, label: str) -> dict:
        base, _ = self.take(SIZE["ClipInfo"], f"{label}.fixed")
        ci = self.parse_clipinfo(base)
        self.walk_clipinfo_payload(ci, label)
        return ci

    def parse_clipinfo(self, base: int) -> dict:
        pairs = [
            ("planeCount", 0, "planes", 4),
            ("numMaterials", 8, "materials", 12),
            ("numBrushSides", 16, "brushsides", 20),
            ("leafbrushNodesCount", 24, "leafbrushNodes", 28),
            ("numLeafBrushes", 32, "leafbrushes", 36),
            ("numBrushVerts", 40, "brushVerts", 44),
            ("nuinds", 48, "uinds", 52),
        ]
        out = {}
        for cn, co, pn, po in pairs:
            out[cn] = self.u32at(base, co)
            out[pn] = self.u32at(base, po)
        out["numBrushes"] = self.u16at(base, 56)
        out["brushes"] = self.u32at(base, 60)
        out["brushBounds"] = self.u32at(base, 64)
        out["brushContents"] = self.u32at(base, 68)
        out["pointers"] = {
            k: ptr_kind(v)
            for k, v in out.items()
            if k
            in {
                "planes",
                "materials",
                "brushsides",
                "leafbrushNodes",
                "leafbrushes",
                "brushVerts",
                "uinds",
                "brushes",
                "brushBounds",
                "brushContents",
            }
        }
        return out

    def walk_clipinfo_payload(self, ci: dict, label: str):
        if is_inline(ci["planes"]):
            self.take(
                ci["planeCount"] * SIZE["cplane_s"],
                f"{label}.planes",
                meta={"count": ci["planeCount"], "recordBytes": SIZE["cplane_s"]},
            )

        if is_inline(ci["materials"]):
            a, _ = self.take(
                ci["numMaterials"] * SIZE["ClipMaterial"],
                f"{label}.materials.fixed",
                meta={
                    "count": ci["numMaterials"],
                    "recordBytes": SIZE["ClipMaterial"],
                },
            )
            names = []
            for i in range(ci["numMaterials"]):
                p = self.u32at(a + i * SIZE["ClipMaterial"], 0)
                txt = self.walk_string_ptr(p, f"{label}.materials[{i}].name")
                if txt is not None:
                    names.append({"index": i, "name": txt})
            if names:
                self.details.setdefault("inlineMaterialNames", []).extend(names)

        if is_inline(ci["brushsides"]):
            a, _ = self.take(
                ci["numBrushSides"] * SIZE["cbrushside_t"],
                f"{label}.brushsides.fixed",
                meta={
                    "count": ci["numBrushSides"],
                    "recordBytes": SIZE["cbrushside_t"],
                },
            )
            inline_planes = 0
            for i in range(ci["numBrushSides"]):
                pp = self.u32at(a + i * SIZE["cbrushside_t"], 0)
                if is_inline(pp):
                    inline_planes += 1
                    self.walk_plane_ptr(pp, f"{label}.brushsides[{i}].plane")
            self.details.setdefault("inlineBrushSidePlanes", 0)
            self.details["inlineBrushSidePlanes"] += inline_planes

        if is_inline(ci["leafbrushNodes"]):
            a, _ = self.take(
                ci["leafbrushNodesCount"] * SIZE["cLeafBrushNode_s"],
                f"{label}.leafbrushNodes.fixed",
                meta={
                    "count": ci["leafbrushNodesCount"],
                    "recordBytes": SIZE["cLeafBrushNode_s"],
                },
            )
            inline_leaf_brushes = 0
            inline_leaf_nodes = 0
            for i in range(ci["leafbrushNodesCount"]):
                b = a + i * SIZE["cLeafBrushNode_s"]
                leaf_count = self.i16at(b, 2)
                if leaf_count > 0:
                    pp = self.u32at(b, 8)
                    if is_inline(pp):
                        inline_leaf_nodes += 1
                        inline_leaf_brushes += leaf_count
                        self.take(
                            leaf_count * SIZE["LeafBrush"],
                            f"{label}.leafbrushNodes[{i}].brushes",
                            meta={
                                "count": leaf_count,
                                "recordBytes": SIZE["LeafBrush"],
                            },
                        )
            self.details.setdefault("inlineLeafBrushNodeArrays", 0)
            self.details["inlineLeafBrushNodeArrays"] += inline_leaf_nodes
            self.details.setdefault("inlineLeafBrushRefs", 0)
            self.details["inlineLeafBrushRefs"] += inline_leaf_brushes

        if is_inline(ci["leafbrushes"]):
            self.take(
                ci["numLeafBrushes"] * SIZE["LeafBrush"],
                f"{label}.leafbrushes",
                meta={
                    "count": ci["numLeafBrushes"],
                    "recordBytes": SIZE["LeafBrush"],
                },
            )

        if is_inline(ci["brushVerts"]):
            self.take(
                ci["numBrushVerts"] * SIZE["vec3_t"],
                f"{label}.brushVerts",
                meta={
                    "count": ci["numBrushVerts"],
                    "recordBytes": SIZE["vec3_t"],
                },
            )

        if is_inline(ci["uinds"]):
            self.take(
                ci["nuinds"] * SIZE["uind"],
                f"{label}.uinds",
                meta={"count": ci["nuinds"], "recordBytes": SIZE["uind"]},
            )

        if is_inline(ci["brushes"]):
            a, _ = self.take(
                ci["numBrushes"] * SIZE["cbrush_t"],
                f"{label}.brushes.fixed",
                meta={
                    "count": ci["numBrushes"],
                    "recordBytes": SIZE["cbrush_t"],
                },
            )
            for i in range(ci["numBrushes"]):
                self.walk_cbrush_nested(
                    a + i * SIZE["cbrush_t"], f"{label}.brushes[{i}]"
                )

        if is_inline(ci["brushBounds"]):
            self.take(
                ci["numBrushes"] * SIZE["Bounds"],
                f"{label}.brushBounds",
                meta={"count": ci["numBrushes"], "recordBytes": SIZE["Bounds"]},
            )
        if is_inline(ci["brushContents"]):
            self.take(
                ci["numBrushes"] * 4,
                f"{label}.brushContents",
                meta={"count": ci["numBrushes"], "recordBytes": 4},
            )

    def walk_cbrush_nested(self, base: int, label: str):
        numsides = self.u32at(base, 28)
        sides = self.u32at(base, 32)
        numverts = self.u32at(base, 84)
        verts = self.u32at(base, 88)
        if is_inline(sides):
            a, _ = self.take(
                numsides * SIZE["cbrushside_t"],
                f"{label}.sides.fixed",
                meta={"count": numsides, "recordBytes": SIZE["cbrushside_t"]},
            )
            for j in range(numsides):
                pp = self.u32at(a + j * SIZE["cbrushside_t"], 0)
                self.walk_plane_ptr(pp, f"{label}.sides[{j}].plane")
        if is_inline(verts):
            self.take(
                numverts * SIZE["vec3_t"],
                f"{label}.verts",
                meta={"count": numverts, "recordBytes": SIZE["vec3_t"]},
            )

    def walk_mapents(self, label: str) -> dict:
        base, _ = self.take(SIZE["MapEnts"], f"{label}.fixed")
        name_ptr = self.u32at(base, 0)
        entity_ptr = self.u32at(base, 4)
        entity_chars = self.i32at(base, 8)
        trig_count = self.u32at(base, 12)
        models_ptr = self.u32at(base, 16)
        hull_count = self.u32at(base, 20)
        hulls_ptr = self.u32at(base, 24)
        slab_count = self.u32at(base, 28)
        slabs_ptr = self.u32at(base, 32)
        name = self.walk_string_ptr(name_ptr, f"{label}.name")
        if entity_chars < 0:
            raise WalkError(f"{label}: negative entity char count {entity_chars}")
        if is_inline(entity_ptr):
            self.take(
                entity_chars,
                f"{label}.entityString",
                meta={"count": entity_chars, "recordBytes": 1},
            )
        if is_inline(models_ptr):
            self.take(
                trig_count * SIZE["TriggerModel"],
                f"{label}.trigger.models",
                meta={"count": trig_count, "recordBytes": SIZE["TriggerModel"]},
            )
        if is_inline(hulls_ptr):
            self.take(
                hull_count * SIZE["TriggerHull"],
                f"{label}.trigger.hulls",
                meta={"count": hull_count, "recordBytes": SIZE["TriggerHull"]},
            )
        if is_inline(slabs_ptr):
            self.take(
                slab_count * SIZE["TriggerSlab"],
                f"{label}.trigger.slabs",
                meta={"count": slab_count, "recordBytes": SIZE["TriggerSlab"]},
            )
        return {
            "namePointer": ptr_kind(name_ptr),
            "name": name,
            "entityStringPointer": ptr_kind(entity_ptr),
            "numEntityChars": entity_chars,
            "trigger": {
                "modelCount": trig_count,
                "modelsPointer": ptr_kind(models_ptr),
                "hullCount": hull_count,
                "hullsPointer": ptr_kind(hulls_ptr),
                "slabCount": slab_count,
                "slabsPointer": ptr_kind(slabs_ptr),
            },
        }

    def walk_xmodelpieces(self, label: str):
        base, _ = self.take(SIZE["XModelPieces"], f"{label}.fixed")
        name_ptr = self.u32at(base, 0)
        count = self.i32at(base, 4)
        pieces_ptr = self.u32at(base, 8)
        self.walk_string_ptr(name_ptr, f"{label}.name")
        if count < 0:
            raise WalkError(f"{label}: negative piece count {count}")
        if is_inline(pieces_ptr):
            a, _ = self.take(
                count * SIZE["XModelPiece"],
                f"{label}.pieces",
                meta={"count": count, "recordBytes": SIZE["XModelPiece"]},
            )
            for i in range(count):
                self.external_asset_ref(
                    f"{label}.pieces[{i}].model", self.u32at(a + i * 16, 0), i
                )

    def walk_dynentdefs(self, ptr: int, count: int, label: str):
        if not is_inline(ptr):
            return
        a, _ = self.take(
            count * SIZE["DynEntityDef"],
            f"{label}.fixed",
            meta={"count": count, "recordBytes": SIZE["DynEntityDef"]},
        )
        types = Counter()
        destroy_piece_inline = 0
        for i in range(count):
            b = a + i * SIZE["DynEntityDef"]
            typ = self.i32at(b, 0)
            types[typ] += 1
            self.external_asset_ref(f"{label}[{i}].xModel", self.u32at(b, 32), i)
            self.external_asset_ref(
                f"{label}[{i}].destroyedxModel", self.u32at(b, 36), i
            )
            self.external_asset_ref(f"{label}[{i}].destroyFx", self.u32at(b, 44), i)
            pieces = self.u32at(b, 52)
            self.external_asset_ref(
                f"{label}[{i}].physPreset", self.u32at(b, 56), i
            )
            if is_inline(pieces):
                destroy_piece_inline += 1
                self.walk_xmodelpieces(f"{label}[{i}].destroyPieces")
        self.details.setdefault("dynEntDefLists", {})[label] = {
            "count": count,
            "typeCounts": {str(k): v for k, v in sorted(types.items())},
            "inlineDestroyPieces": destroy_piece_inline,
        }

    def walk_constraints(self, ptr: int, count: int, label: str):
        if count == 0 or not is_inline(ptr):
            return
        a, _ = self.take(
            count * SIZE["PhysConstraint"],
            f"{label}.fixed",
            meta={"count": count, "recordBytes": SIZE["PhysConstraint"]},
        )
        for i in range(count):
            b = a + i * SIZE["PhysConstraint"]
            self.walk_string_ptr(self.u32at(b, 20), f"{label}[{i}].target_bone1")
            self.walk_string_ptr(self.u32at(b, 36), f"{label}[{i}].target_bone2")
            self.external_asset_ref(f"{label}[{i}].material", self.u32at(b, 140), i)

    def parse_header(self) -> dict:
        base = self.start
        if base < 0 or base + SIZE["clipMap_t"] > len(self.data):
            raise WalkError("fixed clipMap_t outside file")
        h = {
            "name": self.u32at(base, 0),
            "isInUse": self.i32at(base, 4),
            "info": self.parse_clipinfo(base + 8),
            "pInfo": self.u32at(base, 80),
            "numStaticModels": self.u32at(base, 84),
            "staticModelList": self.u32at(base, 88),
            "numNodes": self.u32at(base, 92),
            "nodes": self.u32at(base, 96),
            "numLeafs": self.u32at(base, 100),
            "leafs": self.u32at(base, 104),
            "vertCount": self.u32at(base, 108),
            "verts": self.u32at(base, 112),
            "triCount": self.i32at(base, 116),
            "triIndices": self.u32at(base, 120),
            "triEdgeIsWalkable": self.u32at(base, 124),
            "partitionCount": self.i32at(base, 128),
            "partitions": self.u32at(base, 132),
            "aabbTreeCount": self.i32at(base, 136),
            "aabbTrees": self.u32at(base, 140),
            "numSubModels": self.u32at(base, 144),
            "cmodels": self.u32at(base, 148),
            "numClusters": self.i32at(base, 152),
            "clusterBytes": self.i32at(base, 156),
            "visibility": self.u32at(base, 160),
            "vised": self.i32at(base, 164),
            "mapEnts": self.u32at(base, 168),
            "box_brush": self.u32at(base, 172),
            "originalDynEntCount": self.u16at(base, 252),
            "dynEntCount": [self.u16at(base, 254 + 2 * i) for i in range(4)],
            "dynEntDefList": [self.u32at(base, 264), self.u32at(base, 268)],
            "dynEntPoseList": [self.u32at(base, 272), self.u32at(base, 276)],
            "dynEntClientList": [self.u32at(base, 280), self.u32at(base, 284)],
            "dynEntServerList": [self.u32at(base, 288), self.u32at(base, 292)],
            "dynEntCollList": [self.u32at(base, 296 + 4 * i) for i in range(4)],
            "num_constraints": self.i32at(base, 312),
            "constraints": self.u32at(base, 316),
            "max_ropes": self.i32at(base, 320),
            "ropes": self.u32at(base, 324),
            "checksum": self.u32at(base, 328),
        }
        for k in (
            "triCount",
            "partitionCount",
            "aabbTreeCount",
            "numClusters",
            "clusterBytes",
            "num_constraints",
            "max_ropes",
        ):
            if h[k] < 0:
                raise WalkError(f"negative {k}: {h[k]}")
        return h

    def walk(self) -> dict:
        h = self.parse_header()
        self.take(SIZE["clipMap_t"], "clipMap_t.fixed")

        self.walk_clipinfo_payload(h["info"], "clipMap.info")

        if is_inline(h["pInfo"]):
            self.walk_clipinfo_at_cursor("clipMap.pInfo")

        if is_inline(h["staticModelList"]):
            a, _ = self.take(
                h["numStaticModels"] * SIZE["cStaticModel_s"],
                "clipMap.staticModelList",
                meta={
                    "count": h["numStaticModels"],
                    "recordBytes": SIZE["cStaticModel_s"],
                },
            )
            for i in range(h["numStaticModels"]):
                self.external_asset_ref(
                    f"clipMap.staticModelList[{i}].xmodel",
                    self.u32at(a + i * SIZE["cStaticModel_s"], 4),
                    i,
                )

        if is_inline(h["nodes"]):
            a, _ = self.take(
                h["numNodes"] * SIZE["cNode_t"],
                "clipMap.nodes",
                meta={"count": h["numNodes"], "recordBytes": SIZE["cNode_t"]},
            )
            for i in range(h["numNodes"]):
                self.walk_plane_ptr(
                    self.u32at(a + i * SIZE["cNode_t"], 0),
                    f"clipMap.nodes[{i}].plane",
                )

        if is_inline(h["leafs"]):
            self.take(
                h["numLeafs"] * SIZE["cLeaf_s"],
                "clipMap.leafs",
                meta={"count": h["numLeafs"], "recordBytes": SIZE["cLeaf_s"]},
            )

        if is_inline(h["verts"]):
            self.take(
                h["vertCount"] * SIZE["vec3_t"],
                "clipMap.verts",
                meta={"count": h["vertCount"], "recordBytes": SIZE["vec3_t"]},
            )

        if is_inline(h["triIndices"]):
            self.take(
                h["triCount"] * SIZE["triIndexTriplet"],
                "clipMap.triIndices",
                meta={
                    "count": h["triCount"],
                    "recordBytes": SIZE["triIndexTriplet"],
                },
            )

        if is_inline(h["triEdgeIsWalkable"]):
            n = ((3 * h["triCount"] + 31) // 32) * 4
            self.take(
                n,
                "clipMap.triEdgeIsWalkable",
                meta={"formula": "((3*triCount+31)//32)*4"},
            )

        if is_inline(h["partitions"]):
            self.take(
                h["partitionCount"] * SIZE["CollisionPartition"],
                "clipMap.partitions",
                meta={
                    "count": h["partitionCount"],
                    "recordBytes": SIZE["CollisionPartition"],
                },
            )

        if is_inline(h["aabbTrees"]):
            self.take(
                h["aabbTreeCount"] * SIZE["CollisionAabbTree"],
                "clipMap.aabbTrees",
                meta={
                    "count": h["aabbTreeCount"],
                    "recordBytes": SIZE["CollisionAabbTree"],
                },
            )

        if is_inline(h["cmodels"]):
            a, _ = self.take(
                h["numSubModels"] * SIZE["cmodel_t"],
                "clipMap.cmodels.fixed",
                meta={
                    "count": h["numSubModels"],
                    "recordBytes": SIZE["cmodel_t"],
                },
            )
            for i in range(h["numSubModels"]):
                info = self.u32at(a + i * SIZE["cmodel_t"], 28)
                if is_inline(info):
                    self.walk_clipinfo_at_cursor(f"clipMap.cmodels[{i}].info")

        if is_inline(h["visibility"]):
            n = h["numClusters"] * h["clusterBytes"]
            self.take(
                n,
                "clipMap.visibility",
                meta={
                    "numClusters": h["numClusters"],
                    "clusterBytes": h["clusterBytes"],
                },
            )

        mapents = None
        if is_inline(h["mapEnts"]):
            mapents = self.walk_mapents("clipMap.mapEnts")

        if is_inline(h["box_brush"]):
            b, _ = self.take(SIZE["cbrush_t"], "clipMap.box_brush.fixed")
            self.walk_cbrush_nested(b, "clipMap.box_brush")

        self.walk_dynentdefs(
            h["dynEntDefList"][0], h["dynEntCount"][0], "clipMap.dynEntDefList[0]"
        )
        self.walk_dynentdefs(
            h["dynEntDefList"][1], h["dynEntCount"][1], "clipMap.dynEntDefList[1]"
        )

        self.runtime(
            "clipMap.dynEntPoseList[0]",
            h["dynEntPoseList"][0],
            h["dynEntCount"][0],
            SIZE["DynEntityPose"],
        )
        self.runtime(
            "clipMap.dynEntPoseList[1]",
            h["dynEntPoseList"][1],
            h["dynEntCount"][1],
            SIZE["DynEntityPose"],
        )
        self.runtime(
            "clipMap.dynEntClientList[0]",
            h["dynEntClientList"][0],
            h["dynEntCount"][0],
            SIZE["DynEntityClient"],
        )
        self.runtime(
            "clipMap.dynEntClientList[1]",
            h["dynEntClientList"][1],
            h["dynEntCount"][1],
            SIZE["DynEntityClient"],
        )
        self.runtime(
            "clipMap.dynEntServerList[0]",
            h["dynEntServerList"][0],
            h["dynEntCount"][2],
            SIZE["DynEntityServer"],
        )
        self.runtime(
            "clipMap.dynEntServerList[1]",
            h["dynEntServerList"][1],
            h["dynEntCount"][3],
            SIZE["DynEntityServer"],
        )
        for i in range(4):
            self.runtime(
                f"clipMap.dynEntCollList[{i}]",
                h["dynEntCollList"][i],
                h["dynEntCount"][i],
                SIZE["DynEntityColl"],
            )

        self.walk_constraints(
            h["constraints"], h["num_constraints"], "clipMap.constraints"
        )

        # ropes are runtime virtual. rope_t byte size is not required to determine
        # source span; preserve count and zero-source behavior without guessing a
        # runtime destination stride.
        if h["ropes"] and h["max_ropes"]:
            self.runtime_allocations.append(
                {
                    "name": "clipMap.ropes",
                    "count": h["max_ropes"],
                    "recordBytes": None,
                    "destinationBytes": None,
                    "serializedSourceBytes": 0,
                    "pointer": ptr_kind(h["ropes"]),
                    "rule": (
                        "XBlock BLOCK_TYPE_RUNTIME is zero-filled; rope_t source "
                        "bytes = 0"
                    ),
                }
            )

        header_for_json = dict(h)
        header_for_json["pointers"] = {}
        pointer_keys = [
            "name",
            "pInfo",
            "staticModelList",
            "nodes",
            "leafs",
            "verts",
            "triIndices",
            "triEdgeIsWalkable",
            "partitions",
            "aabbTrees",
            "cmodels",
            "visibility",
            "mapEnts",
            "box_brush",
            "constraints",
            "ropes",
        ]
        for k in pointer_keys:
            header_for_json["pointers"][k] = ptr_kind(h[k])
        for k in (
            "dynEntDefList",
            "dynEntPoseList",
            "dynEntClientList",
            "dynEntServerList",
            "dynEntCollList",
        ):
            header_for_json["pointers"][k] = [ptr_kind(x) for x in h[k]]
        for k in pointer_keys:
            header_for_json.pop(k, None)

        return {
            "format": "t6-clipmap-serialized-walk-v1",
            "assetFixedStart": self.start,
            "assetSerializedEnd": self.pos,
            "assetSerializedBytes": self.pos - self.start,
            "assetSerializedSha256": hashlib.sha256(
                self.data[self.start : self.pos]
            ).hexdigest(),
            "header": header_for_json,
            "mapEnts": mapents,
            "sections": self.sections,
            "runtimeAllocations": self.runtime_allocations,
            "details": self.details,
            "blockers": self.blockers,
            "sourceAlignmentRule": (
                "never pad serialized source cursor for XBlock destination alignment"
            ),
            "runtimeBlockRule": (
                "BLOCK_TYPE_RUNTIME zero-fills destination and consumes zero source bytes"
            ),
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "expanded", type=Path, help="decrypted/decompressed T6 XFile byte stream"
    )
    ap.add_argument(
        "--asset-start",
        type=lambda x: int(x, 0),
        required=True,
        help="raw source offset of fixed clipMap_t record (decimal or 0x...)",
    )
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--expect-end",
        type=lambda x: int(x, 0),
        help="optional fixture assertion for independently known next-asset start",
    )
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    result = Walker(data, args.asset_start).walk()
    result["expandedBytes"] = len(data)
    result["expandedSha256"] = hashlib.sha256(data).hexdigest()
    if args.expect_end is not None:
        result["expectedEnd"] = args.expect_end
        result["expectedEndMatches"] = result["assetSerializedEnd"] == args.expect_end
        if not result["expectedEndMatches"]:
            raise SystemExit(
                f"walk ended at {result['assetSerializedEnd']}, expected {args.expect_end}"
            )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
