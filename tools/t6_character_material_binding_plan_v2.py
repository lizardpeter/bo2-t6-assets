#!/usr/bin/env python3
"""Strict frontend for exact T6 character material binding-plan v1.

v2 accepts durable `t6-xmodel-surface-material-assignments-v1` manifests, but a
packed assignment is exact only when one of two source-closed pointer paths is
explicitly replayed:

Runtime pointer path:
    raw token -> exact Sys_DecodePointer result -> DB_ConvertOffsetToAlias
    -> exact pointer slot -> replayed inline Material owner

Serialized retail XFile path:
    raw 32-bit archive pointer -> subtract-one block/offset decode
    -> T6 XFILE_BLOCK_VIRTUAL (block 5) -> exact independently established
       XModel.materialHandles[] VIRTUAL owner field

The serialized path is deliberately separate from runtime pointer-cookie decoding.
No packed row is admitted from naming, adjacency, LOD similarity, or low bits alone.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "t6_character_material_binding_plan_v1.py"
REPLAY_PATH = HERE / "t6_material_pointer_replay_v1.py"
SERIALIZED_REPLAY_PATH = HERE / "t6_serialized_xfile_pointer_replay_v1.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = _load_module("t6_character_material_binding_plan_v1", BASE_PATH)
replay = _load_module("t6_material_pointer_replay_v1", REPLAY_PATH)
serialized_replay = _load_module("t6_serialized_xfile_pointer_replay_v1", SERIALIZED_REPLAY_PATH)
_original_load = base.load


def adapt_surface_assignment_doc(doc: dict, *, allow_synthetic: bool = False) -> dict:
    if doc.get("format") != "t6-xmodel-surface-material-assignments-v1":
        return doc

    rows = doc.get("assignments")
    if not isinstance(rows, list):
        raise RuntimeError("surface assignment manifest lacks assignments[]")
    expected = int((doc.get("summary") or {}).get("surfaces", len(rows)))
    if len(rows) != expected:
        raise RuntimeError(f"surface assignment row count {len(rows)} != expected {expected}")

    indices = [int(r["surfaceIndex"]) for r in rows]
    if indices != list(range(expected)):
        raise RuntimeError("surface assignment indices are not exact contiguous 0..N-1")

    legacy = []
    inline_count = 0
    runtime_packed_count = 0
    serialized_packed_count = 0
    packed_backrefs = 0
    for r in rows:
        token = replay.u32(r["handleRaw"])
        if r.get("handleKind") == "inline-following":
            if token not in replay.INLINE_SENTINELS:
                raise RuntimeError(
                    f"surface {r['surfaceIndex']}: inline-following has non-inline token 0x{token:08x}"
                )
            evidence = "exact-inline-retail-material"
            inline_count += 1
            derived = None
        elif "serializedReplay" in r:
            result = serialized_replay.validate_serialized_material_replay(r)
            if not result.exact:
                raise RuntimeError(
                    f"surface {r['surfaceIndex']}: packed Material* is not exact under T6 serialized XFile replay: "
                    f"{result.classification}: {result.reason}"
                )
            evidence = "exact-packed-virtual-material-owner-serialized-xfile-replay"
            serialized_packed_count += 1
            proof = r.get("serializedReplay") or {}
            if bool(proof.get("sameOwnerBackreference", False)):
                packed_backrefs += 1
            derived = {
                "mode": "serialized-xfile",
                "blockIndex": result.block_index,
                "resolvedTargetPointerSlotVirtual": result.block_offset,
                "ownerModel": result.owner_model,
                "ownerSlotIndex": result.owner_slot_index,
                "ownerMaterialRawStart": result.owner_material_raw_start,
            }
        else:
            result = replay.validate_packed_loader_replay(r, allow_synthetic=allow_synthetic)
            if not result.exact:
                raise RuntimeError(
                    f"surface {r['surfaceIndex']}: packed Material* is not exact under retail loader replay: "
                    f"{result.classification}: {result.reason}"
                )
            evidence = "exact-packed-virtual-material-owner-loader-replay"
            runtime_packed_count += 1
            proof = r.get("loaderReplay") or {}
            if bool(proof.get("sameOwnerBackreference", False)):
                packed_backrefs += 1
            derived = {
                "mode": "runtime-loader",
                "decodedPointer": result.decoded_pointer,
                "resolvedTargetPointerSlotVirtual": result.target_pointer_slot_virtual,
                "objectVirtual": result.object_virtual,
            }

        out = {
            "surfaceIndex": int(r["surfaceIndex"]),
            "lod": int(r["lodIndex"]),
            "lodLocalSurfaceIndex": int(r["lodLocalSurfaceIndex"]),
            "materialName": r["material"],
            "materialPointerRaw": r["handleRaw"],
            "evidence": evidence,
        }
        if derived is not None:
            out["pointerReplay"] = derived
        legacy.append(out)

    packed_total = runtime_packed_count + serialized_packed_count
    return {
        "format": "t6-surface-proof-v2-adapted-for-binding-v1",
        "source": doc.get("source"),
        "bodyMaterials": {"surfaceAssignments": legacy},
        "adapterProof": {
            "inputFormat": doc["format"],
            "inputRows": len(rows),
            "allSurfaceIndicesContiguous": True,
            "noIdentityInferencePerformed": True,
            "inlineSentinelRows": inline_count,
            "packedRowsExact": packed_total,
            "packedRowsExactByRuntimeLoaderReplay": runtime_packed_count,
            "packedRowsExactBySerializedXFileReplay": serialized_packed_count,
            "packedRowsSameOwnerBackreferences": packed_backrefs,
            "runtimeObfuscatedTokensGuessed": 0,
            "serializedTokensGuessed": 0,
            "proofRule": (
                "packed rows are admitted only through either exact runtime decoded-pointer/DB_ConvertOffsetToAlias replay, "
                "or exact T6 32-bit serialized block/offset replay to an independently established VIRTUAL owner field"
            ),
        },
    }


def load_with_surface_v2(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    return adapt_surface_assignment_doc(doc)


def main() -> int:
    base.load = load_with_surface_v2
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
