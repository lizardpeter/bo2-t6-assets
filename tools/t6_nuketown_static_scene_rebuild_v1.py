#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, json, struct
from pathlib import Path

M_PER_T6 = 0.0254
FORMAT = "t6-nuketown-static-scene-rebuild-v1"

class RebuildError(RuntimeError):
    pass

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def read_glb(path: Path):
    b = path.read_bytes()
    if len(b) < 20:
        raise RebuildError(f"{path}: GLB too short")
    magic, ver, total = struct.unpack_from("<4sII", b, 0)
    if magic != b"glTF" or ver != 2 or total != len(b):
        raise RebuildError(f"{path}: invalid GLB2")
    o = 12
    js = None
    bins = []
    while o < total:
        n, t = struct.unpack_from("<I4s", b, o)
        o += 8
        c = b[o:o+n]
        o += n
        if t == b"JSON":
            js = json.loads(c)
        elif t == b"BIN\0":
            bins.append(c)
    if js is None or len(bins) != 1:
        raise RebuildError(f"{path}: expected one JSON and one BIN")
    return js, bins[0]

def align4(buf: bytearray):
    while len(buf) & 3:
        buf.append(0)

def write_glb(path: Path, js: dict, binbuf: bytearray):
    align4(binbuf)
    js["buffers"] = [{"byteLength": len(binbuf)}]
    jb = json.dumps(js, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    total = 12 + 8 + len(jb) + 8 + len(binbuf)
    out = bytearray(struct.pack("<4sII", b"glTF", 2, total))
    out += struct.pack("<I4s", len(jb), b"JSON") + jb
    out += struct.pack("<I4s", len(binbuf), b"BIN\0") + binbuf
    path.write_bytes(out)
    return bytes(out)

def matmul3(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]

def transpose3(a):
    return [[a[c][r] for c in range(3)] for r in range(3)]

# C maps T6 RH Z-up vectors to glTF RH Y-up: (x,y,z)->(x,z,-y).
_C = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
_CI = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]

def placement_matrix(inst):
    a = [[float(x) for x in row] for row in inst["axis"]]
    # GfxStaticModelDrawInst axis stores basis vectors as rows. Local->world is A^T.
    r = matmul3(matmul3(_C, transpose3(a)), _CI)
    s = float(inst["scale"])
    r = [[x * s for x in row] for row in r]
    x, y, z = [float(x) for x in inst["origin"]]
    tx, ty, tz = x * M_PER_T6, z * M_PER_T6, -y * M_PER_T6
    # glTF matrices are column-major.
    return [
        r[0][0], r[1][0], r[2][0], 0.0,
        r[0][1], r[1][1], r[2][1], 0.0,
        r[0][2], r[1][2], r[2][2], 0.0,
        tx, ty, tz, 1.0,
    ]

