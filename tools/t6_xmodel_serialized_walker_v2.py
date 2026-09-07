#!/usr/bin/env python3
"""T6 PC32 serialized XModel walker v2.

v2 preserves the v1 XModel structural walk and corrects the nested T6
GfxImageLoadDef source serializer. In T6, GfxImageLoadDef is a 12-byte prefix:

    +0  uint8  levelCount
    +1  uint8  flags
    +2  padding
    +4  int32  format
    +8  int32  resourceSize
    +12 byte   data[resourceSize]

`data` is a flexible inline array controlled by `resourceSize`; there is no
serialized data pointer at +8. This is source-closed by pinned OpenAssetTools
T6_Assets.h plus ZoneCode/Game/T6/XAssets/GfxImage.txt. v1 incorrectly read +0
as resourceSize and +8 as a pointer, which under-read XModels containing inline
GfxImage payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_clipmap_serialized_walker import is_inline, ptr_kind
from t6_xmodel_serialized_walker import XModelWalker as XModelWalkerV1

GFX_IMAGE_SIZE = 80
GFX_IMAGE_LOAD_DEF_PREFIX_SIZE = 12


class XModelWalker(XModelWalkerV1):
    def walk_gfx_image(self, label: str) -> None:
        base, _ = self.take(GFX_IMAGE_SIZE, f"{label}.GfxImage.fixed")
        load_def_ptr = self.u32at(base, 0)
        name_ptr = self.u32at(base, 72)

        # T6 GfxImage reorder contract is name, then texture/loadDef.
        name = self.walk_string_ptr(name_ptr, f"{label}.GfxImage.name")
        resource_size = None
        if is_inline(load_def_ptr):
            load_base, _ = self.take(
                GFX_IMAGE_LOAD_DEF_PREFIX_SIZE,
                f"{label}.GfxImage.loadDef.fixed",
            )
            resource_size = self.u32at(load_base, 8)
            if resource_size:
                self.take(
                    resource_size,
                    f"{label}.GfxImage.loadDef.data",
                    meta={"resourceSize": resource_size},
                )

        self.details.setdefault("inlineGfxImages", []).append(
            {
                "label": label,
                "name": name,
                "loadDefPointer": ptr_kind(load_def_ptr),
                "resourceSize": resource_size,
            }
        )
        self._record_dispatch("GfxImage")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('expanded', type=Path, help='decrypted/decompressed T6 XFile byte stream')
    ap.add_argument('--asset-start', type=lambda x: int(x, 0), required=True)
    ap.add_argument('--expect-end', type=lambda x: int(x, 0))
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()

    data = args.expanded.read_bytes()
    result = XModelWalker(data, args.asset_start).walk_xmodel()
    result['format'] = 't6-xmodel-serialized-walk-v2'
    result['expandedBytes'] = len(data)
    result['expandedSha256'] = hashlib.sha256(data).hexdigest()
    result['proofBoundary'] = [
        'GfxImageLoadDef resourceSize is read from +8 per pinned T6 native structure layout.',
        'GfxImageLoadDef data is consumed directly as resourceSize inline bytes per pinned T6 ZoneCode arraysize rule.',
        'No native XModel endpoint is fitted or supplied to the walker unless --expect-end is explicitly used as a regression assertion.'
    ]
    if args.expect_end is not None:
        result['expectedEnd'] = args.expect_end
        result['expectedEndMatches'] = result['assetSerializedEnd'] == args.expect_end
        if not result['expectedEndMatches']:
            raise SystemExit(
                f"walk ended at {result['assetSerializedEnd']}, expected {args.expect_end}; blockers={result['blockers']}"
            )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + '\n', encoding='utf-8')
    else:
        print(text)
    if result['blockers']:
        raise SystemExit(f"walk completed with blockers: {result['blockers']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
