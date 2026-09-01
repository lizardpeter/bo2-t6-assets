#!/usr/bin/env python3
"""Audit T6 GfxWorld vd0/vd1 vertex groups for one retail map fixture.

Inputs are already-extracted GfxWorld surface records and raw vd0/vd1 buffers,
plus material and prefix-trace sidecars needed to bind each surface material to
its TechniqueSet.worldVertFormat.

This tool is deliberately fixture-driven and fail-visible:
- it derives authoritative vertex counts from serialized vd0 allocation spans;
- validates stored nonzero vertexCount values when present;
- validates vd1 stride/alignment for the material's world vertex format;
- decodes source-byte samples for every observed group;
- reports bad groups instead of silently accepting a guessed layout.

The asset pointer-array virtual base is an explicit argument because it is
zone/fixture provenance, not a universal constant.
"""
from __future__ import annotations

import argparse
import collections
import json
import struct
from pathlib import Path

from t6_zone_core import (
    GFX_WORLD_VD0_STRIDE,
    MaterialWorldVertexFormat,
    WORLD_VERTEX_FORMATS,
    align_up,
    decode_world_vd0_vertex,
    decode_world_vd1_vertex,
)


class AuditError(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(
    *,
    map_name: str,
    surfaces_path: Path,
    vd0_path: Path,
    vd1_path: Path,
    materials_path: Path,
    catalog_path: Path,
    prefix_path: Path,
    asset_pointer_array_virtual_base: int,
) -> dict:
    surfaces_doc = load_json(surfaces_path)
    surfaces = surfaces_doc["surfaces"]
    vd0 = vd0_path.read_bytes()
    vd1 = vd1_path.read_bytes()
    materials = load_json(materials_path)["materials"]
    catalog = load_json(catalog_path)["materials"]
    prefix = load_json(prefix_path)["walkedAssets"]

    mat_by_ptr = {int(m["surfacePointerHex"], 16): m for m in catalog}
    mat_detail_by_name = {m["name"]: m for m in materials}

    def technique_asset_index(material_name: str) -> int:
        m = mat_detail_by_name[material_name]
        p = m["techniqueSet"]["pointer"]
        if p["kind"] != "offset" or int(p["block"]) != 5:
            raise AuditError(
                f"{material_name}: TechniqueSet pointer is not virtual offset block 5: {p}"
            )
        target = int(p["offset"])
        q, r = divmod(target - asset_pointer_array_virtual_base - 4, 8)
        if r or not (0 <= q < len(prefix)):
            raise AuditError(
                f"{material_name}: TechniqueSet pointer target {target} does not "
                f"map to prefix asset array base {asset_pointer_array_virtual_base}"
            )
        return q

    mat_fmt: dict[str, int] = {}
    mat_tech: dict[str, dict] = {}
    for name in mat_detail_by_name:
        ai = technique_asset_index(name)
        a = prefix[ai]
        if a["type"] != "techniqueset":
            raise AuditError(f"{name}: prefix asset {ai} is {a['type']}, not techniqueset")
        fmt = int(a["details"]["worldVertFormat"])
        try:
            MaterialWorldVertexFormat(fmt)
        except ValueError as exc:
            raise AuditError(f"{name}: invalid worldVertFormat {fmt}") from exc
        mat_fmt[name] = fmt
        mat_tech[name] = {"assetIndex": ai, "name": a["name"]}

    groups: dict[int, list[dict]] = collections.defaultdict(list)
    for s in surfaces:
        groups[int(s["vertexDataOffset0"])].append(s)
    offs = sorted(groups)

    records: list[dict] = []
    bad: list[dict] = []
    format_group_counts = collections.Counter()

    for gi, off in enumerate(offs):
        gs = groups[off]
        next0 = offs[gi + 1] if gi + 1 < len(offs) else len(vd0)
        vd0_span = next0 - off
        candidates = [
            n
            for n in range(
                max(0, vd0_span // GFX_WORLD_VD0_STRIDE - 2),
                vd0_span // GFX_WORLD_VD0_STRIDE + 2,
            )
            if align_up(GFX_WORLD_VD0_STRIDE * n, 16) == vd0_span
        ]
        owner_counts = sorted(
            {int(s["vertexCount"]) for s in gs if int(s["vertexCount"]) > 0}
        )
        if len(candidates) != 1:
            bad.append(
                {
                    "offset0": off,
                    "reason": "vd0 span does not uniquely determine vertex count",
                    "span": vd0_span,
                    "candidates": candidates,
                    "storedCounts": owner_counts,
                }
            )
            continue
        vc = candidates[0]
        if owner_counts and owner_counts != [vc]:
            bad.append(
                {
                    "offset0": off,
                    "reason": "stored vertexCount disagrees with vd0 span",
                    "spanVertexCount": vc,
                    "storedCounts": owner_counts,
                }
            )
            continue

        fmts: set[int] = set()
        mats: list[str] = []
        unresolved_material = False
        for s in gs:
            raw = int(s["materialPointerRaw"], 16)
            mr = mat_by_ptr.get(raw)
            if mr is None:
                bad.append(
                    {
                        "offset0": off,
                        "surface": int(s["index"]),
                        "reason": "unknown material pointer",
                        "raw": s["materialPointerRaw"],
                    }
                )
                unresolved_material = True
                continue
            name = mr["name"]
            mats.append(name)
            if name not in mat_fmt:
                bad.append(
                    {
                        "offset0": off,
                        "surface": int(s["index"]),
                        "reason": "material missing TechniqueSet format",
                        "material": name,
                    }
                )
                unresolved_material = True
                continue
            fmts.add(mat_fmt[name])
        if unresolved_material:
            continue
        if len(fmts) != 1:
            bad.append(
                {"offset0": off, "reason": "mixed vertex formats", "formats": sorted(fmts)}
            )
            continue

        fmt = next(iter(fmts))
        spec = WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(fmt)]
        off1s = sorted({int(s["vertexDataOffset1"]) for s in gs})
        if len(off1s) != 1:
            bad.append(
                {"offset0": off, "reason": "mixed vd1 offsets", "offsets": off1s}
            )
            continue
        off1 = off1s[0]

        if off < 0 or off + vc * GFX_WORLD_VD0_STRIDE > len(vd0):
            bad.append(
                {
                    "offset0": off,
                    "reason": "vd0 group outside source buffer",
                    "vertexCount": vc,
                    "vd0Bytes": len(vd0),
                }
            )
            continue
        vd0_used = vc * GFX_WORLD_VD0_STRIDE
        if vd0_span != align_up(vd0_used, 16):
            bad.append(
                {
                    "offset0": off,
                    "reason": "vd0 span mismatch",
                    "span": vd0_span,
                    "expected": align_up(vd0_used, 16),
                }
            )

        later = [
            min({int(s["vertexDataOffset1"]) for s in groups[o]})
            for o in offs[gi + 1 :]
        ]
        next1 = next((x for x in later if x > off1), len(vd1))
        vd1_used = vc * spec.vd1_stride
        vd1_span = next1 - off1 if spec.vd1_stride else 0
        if spec.vd1_stride:
            if off1 < 0 or off1 + vd1_used > len(vd1):
                bad.append(
                    {
                        "offset0": off,
                        "offset1": off1,
                        "reason": "vd1 group outside source buffer",
                        "fmt": fmt,
                        "vertexCount": vc,
                        "vd1Bytes": len(vd1),
                    }
                )
                continue
            if vd1_span != align_up(vd1_used, 4):
                bad.append(
                    {
                        "offset0": off,
                        "reason": "vd1 span mismatch",
                        "fmt": fmt,
                        "span": vd1_span,
                        "expected": align_up(vd1_used, 4),
                    }
                )

        samples: list[dict] = []
        for vi in range(min(vc, 3)):
            a = off + GFX_WORLD_VD0_STRIDE * vi
            v = decode_world_vd0_vertex(vd0[a : a + GFX_WORLD_VD0_STRIDE])
            if spec.vd1_stride:
                b = off1 + spec.vd1_stride * vi
                v.update(
                    decode_world_vd1_vertex(
                        vd1[b : b + spec.vd1_stride],
                        fmt,
                    )
                )
            samples.append(v)

        format_group_counts[fmt] += 1
        records.append(
            {
                "groupIndex": gi,
                "vd0Offset": off,
                "vd1Offset": off1,
                "vertexCount": vc,
                "worldVertFormat": fmt,
                "formatName": MaterialWorldVertexFormat(fmt).name,
                "vd1Stride": spec.vd1_stride,
                "vd1Fields": list(spec.vd1_fields),
                "surfaceCount": len(gs),
                "surfaceIndices": [int(s["index"]) for s in gs],
                "lightmapIndices": sorted({int(s["lightmapIndex"]) for s in gs}),
                "materials": sorted(set(mats)),
                "samples": samples,
            }
        )

    lm_raw: list[tuple[int, int]] = []
    for row in records:
        off = int(row["vd0Offset"])
        vc = int(row["vertexCount"])
        for i in range(vc):
            a, b = struct.unpack_from("<HH", vd0, off + i * GFX_WORLD_VD0_STRIDE + 32)
            lm_raw.append((a, b))

    observed = set(format_group_counts)
    format_table = {}
    for key, spec in WORLD_VERTEX_FORMATS.items():
        fmt = int(key)
        format_table[str(fmt)] = {
            "name": key.name,
            "uvCount": spec.uv_count,
            "normalCount": spec.normal_count,
            "vd1Stride": spec.vd1_stride,
            "vd1Fields": list(spec.vd1_fields),
            "validation": (
                f"direct {map_name} byte proof"
                if fmt in observed
                else "T6 enum/formula; not observed in this fixture"
            ),
        }

    lightmap = {
        "encoding": "2xUNORM16 little-endian",
        "sampleCount": len(lm_raw),
    }
    if lm_raw:
        lightmap.update(
            {
                "rawMin": [min(a for a, _ in lm_raw), min(b for _, b in lm_raw)],
                "rawMax": [max(a for a, _ in lm_raw), max(b for _, b in lm_raw)],
                "normalizedMin": [
                    min(a for a, _ in lm_raw) / 65535.0,
                    min(b for _, b in lm_raw) / 65535.0,
                ],
                "normalizedMax": [
                    max(a for a, _ in lm_raw) / 65535.0,
                    max(b for _, b in lm_raw) / 65535.0,
                ],
            }
        )

    return {
        "format": "t6-world-vertex-proof-v1",
        "map": map_name,
        "source": {
            "surfaces": str(surfaces_path),
            "vd0": str(vd0_path),
            "vd1": str(vd1_path),
            "materials": str(materials_path),
            "catalog": str(catalog_path),
            "prefix": str(prefix_path),
        },
        "surfaceCount": len(surfaces),
        "uniqueVertexGroups": len(groups),
        "vd0Bytes": len(vd0),
        "vd1Bytes": len(vd1),
        "vd0StrideBytes": GFX_WORLD_VD0_STRIDE,
        "vd0Layout": [
            {"offset": 0, "size": 12, "field": "position", "encoding": "3xf32"},
            {"offset": 12, "size": 4, "field": "binormalSign", "encoding": "f32"},
            {"offset": 16, "size": 4, "field": "color", "encoding": "RGBA8"},
            {"offset": 20, "size": 4, "field": "uv0", "encoding": "2xfp16"},
            {"offset": 24, "size": 4, "field": "normal", "encoding": "PackedUnitVec u32"},
            {"offset": 28, "size": 4, "field": "tangent", "encoding": "PackedUnitVec u32"},
            {"offset": 32, "size": 4, "field": "lightmapUV", "encoding": "2xUNORM16"},
        ],
        "formatTable": format_table,
        "observedFormatGroupCounts": {
            str(k): v for k, v in sorted(format_group_counts.items())
        },
        "badGroupCount": len(bad),
        "badGroups": bad,
        "lightmapUV": lightmap,
        "techniqueAssetPointerArrayVirtualBase": asset_pointer_array_virtual_base,
        "materialFormatCount": len(mat_fmt),
        "groups": records,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", dest="map_name", required=True)
    ap.add_argument("--surfaces", type=Path, required=True)
    ap.add_argument("--vd0", type=Path, required=True)
    ap.add_argument("--vd1", type=Path, required=True)
    ap.add_argument("--materials", type=Path, required=True)
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--prefix", type=Path, required=True)
    ap.add_argument(
        "--asset-pointer-base",
        type=lambda x: int(x, 0),
        required=True,
        help="asset pointer-array virtual base; fixture provenance, not a universal constant",
    )
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    report = audit(
        map_name=args.map_name,
        surfaces_path=args.surfaces,
        vd0_path=args.vd0,
        vd1_path=args.vd1,
        materials_path=args.materials,
        catalog_path=args.catalog,
        prefix_path=args.prefix,
        asset_pointer_array_virtual_base=args.asset_pointer_base,
    )
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "map": report["map"],
                "surfaces": report["surfaceCount"],
                "groups": report["uniqueVertexGroups"],
                "bad": report["badGroupCount"],
                "observedFormats": report["observedFormatGroupCounts"],
                "vd0Bytes": report["vd0Bytes"],
                "vd1Bytes": report["vd1Bytes"],
            },
            indent=2,
        )
    )
    return 0 if report["badGroupCount"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
