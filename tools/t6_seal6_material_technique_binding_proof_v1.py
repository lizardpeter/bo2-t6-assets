#!/usr/bin/env python3
"""Prove SEAL6 Material -> MaterialTechniqueSet bindings from retail bytes.

Inputs are the exact expanded faction_seals_mp XFile and the independently
retained SEAL6 Material owner ledger.  For each of the 13 unique Material
identities this tool reads Material::techniqueSet from the serialized Material
fixed record, decodes the T6 packed XFile pointer, solves the XAsset pointer-field
VIRTUAL base against type-7 (TECHNIQUE_SET) XAsset headers, and joins the result
to the exact inline MaterialTechniqueSet serialization.

Names, texture names, surface order and rendered appearance are never used to
choose a TechniqueSet.  Ambiguity or an imported/packed TechniqueSet owner fails
closed rather than being inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

FOLLOW = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
MASK29 = (1 << 29) - 1
TECHNIQUE_SET_XASSET_TYPE = 7
EXPECTED_EXPANDED_BYTES = 6_245_916
EXPECTED_EXPANDED_SHA256 = "21a11090990417faefa8c39282f499c7bdb87a7acf62f00082aa9b3811cced30"
EXPECTED_MATERIALS = 13


class ProofError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_material(name: str) -> str:
    return name[1:] if name.startswith(",") else name


def cstr(data: bytes, offset: int, limit: int = 8192) -> tuple[str, int]:
    end = data.find(b"\0", offset, min(len(data), offset + limit))
    if end <= offset:
        raise ProofError(f"unterminated/empty string at {offset}")
    raw = data[offset:end]
    if any(b < 32 or b > 126 for b in raw):
        raise ProofError(f"non-ASCII string at {offset}")
    return raw.decode("ascii"), end + 1


def decode_pointer(raw: int, block_sizes: tuple[int, ...]) -> dict:
    if raw == 0:
        return {"kind": "null"}
    if raw == FOLLOW:
        return {"kind": "follow"}
    if raw == INSERT:
        return {"kind": "insert"}
    encoded = (raw - 1) & 0xFFFFFFFF
    block = encoded >> 29
    offset = encoded & MASK29
    if block >= len(block_sizes) or offset >= block_sizes[block]:
        raise ProofError(f"invalid packed pointer 0x{raw:08x}: block={block} offset=0x{offset:x}")
    return {"kind": "packed", "blockIndex": block, "blockOffset": offset}


def parse_front(data: bytes) -> tuple[tuple[int, ...], list[tuple[int, int]]]:
    if len(data) < 64:
        raise ProofError("expanded XFile too small")
    block_sizes = struct.unpack_from("<8I", data, 8)
    p = 40
    script_count, script_ptr, dep_count, dep_ptr, asset_count, asset_ptr = struct.unpack_from("<6I", data, p)
    p += 24
    if script_count and script_ptr != FOLLOW:
        raise ProofError("unexpected script-string pointer mode")
    if dep_count and dep_ptr != FOLLOW:
        raise ProofError("unexpected dependency pointer mode")
    if asset_ptr != FOLLOW:
        raise ProofError("XAsset header array is not inline-following")
    for count in (script_count, dep_count):
        if not count:
            continue
        ptrs = struct.unpack_from(f"<{count}I", data, p)
        p += 4 * count
        for raw in ptrs:
            if raw == FOLLOW:
                _, p = cstr(data, p)
    if p + asset_count * 8 > len(data):
        raise ProofError("XAsset header array exceeds file")
    assets = [struct.unpack_from("<II", data, p + 8 * i) for i in range(asset_count)]
    return tuple(int(x) for x in block_sizes), assets


def material_fixed(data: bytes, start: int, blocks: tuple[int, ...], expected_name: str) -> dict:
    if start < 0 or start + 104 > len(data):
        raise ProofError(f"Material fixed record out of range at {start}")
    fixed = data[start:start + 104]
    name_ptr = struct.unpack_from("<I", fixed, 0)[0]
    if name_ptr != FOLLOW:
        raise ProofError(f"{expected_name}: Material name is not inline-following at raw {start}")
    texture_count, constant_count, state_count, state_flags, camera_region, probe_mip = fixed[76:82]
    if not (0 < texture_count <= 64 and constant_count <= 64 and 0 < state_count <= 64):
        raise ProofError(f"{expected_name}: invalid Material cardinalities")
    technique_raw, texture_ptr, constant_ptr, state_ptr, thermal_ptr = struct.unpack_from("<IIIII", fixed, 84)
    technique = decode_pointer(technique_raw, blocks)
    if technique.get("kind") != "packed" or technique.get("blockIndex") != 5:
        raise ProofError(f"{expected_name}: TechniqueSet pointer is not packed VIRTUAL: 0x{technique_raw:08x}")
    if texture_ptr != FOLLOW or state_ptr != FOLLOW:
        raise ProofError(f"{expected_name}: unexpected texture/state child pointer mode")
    if constant_ptr != (FOLLOW if constant_count else 0):
        raise ProofError(f"{expected_name}: unexpected constant child pointer mode")
    if thermal_ptr != 0:
        raise ProofError(f"{expected_name}: unexpected thermal Material pointer")
    serialized_name, _ = cstr(data, start + 104)
    if canonical_material(serialized_name) != canonical_material(expected_name):
        raise ProofError(
            f"Material identity mismatch at {start}: {serialized_name!r} != {expected_name!r}"
        )
    return {
        "start": start,
        "serializedName": serialized_name,
        "textureCount": texture_count,
        "constantCount": constant_count,
        "stateBitsCount": state_count,
        "stateFlags": state_flags,
        "cameraRegion": camera_region,
        "probeMipBits": probe_mip,
        "techniqueSetPointerRaw": f"0x{technique_raw:08x}",
        "techniqueSetPointer": technique,
        "fixedSha256": sha256(fixed),
    }


def scan_inline_technique_sets(data: bytes, blocks: tuple[int, ...]) -> list[dict]:
    """Strictly scan serialized inline MaterialTechniqueSet fixed records."""
    out: list[dict] = []
    rx = re.compile(r"[A-Za-z0-9_./$@+~:#-]+")
    off = 64
    while True:
        off = data.find(b"\xff\xff\xff\xff", off)
        if off < 0:
            break
        if off + 152 >= len(data):
            break
        world_fmt = data[off + 4]
        if world_fmt > 8 or data[off + 5:off + 8] != b"\0\0\0":
            off += 1
            continue
        pointers = struct.unpack_from("<36I", data, off + 8)
        if not any(pointers):
            off += 1
            continue
        ok = True
        for raw in pointers:
            if raw == 0:
                continue
            try:
                kind = decode_pointer(raw, blocks)["kind"]
            except ProofError:
                ok = False
                break
            if kind not in ("packed", "follow", "insert"):
                ok = False
                break
        if not ok:
            off += 1
            continue
        try:
            name, _ = cstr(data, off + 152, limit=512)
        except ProofError:
            off += 1
            continue
        if len(name) > 180 or not rx.fullmatch(name):
            off += 1
            continue
        out.append({
            "start": off,
            "name": name,
            "worldVertFormat": world_fmt,
            "techniquePointerNonNullCount": sum(1 for x in pointers if x),
            "fixedSha256": sha256(data[off:off + 152]),
        })
        off += 152
    return out


def solve_asset_pointer_base(materials: list[dict], assets: list[tuple[int, int]], blocks: tuple[int, ...]) -> int:
    q_candidates = {i for i, (typ, _) in enumerate(assets) if typ == TECHNIQUE_SET_XASSET_TYPE}
    if not q_candidates:
        raise ProofError("no TechniqueSet XAsset headers")
    candidate_sets: list[set[int]] = []
    for row in materials:
        off = int(row["techniqueSetPointer"]["blockOffset"])
        candidate_sets.append({off - 4 - 8 * q for q in q_candidates})
    shared = set.intersection(*candidate_sets)
    if len(shared) != 1:
        raise ProofError(f"TechniqueSet XAsset pointer-field base is ambiguous: {len(shared)} candidates")
    base = next(iter(shared))
    if base < 0:
        raise ProofError(f"negative TechniqueSet XAsset pointer-field base {base}")
    return base


def build(expanded: Path, owner_ledger: Path) -> dict:
    data = expanded.read_bytes()
    digest = sha256(data)
    if len(data) != EXPECTED_EXPANDED_BYTES or digest != EXPECTED_EXPANDED_SHA256:
        raise ProofError(
            f"faction_seals_mp expanded identity mismatch: {len(data)} / {digest}"
        )
    ledger = json.loads(owner_ledger.read_text(encoding="utf-8-sig"))
    if ledger.get("format") != "t6-seal6-smg-material-handle-proof-v1":
        raise ProofError("unexpected Material owner ledger format")
    if not (ledger.get("summary") or {}).get("targetAllHandlesExact"):
        raise ProofError("Material owner ledger is not exact")

    owners: dict[str, dict] = {}
    for raw in ledger.get("uniqueHandleOwners", []):
        name = canonical_material(str(raw.get("materialName") or ""))
        start = raw.get("ownerMaterialRawStart")
        if not name or start is None:
            continue
        row = {"material": name, "rawStart": int(start), "ownerEvidence": raw.get("evidence")}
        prev = owners.get(name)
        if prev is not None and prev["rawStart"] != row["rawStart"]:
            raise ProofError(f"conflicting raw Material starts for {name}")
        owners[name] = row
    if len(owners) != EXPECTED_MATERIALS:
        raise ProofError(f"expected {EXPECTED_MATERIALS} unique Material raw starts, got {len(owners)}")

    blocks, assets = parse_front(data)
    mats: list[dict] = []
    for name in sorted(owners):
        owner = owners[name]
        fixed = material_fixed(data, owner["rawStart"], blocks, name)
        mats.append({"material": name, "ownerEvidence": owner["ownerEvidence"], **fixed})

    base = solve_asset_pointer_base(mats, assets, blocks)
    inline_q = [i for i, (typ, raw) in enumerate(assets) if typ == TECHNIQUE_SET_XASSET_TYPE and raw == FOLLOW]
    scanned = scan_inline_technique_sets(data, blocks)
    if len(scanned) != len(inline_q):
        raise ProofError(
            f"inline TechniqueSet serialization count {len(scanned)} != inline type-7 XAsset count {len(inline_q)}"
        )
    inline_by_q = {q: scanned[i] for i, q in enumerate(inline_q)}

    bindings: list[dict] = []
    for row in mats:
        off = int(row["techniqueSetPointer"]["blockOffset"])
        delta = off - base - 4
        if delta < 0 or delta % 8:
            raise ProofError(f"{row['material']}: packed TechniqueSet pointer does not land on XAsset field lattice")
        q = delta // 8
        if q >= len(assets) or assets[q][0] != TECHNIQUE_SET_XASSET_TYPE:
            raise ProofError(f"{row['material']}: resolved XAsset index {q} is not TechniqueSet")
        asset_raw = assets[q][1]
        if asset_raw != FOLLOW:
            raise ProofError(
                f"{row['material']}: resolved TechniqueSet XAsset {q} is not inline-following (0x{asset_raw:08x}); alias replay required"
            )
        tech = inline_by_q.get(q)
        if tech is None:
            raise ProofError(f"{row['material']}: no inline TechniqueSet record for XAsset {q}")
        bindings.append({
            "material": row["material"],
            "materialRawStart": row["start"],
            "materialFixedSha256": row["fixedSha256"],
            "textureCount": row["textureCount"],
            "constantCount": row["constantCount"],
            "stateBitsCount": row["stateBitsCount"],
            "techniqueSetPointerRaw": row["techniqueSetPointerRaw"],
            "techniqueSetPointerVirtualOffset": off,
            "resolvedXAssetIndex": q,
            "techniqueSetXAssetPointerRaw": "0xffffffff",
            "techniqueSet": tech["name"],
            "worldVertFormat": tech["worldVertFormat"],
            "techniqueSetRawStart": tech["start"],
            "techniqueSetFixedSha256": tech["fixedSha256"],
            "evidence": "serialized Material::techniqueSet packed VIRTUAL pointer -> exact type-7 XAsset pointer field -> inline MaterialTechniqueSet fixed record",
        })

    if len(bindings) != EXPECTED_MATERIALS or len({x["material"] for x in bindings}) != EXPECTED_MATERIALS:
        raise ProofError("SEAL6 Material->TechniqueSet binding cardinality mismatch")
    return {
        "format": "t6-seal6-material-technique-binding-proof-v1",
        "producer": "tools/t6_seal6_material_technique_binding_proof_v1.py",
        "source": {
            "expandedPath": str(expanded),
            "expandedBytes": len(data),
            "expandedSha256": digest,
            "ownerLedger": str(owner_ledger),
            "ownerLedgerSha256": sha256(owner_ledger.read_bytes()),
        },
        "xfile": {
            "blockSizes": list(blocks),
            "xassetCount": len(assets),
            "techniqueSetXAssetCount": sum(1 for typ, _ in assets if typ == TECHNIQUE_SET_XASSET_TYPE),
            "inlineTechniqueSetXAssetCount": len(inline_q),
            "scannedInlineTechniqueSetCount": len(scanned),
            "xassetPointerFieldVirtualBase": base,
        },
        "bindings": bindings,
        "summary": {
            "materials": len(bindings),
            "allTechniqueSetBindingsExact": True,
            "identityInferencePerformed": False,
            "uniqueTechniqueSets": len({x["techniqueSet"] for x in bindings}),
            "worldVertFormatHistogram": {
                str(k): sum(1 for x in bindings if x["worldVertFormat"] == k)
                for k in sorted({x["worldVertFormat"] for x in bindings})
            },
        },
        "proofBoundary": (
            "TechniqueSet identity is derived only from the serialized retail Material::techniqueSet packed VIRTUAL pointer, "
            "the exact type-7 XAsset header lattice and the matching inline MaterialTechniqueSet serialization. Material/texture names, "
            "surface adjacency and rendered appearance are not used to choose a TechniqueSet. This proves TechniqueSet identity and "
            "worldVertFormat only; pass arguments and shader arithmetic remain separate until decoded."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded_faction_seals_mp", type=Path)
    ap.add_argument("owner_ledger", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.expanded_faction_seals_mp, args.owner_ledger)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
