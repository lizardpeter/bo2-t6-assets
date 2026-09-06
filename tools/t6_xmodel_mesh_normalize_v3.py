#!/usr/bin/env python3
"""T6 XModel mesh normalizer v3: exact nested render-payload reuse.

This extends mesh-v2 for one narrow retail reuse shape:

- target XModel owns its XModel.surfs.fixed array inline;
- skeleton-v2 proves one unique earlier reusable XModel owner;
- the reusable-owner replay contains an exact matched comparison for every
  packed nested render pointer used by the target; and
- the earlier owner is completely decodable by mesh-v1.

The target XModel header, LOD records, surface scalar records and every inline
payload remain authoritative. Only an individual packed payload is borrowed
from the proven owner. Packed top-level XModel.surfs remains unsupported.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-xmodel-mesh-normalized-v3"
SKELETON_FORMAT = "t6-xmodel-skeleton-normalized-v2"
FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
DOBJ_SKEL_MAT = 64
XSURFACE_SIZE = 80


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_json(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected JSON object")
    return doc


def ptr_kind(raw: int) -> dict[str, Any]:
    if raw == 0:
        return {"kind": "null", "raw": raw, "rawHex": "0x00000000"}
    if raw == FOLLOWING:
        return {"kind": "following", "raw": raw, "rawHex": "0xFFFFFFFF"}
    if raw == INSERT:
        return {"kind": "insert", "raw": raw, "rawHex": "0xFFFFFFFE"}
    enc = (raw - 1) & 0xFFFFFFFF
    return {"kind": "packed", "raw": raw, "rawHex": f"0x{raw:08X}", "block": enc >> 29, "offset": enc & 0x1FFFFFFF}


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def _i16(data: bytes, off: int) -> int:
    return struct.unpack_from("<h", data, off)[0]


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _sections(walk: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in walk.get("sections", []):
        name = row.get("name")
        if not isinstance(name, str):
            continue
        if name in out:
            raise ValueError(f"duplicate serialized section {name}")
        out[name] = row
    return out


def _comparison_map(skeleton: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source = skeleton.get("skeletonSource")
    if not isinstance(source, dict) or source.get("mode") != "packed_reusable_owner":
        raise ValueError("nested render reuse requires skeletonSource.mode=packed_reusable_owner")
    owner = source.get("owner")
    if not isinstance(owner, dict) or not isinstance(owner.get("fixedSourceStart"), int):
        raise ValueError("skeleton reusable-owner metadata is incomplete")
    rows = source.get("comparisons")
    if not isinstance(rows, list):
        raise ValueError("skeleton reusable-owner comparisons are missing")
    out = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("field"), str):
            continue
        field = row["field"]
        if field in out:
            raise ValueError(f"duplicate reusable-owner comparison {field}")
        if row.get("match") is not True:
            raise ValueError(f"reusable-owner comparison is not exact: {field}")
        out[field] = row
    return out


def _require_packed_match(raw: int, field: str, comparisons: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pk = ptr_kind(raw)
    if pk.get("kind") != "packed" or pk.get("block") != 5:
        raise ValueError(f"{field}: reusable render pointer must be packed VIRTUAL")
    row = comparisons.get(field)
    if row is None:
        raise ValueError(f"{field}: packed render pointer has no explicit reusable-owner replay comparison")
    if int(row.get("actualOffset", -1)) != int(pk["offset"]):
        raise ValueError(f"{field}: replay actualOffset does not match target packed pointer")
    if int(row.get("predictedOffset", -1)) != int(pk["offset"]):
        raise ValueError(f"{field}: replay predictedOffset does not match target packed pointer")
    return {"mode": "packed-reusable-owner", "pointer": pk, "comparison": row}


def _inline_or_null(raw: int, field: str) -> str:
    pk = ptr_kind(raw)
    if pk["kind"] in ("following", "insert"):
        return "inline"
    if pk["kind"] == "null":
        return "null"
    raise ValueError(f"{field}: unexpected packed pointer without reuse resolution")


def _surface_scalar(data: bytes, base: int) -> dict[str, Any]:
    blend = [_i16(data, base + 16 + 2 * i) for i in range(4)]
    if any(x < 0 for x in blend):
        raise ValueError("negative XSurface blend count")
    return {
        "tileMode": data[base],
        "vertListCount": data[base + 1],
        "flags": _u16(data, base + 2),
        "vertCount": _u16(data, base + 4),
        "triCount": _u16(data, base + 6),
        "baseVertIndex": _u16(data, base + 8),
        "triIndicesRaw": _u32(data, base + 12),
        "blendCounts": blend,
        "vertsBlendRaw": _u32(data, base + 24),
        "tensionRaw": _u32(data, base + 28),
        "verts0Raw": _u32(data, base + 32),
        "vertListRaw": _u32(data, base + 40),
    }


def _owner_scalar_compatible(target: dict[str, Any], owner: dict[str, Any]) -> bool:
    return (
        target["tileMode"] == owner.get("tileMode")
        and target["flags"] == owner.get("flags")
        and target["vertCount"] == owner.get("vertCount")
        and target["triCount"] == owner.get("triCount")
        and target["baseVertIndex"] == owner.get("baseVertIndex")
        and target["blendCounts"] == owner.get("blendCounts")
        and target["vertListCount"] == len(owner.get("rigidVertLists", []))
    )


def _read_blend_words(data: bytes, section: dict[str, Any], count: int) -> list[int]:
    if count == 0:
        return []
    start = int(section["start"])
    return list(struct.unpack_from("<" + "H" * count, data, start))


def _read_triangles(data: bytes, section: dict[str, Any], count: int) -> list[list[int]]:
    start = int(section["start"])
    return [list(struct.unpack_from("<3H", data, start + i * 6)) for i in range(count)]


def _read_inline_rigid(target_walk: dict[str, Any], index: int) -> list[dict[str, Any]]:
    surfaces = target_walk.get("xmodel", {}).get("surfaces", [])
    if index >= len(surfaces):
        raise ValueError(f"target walk missing surface {index}")
    rows = surfaces[index].get("rigidVertLists")
    if not isinstance(rows, list):
        raise ValueError(f"surface {index}: rigidVertLists missing")
    out = []
    for j, r in enumerate(rows):
        cp = r.get("collisionTreePointer") or {}
        if cp.get("kind") == "packed":
            raise ValueError(f"surface {index} rigid list {j}: packed nested collision tree is not closed by v3")
        out.append(dict(r))
    return out


def _weights_from_inline_blends(blend_words: list[int], blend_counts: list[int]) -> tuple[list[list[int]], list[list[float]]]:
    joints = []
    weights = []
    o = 0
    bucket_sizes = [1, 3, 5, 7]
    for bucket, cnt in enumerate(blend_counts):
        for _ in range(cnt):
            words = blend_words[o:o + bucket_sizes[bucket]]
            o += bucket_sizes[bucket]
            if len(words) != bucket_sizes[bucket]:
                raise ValueError("truncated vertsBlend payload")
            if bucket == 0:
                js = [words[0] // DOBJ_SKEL_MAT]
                ws = [1.0]
            else:
                js = [words[0] // DOBJ_SKEL_MAT]
                ws = []
                accum = 0.0
                for k in range(bucket):
                    ji = words[1 + 2 * k] // DOBJ_SKEL_MAT
                    wi = words[2 + 2 * k] / 65535.0
                    js.append(ji); ws.append(wi); accum += wi
                ws = [1.0 - accum] + ws
            joints.append((js + [0] * 4)[:4])
            weights.append((ws + [0.0] * 4)[:4])
    if o != len(blend_words):
        raise ValueError("vertsBlend word cardinality mismatch")
    return joints, weights


def merge_mesh(data: bytes, target_start: int, skeleton: dict[str, Any], target_walk: dict[str, Any],
               owner_mesh: dict[str, Any], *, base_module) -> dict[str, Any]:
    expanded_sha = hashlib.sha256(data).hexdigest()
    if skeleton.get("format") != SKELETON_FORMAT:
        raise ValueError(f"skeleton format must be {SKELETON_FORMAT}")
    src = skeleton.get("source") or {}; ident = skeleton.get("identity") or {}; sk = skeleton.get("skeleton") or {}; val = skeleton.get("validation") or {}
    if src.get("expandedSha256") != expanded_sha or int(src.get("xmodelFixedStart", -1)) != int(target_start):
        raise ValueError("skeleton dependency does not identify this target in this expanded stream")
    if val.get("allBoneNamesResolved") is not True or val.get("hierarchyValid") is not True:
        raise ValueError("skeleton dependency is not closed")
    comparisons = _comparison_map(skeleton)
    owner_meta = skeleton["skeletonSource"]["owner"]
    owner_name = owner_meta.get("name")
    if owner_mesh.get("identity", {}).get("name") != owner_name:
        raise ValueError("decoded owner mesh identity does not match skeleton reusable owner")

    tx = target_walk.get("xmodel") or {}
    if target_walk.get("blockers"):
        raise ValueError(f"target XModel walk has blockers: {target_walk['blockers']}")
    if tx.get("name") != ident.get("name"):
        raise ValueError("target walk identity does not match skeleton identity")
    if int(tx.get("numBones", -1)) != int(sk.get("numBones", -2)) or int(tx.get("numRootBones", -1)) != int(sk.get("numRootBones", -2)):
        raise ValueError("target XModel/skeleton cardinality mismatch")
    if ptr_kind(_u32(data, target_start + 32))["kind"] not in ("following", "insert"):
        raise ValueError("packed top-level XModel.surfs remains unsupported in mesh v3")

    target_sections = _sections(target_walk)
    sfixed = target_sections.get("XModel.surfs.fixed")
    if sfixed is None:
        raise ValueError("target owns no inline XModel.surfs.fixed array")
    ns = int(tx.get("numSurfs", -1))
    owner_surfaces = owner_mesh.get("surfaces")
    if not isinstance(owner_surfaces, list) or len(owner_surfaces) != ns:
        raise ValueError("owner/target surface cardinality mismatch")

    decoder = base_module.Normalizer(data, target_start)
    surfaces = []
    borrowed_fields = []
    for i in range(ns):
        fixed = int(sfixed["start"]) + i * XSURFACE_SIZE
        t = _surface_scalar(data, fixed)
        o = owner_surfaces[i]
        if not _owner_scalar_compatible(t, o):
            raise ValueError(f"surface {i}: target/owner scalar signature mismatch")
        if t["flags"] & 1:
            raise ValueError(f"surface {i}: flags&1 render representation remains unsupported")

        blend_word_count = t["blendCounts"][0] + 3*t["blendCounts"][1] + 5*t["blendCounts"][2] + 7*t["blendCounts"][3]
        blend_vertex_count = sum(t["blendCounts"])

        # vertsBlend / blended weights
        if ptr_kind(t["vertsBlendRaw"])["kind"] == "packed":
            prov_blend = _require_packed_match(t["vertsBlendRaw"], f"surfs[{i}].vertsBlend", comparisons)
            owner_rigid_count = sum(int(r.get("vertCount", 0)) for r in o.get("rigidVertLists", []))
            blend_joints = [list(x) for x in o.get("joints0", [])[owner_rigid_count:owner_rigid_count + blend_vertex_count]]
            blend_weights = [list(x) for x in o.get("weights0", [])[owner_rigid_count:owner_rigid_count + blend_vertex_count]]
            if len(blend_joints) != blend_vertex_count or len(blend_weights) != blend_vertex_count:
                raise ValueError(f"surface {i}: owner blended-weight rows are incomplete")
            borrowed_fields.append(f"surfs[{i}].vertsBlend")
        else:
            mode = _inline_or_null(t["vertsBlendRaw"], f"surface {i} vertsBlend")
            if blend_word_count and mode != "inline":
                raise ValueError(f"surface {i}: nonzero blend data has null vertsBlend")
            sec = target_sections.get(f"XModel.surfs[{i}].vertInfo.vertsBlend")
            words = _read_blend_words(data, sec, blend_word_count) if blend_word_count else []
            blend_joints, blend_weights = _weights_from_inline_blends(words, t["blendCounts"])
            prov_blend = {"mode": "target-inline" if blend_word_count else "target-null"}

        # tensionData is not needed for static vertex output but ownership still must close.
        if ptr_kind(t["tensionRaw"])["kind"] == "packed":
            prov_tension = _require_packed_match(t["tensionRaw"], f"surfs[{i}].tensionData", comparisons)
            borrowed_fields.append(f"surfs[{i}].tensionData")
        else:
            mode = _inline_or_null(t["tensionRaw"], f"surface {i} tensionData")
            if blend_vertex_count and mode == "null":
                # Retail may legitimately omit tension; do not require it merely from blend count.
                pass
            prov_tension = {"mode": "target-inline" if mode == "inline" else "target-null"}

        # vertex payload
        if ptr_kind(t["verts0Raw"])["kind"] == "packed":
            prov_verts = _require_packed_match(t["verts0Raw"], f"surfs[{i}].verts0", comparisons)
            vertices = [dict(v) if isinstance(v, dict) else v for v in o.get("vertices", [])]
            if len(vertices) != t["vertCount"]:
                raise ValueError(f"surface {i}: owner vertex payload cardinality mismatch")
            borrowed_fields.append(f"surfs[{i}].verts0")
        else:
            mode = _inline_or_null(t["verts0Raw"], f"surface {i} verts0")
            if t["vertCount"] and mode != "inline":
                raise ValueError(f"surface {i}: vertices are not inline or proven reusable")
            sec = target_sections.get(f"XModel.surfs[{i}].verts0")
            if t["vertCount"] and sec is None:
                raise ValueError(f"surface {i}: inline vertex section missing")
            start = int(sec["start"]) if sec else 0
            vertices = [decoder.decode_vertex(start + j * base_module.PACKED_VERTEX) for j in range(t["vertCount"])]
            prov_verts = {"mode": "target-inline" if t["vertCount"] else "target-null"}

        # rigid vert list / rigid weights
        if ptr_kind(t["vertListRaw"])["kind"] == "packed":
            prov_rigid = _require_packed_match(t["vertListRaw"], f"surfs[{i}].vertList", comparisons)
            rigid = [dict(r) for r in o.get("rigidVertLists", [])]
            borrowed_fields.append(f"surfs[{i}].vertList")
        else:
            mode = _inline_or_null(t["vertListRaw"], f"surface {i} vertList")
            if t["vertListCount"] and mode != "inline":
                raise ValueError(f"surface {i}: rigid list is not inline or proven reusable")
            rigid = _read_inline_rigid(target_walk, i) if t["vertListCount"] else []
            prov_rigid = {"mode": "target-inline" if rigid else "target-null"}
        if len(rigid) != t["vertListCount"]:
            raise ValueError(f"surface {i}: rigid list cardinality mismatch")
        rigid_joints = []
        rigid_weights = []
        for r in rigid:
            bo = int(r.get("boneOffset", -1)); vc = int(r.get("vertCount", -1))
            if bo < 0 or bo % DOBJ_SKEL_MAT or vc < 0:
                raise ValueError(f"surface {i}: invalid rigid list row")
            joint = bo // DOBJ_SKEL_MAT
            if joint >= int(sk["numBones"]):
                raise ValueError(f"surface {i}: rigid joint outside skeleton")
            for _ in range(vc):
                rigid_joints.append([joint, 0, 0, 0]); rigid_weights.append([1.0, 0.0, 0.0, 0.0])

        # triangle payload
        if ptr_kind(t["triIndicesRaw"])["kind"] == "packed":
            prov_tri = _require_packed_match(t["triIndicesRaw"], f"surfs[{i}].triIndices", comparisons)
            triangles = [list(x) for x in o.get("triangles", [])]
            if len(triangles) != t["triCount"]:
                raise ValueError(f"surface {i}: owner triangle payload cardinality mismatch")
            borrowed_fields.append(f"surfs[{i}].triIndices")
        else:
            mode = _inline_or_null(t["triIndicesRaw"], f"surface {i} triIndices")
            if t["triCount"] and mode != "inline":
                raise ValueError(f"surface {i}: triangles are not inline or proven reusable")
            sec = target_sections.get(f"XModel.surfs[{i}].triIndices")
            if t["triCount"] and sec is None:
                raise ValueError(f"surface {i}: inline triangle section missing")
            triangles = _read_triangles(data, sec, t["triCount"]) if t["triCount"] else []
            prov_tri = {"mode": "target-inline" if triangles else "target-null"}
        if any(max(tri) >= t["vertCount"] for tri in triangles):
            raise ValueError(f"surface {i}: triangle index outside target local vertex range")

        handled = len(rigid_joints) + len(blend_joints)
        if handled > t["vertCount"]:
            raise ValueError(f"surface {i}: weighted vertices exceed target vertex count")
        joints = rigid_joints + blend_joints + [[0,0,0,0] for _ in range(t["vertCount"] - handled)]
        weights = rigid_weights + blend_weights + [[0.0,0.0,0.0,0.0] for _ in range(t["vertCount"] - handled)]
        surfaces.append({
            "index": i, "tileMode": t["tileMode"], "flags": t["flags"],
            "vertCount": t["vertCount"], "triCount": t["triCount"], "baseVertIndex": t["baseVertIndex"],
            "blendCounts": t["blendCounts"], "vertices": vertices, "triangles": triangles,
            "joints0": joints, "weights0": weights, "rigidVertLists": rigid,
            "unweightedVertexCount": t["vertCount"] - handled,
            "pointers": {
                "verts0": ptr_kind(t["verts0Raw"]), "vertList": ptr_kind(t["vertListRaw"]),
                "triIndices": ptr_kind(t["triIndicesRaw"]), "vertsBlend": ptr_kind(t["vertsBlendRaw"]),
                "tensionData": ptr_kind(t["tensionRaw"]),
            },
            "payloadProvenance": {
                "vertsBlend": prov_blend, "tensionData": prov_tension, "verts0": prov_verts,
                "vertList": prov_rigid, "triIndices": prov_tri,
            },
        })

    # LOD metadata always comes from target header, never owner mesh.
    lods = []
    num_lods = int(tx.get("numLods", 0))
    for i in range(num_lods):
        b = target_start + 40 + i * 28
        lod = {
            "index": i, "dist": struct.unpack_from("<f", data, b)[0],
            "numSurfs": _u16(data, b + 4), "surfIndex": _u16(data, b + 6),
            "partBits": [_u32(data, b + 8 + 4*j) for j in range(5)],
        }
        if lod["surfIndex"] + lod["numSurfs"] > ns:
            raise ValueError(f"target LOD{i} surface span outside target surface array")
        lods.append(lod)

    return {
        "format": FORMAT,
        "identity": {"name": ident.get("name")},
        "expandedSha256": expanded_sha,
        "source": {
            "assetFixedStart": target_start,
            "targetSerializedEnd": target_walk.get("assetSerializedEnd"),
            "targetSerializedBytes": target_walk.get("assetSerializedBytes"),
            "targetSerializedSha256": target_walk.get("assetSerializedSha256"),
        },
        "xmodel": {
            "numBones": int(tx["numBones"]), "numRootBones": int(tx["numRootBones"]),
            "numSurfs": ns, "numLods": num_lods, "lods": lods,
        },
        "surfaces": surfaces,
        "reuseProof": {
            "owner": owner_meta,
            "borrowedFields": sorted(borrowed_fields),
            "borrowedFieldCount": len(borrowed_fields),
            "allBorrowedFieldsHaveExplicitReplayComparison": True,
            "topLevelSurfsBorrowed": False,
        },
        "validation": {
            "allLocalTriangleIndicesInRange": True,
            "targetHeaderAndLodsAuthoritative": True,
            "targetSurfaceScalarRecordsAuthoritative": True,
            "packedNestedRenderReuseSupported": True,
            "packedTopLevelSurfsSupported": False,
            "packedInlineRigidNestedCollisionTreeSupported": False,
        },
    }


def normalize_mesh(data: bytes, target_start: int, skeleton: dict[str, Any], *, base_module=None, walker_module=None) -> dict[str, Any]:
    here = Path(__file__).resolve().parent
    base = base_module or load_module(here / "t6_xmodel_mesh_normalize_v1.py", "t6_mesh_v3_base")
    walker = walker_module or load_module(here / "t6_xmodel_serialized_walker.py", "t6_mesh_v3_walker")
    source = skeleton.get("skeletonSource") or {}
    owner = source.get("owner") or {}
    owner_start = owner.get("fixedSourceStart")
    if not isinstance(owner_start, int):
        raise ValueError("mesh v3 requires exact reusable owner fixedSourceStart")
    target_walk = walker.XModelWalker(data, target_start).walk_xmodel()
    owner_mesh = base.Normalizer(data, owner_start).normalize()
    return merge_mesh(data, target_start, skeleton, target_walk, owner_mesh, base_module=base)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--asset-start", required=True, type=lambda x: int(x, 0))
    ap.add_argument("--skeleton", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    data = a.expanded.read_bytes(); skeleton = load_json(a.skeleton)
    out = normalize_mesh(data, a.asset_start, skeleton)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(a.out), "name": out["identity"]["name"],
        "surfaces": len(out["surfaces"]),
        "vertices": sum(int(s["vertCount"]) for s in out["surfaces"]),
        "triangles": sum(int(s["triCount"]) for s in out["surfaces"]),
        "borrowedFieldCount": out["reuseProof"]["borrowedFieldCount"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
