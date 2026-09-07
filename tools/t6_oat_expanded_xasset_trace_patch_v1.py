#!/usr/bin/env python3
"""Diagnostic-only patch for pinned OAT T6 expanded-stream XAsset positions.

Target: OpenAssetTools 9dca965366541504b71fa8cfb7ac049cb9b717e1.

The existing ProcessorXChunks::Pos() reports the underlying encrypted/compressed
file position and MUST NOT be compared with repository expanded-FastFile byte
offsets. This patch leaves Pos() untouched. Instead it adds a separate expanded
byte counter that advances by exactly the decompressed bytes returned from
ProcessorXChunks::Load, exposes that counter through ZoneInputStream, and logs it
immediately before/after each T6 top-level XAsset dispatch.

No asset parsing, pointer resolution, allocation, alignment, block, or shader
semantics are changed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

PINNED = "9dca965366541504b71fa8cfb7ac049cb9b717e1"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one patch anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("oat", type=Path)
    a = ap.parse_args()
    root = a.oat

    proc = root / "src/ZoneLoading/Loading/Processor/ProcessorXChunks.cpp"
    stream_h = root / "src/ZoneLoading/Zone/Stream/ZoneInputStream.h"
    stream_cpp = root / "src/ZoneLoading/Zone/Stream/ZoneInputStream.cpp"
    content = root / "src/ZoneLoading/Game/T6/ContentLoaderT6.cpp"
    for p in (proc, stream_h, stream_cpp, content):
        if not p.is_file():
            raise SystemExit(f"missing pinned OAT source: {p}")

    replace_once(
        proc,
        "              m_vanilla_buffer_offset(0),\n              m_eof_reached(false),\n              m_eof_stream(0)",
        "              m_vanilla_buffer_offset(0),\n              m_expanded_pos(0),\n              m_eof_reached(false),\n              m_eof_stream(0)",
    )
    replace_once(
        proc,
        "            return loadedSize;\n        }\n\n        int64_t Pos() override\n        {\n            return m_base_stream->Pos();\n        }",
        "            m_expanded_pos += static_cast<int64_t>(loadedSize);\n            return loadedSize;\n        }\n\n        int64_t Pos() override\n        {\n            return m_base_stream->Pos();\n        }\n\n        [[nodiscard]] int64_t ExpandedPos() const\n        {\n            return m_expanded_pos;\n        }",
    )
    replace_once(
        proc,
        "        size_t m_vanilla_buffer_offset;\n\n        bool m_eof_reached;",
        "        size_t m_vanilla_buffer_offset;\n        int64_t m_expanded_pos;\n\n        bool m_eof_reached;",
    )

    # IProcessorXChunks is the concrete processor interface returned to the
    # loader factory, so expose the diagnostic counter there without altering
    # ILoadingStream::Pos().
    iface = root / "src/ZoneLoading/Loading/Processor/ProcessorXChunks.h"
    if not iface.is_file():
        raise SystemExit(f"missing pinned OAT source: {iface}")
    replace_once(
        iface,
        "        virtual void AddChunkProcessor(std::unique_ptr<IXChunkProcessor> chunkProcessor) = 0;",
        "        virtual void AddChunkProcessor(std::unique_ptr<IXChunkProcessor> chunkProcessor) = 0;\n        [[nodiscard]] virtual int64_t ExpandedPos() const = 0;",
    )
    # Make the concrete method satisfy the interface explicitly.
    replace_once(
        proc,
        "        [[nodiscard]] int64_t ExpandedPos() const\n        {",
        "        [[nodiscard]] int64_t ExpandedPos() const override\n        {",
    )

    # ZoneInputStream receives only ILoadingStream, so add its own exact count of
    # serialized bytes requested from that decompressed stream. It starts after
    # the XFile block-size header; ContentLoader's first raw 24-byte XAssetList
    # read therefore lets us recover the absolute expanded offset with a fixed
    # loader-established base, which the workflow independently validates.
    replace_once(
        stream_h,
        "    [[nodiscard]] virtual unsigned GetPointerBitCount() const = 0;",
        "    [[nodiscard]] virtual unsigned GetPointerBitCount() const = 0;\n    [[nodiscard]] virtual uint64_t SerializedBytesRead() const = 0;",
    )
    replace_once(
        stream_cpp,
        "              m_progress_total_size(0uz)",
        "              m_progress_total_size(0uz),\n              m_serialized_bytes_read(0uz)",
    )
    replace_once(
        stream_cpp,
        "        [[nodiscard]] unsigned GetPointerBitCount() const override\n        {\n            return m_pointer_byte_count * 8u;\n        }",
        "        [[nodiscard]] unsigned GetPointerBitCount() const override\n        {\n            return m_pointer_byte_count * 8u;\n        }\n\n        [[nodiscard]] uint64_t SerializedBytesRead() const override\n        {\n            return m_serialized_bytes_read;\n        }",
    )
    replace_once(
        stream_cpp,
        "        void LoadDataRaw(void* dst, const size_t size) override\n        {\n            m_stream.Load(dst, size);\n        }",
        "        void LoadDataRaw(void* dst, const size_t size) override\n        {\n            m_stream.Load(dst, size);\n            m_serialized_bytes_read += size;\n        }",
    )
    replace_once(
        stream_cpp,
        "                m_stream.Load(&byte, 1);\n                block->m_buffer[offset++] = byte;",
        "                m_stream.Load(&byte, 1);\n                m_serialized_bytes_read += 1;\n                block->m_buffer[offset++] = byte;",
    )
    replace_once(
        stream_cpp,
        "            m_fill_buffer.resize(size);\n            m_stream.Load(m_fill_buffer.data(), size);\n            return ZoneStreamFillReadAccessor(m_fill_buffer.data(), size, m_pointer_byte_count, 0);",
        "            m_fill_buffer.resize(size);\n            m_stream.Load(m_fill_buffer.data(), size);\n            m_serialized_bytes_read += size;\n            return ZoneStreamFillReadAccessor(m_fill_buffer.data(), size, m_pointer_byte_count, 0);",
    )
    replace_once(
        stream_cpp,
        "            m_fill_buffer.resize(appendOffset + appendSize);\n            m_stream.Load(m_fill_buffer.data() + appendOffset, appendSize);\n            return ZoneStreamFillReadAccessor(m_fill_buffer.data(), m_last_fill_size, m_pointer_byte_count, 0);",
        "            m_fill_buffer.resize(appendOffset + appendSize);\n            m_stream.Load(m_fill_buffer.data() + appendOffset, appendSize);\n            m_serialized_bytes_read += appendSize;\n            return ZoneStreamFillReadAccessor(m_fill_buffer.data(), m_last_fill_size, m_pointer_byte_count, 0);",
    )
    replace_once(
        stream_cpp,
        "                m_stream.Load(dst, size);\n                break;",
        "                m_stream.Load(dst, size);\n                m_serialized_bytes_read += size;\n                break;",
    )
    replace_once(
        stream_cpp,
        "        size_t m_progress_total_size;\n    };",
        "        size_t m_progress_total_size;\n        uint64_t m_serialized_bytes_read;\n    };",
    )

    # The ZoneInputStream begins after StepLoadZoneSizes consumed the 40-byte
    # expanded XFile block-size header. Emit both the local count and the known
    # absolute expanded position as 40 + local. The workflow validates q3=125632
    # before trusting any later row.
    replace_once(
        content,
        "#include <cassert>\n",
        "#include <cassert>\n#include <iostream>\n",
    )
    replace_once(
        content,
        "    for (size_t index = 0; index < count; index++)\n    {\n        LoadXAsset(false);\n        varXAsset++;",
        "    for (size_t index = 0; index < count; index++)\n    {\n        const auto traceType = varXAsset->type;\n        const auto traceBeforeLocal = m_stream.SerializedBytesRead();\n        LoadXAsset(false);\n        const auto traceAfterLocal = m_stream.SerializedBytesRead();\n        std::cerr << \"T6_EXPANDED_XASSET index=\" << index\n                  << \" type=\" << traceType\n                  << \" beforeLocal=\" << traceBeforeLocal\n                  << \" afterLocal=\" << traceAfterLocal\n                  << \" before=\" << (40u + traceBeforeLocal)\n                  << \" after=\" << (40u + traceAfterLocal) << '\\n';\n        varXAsset++;",
    )

    print("patched pinned OAT with diagnostic-only T6 expanded XAsset trace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
