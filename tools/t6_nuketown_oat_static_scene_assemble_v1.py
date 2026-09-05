#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import itertools
import json
import math
import struct
import zlib
from pathlib import Path

METER = 0.0254
C = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
CT = tuple(zip(*C))
RECOVERED = {
    221: "dest_nt_nuked_male_01_d0",
    230: "dest_nt_nuked_female_01_d0",
    262: "nt_2020_flag_nuclear_01",
    263: "nt_2020_flag_nuclear_02",
    273: "dest_nt_nuked_female_02_d0",
    274: "dest_nt_nuked_female_03_d0",
    306: "nt_2020_flag_england_01",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def tr(a):
    return [list(x) for x in zip(*a)]


def load_json(path: Path):
    raw = path.read_bytes()
    try:
        return json.loads(raw)
    except Exception:
        try:
            return json.loads(zlib.decompress(base64.b64decode(raw)).decode())
        except Exception as exc:
            raise ValueError(f"{path}: neither plain JSON nor zlib/base64 JSON") from exc


def read_glb(path: Path):
    data = path.read_bytes()
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError(f"{path}: invalid GLB")
    off = 12
    root = None
    bins = []
    while off < total:
        length, kind = struct.unpack_from("<I4s", data, off)
        off += 8
        chunk = data[off:off + length]
        off += length
        if kind == b"JSON":
            root = json.loads(chunk.rstrip(b" \0"))
        elif kind == b"BIN\0":
            bins.append(chunk)
    if root is None or len(bins) != 1:
        raise ValueError(f"{path}: expected one JSON/BIN")
    return root, bins[0]


def write_glb(path: Path, root, binbuf: bytearray):
    while len(binbuf) % 4:
        binbuf.append(0)
    root["buffers"] = [{"byteLength": len(binbuf)}]
    jb = json.dumps(root, separators=(",", ":"), ensure_ascii=False).encode()
    while len(jb) % 4:
        jb += b" "
    out = bytearray(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(jb) + 8 + len(binbuf)))
    out += struct.pack("<I4s", len(jb), b"JSON") + jb
    out += struct.pack("<I4s", len(binbuf), b"BIN\0") + binbuf
    path.write_bytes(out)


def resolve_proof_names(proof):
    out = []
    for row in proof["models"]:
        name = row.get("xmodelName") or RECOVERED.get(int(row["xassetIndex"]))
        if not name:
            raise ValueError(f"unresolved retained XModel xasset {row['xassetIndex']}")
        out.append(name)
    if len(out) != 297 or len(set(out)) != 297:
        raise ValueError("expected 297 unique playable static XModel definitions")
    return out


def source_bbox_from_oat(root):
    mins = [math.inf] * 3
    maxs = [-math.inf] * 3
    found = False
    pos_ids = set()
    for mesh in root.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if "POSITION" in primitive.get("attributes", {}):
                pos_ids.add(primitive["attributes"]["POSITION"])
    for accessor_index in pos_ids:
        accessor = root["accessors"][accessor_index]
        if "min" not in accessor or "max" not in accessor:
            continue
        for point in itertools.product(*zip(accessor["min"], accessor["max"])):
            source = mv(CT, point)
            for k in range(3):
                mins[k] = min(mins[k], source[k])
                maxs[k] = max(maxs[k], source[k])
        found = True
    if not found:
        raise ValueError("model has no bounded POSITION accessor")
    return mins, maxs


def transformed_bbox(local_min, local_max, row, convention):
    axis = [list(map(float, v)) for v in row["axis"]]
    a = tr(axis) if convention == "basis-vectors" else axis
    origin = list(map(float, row["origin"]))
    scale = float(row["scale"])
    mins = [math.inf] * 3
    maxs = [-math.inf] * 3
    for point in itertools.product(*zip(local_min, local_max)):
        world = mv(a, point)
        world = [origin[k] + scale * world[k] for k in range(3)]
        for k in range(3):
            mins[k] = min(mins[k], world[k])
            maxs[k] = max(maxs[k], world[k])
    return mins, maxs


