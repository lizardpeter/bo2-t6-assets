# T6 Nuketown car01 Material array proof v2 — 2026-09-06

- exact VIRTUAL Material-handle-array base: **40852396**
- independent pre-drift GfxImage anchors: **2 / 2 agree**
- conflicts: **0**

- `40852396` → `mc/mtl_nt_2020_car_01_glass_out`
- `40852400` → `mc/mtl_nt_2020_car_01_exterior`
- `40852404` → `mc/mtl_nt_2020_car_01_interior`
- `40852408` → `mc/mtl_nt_2020_car_01_tire`
- `40852412` → `mc/mtl_veh_t6_shattered_glass_in`
- `40852416` → `mc/mtl_nt_2020_car_01_tire_d`
- `40852420` → `mc/mtl_nt_2020_car_01_interior_d`
- `40852424` → `mc/mtl_nt_2020_car_01_exterior_d`
- `40852428` → `mc/mtl_veh_t6_shattered_glass_out`
- `40852432` → `mc/mtl_nt_2020_car_01_glass_in`

Proof SHA-256: `edf0432d8c626f2f3aa7b23ed9348a776bc20c8cf74370a5a5c706bf5df7592b`

Base is solved only from two packed GfxImage aliases in Material slot9 that target exact pointer slots in Material slot0, before the later +4 replay discrepancy. No later Material consumer address participates in base derivation.
