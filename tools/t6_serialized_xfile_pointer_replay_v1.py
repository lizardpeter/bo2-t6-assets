#!/usr/bin/env python3
"""Fail-closed replay of T6 32-bit serialized XFile block pointers.

This is intentionally separate from runtime DB_ConvertOffsetToAlias/Sys_DecodePointer
replay. Retail T6 PC fastfiles serialize non-inline pointers as a 32-bit block/offset
value shifted by +1 so zero remains the null pointer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

NULL = 0x00000000
INLINE_SHARED = 0xFFFFFFFF
INLINE_FOLLOWING = 0xFFFFFFFE
INLINE_INSERT = 0xFFFFFFFD
INLINE_SENTINELS = {INLINE_SHARED, INLINE_FOLLOWING, INLINE_INSERT}

POINTER_BITS = 32
BLOCK_BITS = 3
OFFSET_BITS = POINTER_BITS - BLOCK_BITS
OFFSET_MASK = (1 << OFFSET_BITS) - 1
T6_XFILE_BLOCK_VIRTUAL = 5
EXACT_EVIDENCE = "retail-t6-xfile-32bit-3blockbits-offset-plus-one"
OAT_SOURCE_REVISION = "2ca512abe7cb82d70a94d5ad7846043c3978862d"
OAT_SOURCE_PATHS = (
    "src/ZoneCommon/Game/T6/ZoneConstantsT6.h",
    "src/ZoneLoading/Game/T6/ZoneLoaderFactoryT6.cpp",
    "src/ZoneLoading/Zone/Stream/ZoneInputStream.cpp",
    "src/Common/Game/T6/T6_Assets.h",
)


def u32(value: int | str) -> int:
    if isinstance(value, str):
        return int(value, 0) & 0xFFFFFFFF
    return int(value) & 0xFFFFFFFF


@dataclass(frozen=True)
class SerializedPointer:
    raw: int
    block_index: int
    block_offset: int


@dataclass(frozen=True)
class SerializedPointerResolution:
    exact: bool
    classification: str
    reason: str
    raw_token: int
    block_index: Optional[int] = None
    block_offset: Optional[int] = None
    material: Optional[str] = None
    owner_model: Optional[str] = None
    owner_slot_index: Optional[int] = None
    owner_material_raw_start: Optional[int] = None


def decode_serialized_pointer(raw_token: int | str) -> SerializedPointer:
    raw = u32(raw_token)
    if raw == NULL:
        raise ValueError("null pointer is not a packed XFile block pointer")
    if raw in INLINE_SENTINELS:
        raise ValueError("inline sentinel is not a packed XFile block pointer")
    shifted = (raw - 1) & 0xFFFFFFFF
    return SerializedPointer(
        raw=raw,
        block_index=shifted >> OFFSET_BITS,
        block_offset=shifted & OFFSET_MASK,
    )


def validate_serialized_material_replay(row: Mapping[str, object]) -> SerializedPointerResolution:
    """Validate a packed Material* against an independently established owner slot."""
    raw = u32(row.get("handleRaw", 0))
    proof = row.get("serializedReplay")
    if not isinstance(proof, Mapping):
        return SerializedPointerResolution(False, "serialized-replay-missing", "packed assignment has no serializedReplay proof", raw)
    if proof.get("status") != "exact":
        return SerializedPointerResolution(False, "serialized-replay-not-exact", "serializedReplay status is not exact", raw)
    if proof.get("evidence") != EXACT_EVIDENCE:
        return SerializedPointerResolution(False, "serialized-evidence-unaccepted", "serializedReplay evidence is not the pinned T6 XFile pointer format", raw)
    if proof.get("sourceRevision") != OAT_SOURCE_REVISION:
        return SerializedPointerResolution(
            False,
            "serialized-source-revision-unaccepted",
            "serializedReplay does not pin the source-closed OpenAssetTools revision",
            raw,
        )
    if int(proof.get("pointerBits", -1)) != POINTER_BITS or int(proof.get("blockBits", -1)) != BLOCK_BITS:
        return SerializedPointerResolution(False, "serialized-layout-mismatch", "serializedReplay does not declare T6 32-bit/3-block-bit layout", raw)

    owner = proof.get("owner")
    if not isinstance(owner, Mapping):
        return SerializedPointerResolution(False, "serialized-owner-missing", "serializedReplay lacks independent owner", raw)
    try:
        owner_slot = u32(owner["pointerSlotVirtual"])
        material = str(owner["material"])
        owner_model = str(owner["model"])
        owner_slot_index = int(owner["slotIndex"])
        owner_raw_start_v = owner.get("materialRawStart")
        owner_raw_start = None if owner_raw_start_v is None else int(owner_raw_start_v)
    except (KeyError, TypeError, ValueError) as exc:
        return SerializedPointerResolution(False, "serialized-owner-invalid", f"invalid serialized owner: {exc}", raw)

    try:
        decoded = decode_serialized_pointer(raw)
    except ValueError as exc:
        return SerializedPointerResolution(False, "serialized-token-invalid", str(exc), raw)

    if decoded.block_index != T6_XFILE_BLOCK_VIRTUAL:
        return SerializedPointerResolution(
            False, "serialized-block-not-virtual",
            f"packed Material* decodes to XFile block {decoded.block_index}, expected VIRTUAL block {T6_XFILE_BLOCK_VIRTUAL}",
            raw, decoded.block_index, decoded.block_offset,
        )
    if decoded.block_offset != owner_slot:
        return SerializedPointerResolution(
            False, "serialized-owner-slot-mismatch",
            f"decoded VIRTUAL offset 0x{decoded.block_offset:x} != independent owner slot 0x{owner_slot:x}",
            raw, decoded.block_index, decoded.block_offset,
        )
    claimed_block = proof.get("decodedBlockIndex")
    if claimed_block is not None and int(claimed_block) != decoded.block_index:
        return SerializedPointerResolution(False, "serialized-block-claim-mismatch", "claimed block index differs from replay", raw, decoded.block_index, decoded.block_offset)
    claimed_offset = proof.get("decodedBlockOffset")
    if claimed_offset is not None and u32(claimed_offset) != decoded.block_offset:
        return SerializedPointerResolution(False, "serialized-offset-claim-mismatch", "claimed block offset differs from replay", raw, decoded.block_index, decoded.block_offset)
    row_material = row.get("material")
    if row_material is None or str(row_material).lstrip(",") != material.lstrip(","):
        return SerializedPointerResolution(False, "serialized-material-mismatch", f"row material {row_material!r} != independent owner {material!r}", raw, decoded.block_index, decoded.block_offset, material, owner_model, owner_slot_index, owner_raw_start)

    return SerializedPointerResolution(
        True,
        "packed-virtual-material-owner-serialized-xfile-replay",
        "T6 serialized block pointer decodes exactly to the independently established VIRTUAL materialHandles[] owner field",
        raw, decoded.block_index, decoded.block_offset, material, owner_model, owner_slot_index, owner_raw_start,
    )
