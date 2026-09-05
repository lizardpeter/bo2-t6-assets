# Nuketown 2025 v25 Full-Map Checkpoint

Promoted candidate: `mp_nuketown_2020_v25_FULL_WORLD_PRIMARY_STATICS_SKYBOX.glb`

SHA-256: `32197bb8963f635b537b785830b3653b5122d63324eddbfafe51aea4ab7aa11c`

Size: 288,006,612 bytes.

Canonical full scene:
- 5,614 retail GfxWorld surfaces
- 146,764 retail world vertices
- 100,280 retail world triangles
- 2,992 serialized static placements preserved
- 2,923 non-reflection primary static placements preserved
- 2,921 primary statics visible in canonical scene
- 2 `fxanim_*` animation-support statics preserved unchanged in a dedicated support scene
- 69 reflection proxies preserved but not rendered in canonical scene
- 6 parked/destructible MapEnt cars visible
- exact retail `skybox_mp_nuketown2020_ft` six-face cubemap retained losslessly plus Blender preview cube

Document totals:
- 356 meshes
- 718 materials
- 809 embedded images
- 834 textures
- 9 samplers
- 31,470 accessors
- 26,906 bufferViews
- 3 animations
- 1 skin
- 5 scenes

Coverage QA:
- 711 used materials
- 709 used materials with base-color bindings
- 662 used materials with normal bindings
- 9,088 primitives
- 567,122 triangles across all preserved scenes/meshes
- 0 generic `material_surface_*` primitive references
- 0 external image URIs
- 0 invalid texture sources
- 0 invalid embedded images
- independent `trimesh` GLB import passes
- scene-aware non-regression guard passes with zero failures

Universal metadata added to the GLB:
- `T6.fullRetailWorldIntegrationV1`
- `T6.sceneRolePolicyV1`
- `T6.retailSkyboxV1`

The canonical scene intentionally excludes animation-support/helper geometry without modifying or deleting the underlying node/mesh/animation data. This is scene migration, not data loss.