def build(placements_path: Path, model_root: Path, index_path: Path):
    placements = json.loads(placements_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if len(placements.get("instances", [])) != 2992:
        raise RebuildError("expected 2992 static placements")
    if int(index.get("modelsExported", -1)) != 349:
        raise RebuildError("expected 349 exported static XModels")
    idx_by_xasset = {int(m["xassetIndex"]): m for m in index["models"]}
    if len(idx_by_xasset) != 349:
        raise RebuildError("duplicate xasset indices in model index")

    js = {
        "asset": {"version": "2.0", "generator": "t6_nuketown_static_scene_rebuild_v1.py"},
        "scene": 0,
        "scenes": [],
        "nodes": [],
        "meshes": [],
        "materials": [],
        "buffers": [{"byteLength": 0}],
        "bufferViews": [],
        "accessors": [],
        "extras": {"T6": {"staticSceneRebuildV1": {
            "format": FORMAT,
            "map": "mp_nuketown_2020",
            "sourceExpandedSha256": index.get("sourceExpandedSha256"),
            "staticPlacementCountSerialized": 2992,
            "staticModelCount": 349,
            "coordinateConversion": "T6 (x,y,z) Z-up -> glTF (x,z,-y) Y-up",
            "metersPerT6Unit": M_PER_T6,
            "policy": "full archival static-placement layer; reflection proxies and fxanim support remain preserved and are scene-filtered only in later full-map promotion"
        }}}
    }
    blob = bytearray()
    material_cache = {}
    mesh_by_xasset = {}

    def map_material(srcmat):
        name = str(srcmat.get("name") or "")
        if name in material_cache:
            return material_cache[name]
        mi = len(js["materials"])
        material_cache[name] = mi
        js["materials"].append(copy.deepcopy(srcmat))
        return mi

    for model in index["models"]:
        xa = int(model["xassetIndex"])
        lod0 = next((f for f in model.get("files", []) if int(f.get("lod", -1)) == 0), None)
        if lod0 is None:
            raise RebuildError(f"xasset {xa}: missing LOD0")
        p = model_root / lod0["file"]
        sj, sb = read_glb(p)
        if sha256(p.read_bytes()) != str(lod0["sha256"]).lower():
            raise RebuildError(f"{p}: SHA mismatch")
        if len(sj.get("meshes", [])) != 1:
            raise RebuildError(f"{p}: expected exactly one mesh")
        base_view = len(js["bufferViews"])
        base_acc = len(js["accessors"])
        align4(blob)
        base_off = len(blob)
        blob.extend(sb)
        for v in sj.get("bufferViews", []):
            nv = copy.deepcopy(v)
            nv["buffer"] = 0
            nv["byteOffset"] = base_off + int(v.get("byteOffset", 0))
            js["bufferViews"].append(nv)
        for a in sj.get("accessors", []):
            na = copy.deepcopy(a)
            na["bufferView"] = base_view + int(a["bufferView"])
            js["accessors"].append(na)
        nm = copy.deepcopy(sj["meshes"][0])
        for pr in nm.get("primitives", []):
            pr["attributes"] = {k: base_acc + int(v) for k, v in pr.get("attributes", {}).items()}
            if "indices" in pr:
                pr["indices"] = base_acc + int(pr["indices"])
            oldmat = pr.get("material")
            if oldmat is not None:
                pr["material"] = map_material(sj["materials"][int(oldmat)])
        mesh_index = len(js["meshes"])
        js["meshes"].append(nm)
        mesh_by_xasset[xa] = mesh_index

    js["nodes"].append({
        "name": "NUKETOWN_STATIC_XMODEL_PLACEMENTS_ARCHIVE",
        "children": [],
        "extras": {"placementCount": 2992, "uniqueXModels": 349, "role": "full-archive"}
    })
    null_name_count = 0
    fxanim = []
    for inst in placements["instances"]:
        i = int(inst["index"])
        xa = int(inst["xassetIndex"])
        model = idx_by_xasset.get(xa)
        if model is None:
            raise RebuildError(f"placement {i}: unresolved xasset {xa}")
        model_name = inst.get("modelName")
        if model_name is None:
            null_name_count += 1
            model_name = f"xasset_{xa:04d}"
        ni = len(js["nodes"])
        js["nodes"].append({
            "name": f"static_{i:04d}__{str(model_name).replace('/', '__')}",
            "mesh": mesh_by_xasset[xa],
            "matrix": placement_matrix(inst),
            "extras": {
                "staticModelInstanceIndex": i,
                "xassetIndex": xa,
                "modelName": model_name,
                "cullDistT6": float(inst.get("cullDist", 0.0)),
                "smid": int(inst.get("smid", 0))
            }
        })
        js["nodes"][0]["children"].append(ni)
        if str(model_name).lower().startswith("fxanim_"):
            fxanim.append(i)
    if len(js["nodes"][0]["children"]) != 2992:
        raise RebuildError("placement node count mismatch")
    js["scenes"] = [{"name": "NUKETOWN_STATIC_ARCHIVE", "nodes": [0], "extras": {"role": "archive", "placementCount": 2992}}]
    js["extras"]["T6"]["staticSceneRebuildV1"].update({"anonymousPlacementNameCount": null_name_count, "fxanimPlacementIndices": fxanim})
    return js, blob

def inspect_counts(js):
    prims = sum(len(m.get("primitives", [])) for m in js.get("meshes", []))
    tris = 0
    for m in js.get("meshes", []):
        for p in m.get("primitives", []):
            ai = p.get("indices")
            if isinstance(ai, int):
                tris += int(js["accessors"][ai].get("count", 0)) // 3
    return {
        "meshCount": len(js.get("meshes", [])),
        "materialCount": len(js.get("materials", [])),
        "nodeCount": len(js.get("nodes", [])),
        "placementCount": len(js["nodes"][0].get("children", [])),
        "primitiveDefinitions": prims,
        "triangleDefinitions": tris,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placements", type=Path, required=True)
    ap.add_argument("--model-root", type=Path, required=True)
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    a = ap.parse_args()
    js, blob = build(a.placements, a.model_root, a.index)
    out = write_glb(a.out, js, blob)
    manifest = {
        "format": FORMAT,
        "output": {"file": a.out.name, "bytes": len(out), "sha256": sha256(out)},
        "stats": inspect_counts(js),
        "source": {
            "placements": a.placements.name,
            "modelIndex": a.index.name,
            "sourceExpandedSha256": json.loads(a.index.read_text())["sourceExpandedSha256"]
        },
        "validation": {"all349Lod0GlbHashesMatched": True, "all2992PlacementXassetsResolved": True}
    }
    a.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
