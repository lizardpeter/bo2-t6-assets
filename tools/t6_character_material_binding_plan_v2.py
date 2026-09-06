#!/usr/bin/env python3
"""Strict frontend for exact T6 character material binding-plan v1.

v2 accepts the durable `t6-xmodel-surface-material-assignments-v1` manifest, but
it does not treat a packed assignment as exact merely because the manifest names a
material.  Every packed Material* must carry an explicit loaderReplay proof that
reproduces the retail pointer path:

    raw token -> exact Sys_DecodePointer result -> DB_ConvertOffsetToAlias
    -> exact VIRTUAL pointer slot -> previously replayed inline Material owner

Inline sentinels remain exact when their durable row says `inline-following` and
the serialized value is one of the retail -1/-2/-3 sentinels.  Packed rows lacking
source-backed decoder/owner evidence fail closed before v1 sees them.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "t6_character_material_binding_plan_v1.py"
REPLAY_PATH = HERE / "t6_material_pointer_replay_v1.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses and other stdlib helpers may consult sys.modules while executing.
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = _load_module("t6_character_material_binding_plan_v1", BASE_PATH)
replay = _load_module("t6_material_pointer_replay_v1", REPLAY_PATH)
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
    packed_count = 0
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
        else:
            result = replay.validate_packed_loader_replay(r, allow_synthetic=allow_synthetic)
            if not result.exact:
                raise RuntimeError(
                    f"surface {r['surfaceIndex']}: packed Material* is not exact under retail loader replay: "
                    f"{result.classification}: {result.reason}"
                )
            evidence = "exact-packed-virtual-material-owner-loader-replay"
            packed_count += 1
            proof = r.get("loaderReplay") or {}
            if bool(proof.get("sameOwnerBackreference", False)):
                packed_backrefs += 1
            derived = {
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
            out["loaderReplay"] = derived
        legacy.append(out)

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
            "packedRowsExactByLoaderReplay": packed_count,
            "packedRowsSameOwnerBackreferences": packed_backrefs,
            "runtimeObfuscatedTokensGuessed": 0,
            "proofRule": (
                "packed rows are admitted only after exact decoded-pointer evidence, "
                "DB_ConvertOffsetToAlias zone/segment replay, and replayed inline owner-slot identity"
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
