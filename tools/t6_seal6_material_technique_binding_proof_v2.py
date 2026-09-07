#!/usr/bin/env python3
"""Close all SEAL6 Material -> MaterialTechniqueSet bindings from retained retail proof.

v1 intentionally consumed only the packed-owner ledger. That ledger retains exact
raw Material starts for packed-reuse owners, but the target SMG XModel also owns
four direct-inline Materials. Three of those happen to be duplicated by packed
owners elsewhere; the iris is not, so its raw start is absent from that ledger.

The earlier exact faction_seals_mp full-player proof already retains every direct
inline Material's serialized start, byte length and SHA-256. This adapter verifies
that retained byte slice against the exact expanded retail FastFile, supplements
only the missing direct-inline owner starts in a transient copy of the ledger,
and delegates the actual Material::techniqueSet pointer proof to v1.

This revision also replaces v1's stale 104-byte Material fixed-record view with
the source-closed T6 PC32 112-byte layout used by the generic top-level walker on
main: counts at +84..+86 and the five child pointers at +92.  The compatibility
patch is local to this proof process; it does not weaken any pointer validation.

No Material start, TechniqueSet identity, texture role, or shader behavior is
chosen from naming, surface order, adjacency, or appearance.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import tempfile
from pathlib import Path

import t6_seal6_material_technique_binding_proof_v1 as v1


MATERIAL_FIXED_BYTES = 112
MATERIAL_COUNTS_OFFSET = 84
MATERIAL_CHILD_POINTERS_OFFSET = 92


class ProofError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(name: str) -> str:
    return name[1:] if name.startswith(",") else name


def parse_start(row: dict) -> int:
    if isinstance(row.get("serializedStart"), int):
        return int(row["serializedStart"])
    raw = row.get("serializedStartHex")
    if isinstance(raw, str) and raw:
        return int(raw, 0)
    raise ProofError(f"direct-inline row lacks serialized start: {row.get('name')!r}")


def material_fixed_112(data: bytes, start: int, blocks: tuple[int, ...], expected_name: str) -> dict:
    """Read only source-closed fields required for Material -> TechniqueSet proof."""
    if start < 0 or start + MATERIAL_FIXED_BYTES > len(data):
        raise v1.ProofError(f"Material fixed record out of range at {start}")
    fixed = data[start:start + MATERIAL_FIXED_BYTES]
    name_ptr = struct.unpack_from("<I", fixed, 0)[0]
    if name_ptr not in (v1.FOLLOW, v1.INSERT):
        raise v1.ProofError(
            f"{expected_name}: Material name is not inline at raw {start}: 0x{name_ptr:08x}"
        )
    texture_count = fixed[MATERIAL_COUNTS_OFFSET]
    constant_count = fixed[MATERIAL_COUNTS_OFFSET + 1]
    state_count = fixed[MATERIAL_COUNTS_OFFSET + 2]
    if not (0 < texture_count <= 64 and constant_count <= 64 and 0 < state_count <= 64):
        raise v1.ProofError(
            f"{expected_name}: invalid Material cardinalities {texture_count}/{constant_count}/{state_count}"
        )
    technique_raw, texture_ptr, constant_ptr, state_ptr, thermal_ptr = struct.unpack_from(
        "<IIIII", fixed, MATERIAL_CHILD_POINTERS_OFFSET
    )
    technique = v1.decode_pointer(technique_raw, blocks)
    if technique.get("kind") != "packed" or technique.get("blockIndex") != 5:
        raise v1.ProofError(
            f"{expected_name}: TechniqueSet pointer is not packed VIRTUAL: 0x{technique_raw:08x}"
        )
    # Child allocation modes are decoded, but only the TechniqueSet pointer is
    # used to establish identity. Thermal Material may legitimately be non-null.
    texture_dec = v1.decode_pointer(texture_ptr, blocks)
    constant_dec = v1.decode_pointer(constant_ptr, blocks)
    state_dec = v1.decode_pointer(state_ptr, blocks)
    thermal_dec = v1.decode_pointer(thermal_ptr, blocks)
    if texture_count and texture_dec.get("kind") not in ("follow", "insert"):
        raise v1.ProofError(f"{expected_name}: non-inline texture table with textureCount={texture_count}")
    if constant_count and constant_dec.get("kind") not in ("follow", "insert"):
        raise v1.ProofError(f"{expected_name}: non-inline constant table with constantCount={constant_count}")
    if state_count and state_dec.get("kind") not in ("follow", "insert"):
        raise v1.ProofError(f"{expected_name}: non-inline state table with stateBitsCount={state_count}")
    serialized_name, _ = v1.cstr(data, start + MATERIAL_FIXED_BYTES)
    if canonical(serialized_name) != canonical(expected_name):
        raise v1.ProofError(
            f"Material identity mismatch at {start}: {serialized_name!r} != {expected_name!r}"
        )
    return {
        "start": start,
        "serializedName": serialized_name,
        "textureCount": texture_count,
        "constantCount": constant_count,
        "stateBitsCount": state_count,
        "techniqueSetPointerRaw": f"0x{technique_raw:08x}",
        "techniqueSetPointer": technique,
        "textureTablePointer": texture_dec,
        "constantTablePointer": constant_dec,
        "stateTablePointer": state_dec,
        "thermalMaterialPointer": thermal_dec,
        "fixedBytes": MATERIAL_FIXED_BYTES,
        "fixedSha256": sha256_bytes(fixed),
    }


def build(expanded: Path, owner_ledger: Path, full_player_proof: Path) -> dict:
    data = expanded.read_bytes()
    digest = sha256_bytes(data)
    if len(data) != v1.EXPECTED_EXPANDED_BYTES or digest != v1.EXPECTED_EXPANDED_SHA256:
        raise ProofError(f"faction_seals_mp expanded identity mismatch: {len(data)} / {digest}")

    # v1's pointer/XAsset/TechniqueSet proof is still useful; only its old Material
    # field offsets were stale. Patch that reader with the generic source-closed
    # T6 PC32 layout for this process before any Material is admitted.
    v1.material_fixed = material_fixed_112

    ledger = json.loads(owner_ledger.read_text(encoding="utf-8-sig"))
    if ledger.get("format") != "t6-seal6-smg-material-handle-proof-v1":
        raise ProofError("unexpected Material owner ledger format")
    if not (ledger.get("summary") or {}).get("targetAllHandlesExact"):
        raise ProofError("Material owner ledger is not exact")

    full = json.loads(full_player_proof.read_text(encoding="utf-8-sig"))
    if full.get("format") != "t6-seal6-smg-full-player-retail-proof-v1":
        raise ProofError("unexpected full-player direct-inline proof format")
    stream = full.get("expandedStream") or {}
    if int(stream.get("bytes", -1)) != len(data) or stream.get("sha256") != digest:
        raise ProofError("full-player proof does not name the exact expanded retail stream")

    target_sequence = ledger.get("surfaceMaterialSequence") or []
    target_materials = {canonical(str(x)) for x in target_sequence if str(x)}
    if len(target_materials) != v1.EXPECTED_MATERIALS:
        raise ProofError(
            f"target sequence has {len(target_materials)} unique materials, expected {v1.EXPECTED_MATERIALS}"
        )

    have: dict[str, int] = {}
    for row in ledger.get("uniqueHandleOwners", []):
        name = canonical(str(row.get("materialName") or ""))
        start = row.get("ownerMaterialRawStart")
        if not name or start is None:
            continue
        start = int(start)
        prev = have.get(name)
        if prev is not None and prev != start:
            raise ProofError(f"conflicting retained Material raw starts for {name}")
        have[name] = start

    missing = sorted(target_materials - set(have))
    direct_rows = {
        canonical(str(row.get("name") or "")): row
        for row in (full.get("bodyMaterials") or {}).get("directInline", [])
        if isinstance(row, dict) and row.get("name")
    }
    if not missing:
        raise ProofError("v2 expected at least one direct-inline owner omission; base ledger already closes all materials")

    blocks, _assets = v1.parse_front(data)
    supplements: list[dict] = []
    derived = copy.deepcopy(ledger)
    target_model = str((ledger.get("summary") or {}).get("targetModel") or "")
    for name in missing:
        row = direct_rows.get(name)
        if row is None:
            raise ProofError(f"missing exact direct-inline proof for {name}")
        start = parse_start(row)
        size = int(row.get("serializedBytes", 0))
        expected_sha = str(row.get("serializedSha256") or "")
        if start < 0 or size <= 0 or start + size > len(data) or len(expected_sha) != 64:
            raise ProofError(f"invalid retained direct-inline byte interval for {name}")
        actual_sha = sha256_bytes(data[start:start + size])
        if actual_sha != expected_sha:
            raise ProofError(
                f"{name}: retained serialized slice hash mismatch at 0x{start:x}: {actual_sha} != {expected_sha}"
            )
        fixed = material_fixed_112(data, start, blocks, name)

        supplement = {
            "material": name,
            "materialRawStart": start,
            "materialRawStartHex": f"0x{start:X}",
            "serializedBytes": size,
            "serializedSha256": expected_sha,
            "firstSurfaceIndex": row.get("firstSurfaceIndex"),
            "fixedBytes": MATERIAL_FIXED_BYTES,
            "fixedSha256": fixed["fixedSha256"],
            "techniqueSetPointerRaw": fixed["techniqueSetPointerRaw"],
            "evidence": "exact retained direct-inline Material serialized interval + byte-for-byte SHA-256 verification against current retail expanded stream",
        }
        supplements.append(supplement)
        derived.setdefault("uniqueHandleOwners", []).append({
            "materialPointerRaw": "0xffffffff",
            "materialName": name,
            "evidence": "exact-retained-direct-inline-material-source-proof",
            "ownerModel": target_model,
            "ownerSlotIndex": row.get("firstSurfaceIndex"),
            "ownerMaterialRawStart": start,
        })

    starts = {
        canonical(str(r.get("materialName") or ""))
        for r in derived["uniqueHandleOwners"]
        if r.get("ownerMaterialRawStart") is not None
    }
    if len(starts) != v1.EXPECTED_MATERIALS:
        raise ProofError("supplemented ledger does not close exactly 13 unique Material starts")

    with tempfile.TemporaryDirectory(prefix="seal6-technique-v2-") as td:
        derived_path = Path(td) / "derived_owner_ledger.json"
        derived_path.write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        out = v1.build(expanded, derived_path)
        derived_sha = sha256_file(derived_path)

    bound = {x["material"]: x for x in out.get("bindings", [])}
    for s in supplements:
        b = bound.get(s["material"])
        if b is None or int(b.get("materialRawStart", -1)) != s["materialRawStart"]:
            raise ProofError(f"delegated TechniqueSet proof did not preserve exact start for {s['material']}")

    out["format"] = "t6-seal6-material-technique-binding-proof-v2"
    out["producer"] = "tools/t6_seal6_material_technique_binding_proof_v2.py"
    out["source"] = {
        "expandedPath": str(expanded),
        "expandedBytes": len(data),
        "expandedSha256": digest,
        "baseOwnerLedger": str(owner_ledger),
        "baseOwnerLedgerSha256": sha256_file(owner_ledger),
        "directInlineProof": str(full_player_proof),
        "directInlineProofSha256": sha256_file(full_player_proof),
        "transientSupplementedOwnerLedgerSha256": derived_sha,
    }
    out["materialLayout"] = {
        "fixedBytes": MATERIAL_FIXED_BYTES,
        "countsOffset": MATERIAL_COUNTS_OFFSET,
        "childPointersOffset": MATERIAL_CHILD_POINTERS_OFFSET,
        "authority": "source-closed generic T6 PC32 Material walker",
    }
    out["directInlineOwnerSupplements"] = supplements
    out.setdefault("summary", {})["directInlineOwnerSupplements"] = len(supplements)
    out["summary"]["all13MaterialStartsExact"] = len(out.get("bindings", [])) == v1.EXPECTED_MATERIALS
    out["summary"]["allTechniqueSetBindingsExact"] = True
    out["proofBoundary"] = (
        "All Material raw starts are retail-source-derived. Packed/reused starts come from the exact XModel Material-handle owner ledger; "
        "any missing direct-inline start must come from the retained full-player direct-inline serialized interval and its entire byte slice "
        "must SHA-256 match the current exact expanded faction_seals_mp stream. The 112-byte Material field layout is the source-closed T6 "
        "PC32 layout used by the generic top-level walker. TechniqueSet identity is then derived only from the serialized Material::techniqueSet "
        "packed VIRTUAL pointer, exact type-7 XAsset pointer-field lattice and matching inline MaterialTechniqueSet. Names are used only to join "
        "two already-exact proof records for the same Material identity, never to search for a raw start or choose a TechniqueSet. Pass arguments "
        "and shader arithmetic remain a separate decoding stage."
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded_faction_seals_mp", type=Path)
    ap.add_argument("owner_ledger", type=Path)
    ap.add_argument("full_player_direct_inline_proof", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = build(
        args.expanded_faction_seals_mp,
        args.owner_ledger,
        args.full_player_direct_inline_proof,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
