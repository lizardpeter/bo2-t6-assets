# T6 Nuketown car Blender-safe static bind-pose fix v1 — 2026-09-06

The first rigged standalone parked-car GLBs were numerically source-valid but poor visual inspection artifacts in Blender because the exact T6 armature/wrapper hierarchy remained active and no materials were attached. User inspection exposed that the end-on X-axis cross-section could be mistaken for a faceted blob.

## Diagnosis

- normalized retail vertex clouds are car-shaped and preserve exact LOD0 bounds
- complete triangle wireframe projections reproduce the full body, cabin, wheels, spoiler/bumper structure
- glTF bind-pose skin matrices evaluate to identity within floating-point error, so the retail mesh is not collapsed by the exporter
- the first screenshot is an almost exact view down the car length/X axis; the YZ cross-section is approximately 82 x 59 T6 units for car01 and appears round/faceted without material separation

## Fix

Added `tools/t6_xmodel_blender_static_bindpose_export_v1.py`.

This inspection exporter:

- consumes only `t6-xmodel-mesh-normalized-v1`
- preserves exact retail LOD geometry, local triangle topology, normals, UV0, and vertex color
- removes armature/skin only for the static inspection variant
- bakes T6 Z-up inches into glTF Y-up meters (`[x,z,-y] * 0.0254`) so Blender imports directly into its Z-up scene without a wrapper node
- preserves each source XSurface as a separate glTF primitive with provenance extras
- does not infer or attach materials/textures

## Current corrected car outputs

### `veh_t6_nuketown_2020_car01_clean`

- LOD0 vertices / triangles: **10,814 / 12,390**
- corrected static GLB bytes: **599,020**
- SHA-256: `165e3af352ee094331d57cb362be59a51b819696a6a631c296813e44a1d88d8a`

### `veh_t6_nuketown_2020_car02_whole`

- LOD0 vertices / triangles: **18,198 / 22,213**
- corrected static GLB bytes: **1,015,336**
- SHA-256: `1bbef2455a41ca231fa2d172c9bb9bb79e8550a114df2ff73299e8e67d1a5b9d`

Both corrected outputs independently reload through trimesh with exact vertex/face counts.

## Boundary

The corrected static files are visual-inspection/bind-pose exports. The exact rigged files remain retained for animation/destruction work. Retail Material/Image attachment is a separate source-closed pass and is still intentionally absent here.
