#!/usr/bin/env python3
"""Attach exact serialized-XFile pointer replay proofs to T6 character materials.

This producer does not discover material identity from a packed token.  It requires
an independently established XModel.materialHandles[] owner ledger, decodes the
serialized pointer with the pinned T6 XFile format, and admits the row only when
that decoded VIRTUAL offset equals the ledger's owner field exactly.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
from typing import Mapping

HERE = Path(__file__).resolve().parent
REPLAY_PATH = HERE / "t6_serialized_xfile_pointer_replay_v1.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


replay = _load_module("t6_serialized_xfile_pointer_replay_v1_for_producer", REPLAY_PATH)


def _norm_material(value: object) -> str:
    return str(value).lstrip(",")


def _build_owner_index(owner_doc: Mapping[str, object]) -> dict[int, Mapping[str, object]]:
    owners = owner_doc.get("uniqueHandleOwners")
    if not isinstance(owners, list):
        raise RuntimeError("owner ledger lacks uniqueHandleOwners[]")

    out: dict[int, Mapping[str, object]] = {}
    for owner in owners:
        if not isinstance(owner, Mapping):
            raise RuntimeError("owner ledger contains a non-object entry")
        raw = replay.u32(owner.get("materialPointerRaw", 0))
        if raw in replay.INLINE_SENTINELS or raw == replay.NULL:
            continue
        if owner.get("evidence") != "exact-xmodel-materialHandles-field-alias":
            raise RuntimeError(f"owner 0x{raw:08x}: evidence is not exact XModel materialHandles field ownership")
        required = ("materialName", "ownerModel", "ownerSlotIndex", "ownerFieldVirtualOffset", "ownerMaterialRawStart")
        missing = [key for key in required if key not in owner]
        if missing:
            raise RuntimeError(f"owner 0x{raw:08x}: missing {', '.join(missing)}")
        previous = out.get(raw)
        if previous is not None:
            fields = ("materialName", "ownerModel", "ownerSlotIndex", "ownerFieldVirtualOffset", "ownerMaterialRawStart")
            if any(previous.get(k) != owner.get(k) for k in fields):
                raise RuntimeError(f"owner 0x{raw:08x}: conflicting duplicate owner records")
            continue
        out[raw] = owner
    return out


def attach_serialized_replays(assignment_doc: Mapping[str, object], owner_doc: Mapping[str, object]) -> dict:
    if assignment_doc.get("format") != "t6-xmodel-surface-material-assignments-v1":
        raise RuntimeError("unsupported assignment manifest format")
    if owner_doc.get("format") != "t6-seal6-smg-material-handle-proof-v1" and not str(owner_doc.get("format", "")).endswith("material-handle-proof-v1"):
        raise RuntimeError("unsupported material owner ledger format")

    assignment_source = assignment_doc.get("source")
    owner_source = owner_doc.get("source")
    if not isinstance(assignment_source, Mapping) or not isinstance(owner_source, Mapping):
        raise RuntimeError("assignment/owner source metadata is missing")
    assignment_sha = assignment_source.get("expandedSha256")
    owner_sha = owner_source.get("expandedSha256")
    if not assignment_sha or assignment_sha != owner_sha:
        raise RuntimeError("assignment and owner ledger do not identify the same expanded retail XFile")

    rows = assignment_doc.get("assignments")
    if not isinstance(rows, list):
        raise RuntimeError("assignment manifest lacks assignments[]")
    expected = int((assignment_doc.get("summary") or {}).get("surfaces", len(rows)))
    if len(rows) != expected:
        raise RuntimeError(f"assignment row count {len(rows)} != expected {expected}")
    indices = [int(row["surfaceIndex"]) for row in rows]
    if indices != list(range(expected)):
        raise RuntimeError("assignment surface indices are not exact contiguous 0..N-1")

    owner_index = _build_owner_index(owner_doc)
    enriched = copy.deepcopy(dict(assignment_doc))
    enriched_rows = enriched["assignments"]
    seen: set[int] = set()
    packed_count = 0
    backref_count = 0

    for row in enriched_rows:
        raw = replay.u32(row["handleRaw"])
        kind = row.get("handleKind")
        if kind == "inline-following":
            if raw not in replay.INLINE_SENTINELS:
                raise RuntimeError(f"surface {row['surfaceIndex']}: inline row has non-inline token 0x{raw:08x}")
            continue
        if raw in replay.INLINE_SENTINELS or raw == replay.NULL:
            raise RuntimeError(f"surface {row['surfaceIndex']}: packed row has invalid token 0x{raw:08x}")

        owner = owner_index.get(raw)
        if owner is None:
            raise RuntimeError(f"surface {row['surfaceIndex']}: packed token 0x{raw:08x} has no exact owner-ledger entry")
        decoded = replay.decode_serialized_pointer(raw)
        owner_offset = replay.u32(owner["ownerFieldVirtualOffset"])
        if decoded.block_index != replay.T6_XFILE_BLOCK_VIRTUAL:
            raise RuntimeError(
                f"surface {row['surfaceIndex']}: token 0x{raw:08x} decodes to block {decoded.block_index}, not T6 VIRTUAL block 5"
            )
        if decoded.block_offset != owner_offset:
            raise RuntimeError(
                f"surface {row['surfaceIndex']}: decoded offset 0x{decoded.block_offset:x} != owner field 0x{owner_offset:x}"
            )
        if _norm_material(row.get("material")) != _norm_material(owner["materialName"]):
            raise RuntimeError(
                f"surface {row['surfaceIndex']}: assignment material {row.get('material')!r} != owner-ledger material {owner['materialName']!r}"
            )

        is_backref = raw in seen
        seen.add(raw)
        packed_count += 1
        backref_count += int(is_backref)
        row["serializedReplay"] = {
            "status": "exact",
            "mode": "t6-serialized-xfile-block-pointer",
            "evidence": replay.EXACT_EVIDENCE,
            "sourceRevision": replay.OAT_SOURCE_REVISION,
            "pointerBits": replay.POINTER_BITS,
            "blockBits": replay.BLOCK_BITS,
            "decodedBlockIndex": decoded.block_index,
            "decodedBlockName": "XFILE_BLOCK_VIRTUAL",
            "decodedBlockOffset": f"0x{decoded.block_offset:08x}",
            "sameOwnerBackreference": is_backref,
            "owner": {
                "model": owner["ownerModel"],
                "slotIndex": int(owner["ownerSlotIndex"]),
                "pointerSlotVirtual": f"0x{owner_offset:08x}",
                "material": owner["materialName"],
                "materialRawStart": int(owner["ownerMaterialRawStart"]),
                "evidence": owner["evidence"],
            },
        }
        check = replay.validate_serialized_material_replay(row)
        if not check.exact:
            raise RuntimeError(
                f"surface {row['surfaceIndex']}: generated serialized replay failed self-validation: "
                f"{check.classification}: {check.reason}"
            )

    enriched["serializedPointerProof"] = {
        "status": "exact",
        "sourceRevision": replay.OAT_SOURCE_REVISION,
        "sourcePaths": list(replay.OAT_SOURCE_PATHS),
        "pointerBits": replay.POINTER_BITS,
        "blockBits": replay.BLOCK_BITS,
        "offsetEncoding": "((blockIndex << 29) | blockOffset) + 1",
        "virtualBlockIndex": replay.T6_XFILE_BLOCK_VIRTUAL,
        "ownerLedgerFormat": owner_doc.get("format"),
        "ownerLedgerMaterialCatalogSha256": owner_source.get("materialCatalogSha256"),
        "packedRowsExact": packed_count,
        "uniquePackedTokens": len(seen),
        "sameOwnerBackreferences": backref_count,
        "identityInferencePerformed": False,
        "proofBoundary": (
            "raw token is decoded only by the pinned T6 XFile block-pointer format and must land exactly on an "
            "independently established XModel.materialHandles[] VIRTUAL owner field; names/LOD/appearance are not used to derive identity"
        ),
    }
    return enriched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("assignment_manifest", type=Path)
    ap.add_argument("owner_ledger", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()
    assignments = json.loads(args.assignment_manifest.read_text(encoding="utf-8-sig"))
    owners = json.loads(args.owner_ledger.read_text(encoding="utf-8-sig"))
    out = attach_serialized_replays(assignments, owners)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps(out["serializedPointerProof"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
