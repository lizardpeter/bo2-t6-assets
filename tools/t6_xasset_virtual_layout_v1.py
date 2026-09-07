#!/usr/bin/env python3
"""Derive the top-level T6 XAsset-array VIRTUAL base from XAssetList load order.

T6 ContentLoader::Load loads the fixed 24-byte XAssetList into a local object
*before* pushing XFILE_BLOCK_VIRTUAL.  Therefore those 24 bytes never advance
the VIRTUAL allocation cursor.  After PushBlock(XFILE_BLOCK_VIRTUAL), the
loader allocates, in order:

  1. ScriptStringList pointer array (4-byte aligned), then inline strings;
  2. dependency pointer array (4-byte aligned), then inline strings;
  3. XAsset array (4-byte aligned).

The returned ``xassetArrayVirtualBase`` is the VIRTUAL cursor immediately
before allocation (3), i.e. the base used by packed pointers to XAsset.header.

Source-closure reference used to pin this order:
Laupetin/OpenAssetTools src/ZoneLoading/Game/T6/ContentLoaderT6.cpp,
ContentLoader::Load / LoadScriptStringList.  Runtime extraction does not depend
on that repository: the calculation below is performed solely from exact
expanded retail bytes and fails closed on unsupported pointer modes.
"""
from __future__ import annotations

import struct
from typing import Any

FOLLOW = 0xFFFFFFFF
INSERT = 0xFFFFFFFE


class XAssetVirtualLayoutError(RuntimeError):
    pass


def align4(value: int) -> int:
    return (int(value) + 3) & ~3


def _inline_cstring(data: bytes, source: int, label: str) -> tuple[int, str]:
    if source < 0 or source >= len(data):
        raise XAssetVirtualLayoutError(f"{label}: source cursor out of range: {source}")
    end = data.find(b"\0", source)
    if end < 0:
        raise XAssetVirtualLayoutError(f"{label}: unterminated inline string")
    try:
        value = data[source:end].decode("latin1")
    except Exception as exc:  # pragma: no cover - latin1 is total, retained for fail-closed clarity
        raise XAssetVirtualLayoutError(f"{label}: string decode failed") from exc
    return end + 1, value


def _consume_xstring_array(
    data: bytes,
    source: int,
    virtual: int,
    count: int,
    outer_pointer: int,
    label: str,
) -> tuple[int, int, dict[str, Any]]:
    if count < 0:
        raise XAssetVirtualLayoutError(f"{label}: negative count")
    if count == 0:
        if outer_pointer not in (0,):
            raise XAssetVirtualLayoutError(
                f"{label}: zero count has non-null outer pointer 0x{outer_pointer:08X}"
            )
        return source, virtual, {
            "count": 0,
            "pointerArrayBytes": 0,
            "inlineCount": 0,
            "inlineBytes": 0,
            "virtualStart": virtual,
            "virtualEnd": virtual,
        }
    if outer_pointer != FOLLOW:
        raise XAssetVirtualLayoutError(
            f"{label}: unsupported outer pointer mode 0x{outer_pointer:08X}; expected FOLLOWING"
        )

    virtual = align4(virtual)
    virtual_start = virtual
    pointer_bytes = 4 * count
    if source + pointer_bytes > len(data):
        raise XAssetVirtualLayoutError(f"{label}: pointer array overruns expanded stream")
    pointers = struct.unpack_from(f"<{count}I", data, source)
    source += pointer_bytes
    virtual += pointer_bytes

    inline_count = 0
    inline_bytes = 0
    values: list[str] = []
    for index, raw in enumerate(pointers):
        if raw == FOLLOW:
            before = source
            source, value = _inline_cstring(data, source, f"{label}[{index}]")
            consumed = source - before
            virtual += consumed
            inline_bytes += consumed
            inline_count += 1
            values.append(value)
        elif raw == 0:
            values.append("")
        else:
            # A packed/insert XString does not have an inline byte extent that can
            # be inferred here without replaying its pointer semantics.  Refuse to
            # fabricate a VIRTUAL cursor.
            raise XAssetVirtualLayoutError(
                f"{label}[{index}]: unsupported XString pointer 0x{raw:08X}"
            )

    return source, virtual, {
        "count": count,
        "pointerArrayBytes": pointer_bytes,
        "inlineCount": inline_count,
        "inlineBytes": inline_bytes,
        "virtualStart": virtual_start,
        "virtualEnd": virtual,
        "values": values,
    }


def derive_xasset_array_virtual_base(data: bytes) -> dict[str, Any]:
    """Replay the T6 XAssetList front allocations up to the XAsset array."""
    if len(data) < 64:
        raise XAssetVirtualLayoutError("expanded stream too small for T6 XAssetList front")

    # 8 block sizes at +8 consume the first 40 source bytes.  The serialized
    # XAssetList fixed fields begin at source +40 and are 24 bytes on T6 PC32:
    # ScriptStringList (8), dependCount/depends (8), assetCount/assets (8).
    script_count, script_ptr, depend_count, depend_ptr, asset_count, asset_ptr = struct.unpack_from(
        "<6I", data, 40
    )
    source = 64
    virtual = 0

    source, virtual, scripts = _consume_xstring_array(
        data, source, virtual, script_count, script_ptr, "scriptStrings"
    )
    source, virtual, dependencies = _consume_xstring_array(
        data, source, virtual, depend_count, depend_ptr, "dependencies"
    )

    if asset_count == 0:
        if asset_ptr != 0:
            raise XAssetVirtualLayoutError(
                f"zero asset count has non-null asset pointer 0x{asset_ptr:08X}"
            )
    elif asset_ptr != FOLLOW:
        raise XAssetVirtualLayoutError(
            f"unsupported XAsset array pointer 0x{asset_ptr:08X}; expected FOLLOWING"
        )

    xasset_base = align4(virtual)
    expected_asset_source = source
    asset_bytes = 8 * asset_count
    if expected_asset_source + asset_bytes > len(data):
        raise XAssetVirtualLayoutError("serialized XAsset array overruns expanded stream")

    return {
        "format": "t6-xasset-virtual-layout-v1",
        "fixedXAssetListBytes": 24,
        "fixedXAssetListConsumesVirtualBytes": False,
        "virtualBlock": 5,
        "scriptStrings": scripts,
        "dependencies": dependencies,
        "assetCount": asset_count,
        "assetPointerRaw": f"0x{asset_ptr:08X}",
        "xassetArraySourceStart": expected_asset_source,
        "xassetArrayBytes": asset_bytes,
        "xassetArrayVirtualBase": xasset_base,
        "xassetHeaderFieldVirtualBase": xasset_base + 4,
        "virtualCursorBeforeXAssetAlignment": virtual,
        "proof": (
            "24-byte XAssetList fixed data is resident before XFILE_BLOCK_VIRTUAL is pushed; "
            "only ScriptString pointer/string payloads and dependency pointer/string payloads "
            "advance the VIRTUAL cursor before the 4-byte-aligned XAsset array allocation"
        ),
    }
