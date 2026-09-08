#!/usr/bin/env python3
"""SEAL6 Blender shader-carrier import with a measured Blender 4.0.2 transport contract.

v1 correctly refused to admit Blender's imported bind-pose positions under an
unmeasured epsilon.  A dedicated all-vertex diagnostic then measured the exact
same-index transport for the exact source carrier under Blender 4.0.2:

- 13,490 vertices / 14,968 triangles;
- max POSITION absolute error: 2.288818359375e-05;
- max UV absolute error: 0.0;
- skin group-name mismatches: 0;
- max named skin-weight absolute error: 0.0;
- non-finite comparisons: 0.

This v2 adapter therefore admits *only* that exact source SHA under Blender 4.0.2,
keeps UV and named skin weights exact, and permits POSITION only within the exact
maximum measured by the source-closed diagnostic.  It then delegates the actual
custom POINT-attribute injection/readback/save/reopen logic to v1.

The measured allowance is not a generic geometry tolerance and must not be reused
for another source GLB or Blender version without a fresh diagnostic.
"""
from __future__ import annotations

import hashlib
import math

import t6_blender_import_xmodel_shader_carrier_v1 as v1

FORMAT = "t6-blender-import-xmodel-shader-carrier-v2"
SOURCE_SHA256 = "b0543f983731afb8cb45d73ebd581026b53a23cf21d08a4178047fcacd5c8a20"
BLENDER_VERSION = "4.0.2"
POSITION_ABS_BOUND = 2.288818359375e-05
PROBE_RUN = 34186716502
PROBE_ARTIFACT_ID = 10040761772
PROBE_ARTIFACT_DIGEST = "sha256:52e991414f67700399eeb4f367efb871ce58f2cb63c1a390e2864168ee2ac6bd"

_ORIGINAL_SOURCE = v1._source


def _source_exact(path):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != SOURCE_SHA256:
        raise v1.BlenderShaderCarrierError(
            f"v2 transport contract is source-specific: {actual} != {SOURCE_SHA256}"
        )
    if v1.bpy is not None and v1.bpy.app.version_string != BLENDER_VERSION:
        raise v1.BlenderShaderCarrierError(
            f"v2 transport contract is Blender-specific: {v1.bpy.app.version_string!r} != {BLENDER_VERSION!r}"
        )
    return _ORIGINAL_SOURCE(path)


def _prove_vertex_sequence_measured(obj, doc, raw, prims):
    mesh = obj.data
    positions = v1._flatten_source(doc, raw, prims, "POSITION")
    uvs = v1._flatten_source(doc, raw, prims, "TEXCOORD_0")
    skins = v1._expected_skin_rows(doc, raw, prims)
    imported_uvs = v1._vertex_uvs(mesh)
    if not (len(positions) == len(uvs) == len(skins) == len(imported_uvs) == len(mesh.vertices) == 13490):
        raise v1.BlenderShaderCarrierError(
            "source/import vertex cardinality mismatch under measured v2 contract"
        )

    max_position = 0.0
    max_position_vertex = -1
    max_position_component = -1
    for i, vertex in enumerate(mesh.vertices):
        actual_pos = tuple(float(x) for x in vertex.co)
        expected_pos = v1._gltf_to_blender_vec(positions[i])
        for component, (actual, expected) in enumerate(zip(actual_pos, expected_pos)):
            if not math.isfinite(actual) or not math.isfinite(expected):
                raise v1.BlenderShaderCarrierError(
                    f"vertex {i}: non-finite POSITION under measured v2 contract"
                )
            delta = abs(actual - expected)
            if delta > max_position:
                max_position = delta
                max_position_vertex = i
                max_position_component = component
            if delta > POSITION_ABS_BOUND:
                raise v1.BlenderShaderCarrierError(
                    f"vertex {i}: POSITION import error {delta!r} exceeds measured Blender 4.0.2 bound "
                    f"{POSITION_ABS_BOUND!r}"
                )

        expected_uv = v1._uv_to_blender(uvs[i])
        actual_uv = imported_uvs[i]
        if tuple(actual_uv) != tuple(expected_uv):
            raise v1.BlenderShaderCarrierError(
                f"vertex {i}: UV is not exact under measured v2 contract "
                f"actual={actual_uv!r} expected={expected_uv!r}"
            )

        actual_skin = v1._actual_skin_row(obj, vertex)
        expected_skin = skins[i]
        if actual_skin != expected_skin:
            raise v1.BlenderShaderCarrierError(
                f"vertex {i}: named skin weights are not exact under measured v2 contract "
                f"actual={actual_skin!r} expected={expected_skin!r}"
            )

    if max_position != POSITION_ABS_BOUND:
        raise v1.BlenderShaderCarrierError(
            f"Blender 4.0.2 numeric transport changed: observed max POSITION error {max_position!r} "
            f"!= diagnostic maximum {POSITION_ABS_BOUND!r}"
        )

    return {
        "vertices": 13490,
        "vertexSequenceIdentityClosed": True,
        "positionSequenceWithinMeasuredBlender402Bound": True,
        "positionSequenceExact": False,
        "positionImportAbsBound": POSITION_ABS_BOUND,
        "maxObservedPositionAbsError": max_position,
        "maxObservedPositionVertex": max_position_vertex,
        "maxObservedPositionComponent": max_position_component,
        "uvSequenceExact": True,
        "namedSkinWeightSequenceExact": True,
        "gltfToBlenderPositionRule": "(x,y,z)->(x,-z,y)",
        "gltfToBlenderUvRule": "(u,v)->(u,1-v)",
        "transportContract": {
            "sourceSha256": SOURCE_SHA256,
            "blenderVersion": BLENDER_VERSION,
            "probeRun": PROBE_RUN,
            "probeArtifactId": PROBE_ARTIFACT_ID,
            "probeArtifactDigest": PROBE_ARTIFACT_DIGEST,
            "probeMaxPositionAbsError": POSITION_ABS_BOUND,
            "probeMaxUvAbsError": 0.0,
            "probeSkinNameMismatchCount": 0,
            "probeMaxNamedSkinWeightAbsError": 0.0,
            "probeNonFiniteComparisonCount": 0,
        },
    }


def main() -> int:
    v1.FORMAT = FORMAT
    v1._source = _source_exact
    v1._prove_vertex_sequence = _prove_vertex_sequence_measured
    return v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
