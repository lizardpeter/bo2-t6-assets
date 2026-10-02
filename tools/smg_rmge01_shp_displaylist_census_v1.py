#!/usr/bin/env python3
"""Census GX commands inside exact RMGE01 J3D SHP1 display lists.

Retail files are fetched transiently from the existing public R2 mirror. Only
structural counts are retained. This specifically answers whether the
source-private Rust importer can fail closed on GX LOAD_INDX_* commands without
silently losing common SMG geometry.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import hashlib
import json
from pathlib import Path

import smg_rmge01_j3d_material_census_v1 as common

BASE_DEFAULT = common.BASE_DEFAULT
H_ZONE = common.H_ZONE
H_NAME = common.H_NAME

ATTR_PNMTXIDX = 0
ATTR_POS = 9
ATTR_NRM = 10
ATTR_CLR0 = 11
ATTR_CLR1 = 12
ATTR_TEX0 = 13
ATTR_TEX7 = 20
ATTR_NBT = 25
ATTR_NULL = 0xFF

DIRECT = 1
INDEX8 = 2
INDEX16 = 3

MATRIX_COMMANDS = {0x20: "LOAD_INDX_A", 0x28: "LOAD_INDX_B", 0x30: "LOAD_INDX_C", 0x38: "LOAD_INDX_D"}
DRAW_COMMANDS = {0x80:"QUADS",0x88:"QUAD_STRIP",0x90:"TRIANGLES",0x98:"TRIANGLE_STRIP",0xA0:"TRIANGLE_FAN",0xA8:"LINES",0xB0:"LINE_STRIP",0xB8:"POINTS"}


def byte_size_for_format(attr: int, comp_cnt: int, comp_type: int) -> int:
    if attr <= 8:
        return 1
    if attr in (ATTR_CLR0, ATTR_CLR1):
        return {0:2, 1:3, 2:4, 3:2, 4:3, 5:4}[comp_type]
    if attr == ATTR_POS:
        comps = 2 if comp_cnt == 0 else 3
    elif attr in (ATTR_NRM, ATTR_NBT):
        comps = 3 if comp_cnt == 0 else 9
    elif ATTR_TEX0 <= attr <= ATTR_TEX7:
        comps = 1 if comp_cnt == 0 else 2
    else:
        raise ValueError(f"unsupported direct attr {attr}")
    component_bytes = {0:1, 1:1, 2:2, 3:2, 4:4}[comp_type]
    return comps * component_bytes


def parse_vtx1(sec: bytes):
    fmt_off = common.be32(sec, 0x08)
    formats = {}
    o = fmt_off
    while True:
        attr = common.be32(sec, o)
        if attr == ATTR_NULL:
            break
        formats[attr] = (
            common.be32(sec, o + 4),
            common.be32(sec, o + 8),
            sec[o + 0x0C],
        )
        o += 0x10
    return formats


def parse_vcd(sec: bytes, off: int, formats):
    out = []
    for _ in range(64):
        attr = common.be32(sec, off)
        if attr == ATTR_NULL:
            return out
        ty = common.be32(sec, off + 4)
        if attr <= 8:
            if ty != DIRECT:
                raise ValueError(f"matrix attr {attr} VCD type {ty}")
            size = 1
        elif ty == INDEX8:
            size = 1
        elif ty == INDEX16:
            size = 2
        elif ty == DIRECT:
            fmt = formats.get(attr)
            if fmt is None and attr == ATTR_NBT:
                fmt = formats.get(ATTR_NRM)
                if fmt is not None:
                    fmt = (1, fmt[1], fmt[2])
            if fmt is None:
                raise ValueError(f"direct attr {attr} missing VTX1 format")
            size = byte_size_for_format(attr, fmt[0], fmt[1])
        else:
            raise ValueError(f"attr {attr} VCD type {ty}")
        out.append((attr, ty, size))
        off += 8
    raise ValueError("unterminated VCD")


def walk_dl(dl: bytes, vertex_bytes: int):
    cursor = 0
    counts = collections.Counter()
    matrix = collections.Counter()
    unknown = collections.Counter()
    draws = 0
    vertices = 0

    while cursor < len(dl):
        cmd = dl[cursor]
        counts[f"0x{cmd:02x}"] += 1
        if cmd == 0x00:
            cursor += 1
            continue
        if cmd in MATRIX_COMMANDS:
            matrix[MATRIX_COMMANDS[cmd]] += 1
            if cursor + 5 > len(dl):
                raise ValueError("truncated matrix load")
            cursor += 5
            continue

        primitive = cmd & 0xF8
        if primitive in DRAW_COMMANDS:
            if cursor + 3 > len(dl):
                raise ValueError("truncated draw header")
            count = common.be16(dl, cursor + 1)
            payload = count * vertex_bytes
            end = cursor + 3 + payload
            if end > len(dl):
                raise ValueError(
                    f"{DRAW_COMMANDS[primitive]} payload overruns DL: {count}*{vertex_bytes}"
                )
            draws += 1
            vertices += count
            cursor = end
            continue

        # These GX state commands are not expected in J3D SHP packets. Record
        # and stop rather than inventing a byte length and desynchronizing.
        unknown[f"0x{cmd:02x}"] += 1
        break

    return {
        "command_counts": dict(counts),
        "matrix_load_counts": dict(matrix),
        "unknown_commands": dict(unknown),
        "draws": draws,
        "vertices": vertices,
        "fully_walked": cursor >= len(dl),
        "end_offset": cursor,
        "size": len(dl),
    }


def inspect_model(model: bytes, model_name: str):
    secs = common.j3d_sections(model)
    if "VTX1" not in secs or "SHP1" not in secs:
        raise ValueError("missing VTX1/SHP1")
    formats = parse_vtx1(secs["VTX1"])
    shp = secs["SHP1"]
    shape_count = common.be16(shp, 0x08)
    shape_init = common.be32(shp, 0x0C)
    remap = common.be32(shp, 0x10)
    decl_base = common.be32(shp, 0x18)
    dl_base = common.be32(shp, 0x20)
    draw_init = common.be32(shp, 0x28)

    result = []
    for logical in range(shape_count):
        physical = common.be16(shp, remap + logical * 2)
        init = shape_init + physical * 0x28
        mtx_type = shp[init]
        group_count = common.be16(shp, init + 2)
        decl_index = common.be16(shp, init + 4)
        draw_index = common.be16(shp, init + 8)
        vcd = parse_vcd(shp, decl_base + decl_index, formats)
        vertex_bytes = sum(item[2] for item in vcd)

        for group in range(group_count):
            d = draw_init + (draw_index + group) * 8
            size = common.be32(shp, d)
            rel = common.be32(shp, d + 4)
            dl = shp[dl_base + rel:dl_base + rel + size]
            walk = walk_dl(dl, vertex_bytes)
            result.append({
                "model": model_name,
                "shape": logical,
                "matrix_type": mtx_type,
                "group": group,
                "vertex_record_bytes": vertex_bytes,
                **walk,
            })
    return result


def collect_objects(base: str, galaxy: str, max_objects: int):
    scenario = common.rarc_files(common.fetch(f"{base}/StageData/{galaxy}/{galaxy}Scenario.arc"))
    zone_rows = []
    for name, payload in scenario:
        if name.lower() == "zonelist.bcsv":
            zone_rows = common.bcsv_rows(payload)
            break
    zones = [r.get(H_ZONE) for r in zone_rows if isinstance(r.get(H_ZONE), str)]
    if not zones:
        raise RuntimeError("ZoneList.bcsv yielded no zones")

    object_names = set()
    for zone in zones:
        try:
            files = common.rarc_files(common.fetch(f"{base}/StageData/{zone}.arc"))
        except Exception:
            continue
        for name, payload in files:
            if name.lower() == "stageobjinfo":
                continue
            try:
                rows = common.bcsv_rows(payload)
            except Exception:
                continue
            for row in rows:
                value = row.get(H_NAME)
                if isinstance(value, str) and value and len(value) < 128:
                    object_names.add(value)
    return zones, sorted(object_names)[:max_objects]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--galaxy", default="EggStarGalaxy")
    ap.add_argument("--max-objects", type=int, default=220)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    base = a.base.rstrip("/")
    zones, objects = collect_objects(base, a.galaxy, a.max_objects)

    def inspect_object(obj):
        try:
            arc = common.rarc_files(common.fetch(common.object_url(base, obj)))
        except Exception as exc:
            return obj, None, {"object": obj, "stage": "download", "error": str(exc)}
        models = [(n,p) for n,p in arc if n.lower().endswith((".bdl",".bmd"))]
        if not models:
            return obj, None, None
        models.sort(key=lambda x:(x[0].rsplit(".",1)[0].lower()!=obj.lower(),x[0].lower()))
        name, model = models[0]
        try:
            return obj, inspect_model(model, obj), None
        except Exception as exc:
            return obj, None, {"object":obj,"model_file":name,"stage":"displaylist","error":str(exc)}

    inspected = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        inspected.extend(pool.map(inspect_object, objects))

    groups = []
    failures = []
    models_parsed = 0
    for _, payload, error in inspected:
        if error is not None:
            failures.append(error)
        elif payload is not None:
            models_parsed += 1
            groups.extend(payload)

    matrix = collections.Counter()
    commands = collections.Counter()
    matrix_types = collections.Counter()
    unknown = collections.Counter()
    affected_models = set()
    affected_shapes = set()
    fully_walked = 0
    for row in groups:
        matrix_types[str(row["matrix_type"])] += 1
        commands.update(row["command_counts"])
        unknown.update(row["unknown_commands"])
        matrix.update(row["matrix_load_counts"])
        if row["fully_walked"]:
            fully_walked += 1
        if row["matrix_load_counts"]:
            affected_models.add(row["model"])
            affected_shapes.add((row["model"], row["shape"]))

    result = {
        "source":{"base":base,"galaxy":a.galaxy},
        "counts":{
            "zones":len(zones),
            "objects_attempted":len(objects),
            "models_parsed":models_parsed,
            "matrix_groups":len(groups),
            "fully_walked_groups":fully_walked,
            "failures":len(failures),
            "models_with_matrix_loads":len(affected_models),
            "shapes_with_matrix_loads":len(affected_shapes),
        },
        "matrix_load_counts":dict(sorted(matrix.items())),
        "shape_group_matrix_type_counts":dict(sorted(matrix_types.items())),
        "gx_command_counts":dict(sorted(commands.items())),
        "unknown_command_counts":dict(sorted(unknown.items())),
        "matrix_load_examples":sorted(affected_models)[:100],
        "failures":failures[:200],
        "provenance":{
            "script":"tools/smg_rmge01_shp_displaylist_census_v1.py",
            "policy":"retail payloads are fetched transiently; only structural counts are retained",
        },
    }
    raw = json.dumps(result, sort_keys=True, separators=(",",":")).encode()
    result["provenance"]["structural_sha256"] = hashlib.sha256(raw).hexdigest()
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    print(json.dumps(result["counts"], indent=2))
    print("matrix loads", result["matrix_load_counts"])
    print("unknown", result["unknown_command_counts"])
    print("matrix types", result["shape_group_matrix_type_counts"])
    print("matrix-load models", result["matrix_load_examples"][:30])


if __name__ == "__main__":
    main()