def calibrate_axis(rows, model_bounds):
    scores = {}
    for convention in ("basis-vectors", "matrix-rows"):
        errors = []
        for row in rows[: min(len(rows), 512)]:
            bounds = model_bounds.get(row["model"])
            if not bounds:
                continue
            lo, hi = transformed_bbox(*bounds, row, convention)
            target_lo = row["mins"]
            target_hi = row["maxs"]
            errors.append(
                sum(abs(lo[k] - target_lo[k]) + abs(hi[k] - target_hi[k]) for k in range(3)) / 6.0
            )
        if not errors:
            raise ValueError("no rows available for axis calibration")
        errors.sort()
        scores[convention] = {
            "medianAbsBoundError": errors[len(errors) // 2],
            "meanAbsBoundError": sum(errors) / len(errors),
            "samples": len(errors),
        }
    chosen = min(scores, key=lambda x: scores[x]["medianAbsBoundError"])
    other = next(x for x in scores if x != chosen)
    if scores[chosen]["medianAbsBoundError"] >= scores[other]["medianAbsBoundError"] * 0.95:
        raise ValueError(f"axis convention ambiguous: {scores}")
    return chosen, scores


def gltf_matrix(row, convention):
    axis = [list(map(float, v)) for v in row["axis"]]
    a = tr(axis) if convention == "basis-vectors" else axis
    rg = mm(mm(C, a), CT)
    factor = float(row["scale"]) * METER
    linear = [[rg[i][j] * factor for j in range(3)] for i in range(3)]
    translation = [x * METER for x in mv(C, list(map(float, row["origin"])))]
    return [
        linear[0][0], linear[1][0], linear[2][0], 0.0,
        linear[0][1], linear[1][1], linear[2][1], 0.0,
        linear[0][2], linear[1][2], linear[2][2], 0.0,
        translation[0], translation[1], translation[2], 1.0,
    ]


def build(placements_path: Path, proof_path: Path, model_dir: Path, out_path: Path,
          manifest_path: Path, expected: int = 1943, full_smodel_count: int = 2992):
    placements = load_json(placements_path)
    proof = load_json(proof_path)
    names = resolve_proof_names(proof)
    name_set = set(names)

    selected = [row for row in placements["placements"] if row["model"] in name_set]
    selected_models = {row["model"] for row in selected}
    if len(selected) != expected:
        raise ValueError(f"placement input yielded {len(selected)} proof-backed rows, expected {expected}")
    unknown = sorted(selected_models - name_set)
    if unknown:
        raise ValueError(f"selected rows contain models outside retained proof: {unknown[:20]}")
    uninstantiated_definitions = sorted(name_set - selected_models)

    root = {
        "asset": {"version": "2.0", "generator": "bo2-t6-assets Nuketown OAT static assembler v2"},
        "scene": 0,
        "scenes": [{"name": "mp_nuketown_2020_static", "nodes": [0]}],
        "nodes": [{"name": "T6_PLAYABLE_STATIC_ROOT", "children": []}],
        "meshes": [],
        "materials": [],
        "accessors": [],
        "bufferViews": [],
        "buffers": [{"byteLength": 0}],
        "extras": {"T6": {"source": "retail GfxWorld placements + OAT v0.33.0 LOD0 XModels"}},
    }
    binbuf = bytearray()
    material_index = {}
    model_mesh = {}
    model_bounds = {}
    primitive_slots = 0
    proof_by_name = {name: row for name, row in zip(names, proof["models"])}

    # Import every retained definition even when the playable spatial partition
    # leaves that definition uninstantiated. This preserves the historical
    # definition-level 297/538/344 proof boundary.
    for name in names:
        file_path = model_dir / (name + "_lod0.glb")
        if not file_path.exists():
            raise FileNotFoundError(file_path)
        src, src_bin = read_glb(file_path)
        for node in src.get("nodes", []):
            if "mesh" in node and any(k in node for k in ("translation", "rotation", "scale", "matrix")):
                raise ValueError(f"{name}: transformed mesh node cannot be flattened safely")
        model_bounds[name] = source_bbox_from_oat(src)

        while len(binbuf) % 4:
            binbuf.append(0)
        bin_base = len(binbuf)
        binbuf.extend(src_bin)
        bv_base = len(root["bufferViews"])
        accessor_base = len(root["accessors"])

        for bv in src.get("bufferViews", []):
            copied = copy.deepcopy(bv)
            copied["buffer"] = 0
            copied["byteOffset"] = bin_base + copied.get("byteOffset", 0)
            root["bufferViews"].append(copied)
        for accessor in src.get("accessors", []):
            copied = copy.deepcopy(accessor)
            if "bufferView" in copied:
                copied["bufferView"] = bv_base + copied["bufferView"]
            if "sparse" in copied:
                raise ValueError(f"{name}: sparse accessor unsupported in static assembler")
            root["accessors"].append(copied)

        primitives = []
        used_materials = []
        for mesh in src.get("meshes", []):
            for primitive in mesh.get("primitives", []):
                copied = copy.deepcopy(primitive)
                copied["attributes"] = {
                    k: accessor_base + v
                    for k, v in copied.get("attributes", {}).items()
                    if not (k.startswith("JOINTS_") or k.startswith("WEIGHTS_"))
                }
                if "indices" in copied:
                    copied["indices"] = accessor_base + copied["indices"]
                if "targets" in copied:
                    copied["targets"] = [
                        {k: accessor_base + v for k, v in target.items()} for target in copied["targets"]
                    ]
                src_material_index = copied.get("material")
                if src_material_index is None:
                    raise ValueError(f"{name}: primitive without material")
                material_name = src["materials"][src_material_index].get("name")
                if not material_name:
                    raise ValueError(f"{name}: unnamed primitive material")
                used_materials.append(material_name)
                if material_name not in material_index:
                    material_index[material_name] = len(root["materials"])
                    root["materials"].append({
                        "name": material_name,
                        "pbrMetallicRoughness": {
                            "baseColorFactor": [1, 1, 1, 1],
                            "metallicFactor": 0.0,
                            "roughnessFactor": 1.0,
                        },
                        "doubleSided": True,
                    })
                copied["material"] = material_index[material_name]
                primitives.append(copied)
                primitive_slots += 1

        if used_materials != proof_by_name[name]["materials"]:
            raise ValueError(f"{name}: OAT LOD0 primitive/material sequence diverged from retained proof")
        model_mesh[name] = len(root["meshes"])
        root["meshes"].append({
            "name": name,
            "primitives": primitives,
            "extras": {"T6": {"xassetIndex": proof_by_name[name]["xassetIndex"], "lod": 0}},
        })

    convention, scores = calibrate_axis(selected, model_bounds)
    for row in selected:
        node_index = len(root["nodes"])
        root["nodes"].append({
            "name": f"smodel_{row['index']:04d}_{row['model']}",
            "mesh": model_mesh[row["model"]],
            "matrix": gltf_matrix(row, convention),
            "extras": {
                "T6": {
                    "smodelIndex": row["index"],
                    "cullDist": row["cullDist"],
                    "flags": row["flags"],
                    "visibility": row.get("visibility"),
                    "reflectionProbeIndex": row.get("reflectionProbeIndex"),
                    "sourceOrigin": row["origin"],
                    "sourceScale": row["scale"],
                    "sourceMins": row.get("mins"),
                    "sourceMaxs": row.get("maxs"),
                }
            },
        })
        root["nodes"][0]["children"].append(node_index)

    retained_full_count = int(placements.get("smodelCount", placements.get("fullGfxWorldSmodelCount", full_smodel_count)))
    root["extras"]["T6"].update({
        "fullGfxWorldSmodelCount": retained_full_count,
        "playablePlacementCount": len(selected),
        "playableDefinitionXModels": len(names),
        "referencedPlayableXModels": len(selected_models),
        "uninstantiatedDefinitionXModels": uninstantiated_definitions,
        "axisConvention": convention,
        "axisCalibration": scores,
        "metersPerGameUnit": METER,
    })

    write_glb(out_path, root, binbuf)
    check, _ = read_glb(out_path)
    if len(check["nodes"]) != expected + 1 or len(check["meshes"]) != 297:
        raise ValueError("output structural regression")
    if len(check["materials"]) != 344 or primitive_slots != 538:
        raise ValueError("retained definition-level material/primitive proof regression")

    manifest = {
        "format": "t6-nuketown-oat-playable-static-scene-v2",
        "inputs": {
            "placements": {"file": placements_path.name, "sha256": sha(placements_path)},
            "proof": {"file": proof_path.name, "sha256": sha(proof_path)},
        },
        "summary": {
            "fullGfxWorldSmodelCount": retained_full_count,
            "playablePlacementCount": len(selected),
            "definitionXModels": len(names),
            "referencedXModels": len(selected_models),
            "uninstantiatedDefinitionXModels": uninstantiated_definitions,
            "meshDefinitions": len(root["meshes"]),
            "rootPlusInstanceNodes": len(root["nodes"]),
            "uniqueMaterials": len(root["materials"]),
            "uniqueModelPrimitiveSlots": primitive_slots,
            "axisConvention": convention,
            "axisCalibration": scores,
        },
        "output": {"file": out_path.name, "bytes": out_path.stat().st_size, "sha256": sha(out_path)},
        "proofBoundary": (
            "Placement membership is supplied by the separately fail-closed 1943-row playable-bounds proof. "
            "All 297 retained XModel definitions are imported from exact OAT v0.33.0 LOD0 GLBs and their "
            "primitive/material sequences must match the retained 538-slot/344-material proof. Definitions are "
            "allowed to remain uninstantiated after spatial cropping. GfxWorld axis interpretation is selected "
            "only by independent GfxStaticModelInst bounds agreement; ambiguous conventions fail closed."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placements", type=Path, required=True)
    ap.add_argument("--proof", type=Path, required=True)
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--expected", type=int, default=1943)
    ap.add_argument("--full-smodel-count", type=int, default=2992)
    args = ap.parse_args()
    result = build(
        args.placements,
        args.proof,
        args.model_dir,
        args.out,
        args.manifest,
        args.expected,
        args.full_smodel_count,
    )
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
