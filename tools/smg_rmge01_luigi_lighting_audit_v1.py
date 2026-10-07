#!/usr/bin/env python3
"""Exact RMGE01 playable-Luigi J3D lighting/skin audit.

Retail bytes are fetched transiently from the owner-hosted R2 mirror. Only a
structural JSON report is retained. The report is intentionally narrow: it
captures the material raster-light contracts that MarioActor mutates at draw
time plus the J3D joint/envelope scale facts needed to reproduce normal
lighting exactly.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import math
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
CENSUS_PATH = HERE / "smg_rmge01_j3d_material_census_v1.py"
BASE_DEFAULT = "https://r2.houseofkublai.com/super-mario-galaxy/DATA/files"
LUIGI_ARC_SHA256 = "27b75ff16672b38f09f1dff6d30619d24a2b5b8ea8f3bbab5dc8b474b6a14b80"
LUIGI_BDL_SHA256 = "68ca8d7115f8c832ca1809a297719136461cc02dff7efc06503472bb334490e5"


def load_census_module():
    spec = importlib.util.spec_from_file_location("smg_j3d_census", CENSUS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {CENSUS_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def be16(b: bytes, o: int) -> int:
    return struct.unpack_from(">H", b, o)[0]


def be32(b: bytes, o: int) -> int:
    return struct.unpack_from(">I", b, o)[0]


def f32(b: bytes, o: int) -> float:
    return struct.unpack_from(">f", b, o)[0]


def string_table(sec: bytes, off: int) -> list[str]:
    count = be16(sec, off)
    out = []
    for i in range(count):
        rel = be16(sec, off + 4 + i * 4 + 2)
        start = off + rel
        end = sec.find(b"\0", start)
        if end < 0:
            end = len(sec)
        out.append(sec[start:end].decode("shift_jis", "replace"))
    return out


def jnt1_audit(sec: bytes) -> dict:
    count = be16(sec, 0x08)
    data_off = be32(sec, 0x0C)
    remap_off = be32(sec, 0x10)
    names_off = be32(sec, 0x14)
    names = string_table(sec, names_off)
    joints = []
    non_unit = []
    non_uniform = []
    special_flags = []
    for i in range(count):
        remap = be16(sec, remap_off + i * 2)
        off = data_off + remap * 0x40
        flags = sec[off + 2]
        scale = [f32(sec, off + 4), f32(sec, off + 8), f32(sec, off + 0x0C)]
        name = names[i] if i < len(names) else f"joint_{i}"
        unit = all(abs(v - 1.0) <= 1.0e-6 for v in scale)
        uniform = max(scale) - min(scale) <= 1.0e-6
        row = {
            "index": i,
            "name": name,
            "calc_flags": flags,
            "scale": scale,
            "unit_scale": unit,
            "uniform_scale": uniform,
        }
        joints.append(row)
        if not unit:
            non_unit.append(row)
        if not uniform:
            non_uniform.append(row)
        if flags:
            special_flags.append(row)
    return {
        "joint_count": count,
        "non_unit_scale_count": len(non_unit),
        "non_uniform_scale_count": len(non_uniform),
        "special_calc_flag_count": len(special_flags),
        "non_unit_scale_joints": non_unit,
        "non_uniform_scale_joints": non_uniform,
        "special_calc_flag_joints": special_flags,
        "joints": joints,
    }


def inf1_audit(sec: bytes) -> dict:
    return {
        "load_flags": be16(sec, 0x08),
        "scaling_rule": be16(sec, 0x08) & 0x000F,
    }


def evp1_audit(sec: bytes) -> dict:
    envelope_count = be16(sec, 0x08)
    count_off = be32(sec, 0x0C)
    joint_off = be32(sec, 0x10)
    weight_off = be32(sec, 0x14)
    cursor = 0
    envelopes = []
    max_influences = 0
    for envelope in range(envelope_count):
        bone_count = sec[count_off + envelope]
        max_influences = max(max_influences, bone_count)
        influences = []
        weight_sum = 0.0
        for _ in range(bone_count):
            joint = be16(sec, joint_off + cursor * 2)
            weight = f32(sec, weight_off + cursor * 4)
            influences.append({"joint": joint, "weight": weight})
            weight_sum += weight
            cursor += 1
        envelopes.append(
            {
                "index": envelope,
                "influence_count": bone_count,
                "weight_sum": weight_sum,
                "influences": influences,
            }
        )
    return {
        "envelope_count": envelope_count,
        "weighted_reference_count": cursor,
        "max_influences": max_influences,
        "envelopes": envelopes,
    }


def drw1_audit(sec: bytes) -> dict:
    count = be16(sec, 0x08)
    type_off = be32(sec, 0x0C)
    data_off = be32(sec, 0x10)
    rows = []
    kinds = collections.Counter()
    for i in range(count):
        kind = sec[type_off + i]
        value = be16(sec, data_off + i * 2)
        kinds["joint" if kind == 0 else "envelope" if kind == 1 else f"unknown_{kind}"] += 1
        rows.append({"index": i, "kind": kind, "value": value})
    return {"draw_matrix_count": count, "kind_counts": dict(kinds), "draw_matrices": rows}


def material_lighting_audit(materials: list[dict]) -> dict:
    rows = []
    light_mask_counts = collections.Counter()
    raster_materials = 0
    point_light4_materials = 0
    for material in materials:
        raster_stages = []
        effective_channels = {}
        for stage in material["stages"]:
            color = stage["color"]
            alpha = stage["alpha"]
            uses_rgb = any(v == 10 for v in color[:4])
            uses_color_alpha = any(v == 11 for v in color[:4])
            uses_alpha = any(v == 5 for v in alpha[:4])
            if not (uses_rgb or uses_color_alpha or uses_alpha):
                continue
            order = stage.get("order")
            raw = 0xFF if order is None else order[2]
            channel = None
            bp = None
            # Public GXChannelID -> J3D BP raster selector mapping.
            c2r = [0, 1, 0, 1, 0, 1, 7, 5, 6, 0, 0, 0, 0, 0, 0, 7]
            if 0 <= raw < len(c2r):
                bp = c2r[raw]
                if bp in (0, 1):
                    channel = bp
            if channel is not None and channel < len(material["channels"]):
                pair = material["channels"][channel]
                # MarioActor::updateLightDL runs after the J3D material DL:
                # COLOR1 control is disabled, ALPHA1 is untouched.
                color_ctrl = pair.get("color")
                alpha_ctrl = pair.get("alpha")
                if channel == 1 and color_ctrl is not None:
                    color_ctrl = {
                        **color_ctrl,
                        "enable": 0,
                        "mat_src": 0,
                        "light_mask": 0,
                        "diff_fn": 2,
                        "attn_raw": 2,
                        "amb_src": 0,
                        "mario_actor_override": True,
                    }
                effective_channels[str(channel)] = {
                    "color": color_ctrl,
                    "alpha": alpha_ctrl,
                }
                for ctrl, used in ((color_ctrl, uses_rgb), (alpha_ctrl, uses_color_alpha or uses_alpha)):
                    if ctrl is not None and used and ctrl.get("enable"):
                        mask = int(ctrl.get("light_mask", 0))
                        light_mask_counts[f"0x{mask:02x}"] += 1
                        if mask & 0x10:
                            point_light4_materials += 1
            raster_stages.append(
                {
                    "slot": stage["slot"],
                    "raw_channel": raw,
                    "bp_raster_selector": bp,
                    "channel": channel,
                    "uses_rgb": uses_rgb,
                    "uses_color_alpha": uses_color_alpha,
                    "uses_alpha": uses_alpha,
                }
            )
        if not raster_stages:
            continue
        raster_materials += 1
        rows.append(
            {
                "material_index": material["material_index"],
                "material_name": material["material_name"],
                "material_colors_source": material["material_colors"],
                "ambient_colors_source": material["ambient_colors"],
                "mario_actor_color0_material_after_dl": [255, 255, 255, 255],
                "raster_stages": raster_stages,
                "effective_channels": effective_channels,
            }
        )
    return {
        "material_count": len(materials),
        "raster_material_count": raster_materials,
        "point_light4_enabled_use_count": point_light4_materials,
        "enabled_light_mask_use_counts": dict(sorted(light_mask_counts.items())),
        "raster_materials": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    census = load_census_module()
    url = args.base.rstrip("/") + "/ObjectData/Luigi.arc"
    arc_raw = census.fetch(url)
    arc_sha = hashlib.sha256(arc_raw).hexdigest()
    if arc_sha != LUIGI_ARC_SHA256:
        raise RuntimeError(f"Luigi.arc SHA-256 {arc_sha}, expected {LUIGI_ARC_SHA256}")

    files = census.rarc_files(arc_raw)
    models = [(name, payload) for name, payload in files if name.lower() == "luigi.bdl"]
    if len(models) != 1:
        raise RuntimeError(f"expected exactly one luigi.bdl, found {[name for name, _ in models]}")
    model_name, bdl = models[0]
    bdl_sha = hashlib.sha256(bdl).hexdigest()
    if bdl_sha != LUIGI_BDL_SHA256:
        raise RuntimeError(f"luigi.bdl SHA-256 {bdl_sha}, expected {LUIGI_BDL_SHA256}")

    sections = census.j3d_sections(bdl)
    required = {"INF1", "JNT1", "EVP1", "DRW1", "MAT3", "TEX1", "SHP1"}
    missing = sorted(required - set(sections))
    if missing:
        raise RuntimeError(f"luigi.bdl missing sections: {missing}")

    materials = census.mat3_census(sections["MAT3"], "Luigi")
    textures = census.tex1_census(sections["TEX1"])
    result = {
        "source": {
            "url": url,
            "archive_sha256": arc_sha,
            "model_file": model_name,
            "model_sha256": bdl_sha,
            "policy": "exact retail bytes fetched transiently; structural facts only",
        },
        "sections": {name: len(payload) for name, payload in sections.items()},
        "inf1": inf1_audit(sections["INF1"]),
        "jnt1": jnt1_audit(sections["JNT1"]),
        "evp1": evp1_audit(sections["EVP1"]),
        "drw1": drw1_audit(sections["DRW1"]),
        "lighting": material_lighting_audit(materials),
        "textures": textures,
        "provenance": {
            "script": "tools/smg_rmge01_luigi_lighting_audit_v1.py",
            "material_parser": "tools/smg_rmge01_j3d_material_census_v1.py",
            "retail_normal_rule_source": "Petari J3DMtxBuffer::calcWeightEnvelopeMtx/calcNrmMtx",
            "retail_player_dl_source": "Petari MarioActor::updateLightDL/J3DModelX::drawIn",
        },
    }
    raw = json.dumps(result, indent=2, sort_keys=True) + "\n"
    result["provenance"]["report_sha256_pre_field"] = hashlib.sha256(raw.encode()).hexdigest()
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "materials": result["lighting"]["material_count"],
        "raster_materials": result["lighting"]["raster_material_count"],
        "light_masks": result["lighting"]["enabled_light_mask_use_counts"],
        "point_light4_uses": result["lighting"]["point_light4_enabled_use_count"],
        "joints": result["jnt1"]["joint_count"],
        "non_unit_scale_joints": result["jnt1"]["non_unit_scale_count"],
        "non_uniform_scale_joints": result["jnt1"]["non_uniform_scale_count"],
        "envelopes": result["evp1"]["envelope_count"],
        "draw_matrix_kinds": result["drw1"]["kind_counts"],
        "scaling_rule": result["inf1"]["scaling_rule"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
