#!/usr/bin/env python3
"""Synthetic regression for the Nuketown $identitynormalmap block-5 proof."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFIER = HERE / "t6_nuketown_identitynormalmap_block5_proof_v1.py"
spec = importlib.util.spec_from_file_location("identityproof", VERIFIER)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

# XSurfaceCollisionNode is 16-byte aligned in retail T6.
assert mod.align_up(512820, 16) == 512832
assert mod.align_up(512820, 4) == 512820

# Three contiguous 16-byte MaterialTextureDef records, image at +12.
table_base = 514592
assert [table_base + i * 16 + 12 for i in range(3)] == [514604, 514620, 514636]
assert table_base + 16 + 12 == mod.EXPECTED_TARGET_OFFSET

# Lock packed XAsset 836 pointer encoding/decoding.
raw = ((5 << mod.BLOCK_SHIFT) | mod.EXPECTED_TARGET_OFFSET) + 1
assert raw == 0xA007DA3D
assert mod.decode_packed(raw) == (5, 514620)

# Historical wrong node alignment lands exactly 16 bytes too early.
assert mod.EXPECTED_TARGET_OFFSET - 16 == 514604

print("Nuketown identitynormalmap block5 synthetic regression: OK")
