#!/usr/bin/env python3
"""Regression for the portable imagecodecs LZO adapter used by materializer v2."""
from __future__ import annotations

import ctypes
import importlib.util
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "t6_ipak_iwi_materialize_v2.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("t6_ipak_iwi_materialize_v2_test", TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import materializer v2")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    tool = load_tool()
    expected = b"portable-lzo-output"
    calls = []

    fake = types.ModuleType("imagecodecs")
    fake.LZO = types.SimpleNamespace(available=True)

    def fake_decode(data, *, out):
        calls.append((bytes(data), out))
        assert bytes(data) == b"compressed-fixture"
        assert out == 0x8000
        return expected

    fake.lzo_decode = fake_decode
    previous = sys.modules.get("imagecodecs")
    sys.modules["imagecodecs"] = fake
    try:
        adapter = tool.ImagecodecsLzo1xAdapter()
        src = ctypes.create_string_buffer(b"compressed-fixture")
        dst = ctypes.create_string_buffer(0x8000)
        n = ctypes.c_size_t(0x8000)
        rc = adapter(src, len(b"compressed-fixture"), dst, ctypes.byref(n), None)
        assert rc == 0
        assert n.value == len(expected)
        assert dst.raw[: n.value] == expected
        assert calls == [(b"compressed-fixture", 0x8000)]
    finally:
        if previous is None:
            sys.modules.pop("imagecodecs", None)
        else:
            sys.modules["imagecodecs"] = previous

    print("t6_ipak_iwi_materialize_v2 portable LZO adapter: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
