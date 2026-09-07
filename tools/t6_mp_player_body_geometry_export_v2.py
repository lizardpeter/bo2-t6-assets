#!/usr/bin/env python3
"""Player-body geometry exporter v2: source-closed winding + robust normal sanity.

v1 incorrectly treated a 98% triangle-vs-vertex-normal agreement threshold as the
authority for T6 -> glTF front-face winding.  The winding convention itself is
already source-closed for recovered T6 XModel/world triangles: native T6 order is
the opposite of core glTF CCW, so index 1/2 must be swapped.

Authored/interpolated vertex normals are only an independent corruption sanity
check.  Five otherwise exact LOD3 bodies had 2.5-4.0% sampled triangles whose
geometric face normal disagreed with averaged vertex normals while retaining a
very strong negative global median.  v2 therefore requires a strong negative
median and >=90% negative samples before the source-closed swap, then the exact
mirror condition after it.  No identity, source hash, geometry, skeleton, skin,
COLOR_0, or material gate is relaxed.
"""
from __future__ import annotations

import copy

import t6_mp_player_body_geometry_export_v1 as v1

FORMAT = "t6-mp-player-body-geometry-export-v2"
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

    out = copy.deepcopy(mesh_doc)
    lm = next(x for x in out["xmodel"]["lods"] if int(x["index"]) == lod)
    first, count = int(lm["surfIndex"]), int(lm["numSurfs"])
    tri_count = 0
    for s in out["surfaces"][first:first+count]:
        s["triangles"] = [[int(t[0]), int(t[2]), int(t[1])] for t in s["triangles"]]
        tri_count += len(s["triangles"])

    after = v1.source_orientation(out, lod)
    if (after["positiveFraction"] < NORMAL_SANITY_FRACTION
            or after["medianNormalDot"] < NORMAL_SANITY_MEDIAN):
        raise v1.ExportError(
            f"LOD{lod}: glTF winding swap failed triangle/vertex-normal sanity: {after}"
        )
    if abs(after["positiveFraction"] - before["negativeFraction"]) > 1e-12:
        raise v1.ExportError(f"LOD{lod}: winding sign population did not mirror exactly")
    if abs(after["medianNormalDot"] + before["medianNormalDot"]) > 1e-9:
        raise v1.ExportError(f"LOD{lod}: winding median did not negate exactly")

    return out, {
        "authority": "source-closed T6 triangle order is opposite core glTF CCW front-face convention",
        "normalEvidenceRole": "independent corruption sanity only; vertex normals do not define engine front-face winding",
        "normalSanityFraction": NORMAL_SANITY_FRACTION,
        "normalSanityMedianMagnitude": NORMAL_SANITY_MEDIAN,
        "trianglesFlipped": tri_count,
        "before": before,
        "after": after,
    }


def main() -> int:
    # Reuse v1's exact retail identity/mesh/skeleton/COLOR_0/GLB gates.  Only the
    # winding validator is replaced, and the emitted audit format is versioned.
    v1.reverse_lod_winding = reverse_lod_winding
    v1.FORMAT = FORMAT
    return v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
