#!/usr/bin/env python3
"""T6 ClipMap serialized walker v3.

Extends v2 with retail-proven T6 PC32 Material and GfxImage dispatch. This is
needed for ClipMap PhysConstraint material pointers such as Mob of the Dead's
rope material. Unsupported inline external asset types remain fail-closed.

Validated against retail mp_nuketown_2020, mp_raid, mp_hijacked, zm_prison,
and zm_tomb FastFiles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_clipmap_serialized_walker import SIZE, is_inline, ptr_kind
from t6_clipmap_serialized_walker_v2 import Walker as V2

MATERIAL_SIZE = 112
MATERIAL_TEXTURE_DEF_SIZE = 16
MATERIAL_CONSTANT_DEF_SIZE = 32
GFX_STATE_BITS_SIZE = 20
GFX_IMAGE_SIZE = 80
GFX_IMAGE_LOAD_DEF_SIZE = 12


class Walker(V2):
    def walk_gfx_image(self, label: str) -> None:
        base, _ = self.take(GFX_IMAGE_SIZE, f"{label}.GfxImage.fixed")
        load_def_ptr = self.u32at(base, 0)
        name_ptr = self.u32at(base, 72)

        # T6 GfxImage reorder contract is name, then texture/loadDef.
        self.walk_string_ptr(name_ptr, f"{label}.GfxImage.name")
        if is_inline(load_def_ptr):
            load_base, _ = self.take(
                GFX_IMAGE_LOAD_DEF_SIZE,
                f"{label}.GfxImage.loadDef.fixed",
            )
            resource_size = self.u32at(load_base, 0)
            data_ptr = self.u32at(load_base, 8)
            if resource_size and is_inline(data_ptr):
                self.take(
                    resource_size,
                    f"{label}.GfxImage.loadDef.data",
                    meta={"resourceSize": resource_size},
                )

        self._record_dispatch("GfxImage")

    def walk_material(self, label: str) -> None:
        base, _ = self.take(MATERIAL_SIZE, f"{label}.Material.fixed")
        name_ptr = self.u32at(base, 0)
        texture_count = self.data[base + 84]
        constant_count = self.data[base + 85]
        state_bits_count = self.data[base + 86]
        technique_set_ptr = self.u32at(base, 92)
        texture_table_ptr = self.u32at(base, 96)
        constant_table_ptr = self.u32at(base, 100)
        state_bits_table_ptr = self.u32at(base, 104)
        thermal_material_ptr = self.u32at(base, 108)

        name = self.walk_string_ptr(name_ptr, f"{label}.Material.name")

        # Preserve native field/order semantics. A packed technique set consumes
        # no source bytes; an inline one remains an explicit unsupported dispatch.
        self.external_asset_ref(
            f"{label}.Material.techniqueSet",
            technique_set_ptr,
            asset_type="MaterialTechniqueSet",
        )

        if is_inline(texture_table_ptr):
            table_base, _ = self.take(
                texture_count * MATERIAL_TEXTURE_DEF_SIZE,
                f"{label}.Material.textureTable.fixed",
                meta={
                    "count": texture_count,
                    "recordBytes": MATERIAL_TEXTURE_DEF_SIZE,
                },
            )
            for index in range(texture_count):
                image_ptr = self.u32at(
                    table_base + index * MATERIAL_TEXTURE_DEF_SIZE,
                    12,
                )
                self.external_asset_ref(
                    f"{label}.Material.textureTable[{index}].image",
                    image_ptr,
                    index,
                    asset_type="GfxImage",
                )

        if is_inline(constant_table_ptr):
            self.take(
                constant_count * MATERIAL_CONSTANT_DEF_SIZE,
                f"{label}.Material.constantTable",
                meta={
                    "count": constant_count,
                    "recordBytes": MATERIAL_CONSTANT_DEF_SIZE,
                },
            )

        if is_inline(state_bits_table_ptr):
            self.take(
                state_bits_count * GFX_STATE_BITS_SIZE,
                f"{label}.Material.stateBitsTable",
                meta={
                    "count": state_bits_count,
                    "recordBytes": GFX_STATE_BITS_SIZE,
                },
            )

        self.external_asset_ref(
            f"{label}.Material.thermalMaterial",
            thermal_material_ptr,
            asset_type="Material",
        )
        self.details.setdefault("inlineMaterials", []).append(
            {
                "label": label,
                "name": name,
                "textureCount": texture_count,
                "constantCount": constant_count,
                "stateBitsCount": state_bits_count,
            }
        )
        self._record_dispatch("Material")

    def external_asset_ref(
        self,
        field: str,
        ptr: int,
        owner_index=None,
        asset_type: str | None = None,
    ) -> None:
        if not is_inline(ptr):
            return
        if asset_type == "PhysPreset":
            self.walk_phys_preset(field)
            return
        if asset_type == "Material":
            self.walk_material(field)
            return
        if asset_type == "GfxImage":
            self.walk_gfx_image(field)
            return
        self.blockers.append(
            {
                "kind": "inline_external_asset_reference_requires_xasset_dispatch",
                "field": field,
                "ownerIndex": owner_index,
                "assetType": asset_type,
                "pointer": ptr_kind(ptr),
            }
        )

    def walk_constraints(self, ptr: int, count: int, label: str) -> None:
        if count == 0 or not is_inline(ptr):
            return
        array_base, _ = self.take(
            count * SIZE["PhysConstraint"],
            f"{label}.fixed",
            meta={"count": count, "recordBytes": SIZE["PhysConstraint"]},
        )
        for index in range(count):
            base = array_base + index * SIZE["PhysConstraint"]
            self.walk_string_ptr(
                self.u32at(base, 20), f"{label}[{index}].target_bone1"
            )
            self.walk_string_ptr(
                self.u32at(base, 36), f"{label}[{index}].target_bone2"
            )
            self.external_asset_ref(
                f"{label}[{index}].material",
                self.u32at(base, 140),
                index,
                asset_type="Material",
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--asset-start", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--expect-end", type=lambda x: int(x, 0))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    data = args.expanded.read_bytes()
    result = Walker(data, args.asset_start).walk()
    result["format"] = "t6-clipmap-serialized-walk-v3"
    result["expandedBytes"] = len(data)
    result["expandedSha256"] = hashlib.sha256(data).hexdigest()

    if args.expect_end is not None:
        result["expectedEnd"] = args.expect_end
        result["expectedEndMatches"] = (
            result["assetSerializedEnd"] == args.expect_end
        )
        if not result["expectedEndMatches"]:
            raise SystemExit(
                f"walk ended {result['assetSerializedEnd']} expected {args.expect_end}"
            )

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
