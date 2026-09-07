#!/usr/bin/env python3
"""Add a narrow native source-read trace for Nuketown q4 XMODEL debugging.

This patch is intentionally diagnostic-only. It is applied after
`t6_oat_expanded_xasset_trace_patch_v1.py`, which adds the monotonically
increasing `m_serialized_bytes_read` counter to ZoneInputStream. The trace is
restricted to the independently validated expanded-stream interval occupied by
Nuketown q4 (`499456..525881`) so the output stays compact and does not alter
loader semantics.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

TARGET = Path("src/ZoneLoading/Zone/Stream/ZoneInputStream.cpp")
Q4_START = 499456
Q4_END = 525881


def patch_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    if "T6_SOURCE_READ" in text:
        return 0
    if "m_serialized_bytes_read" not in text:
        raise SystemExit(
            "expanded-position patch is missing; apply "
            "t6_oat_expanded_xasset_trace_patch_v1.py first"
        )

    pat = re.compile(r"^(?P<indent>\s*)m_serialized_bytes_read \+= (?P<size>[^;]+);$", re.M)
    matches = list(pat.finditer(text))
    if not matches:
        raise SystemExit("could not find serialized-byte accounting increments")

    def repl(m: re.Match[str]) -> str:
        indent = m.group("indent")
        size = m.group("size").strip()
        return (
            f"{indent}m_serialized_bytes_read += {size};\n"
            f"{indent}{{\n"
            f"{indent}    const auto t6TraceSize = static_cast<uint64_t>({size});\n"
            f"{indent}    const auto t6TraceAfter = 40u + m_serialized_bytes_read;\n"
            f"{indent}    const auto t6TraceBefore = t6TraceAfter - t6TraceSize;\n"
            f"{indent}    if (t6TraceAfter > {Q4_START}u && t6TraceBefore < {Q4_END}u)\n"
            f"{indent}        std::cerr << \"T6_SOURCE_READ func=\" << __func__\n"
            f"{indent}                  << \" size=\" << t6TraceSize\n"
            f"{indent}                  << \" before=\" << t6TraceBefore\n"
            f"{indent}                  << \" after=\" << t6TraceAfter << '\\n';\n"
            f"{indent}}}"
        )

    patched, count = pat.subn(repl, text)
    if count != len(matches):
        raise SystemExit(f"patched {count} increments but found {len(matches)}")
    path.write_text(patched, encoding="utf-8")
    print(f"patched {path}: {count} serialized source-read sites")
    return count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("oat_root", type=Path)
    args = ap.parse_args()
    target = args.oat_root / TARGET
    if not target.is_file():
        raise SystemExit(f"missing {target}")
    count = patch_file(target)
    if count <= 0:
        print("source-read trace already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
