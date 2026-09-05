#!/usr/bin/env python3
"""Portable frontend for the proven T6 IPAK/IWI materializer v1.

v1's byte/identity semantics remain authoritative and untouched. v2 changes only
the LZO1X backend selection so Windows does not require a separately installed
lzo2 DLL:

1. Prefer imagecodecs.lzo_decode (prebuilt wheels include the LZO decoder).
2. Fall back to v1's system liblzo2 backend when available.

The adapter deliberately implements the same five-argument call contract used by
v1's ctypes lzo1x_decompress_safe invocation. Every reconstructed IPAK payload is
still independently CRC29-checked by v1 before it can be promoted.
"""
from __future__ import annotations

import ctypes
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "t6_ipak_iwi_materialize_v1.py"


def _load_v1():
    spec = importlib.util.spec_from_file_location("t6_ipak_iwi_materialize_v1", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_v1()
TextureError = base.TextureError


class ImagecodecsLzo1xAdapter:
    """Expose imagecodecs.lzo_decode through v1's ctypes-style call contract."""

    backend_name = "imagecodecs.lzo_decode"

    def __init__(self):
        try:
            import imagecodecs
        except Exception as exc:  # pragma: no cover - platform/package dependent
            raise TextureError(f"imagecodecs import failed: {exc}") from exc
        if not getattr(getattr(imagecodecs, "LZO", None), "available", False):
            raise TextureError("imagecodecs is installed but its LZO decoder is unavailable")
        self._decode = imagecodecs.lzo_decode

    def __call__(self, src, src_len, dst, out_len_ptr, _workmem):
        try:
            src_len = int(src_len)
            compressed = ctypes.string_at(src, src_len)
            # T6 IPAK LZO commands decompress to at most one 0x8000-byte chunk.
            decoded = self._decode(compressed, out=0x8000)
            if not isinstance(decoded, (bytes, bytearray, memoryview)):
                decoded = bytes(decoded)
            decoded = bytes(decoded)
            if len(decoded) > 0x8000:
                return -5  # mirror an output-overrun style failure
            ctypes.memmove(dst, decoded, len(decoded))
            ctypes.cast(out_len_ptr, ctypes.POINTER(ctypes.c_size_t))[0] = len(decoded)
            return 0
        except Exception:
            return -1


def load_portable_lzo():
    errors = []
    try:
        return ImagecodecsLzo1xAdapter()
    except Exception as exc:
        errors.append(f"imagecodecs: {exc}")
    try:
        native = base.load_lzo()
        try:
            setattr(native, "backend_name", "system liblzo2")
        except Exception:
            pass
        return native
    except Exception as exc:
        errors.append(f"system liblzo2: {exc}")
    raise TextureError(
        "no LZO1X backend is available. Install the pinned portable Python "
        "dependency with `python -m pip install imagecodecs==2026.8.16`, or "
        "provide a system liblzo2. Backend errors: " + " | ".join(errors)
    )


def main() -> int:
    # v1.main resolves load_lzo from its own module globals. Override only that
    # backend hook; all exact-key, CRC29, IWI27, dimension and PNG semantics stay v1.
    base.load_lzo = load_portable_lzo
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
