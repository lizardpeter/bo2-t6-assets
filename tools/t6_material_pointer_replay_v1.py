#!/usr/bin/env python3
"""Exact, fail-closed replay primitives for T6 serialized Material* pointers.

This module deliberately separates three things which older forensic scripts often
blurred together:

* the 32-bit value stored in the serialized pointer field;
* the *decoded* value consumed by DB_ConvertOffsetToAlias; and
* the pointer slot/object reached after the zone/segment arithmetic.

A packed raw token is never decoded heuristically here.  Production callers must
supply a decoded value with source-backed decoder evidence.  The helper then
replays the retail DB_ConvertOffsetToAlias arithmetic and resolves the resulting
pointer slot against objects that were established by inline Material* loads.

Inline sentinels are also modeled.  In particular, -3 allocates its insert slot
before loading the inline object and back-fills that slot afterwards, matching the
retail DB_InsertPointer lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

NULL = 0x00000000
INLINE_SHARED = 0xFFFFFFFF   # -1
INLINE_FOLLOWING = 0xFFFFFFFE  # -2
INLINE_INSERT = 0xFFFFFFFD   # -3
INLINE_SENTINELS = {INLINE_SHARED, INLINE_FOLLOWING, INLINE_INSERT}

EXACT_DECODER_EVIDENCE = {
    "retail-Sys_DecodePointer-replay",
    "retail-RtlDecodePointer-Sys_DecodePointer-replay",
}
SYNTHETIC_DECODER_EVIDENCE = "synthetic-decoded-pointer-fixture"


def u32(value: int | str) -> int:
    if isinstance(value, str):
        return int(value, 0) & 0xFFFFFFFF
    return int(value) & 0xFFFFFFFF


@dataclass(frozen=True)
class MaterialObject:
    material: str
    object_virtual: int
    owner_pointer_slot_virtual: int


@dataclass(frozen=True)
class PointerResolution:
    exact: bool
    classification: str
    reason: str
    raw_token: int
    decoded_pointer: Optional[int] = None
    target_pointer_slot_virtual: Optional[int] = None
    material: Optional[str] = None
    object_virtual: Optional[int] = None


class MaterialPointerReplay:
    """Replay enough Material* loader state to prove pointer-slot aliases exactly."""

    def __init__(self) -> None:
        self.pointer_slots: Dict[int, MaterialObject] = {}
        self.objects: Dict[int, MaterialObject] = {}
        self.insert_slots: Dict[int, Optional[MaterialObject]] = {}
        self.events: list[Tuple[str, int]] = []

    def load_inline(
        self,
        *,
        pointer_slot_virtual: int,
        raw_token: int | str,
        object_virtual: int,
        material: str,
        insert_slot_virtual: Optional[int] = None,
    ) -> MaterialObject:
        token = u32(raw_token)
        if token not in INLINE_SENTINELS:
            raise ValueError(f"0x{token:08x} is not an inline Material* sentinel")
        slot = int(pointer_slot_virtual)
        objv = int(object_virtual)
        if slot in self.pointer_slots:
            raise ValueError(f"pointer slot 0x{slot:x} already populated")
        if objv in self.objects:
            raise ValueError(f"Material object 0x{objv:x} already loaded")

        insert = None
        if token == INLINE_INSERT:
            if insert_slot_virtual is None:
                raise ValueError("-3 Material* requires an insert-slot virtual address")
            insert = int(insert_slot_virtual)
            if insert in self.insert_slots or insert in self.pointer_slots:
                raise ValueError(f"insert slot 0x{insert:x} already exists")
            self.insert_slots[insert] = None
            self.events.append(("insert-allocate", insert))
        elif insert_slot_virtual is not None:
            raise ValueError("insert-slot address is valid only for -3 Material*")

        # Retail order: DB_InsertPointer (for -3), inline Material load, then back-fill.
        self.events.append(("inline-load", objv))
        obj = MaterialObject(material=material, object_virtual=objv, owner_pointer_slot_virtual=slot)
        self.objects[objv] = obj
        self.pointer_slots[slot] = obj
        self.events.append(("owner-slot-write", slot))

        if insert is not None:
            self.insert_slots[insert] = obj
            self.pointer_slots[insert] = obj
            self.events.append(("insert-backfill", insert))
        return obj

    @staticmethod
    def convert_decoded_offset_to_alias(
        decoded_pointer: int | str,
        zone_segment_bases: Mapping[int | str, Sequence[int | None] | Mapping[int | str, int | None]],
    ) -> Tuple[int, int, int, int]:
        """Replay the non-fallback DB_ConvertOffsetToAlias zone/segment arithmetic.

        Decoded values below 8 take a retail fallback branch whose owning-zone
        context is external to the pointer value.  This helper refuses to invent
        that context and therefore fails closed for those values.
        """
        decoded = u32(decoded_pointer)
        if decoded < 8:
            raise ValueError("decoded pointer < 8 requires external retail zone-fallback context")

        zone_index = decoded >> 29
        masked = decoded & 0x1FFFFFFF
        segment_index = masked >> 27
        segment_offset = masked & 0x07FFFFFF

        zone = zone_segment_bases.get(zone_index)
        if zone is None:
            zone = zone_segment_bases.get(str(zone_index))
        if zone is None:
            raise ValueError(f"zone {zone_index} has no exact segment-base table")

        base = None
        if isinstance(zone, Mapping):
            base = zone.get(segment_index)
            if base is None:
                base = zone.get(str(segment_index))
        elif segment_index < len(zone):
            base = zone[segment_index]
        if base is None:
            raise ValueError(
                f"zone {zone_index} segment {segment_index} has no exact base"
            )
        target = int(base) + segment_offset
        return target, zone_index, segment_index, segment_offset

    def resolve_packed(
        self,
        *,
        raw_token: int | str,
        decoded_pointer: int | str | None,
        decoded_pointer_evidence: str | None,
        zone_segment_bases: Mapping[int | str, Sequence[int | None] | Mapping[int | str, int | None]],
        allow_synthetic: bool = False,
    ) -> PointerResolution:
        raw = u32(raw_token)
        if raw == NULL:
            return PointerResolution(True, "null", "serialized null Material*", raw)
        if raw in INLINE_SENTINELS:
            return PointerResolution(
                False,
                "inline-sentinel-not-packed",
                "inline sentinels must be replayed with load_inline",
                raw,
            )
        if decoded_pointer is None:
            return PointerResolution(
                False,
                "runtime-token-unresolved",
                "packed raw token has no exact Sys_DecodePointer result",
                raw,
            )
        allowed = set(EXACT_DECODER_EVIDENCE)
        if allow_synthetic:
            allowed.add(SYNTHETIC_DECODER_EVIDENCE)
        if decoded_pointer_evidence not in allowed:
            return PointerResolution(
                False,
                "decoder-evidence-unaccepted",
                f"decoded pointer evidence {decoded_pointer_evidence!r} is not source-backed",
                raw,
                decoded_pointer=u32(decoded_pointer),
            )
        try:
            target, _zone, _segment, _offset = self.convert_decoded_offset_to_alias(
                decoded_pointer, zone_segment_bases
            )
        except ValueError as exc:
            return PointerResolution(
                False,
                "alias-target-invalid",
                str(exc),
                raw,
                decoded_pointer=u32(decoded_pointer),
            )
        obj = self.pointer_slots.get(target)
        if obj is None:
            return PointerResolution(
                False,
                "alias-target-unpopulated",
                f"resolved pointer slot 0x{target:x} has no replayed Material* owner",
                raw,
                decoded_pointer=u32(decoded_pointer),
                target_pointer_slot_virtual=target,
            )
        return PointerResolution(
            True,
            "packed-virtual-material-owner",
            "decoded pointer resolved through exact zone/segment arithmetic to a replayed Material* pointer slot",
            raw,
            decoded_pointer=u32(decoded_pointer),
            target_pointer_slot_virtual=target,
            material=obj.material,
            object_virtual=obj.object_virtual,
        )


def validate_packed_loader_replay(
    row: Mapping[str, object], *, allow_synthetic: bool = False
) -> PointerResolution:
    """Validate one durable surface assignment's explicit loaderReplay proof.

    The proof must contain the inline owner that populated the target pointer slot,
    plus the exact decoded-pointer evidence and zone segment bases needed to derive
    that slot.  Merely naming a material or supplying a precomputed target is not
    sufficient.
    """
    proof = row.get("loaderReplay")
    raw = row.get("handleRaw", 0)
    if not isinstance(proof, Mapping):
        return PointerResolution(
            False,
            "loader-replay-missing",
            "packed assignment has no loaderReplay proof",
            u32(raw),
        )
    if proof.get("status") != "exact":
        return PointerResolution(
            False,
            "loader-replay-not-exact",
            "loaderReplay status is not exact",
            u32(raw),
        )
    owner = proof.get("inlineOwner")
    if not isinstance(owner, Mapping):
        return PointerResolution(False, "inline-owner-missing", "loaderReplay lacks inlineOwner", u32(raw))
    bases = proof.get("zoneSegmentBases")
    if not isinstance(bases, Mapping):
        return PointerResolution(False, "segment-bases-missing", "loaderReplay lacks exact zoneSegmentBases", u32(raw))

    try:
        owner_material = str(owner["material"])
        owner_slot = u32(owner["pointerSlotVirtual"])
        owner_obj = u32(owner["objectVirtual"])
        owner_token = u32(owner["rawToken"])
        insert_slot = owner.get("insertSlotVirtual")
        insert_slot_i = None if insert_slot is None else u32(insert_slot)
    except (KeyError, TypeError, ValueError) as exc:
        return PointerResolution(False, "inline-owner-invalid", f"invalid inlineOwner: {exc}", u32(raw))

    state = MaterialPointerReplay()
    try:
        state.load_inline(
            pointer_slot_virtual=owner_slot,
            raw_token=owner_token,
            object_virtual=owner_obj,
            material=owner_material,
            insert_slot_virtual=insert_slot_i,
        )
    except ValueError as exc:
        return PointerResolution(False, "inline-owner-invalid", str(exc), u32(raw))

    result = state.resolve_packed(
        raw_token=raw,
        decoded_pointer=proof.get("decodedPointer"),
        decoded_pointer_evidence=(
            None if proof.get("decodedPointerEvidence") is None else str(proof.get("decodedPointerEvidence"))
        ),
        zone_segment_bases=bases,
        allow_synthetic=allow_synthetic,
    )
    if not result.exact:
        return result

    claimed_material = row.get("material")
    if claimed_material is None or str(claimed_material) != result.material:
        return PointerResolution(
            False,
            "material-identity-mismatch",
            f"row material {claimed_material!r} != replayed owner {result.material!r}",
            result.raw_token,
            result.decoded_pointer,
            result.target_pointer_slot_virtual,
            result.material,
            result.object_virtual,
        )
    claimed_target = proof.get("resolvedTargetPointerSlotVirtual")
    if claimed_target is not None and u32(claimed_target) != result.target_pointer_slot_virtual:
        return PointerResolution(
            False,
            "target-claim-mismatch",
            "claimed resolved target does not match DB_ConvertOffsetToAlias replay",
            result.raw_token,
            result.decoded_pointer,
            result.target_pointer_slot_virtual,
            result.material,
            result.object_virtual,
        )
    return result
