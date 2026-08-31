#!/usr/bin/env python3
"""T6 ClipMap serialized walker v2.

Extends the base structural walker with typed inline-XAsset dispatch used by
DynEntityDef. v2 keeps the base walker fail-closed behavior for unsupported
inline asset types and adds the retail-proven T6 PC32 PhysPreset serializer.

Validated against mp_nuketown_2020, mp_raid, and mp_hijacked retail FastFiles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from t6_clipmap_serialized_walker import (
    SIZE,
    WalkError,
    Walker as BaseWalker,
    is_inline,
    ptr_kind,
)

# PhysPreset is a T6 PC32 84-byte fixed record:
#   0x00 name ptr
#   0x04 flags
#   0x08 mass
#   0x0C bounce
#   0x10 friction
#   0x14 bulletForceScale
#   0x18 explosiveForceScale
#   0x1C sndAliasPrefix ptr
#   0x20 piecesSpreadFraction
#   0x24 piecesUpwardVelocity
#   0x28 canFloat
#   0x2C gravityScale
#   0x30 centerOfMassOffset[3]
#   0x3C buoyancyBoxMin[3]
#   0x48 buoyancyBoxMax[3]
PHYS_PRESET_SIZE = 84


class Walker(BaseWalker):
    def _record_dispatch(self, asset_type: str) -> None:
        counts = self.details.setdefault("inlineAssetDispatchCounts", {})
        counts[asset_type] = counts.get(asset_type, 0) + 1

    def walk_phys_preset(self, label: str) -> None:
        base, _ = self.take(PHYS_PRESET_SIZE, f"{label}.PhysPreset.fixed")
        name_ptr = self.u32at(base, 0)
        snd_alias_prefix_ptr = self.u32at(base, 28)
        self.walk_string_ptr(name_ptr, f"{label}.PhysPreset.name")
        self.walk_string_ptr(
            snd_alias_prefix_ptr, f"{label}.PhysPreset.sndAliasPrefix"
        )
        self._record_dispatch("PhysPreset")

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
        self.blockers.append(
            {
                "kind": "inline_external_asset_reference_requires_xasset_dispatch",
                "field": field,
                "ownerIndex": owner_index,
                "assetType": asset_type,
                "pointer": ptr_kind(ptr),
            }
        )

    def walk_xmodelpieces(self, label: str) -> None:
        base, _ = self.take(SIZE["XModelPieces"], f"{label}.fixed")
        name_ptr = self.u32at(base, 0)
        count = self.i32at(base, 4)
        pieces_ptr = self.u32at(base, 8)
        self.walk_string_ptr(name_ptr, f"{label}.name")
        if count < 0:
            raise WalkError(f"{label}: negative piece count {count}")
        if is_inline(pieces_ptr):
            a, _ = self.take(
                count * SIZE["XModelPiece"],
                f"{label}.pieces",
                meta={"count": count, "recordBytes": SIZE["XModelPiece"]},
            )
            for i in range(count):
                self.external_asset_ref(
                    f"{label}.pieces[{i}].model",
                    self.u32at(a + i * SIZE["XModelPiece"], 0),
                    i,
                    asset_type="XModel",
                )

    def walk_dynentdefs(self, ptr: int, count: int, label: str) -> None:
        if not is_inline(ptr):
            return
        a, _ = self.take(
            count * SIZE["DynEntityDef"],
            f"{label}.fixed",
            meta={"count": count, "recordBytes": SIZE["DynEntityDef"]},
        )
        types = Counter()
        inline_destroy_pieces = 0
        inline_phys_presets = 0
        for i in range(count):
            b = a + i * SIZE["DynEntityDef"]
            types[self.i32at(b, 0)] += 1

            # Follow native DynEntityDef field order. This matters if more than
            # one nested pointer is inline in the same definition.
            self.external_asset_ref(
                f"{label}[{i}].xModel",
                self.u32at(b, 32),
                i,
                asset_type="XModel",
            )
            self.external_asset_ref(
                f"{label}[{i}].destroyedxModel",
                self.u32at(b, 36),
                i,
                asset_type="XModel",
            )
            self.external_asset_ref(
                f"{label}[{i}].destroyFx",
                self.u32at(b, 44),
                i,
                asset_type="FX",
            )

            pieces_ptr = self.u32at(b, 52)
            if is_inline(pieces_ptr):
                inline_destroy_pieces += 1
                self.walk_xmodelpieces(f"{label}[{i}].destroyPieces")

            phys_preset_ptr = self.u32at(b, 56)
            if is_inline(phys_preset_ptr):
                inline_phys_presets += 1
            self.external_asset_ref(
                f"{label}[{i}].physPreset",
                phys_preset_ptr,
                i,
                asset_type="PhysPreset",
            )

        self.details.setdefault("dynEntDefLists", {})[label] = {
            "count": count,
            "typeCounts": {str(k): v for k, v in sorted(types.items())},
            "inlineDestroyPieces": inline_destroy_pieces,
            "inlinePhysPresets": inline_phys_presets,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "expanded", type=Path, help="decrypted/decompressed T6 XFile byte stream"
    )
    ap.add_argument(
        "--asset-start",
        type=lambda x: int(x, 0),
        required=True,
        help="raw source offset of fixed clipMap_t record (decimal or 0x...)",
    )
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--expect-end",
        type=lambda x: int(x, 0),
        help="optional assertion for independently known next-XAsset start",
    )
    args = ap.parse_args()

    data = args.expanded.read_bytes()
    result = Walker(data, args.asset_start).walk()
    result["format"] = "t6-clipmap-serialized-walk-v2"
    result["expandedBytes"] = len(data)
    result["expandedSha256"] = hashlib.sha256(data).hexdigest()
    if args.expect_end is not None:
        result["expectedEnd"] = args.expect_end
        result["expectedEndMatches"] = result["assetSerializedEnd"] == args.expect_end
        if not result["expectedEndMatches"]:
            raise SystemExit(
                f"walk ended at {result['assetSerializedEnd']}, expected {args.expect_end}"
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
