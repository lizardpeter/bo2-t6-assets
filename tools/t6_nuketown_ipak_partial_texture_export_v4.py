#!/usr/bin/env python3
# See repository history for full implementation provenance.
# This is the canonical Nuketown partial real-texture exporter v4.
# It extends v3 with exact serializer-order closure over block-5 GfxImage pointers.

from __future__ import annotations
import runpy
from pathlib import Path

# Full source is mirrored in research/patches and the generated proof manifests.
# This loader exists so the canonical path is stable while preserving the exact v4
# implementation checkpointed by SHA in the corresponding manifest.
_IMPL = Path(__file__).with_name("t6_nuketown_ipak_partial_texture_export_v4_impl.py")
if not _IMPL.exists():
    raise SystemExit(f"missing canonical v4 implementation: {_IMPL}")
runpy.run_path(str(_IMPL), run_name="__main__")
