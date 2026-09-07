#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "compat", HERE / "t6_oat_9dca_gcc_compat_patch_v2.py"
)
assert SPEC and SPEC.loader
compat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compat)


class CompatPatchV2Tests(unittest.TestCase):
    def test_exact_missing_headers_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in compat.FORMAT_TARGETS:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    '#include "x.h"\n\n#include <cassert>\n#include <cmath>\n#include <limits>\n#include <sstream>\n',
                    encoding="utf-8",
                )
            xanim = root / compat.LIMITS_TARGET
            xanim.parent.mkdir(parents=True, exist_ok=True)
            xanim.write_text(
                '#include "FlatXAnimDataWriter.h"\n\n#include <cassert>\n#include <iterator>\n',
                encoding="utf-8",
            )

            for rel in compat.FORMAT_TARGETS:
                self.assertEqual(
                    "patched",
                    compat.insert_once(
                        root / rel,
                        needle="#include <cmath>\n",
                        insert="#include <cmath>\n#include <format>\n",
                        marker="#include <format>\n",
                    ),
                )
            self.assertEqual(
                "patched",
                compat.insert_once(
                    xanim,
                    needle="#include <iterator>\n",
                    insert="#include <iterator>\n#include <limits>\n",
                    marker="#include <limits>\n",
                ),
            )

            for rel in compat.FORMAT_TARGETS:
                text = (root / rel).read_text(encoding="utf-8")
                self.assertEqual(1, text.count("#include <format>\n"))
                self.assertIn("#include <cmath>\n#include <format>\n#include <limits>\n", text)
            text = xanim.read_text(encoding="utf-8")
            self.assertEqual(1, text.count("#include <limits>\n"))
            self.assertEqual(
                '#include "FlatXAnimDataWriter.h"\n\n#include <cassert>\n#include <iterator>\n#include <limits>\n',
                text,
            )

    def test_unexpected_layout_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.cpp"
            path.write_text("#include <cmath>\n#include <cmath>\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                compat.insert_once(
                    path,
                    needle="#include <cmath>\n",
                    insert="#include <cmath>\n#include <format>\n",
                    marker="#include <format>\n",
                )
            self.assertEqual("#include <cmath>\n#include <cmath>\n", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
