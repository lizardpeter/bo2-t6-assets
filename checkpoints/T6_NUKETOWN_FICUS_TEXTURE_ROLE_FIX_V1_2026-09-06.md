# T6 Nuketown Ficus texture-role fix v1 — 2026-09-06

The blue/purple Ficus bark regression is source-closed and fixed.

- exact bark slot 0: semantic **5 NORMAL_MAP** -> `p6_tree_ficus_lrg_01_bark1_n`
- exact bark slot 1: semantic **2 COLOR_MAP** -> `~-gp6_tree_ficus_lrg_01_bark1_c`
- both exact GfxImage payloads resolve from retail `base.ipak` by `(imageHash,dataHash)` and CRC29
- corrected standalone LOD0 GLB: **1,333,320 bytes**, SHA-256 `582ae0359f3dcde129070bd8ce316897adb52b4ee33f227aebace5080f35862f`
- Base Color normal-map regression: **forbidden and fail-closed**

The reusable full-map role repair is `tools/t6_nuketown_static_xmodel_texture_apply_v3.py`; occupied legacy roles are no longer trusted merely because they already contain a texture.
