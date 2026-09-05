#!/usr/bin/env python3
"""Build a viewable Nuketown preview GLB from exact world/static GLBs and validated texture banks.

This is deliberately a preview assembler. It does not rewrite the frozen retail
geometry/static proof artifacts. Texture attachment is fail-closed: only the
first color/normal identities marked validated by
NUKETOWN_WORLD_TEXTURE_COVERAGE_V1.json are embedded. Static materials only
inherit a validated world binding when their material name matches exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from copy import deepcopy
from pathlib import Path
from typing import Any

PNG_MIME = "image/png"

class PreviewError(RuntimeError):
    pass

def align4(buf: bytearray) -> None:
    while len(buf) % 4:
        buf.append(0)

def read_glb(path: Path) -> tuple[dict[str, Any], bytearray]:
    b = path.read_bytes()
    if len(b) < 20:
        raise PreviewError(f"{path}: too small for GLB")
    magic, version, total = struct.unpack_from("<4sII", b, 0)
    if magic != b"glTF" or version != 2 or total != len(b):
        raise PreviewError(f"{path}: invalid GLB header")
    jlen, jtype = struct.unpack_from("<I4s", b, 12)
    if jtype != b"JSON":
        raise PreviewError(f"{path}: first chunk is not JSON")
    jstart, jend = 20, 20 + jlen
    g = json.loads(b[jstart:jend].rstrip(b" \0"))
    pos = jend
    raw = bytearray()
    if pos + 8 <= len(b):
        blen, btype = struct.unpack_from("<I4s", b, pos)
        if btype != b"BIN\0":
            raise PreviewError(f"{path}: second chunk is not BIN")
        raw = bytearray(b[pos + 8:pos + 8 + blen])
    return g, raw

def write_glb(path: Path, g: dict[str, Any], raw: bytearray) -> None:
    align4(raw)
    g["buffers"] = [{"byteLength": len(raw)}]
    jb = json.dumps(g, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    while len(jb) % 4:
        jb += b" "
    total = 12 + 8 + len(jb)
    if raw:
        total += 8 + len(raw)
    out = bytearray(struct.pack("<4sII", b"glTF", 2, total))
    out += struct.pack("<I4s", len(jb), b"JSON") + jb
    if raw:
        out += struct.pack("<I4s", len(raw), b"BIN\0") + raw
    path.write_bytes(out)

def load_bank(bank_dir: Path) -> dict[str, dict[str, Any]]:
    proof_path = bank_dir / "TEXTURE_EXTRACTION_V1.json"
    proof = json.loads(proof_path.read_text())
    out: dict[str, dict[str, Any]] = {}
    for row in proof.get("rows", []):
        image = row["image"]
        variants = row.get("pngVariants", [])
        if not variants:
            continue
        wanted = "normal" if 5 in [int(x) for x in row.get("semanticSet", [])] else "color"
        choices = [v for v in variants if v.get("role") == wanted]
        if len(choices) != 1:
            if len(variants) == 1:
                choices = variants
            else:
                raise PreviewError(f"{bank_dir}: ambiguous PNG variants for {image}")
        p = bank_dir / choices[0]["file"]
        if not p.is_file():
            raise PreviewError(f"{bank_dir}: missing {p.name}")
        rec = {
            "path": p,
            "sha256": choices[0].get("sha256"),
            "role": choices[0].get("role", wanted),
            "source": bank_dir.name,
        }
        if rec["sha256"] and hashlib.sha256(p.read_bytes()).hexdigest() != rec["sha256"]:
            raise PreviewError(f"{p}: PNG SHA mismatch")
        if image in out:
            raise PreviewError(f"{bank_dir}: duplicate image identity {image}")
        out[image] = rec
    return out

def append_png(g: dict[str, Any], raw: bytearray, png_path: Path, label: str,
               cache: dict[str, int]) -> int:
    payload = png_path.read_bytes()
    key = hashlib.sha256(payload).hexdigest()
    if key in cache:
        return cache[key]
    align4(raw)
    offset = len(raw)
    raw.extend(payload)
    views = g.setdefault("bufferViews", [])
    bv = len(views)
    views.append({
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": len(payload),
        "name": f"preview:{label}",
    })
    images = g.setdefault("images", [])
    ii = len(images)
    images.append({
        "bufferView": bv,
        "mimeType": PNG_MIME,
        "name": label,
    })
    textures = g.setdefault("textures", [])
    ti = len(textures)
    textures.append({"source": ii, "name": label})
    cache[key] = ti
    return ti

def make_identity_normal(path: Path) -> None:
    from PIL import Image
    im = Image.new("RGBA", (1, 1), (128, 128, 255, 255))
    im.save(path, format="PNG", optimize=False)

def material_name(m: dict[str, Any]) -> str:
    t6 = (m.get("extras") or {}).get("T6") or {}
    return str(t6.get("sourceMaterial") or m.get("name") or "")

def attach_validated_world_textures(
    g: dict[str, Any],
    raw: bytearray,
    coverage_path: Path,
    map_bank_dir: Path,
    base_bank_dir: Path,
    identity_png: Path,
) -> dict[str, Any]:
    coverage = json.loads(coverage_path.read_text())
    rows = coverage.get("materials", [])
    by_material = {str(r["material"]): r for r in rows}
    map_bank = load_bank(map_bank_dir)
    base_bank = load_bank(base_bank_dir)
    banks = {"map": map_bank, "base": base_bank}
    cache: dict[str, int] = {}

    stats = {
        "materialsSeen": 0,
        "exactCoverageMatches": 0,
        "colorBindings": 0,
        "normalBindings": 0,
        "visuallyCompleteBindings": 0,
        "unmatchedMaterialNames": [],
    }

    for m in g.get("materials", []):
        stats["materialsSeen"] += 1
        name = material_name(m)
        row = by_material.get(name)
        if row is None:
            stats["unmatchedMaterialNames"].append(name)
            continue
        stats["exactCoverageMatches"] += 1
        pbr = m.setdefault("pbrMetallicRoughness", {})
        pbr.setdefault("metallicFactor", 0.0)
        pbr.setdefault("roughnessFactor", 1.0)
        bound_color = False
        bound_normal = False

        c = row.get("firstColor")
        if c and c.get("validated"):
            source = c.get("source")
            image = c.get("image")
            if source in banks:
                rec = banks[source].get(image)
                if rec is None:
                    raise PreviewError(f"{name}: validated {source} color missing from bank: {image}")
                ti = append_png(g, raw, rec["path"], f"{source}:{image}:color", cache)
                pbr["baseColorTexture"] = {"index": ti, "texCoord": 0}
                pbr.setdefault("baseColorFactor", [1.0, 1.0, 1.0, 1.0])
                bound_color = True

        n = row.get("firstNormal")
        if n and n.get("validated"):
            source = n.get("source")
            image = n.get("image")
            if source == "identity":
                ti = append_png(g, raw, identity_png, "$identitynormalmap", cache)
                m["normalTexture"] = {"index": ti, "texCoord": 0, "scale": 1.0}
                bound_normal = True
            elif source in banks:
                rec = banks[source].get(image)
                if rec is None:
                    raise PreviewError(f"{name}: validated {source} normal missing from bank: {image}")
                ti = append_png(g, raw, rec["path"], f"{source}:{image}:normal", cache)
                m["normalTexture"] = {"index": ti, "texCoord": 0, "scale": 1.0}
                bound_normal = True

        if bound_color:
            stats["colorBindings"] += 1
        if bound_normal:
            stats["normalBindings"] += 1
        if bound_color and bound_normal:
            stats["visuallyCompleteBindings"] += 1

    return stats

def shift_texture_ref(d: dict[str, Any] | None, tex_off: int) -> None:
    if d is not None and "index" in d:
        d["index"] = int(d["index"]) + tex_off

def merge_static_into_world(world_g: dict[str, Any], world_bin: bytearray,
                            static_g: dict[str, Any], static_bin: bytearray) -> dict[str, Any]:
    scene_nodes = list((static_g.get("scenes") or [{}])[0].get("nodes", []))
    if len(scene_nodes) != 1:
        raise PreviewError(f"static GLB: expected one scene root, got {scene_nodes}")
    root_index = int(scene_nodes[0])
    root = static_g.get("nodes", [])[root_index]
    children = [int(x) for x in root.get("children", [])]
    mesh_nodes = [i for i, n in enumerate(static_g.get("nodes", [])) if "mesh" in n]
    if children != mesh_nodes:
        raise PreviewError(
            f"static GLB: root child list does not exactly equal mesh-node population "
            f"({len(children)} vs {len(mesh_nodes)})"
        )
    if len(children) != 1943:
        raise PreviewError(f"static GLB: expected 1943 instances, got {len(children)}")

    align4(world_bin)
    static_bin_offset = len(world_bin)
    world_bin.extend(static_bin)

    bv_off = len(world_g.setdefault("bufferViews", []))
    acc_off = len(world_g.setdefault("accessors", []))
    sampler_off = len(world_g.setdefault("samplers", []))
    image_off = len(world_g.setdefault("images", []))
    tex_off = len(world_g.setdefault("textures", []))
    mat_off = len(world_g.setdefault("materials", []))
    mesh_off = len(world_g.setdefault("meshes", []))

    for bv0 in static_g.get("bufferViews", []):
        bv = deepcopy(bv0)
        bv["buffer"] = 0
        bv["byteOffset"] = int(bv.get("byteOffset", 0)) + static_bin_offset
        world_g["bufferViews"].append(bv)

    for a0 in static_g.get("accessors", []):
        a = deepcopy(a0)
        if "bufferView" in a:
            a["bufferView"] = int(a["bufferView"]) + bv_off
        if "sparse" in a:
            sp = a["sparse"]
            if "indices" in sp and "bufferView" in sp["indices"]:
                sp["indices"]["bufferView"] = int(sp["indices"]["bufferView"]) + bv_off
            if "values" in sp and "bufferView" in sp["values"]:
                sp["values"]["bufferView"] = int(sp["values"]["bufferView"]) + bv_off
        world_g["accessors"].append(a)

    world_g["samplers"].extend(deepcopy(static_g.get("samplers", [])))

    for im0 in static_g.get("images", []):
        im = deepcopy(im0)
        if "bufferView" in im:
            im["bufferView"] = int(im["bufferView"]) + bv_off
        world_g["images"].append(im)

    for t0 in static_g.get("textures", []):
        t = deepcopy(t0)
        if "source" in t:
            t["source"] = int(t["source"]) + image_off
        if "sampler" in t:
            t["sampler"] = int(t["sampler"]) + sampler_off
        world_g["textures"].append(t)

    for m0 in static_g.get("materials", []):
        m = deepcopy(m0)
        pbr = m.get("pbrMetallicRoughness") or {}
        shift_texture_ref(pbr.get("baseColorTexture"), tex_off)
        shift_texture_ref(pbr.get("metallicRoughnessTexture"), tex_off)
        shift_texture_ref(m.get("normalTexture"), tex_off)
        shift_texture_ref(m.get("occlusionTexture"), tex_off)
        shift_texture_ref(m.get("emissiveTexture"), tex_off)
        world_g["materials"].append(m)

    for mesh0 in static_g.get("meshes", []):
        mesh = deepcopy(mesh0)
        for prim in mesh.get("primitives", []):
            if "indices" in prim:
                prim["indices"] = int(prim["indices"]) + acc_off
            attrs = prim.get("attributes") or {}
            for key in list(attrs):
                attrs[key] = int(attrs[key]) + acc_off
            for target in prim.get("targets", []):
                for key in list(target):
                    target[key] = int(target[key]) + acc_off
            if "material" in prim:
                prim["material"] = int(prim["material"]) + mat_off
        world_g["meshes"].append(mesh)

    old_to_new: dict[int, int] = {}
    for old_idx in children:
        n0 = static_g["nodes"][old_idx]
        n = deepcopy(n0)
        n.pop("children", None)
        n["mesh"] = int(n["mesh"]) + mesh_off
        new_idx = len(world_g["nodes"])
        old_to_new[old_idx] = new_idx
        world_g["nodes"].append(n)

    scenes = world_g.setdefault("scenes", [{"nodes": []}])
    if len(scenes) != 1:
        raise PreviewError("world GLB: expected one scene")
    world_top = list(scenes[0].get("nodes", []))
    scenes[0]["nodes"] = world_top + [old_to_new[i] for i in children]

    return {
        "staticRootDropped": True,
        "staticInstances": len(children),
        "worldTopLevelNodesBefore": len(world_top),
        "sceneTopLevelNodesAfter": len(scenes[0]["nodes"]),
        "staticMaterialsAdded": len(static_g.get("materials", [])),
        "staticMeshesAdded": len(static_g.get("meshes", [])),
        "staticBufferBytesAdded": len(static_bin),
    }

def copy_exact_bindings_to_static_materials(g: dict[str, Any], world_material_count: int) -> dict[str, int]:
    world: dict[str, dict[str, Any]] = {}
    for m in g.get("materials", [])[:world_material_count]:
        world[material_name(m)] = m
    stats = {"staticMaterials": 0, "exactNameMatches": 0, "colorInherited": 0, "normalInherited": 0}
    for m in g.get("materials", [])[world_material_count:]:
        stats["staticMaterials"] += 1
        src = world.get(material_name(m))
        if src is None:
            continue
        stats["exactNameMatches"] += 1
        sp = src.get("pbrMetallicRoughness") or {}
        dp = m.setdefault("pbrMetallicRoughness", {})
        if sp.get("baseColorTexture") is not None and dp.get("baseColorTexture") is None:
            dp["baseColorTexture"] = deepcopy(sp["baseColorTexture"])
            dp.setdefault("baseColorFactor", deepcopy(sp.get("baseColorFactor", [1, 1, 1, 1])))
            stats["colorInherited"] += 1
        if src.get("normalTexture") is not None and m.get("normalTexture") is None:
            m["normalTexture"] = deepcopy(src["normalTexture"])
            stats["normalInherited"] += 1
    return stats

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", type=Path, required=True)
    ap.add_argument("--static", type=Path, required=True)
    ap.add_argument("--coverage", type=Path, required=True)
    ap.add_argument("--map-bank", type=Path, required=True)
    ap.add_argument("--base-bank", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--proof", type=Path, required=True)
    args = ap.parse_args()

    world_g, world_bin = read_glb(args.world)
    static_g, static_bin = read_glb(args.static)
    world_material_count = len(world_g.get("materials", []))
    if world_material_count != 327:
        raise PreviewError(f"world material count changed: {world_material_count}")
    if len((world_g.get("scenes") or [{}])[0].get("nodes", [])) != 340:
        raise PreviewError("world GLB is not the frozen 340-top-level-node geometry export")

    identity_png = args.out.with_suffix(".identity-normal.png")
    make_identity_normal(identity_png)
    tex_stats = attach_validated_world_textures(
        world_g, world_bin, args.coverage, args.map_bank, args.base_bank, identity_png
    )
    if tex_stats["exactCoverageMatches"] != 327:
        raise PreviewError(f"world coverage name match count changed: {tex_stats}")
    if tex_stats["colorBindings"] != 259:
        raise PreviewError(f"world color binding count changed: {tex_stats}")
    if tex_stats["normalBindings"] != 300:
        raise PreviewError(f"world normal binding count changed: {tex_stats}")
    if tex_stats["visuallyCompleteBindings"] != 259:
        raise PreviewError(f"world complete binding count changed: {tex_stats}")

    merge_stats = merge_static_into_world(world_g, world_bin, static_g, static_bin)
    static_tex_stats = copy_exact_bindings_to_static_materials(world_g, world_material_count)

    scene_nodes = world_g["scenes"][0]["nodes"]
    if len(scene_nodes) != 340 + 1943:
        raise PreviewError(f"combined top-level node count changed: {len(scene_nodes)}")
    if any("children" in world_g["nodes"][i] for i in scene_nodes):
        raise PreviewError("combined scene still contains parented top-level nodes")

    extras = world_g.setdefault("extras", {})
    t6 = extras.setdefault("T6", {})
    t6["preview"] = {
        "format": "t6-nuketown-world-plus-1943-statics-validated-texture-preview-v1",
        "proofBoundary": (
            "Geometry and placements come from their frozen proof GLBs. "
            "World texture bindings are restricted to exact validated first-color/first-normal "
            "coverage rows. Static texture inheritance is exact material-name match only. "
            "No unresolved texture is replaced by a guessed fallback."
        ),
        "worldTextureBindings": tex_stats,
        "staticMerge": merge_stats,
        "staticTextureInheritance": static_tex_stats,
    }

    write_glb(args.out, world_g, world_bin)
    identity_png.unlink(missing_ok=True)

    b = args.out.read_bytes()
    proof = {
        "format": "t6-nuketown-world-plus-1943-statics-validated-texture-preview-v1",
        "file": args.out.name,
        "bytes": len(b),
        "sha256": hashlib.sha256(b).hexdigest(),
        "worldMaterials": 327,
        "worldPrimaryColorBound": tex_stats["colorBindings"],
        "worldPrimaryNormalBound": tex_stats["normalBindings"],
        "worldPrimaryColorNormalComplete": tex_stats["visuallyCompleteBindings"],
        "sceneTopLevelNodes": len(scene_nodes),
        "worldTopLevelNodes": 340,
        "staticTopLevelNodes": 1943,
        "flatHierarchy": True,
        "staticTextureInheritance": static_tex_stats,
        "remainingUnresolvedWorldPrimaryColors": 327 - tex_stats["colorBindings"],
        "remainingUnresolvedWorldPrimaryNormals": 316 - tex_stats["normalBindings"],
    }
    args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps(proof, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
