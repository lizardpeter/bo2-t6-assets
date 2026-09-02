#!/usr/bin/env python3
"""Retail T6 XAnim delta-branch census v2.

V2 deliberately extends the v1 structural validator for one additional retail-observed
XAnimParts form: assetType 0.  Two direct patch_mp fixtures (`void` and `void_loop`)
use assetType 0, inline names, and non-zero frame counts.

Blindly accepting assetType 0 is unsafe: packed-name/zero-frame byte patterns elsewhere
can satisfy the generic fixed-header checks accidentally.  Therefore v2 accepts type 0
only in the exact directly-observed structural class (inline name + numframes > 0), while
retaining the v1 checks for pointers, flags, padding, timing, child serialization and all
previously observed assetType values.

The rest of the census implementation is inherited unchanged from v1 so the evidence
delta is small and auditable.
"""
from __future__ import annotations

import t6_xanim_retail_delta_branch_census_v1 as v1


_original_valid_fixed = v1.valid_fixed


def valid_fixed_v2(data: bytes, start: int, rec: dict, blocks: list[int]) -> bool:
    if rec["assetType"] != 0:
        return _original_valid_fixed(data, start, rec, blocks)

    # Direct retained retail fixtures:
    #   patch_mp `void`      fixed SHA-256
    #     b82412114fc78c6778f841e42e5d479ad7a5c50b9480eae217014a5ef2df6a58
    #   patch_mp `void_loop` fixed SHA-256
    #     1f0c6d6e166937c02ffc7a5618d21c03db67f637bd7a5a15013e5905270716da
    # Both are inline-name, 80-frame records.  Do not generalize type 0 to packed or
    # zero-frame candidates without another direct retail fixture.
    if rec["namePtr"] != v1.FOLLOW or rec["numframes"] <= 0:
        return False

    # Reuse every v1 invariant by validating a shallow copy as an already-observed
    # assetType.  Only the assetType discriminator is broadened here.
    proxy = dict(rec)
    proxy["assetType"] = 1
    return _original_valid_fixed(data, start, proxy, blocks)


v1.valid_fixed = valid_fixed_v2


if __name__ == "__main__":
    v1.main()
