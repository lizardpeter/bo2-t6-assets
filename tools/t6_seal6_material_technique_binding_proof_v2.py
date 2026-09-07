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

No Material start, TechniqueSet identity, texture role, or shader behavior is
chosen from naming, surface order, adjacency, or appearance.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path

import t6_seal6_material_technique_binding_proof_v1 as v1


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


def build(expanded: Path, owner_ledger: Path, full_player_proof: Path) -> dict:
    data = expanded.read_bytes()
    digest = sha256_bytes(data)
    if len(data) != v1.EXPECTED_EXPANDED_BYTES or digest != v1.EXPECTED_EXPANDED_SHA256:
        raise ProofError(f"faction_seals_mp expanded identity mismatch: {len(data)} / {digest}")

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
        # Re-read the fixed Material/name from current bytes before allowing v1 to
        # use this start. This independently rejects a stale but hash-colliding
        # manifest/name pairing and validates the TechniqueSet pointer structure.
        blocks, _assets = v1.parse_front(data)
        fixed = v1.material_fixed(data, start, blocks, name)

        supplement = {
            "material": name,
            "materialRawStart": start,
            "materialRawStartHex": f"0x{start:X}",
            "serializedBytes": size,
            "serializedSha256": expected_sha,
            "firstSurfaceIndex": row.get("firstSurfaceIndex"),
            "fixedSha256": fixed["fixedSha256"],
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

    if len({canonical(str(r.get("materialName") or "")) for r in derived["uniqueHandleOwners"] if r.get("ownerMaterialRawStart") is not None}) != v1.EXPECTED_MATERIALS:
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
    out["directInlineOwnerSupplements"] = supplements
    out.setdefault("summary", {})["directInlineOwnerSupplements"] = len(supplements)
    out["summary"]["all13MaterialStartsExact"] = len(out.get("bindings", [])) == v1.EXPECTED_MATERIALS
    out["summary"]["allTechniqueSetBindingsExact"] = True
    out["proofBoundary"] = (
        "All Material raw starts are retail-source-derived. Packed/reused starts come from the exact XModel Material-handle owner ledger; "
        "any missing direct-inline start must come from the retained full-player direct-inline serialized interval and its entire byte slice "
        "must SHA-256 match the current exact expanded faction_seals_mp stream. TechniqueSet identity is then derived only from the serialized "
        "Material::techniqueSet packed VIRTUAL pointer, exact type-7 XAsset pointer-field lattice and matching inline MaterialTechniqueSet. "
        "Names are used only to join two already-exact proof records for the same Material identity, never to search for a raw start or choose "
        "a TechniqueSet. Pass arguments and shader arithmetic remain a separate decoding stage."
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
