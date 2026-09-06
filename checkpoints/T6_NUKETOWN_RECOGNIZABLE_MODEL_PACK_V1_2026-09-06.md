# T6 Nuketown recognizable model pack v1 — 2026-09-06

A destructible Nuketown mannequin and the full 56-bone retail German shepherd now export as standalone LOD0 GLBs from the exact map FastFile.

## Result

- models exported: **2 / 2**
- source/walker/skin/export/GLB failures: **0**
- independent `trimesh` loader failures: **0**

### `dest_nt_nuked_female_02_d0`

- XAsset: **273**; bones: **4**; LOD0 surfaces: **3**
- vertices / triangles: **5,395 / 8,762**
- rigid / blended / unweighted vertices: **5,395 / 0 / 0**
- GLB bytes: **449,344**
- GLB SHA-256: `5e04beb6e797964e6bd3597c76186e1fcbdcafef3b35b526ae85140d2f89b2b7`
- independent `trimesh 4.11.1` load: **3 geometries / 5,395 vertices / 8,762 faces**

### `german_shepherd`

- XAsset: **447**; bones: **56**; LOD0 surfaces: **3**
- vertices / triangles: **5,731 / 7,123**
- rigid / blended / unweighted vertices: **1,177 / 4,554 / 0**
- GLB bytes: **480,416**
- GLB SHA-256: `e9236ef93ed410d057b5ff5231973b5dfa54d3084453a6d6de63774a4c1a761f`
- independent `trimesh 4.11.1` load: **3 geometries / 5,731 vertices / 7,123 faces**

## German shepherd closure

The regenerated shepherd matches the previously retained retail census exactly: **56 bones, 3 LOD0 surfaces, 5,731 vertices, 7,123 triangles, 1,177 rigid vertices, 4,554 blended vertices, 0 unweighted vertices**, with the exact stored 1/2/3/4-influence histogram.

The earlier independent-loader requirement is now closed too. The emitted GLB was downloaded from the successful GitHub Actions artifact and loaded separately with `trimesh 4.11.1` using `force='scene', process=False`. The independent consumer recovered exactly **3 geometries, 5,731 vertices, and 7,123 faces** while preserving the expected GLB SHA-256. The mannequin independently recovered exactly **3 / 5,395 / 8,762** as well.

Machine-readable independent-load evidence is retained in `manifests/maps/mp_nuketown_2020/T6_NUKETOWN_RECOGNIZABLE_MODEL_PACK_V1_INDEPENDENT_LOAD_VALIDATION.json`.

## Material boundary

Materials/textures are not yet attached to these GLBs; that remains a separate exact Material/Image provenance pass. No visual or name-based texture guesses were introduced to make the models look finished.

- model-pack manifest SHA-256: `76a285b95309ec98ee9ce36bee02cfadcd9b86848273b387191b4c5717268132`
