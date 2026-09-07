#!/usr/bin/env python3
"""Player-body geometry exporter v3: exact index winding proof.

v2 correctly separated the source-closed T6 front-face convention from vertex-normal
sanity, but still compared floating-point summary medians before/after the swap.
That was an unnecessarily brittle validator: the authority is the exact index-array
transformation, not exact floating-point reduction equality.

v3 therefore requires all of the following for every selected LOD:
- source triangle/vertex-normal evidence remains strongly reverse-oriented as an
  independent corruption sanity check (>=90% negative, median <= -0.5);
- every triangle is transformed exactly [i0,i1,i2] -> [i0,i2,i1];
- triangle and sample cardinalities are unchanged;
- the post-swap normal sanity is strongly forward-oriented (>=90% positive,
  median >= +0.5).

No identity, FastFile hash, fixed-record hash, geometry, skeleton, skin, COLOR_0,
material, or animation boundary is relaxed.
"""
from __future__ import annotations

import copy

import t6_mp_player_body_geometry_export_v1 as v1

FORMAT = "t6-mp-player-body-geometry-export-v3"
NORMAL_SANITY_FRACTION = 0.90
NORMAL_SANITY_MEDIAN = 0.50


def reverse_lod_winding(mesh_doc: dict, lod: int) -> tuple[dict, dict]:
    before = v1.source_orientation(mesh_doc, lod)
    if (before["negativeFraction"] < NORMAL_SANITY_FRACTION
            or before["medianNormalDot"] > -NORMAL_SANITY_MEDIAN):
        raise v1.ExportError(
            f"LOD{lod}: triangle/vertex-normal sanity does not support the "
            f"source-closed T6 reverse-winding convention: {before}"
        )

    source_lm = next(x for x in mesh_doc["xmodel"]["lods"] if int(x["index"]) == lod)
    source_first, source_count = int(source_lm["surfIndex"]), int(source_lm["numSurfs"])
    source_surfaces = mesh_doc["surfaces"][source_first:source_first + source_count]

    out = copy.deepcopy(mesh_doc)
    out_lm = next(x for x in out["xmodel"]["lods"] if int(x["index"]) == lod)
    out_first, out_count = int(out_lm["surfIndex"]), int(out_lm["numSurfs"])
    if (out_first, out_count) != (source_first, source_count):
        raise v1.ExportError(f"LOD{lod}: copied LOD span changed")
    out_surfaces = out["surfaces"][out_first:out_first + out_count]
    if len(out_surfaces) != len(source_surfaces):
        raise v1.ExportError(f"LOD{lod}: copied surface cardinality changed")

    tri_count = 0
    for src, dst in zip(source_surfaces, out_surfaces):
        src_tris = src["triangles"]
        dst_tris = dst["triangles"]
        if len(src_tris) != len(dst_tris):
            raise v1.ExportError(f"LOD{lod}: copied triangle cardinality changed")
        rewritten = []
        for tri in src_tris:
            if len(tri) != 3:
                raise v1.ExportError(f"LOD{lod}: malformed source triangle {tri!r}")
            rewritten.append([int(tri[0]), int(tri[2]), int(tri[1])])
        dst["triangles"] = rewritten
        tri_count += len(rewritten)

    # This is the authoritative transformation gate: compare every emitted index
    # triplet back to its exact source triplet, not a floating-point proxy.
    exact_matches = 0
    for src, dst in zip(source_surfaces, out_surfaces):
        if len(src["triangles"]) != len(dst["triangles"]):
            raise v1.ExportError(f"LOD{lod}: post-swap triangle cardinality changed")
        for a, b in zip(src["triangles"], dst["triangles"]):
            expected = [int(a[0]), int(a[2]), int(a[1])]
            if [int(x) for x in b] != expected:
                raise v1.ExportError(
                    f"LOD{lod}: exact winding transformation mismatch {a!r} -> {b!r}, "
                    f"expected {expected!r}"
                )
            exact_matches += 1
    if exact_matches != tri_count:
        raise v1.ExportError(f"LOD{lod}: exact winding proof count {exact_matches} != {tri_count}")

    after = v1.source_orientation(out, lod)
    if after["sampleCount"] != before["sampleCount"]:
        raise v1.ExportError(
            f"LOD{lod}: triangle/normal sample count changed "
            f"{before['sampleCount']} -> {after['sampleCount']}"
        )
    if (after["positiveFraction"] < NORMAL_SANITY_FRACTION
            or after["medianNormalDot"] < NORMAL_SANITY_MEDIAN):
        raise v1.ExportError(
            f"LOD{lod}: exact glTF winding swap failed independent normal sanity: {after}"
        )

    return out, {
        "authority": "source-closed T6 triangle order is opposite core glTF CCW front-face convention",
        "indexProof": "every selected triangle exactly transformed [i0,i1,i2] -> [i0,i2,i1]",
        "normalEvidenceRole": "independent corruption sanity only; vertex normals do not define engine front-face winding",
        "normalSanityFraction": NORMAL_SANITY_FRACTION,
        "normalSanityMedianMagnitude": NORMAL_SANITY_MEDIAN,
        "trianglesFlipped": tri_count,
        "exactTriangleTransformMatches": exact_matches,
        "before": before,
        "after": after,
    }


def main() -> int:
    v1.reverse_lod_winding = reverse_lod_winding
    v1.FORMAT = FORMAT
    return v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
