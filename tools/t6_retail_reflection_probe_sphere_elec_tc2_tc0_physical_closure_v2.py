#!/usr/bin/env python3
"""Corrected physical closure gate for the 24 Tomb sphere-electric shaders.

IMPORTANT CORRECTION FROM V1
----------------------------
The global reflection census contains two distinct 24-fetch populations involving
TEXCOORD0:

  * 24 TEMP_OP50 / TEXCOORD0 shifted tangent-basis shaders -- already closed in the
    5,808 pre-TEMP15 baseline;
  * 24 TEXCOORD2 / TEXCOORD0 shaders -- the still-unresolved Tomb sphere-electric
    bank.

The v1 sphere physical gate incorrectly attempted to join the named sphere-electric
bank to the first population. This v2 gate never uses the shifted-TBN manifest.
Instead it rediscovers the exact 24 named sphere-electric PS objects, requires each
actual retained PS payload to classify as exactly:

    A = normalize(TEXCOORD2.xyz)
    B = normalize(TEXCOORD0.xyz)
    cubeCoord = B - 2*A*dot(A,B)

and then requires every retained owner occurrence to resolve to a paired VS whose
SM4 directly proves:

    TEXCOORD2.xyz = normalize(worldMatrix3x3 * decoded NORMAL0)
    TEXCOORD0.xyz = (worldMatrix * float4(POSITION0.xyz, 1)).xyz

No role is inferred from the sphere-electric name. The name prefix only locates the
24 direct PS objects; their family membership is proved from the pixel bytecode.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path

TARGET_MAP = "zm_tomb"
EXPECTED_TARGETS = 24
EXPECTED_FORMULA_A = ("TEXCOORD", 2)
EXPECTED_FORMULA_B = ("TEXCOORD", 0)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def jhash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def target_role(row):
    if not row or len(row) != 2:
        return False
    a, b = row
    return bool(
        a
        and b
        and a[0] == EXPECTED_FORMULA_A
        and b[0] == EXPECTED_FORMULA_B
        and a[1] == "xyz"
        and b[1] == "xyz"
    )


def classify_pixel(base, blob):
    roles = base.family_roles(blob)
    hits = [r for r in roles if target_role(r)]
    if len(hits) != 1:
        raise ValueError(
            f"sphere-electric PS has {len(hits)} TC2/TC0 reflection roles"
        )
    return {
        "formulaA": "normalize(TEXCOORD2.xyz)",
        "formulaB": "normalize(TEXCOORD0.xyz)",
        "roleRow": [list(hits[0][0][0]), hits[0][0][1], list(hits[0][1][0]), hits[0][1][1]],
    }


def target_pixel_blobs(root, base, target_shas):
    cfg = base.MAPS[TARGET_MAP]
    path = root / cfg["rel"]
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != base.SHAS[TARGET_MAP]:
        raise ValueError(f"{TARGET_MAP}: expanded SHA mismatch {actual}")
    found = {}
    for pos, blob in base.all_dxbc(data):
        h = hashlib.sha256(blob).hexdigest()
        if h not in target_shas:
            continue
        old = found.setdefault(h, blob)
        if old != blob:
            raise ValueError(f"pixel SHA collision {h}")
    missing = sorted(set(target_shas) - set(found))
    if missing:
        raise ValueError(f"sphere target PS payloads absent from Tomb: {missing}")
    return found


def prove_vs_roles(paired, base, blob):
    normal = paired.normalized_raw_direction(base, blob, 2, "NORMAL")
    position = paired.prove_world_position(base, blob, 0)
    return {
        "texcoord2WorldNormal": normal,
        "texcoord0WorldPosition": position,
    }


def build(
    root: Path,
    owner_probe_path: Path,
    paired_probe_path: Path,
    base_path: Path,
    broad_path: Path,
    packed_vs_alias_path: Path,
):
    owner = load(owner_probe_path, "sphere2_owner")
    paired = load(paired_probe_path, "sphere2_paired")
    base = load(base_path, "sphere2_base")
    broad = load(broad_path, "sphere2_broad")

    ownership = owner.build(root, base_path, broad_path)
    osum = ownership["summary"]
    if osum.get("sphereElectricTargetObjectCount") != EXPECTED_TARGETS:
        raise ValueError("sphere owner target-object count is not 24")
    if not osum.get("targetBankUniquelyResolved"):
        raise ValueError(
            f"sphere packed-PS owner bank unresolved: {osum.get('candidateTargetBankCount')} candidates"
        )
    if osum.get("resolvedTargetShaderCount") != EXPECTED_TARGETS:
        raise ValueError("sphere packed-PS owner coverage is not 24/24")

    target_objects = ownership["targetObjects"]
    target_shas = sorted({r["sha256"] for r in target_objects})
    if len(target_shas) != EXPECTED_TARGETS:
        raise ValueError(f"sphere target SHA count {len(target_shas)}")

    pixel_blobs = target_pixel_blobs(root, base, target_shas)
    pixel_rows = []
    for h in target_shas:
        q = classify_pixel(base, pixel_blobs[h])
        pixel_rows.append({"pixelShaderSha256": h, **q})
    pixel_by_sha = {r["pixelShaderSha256"]: r for r in pixel_rows}

    paired_data = paired.build(
        root, owner_probe_path, base_path, broad_path, packed_vs_alias_path
    )
    psum = paired_data["summary"]
    if not psum.get("allPairedVertexPayloadsResolved"):
        raise ValueError("sphere paired-VS stage is not fully resolved")

    owner_ps = {r["pixelShaderSha256"] for r in paired_data["ownerRows"]}
    if owner_ps != set(target_shas):
        raise ValueError(
            f"paired owner target set differs: owners={len(owner_ps)} targets={len(target_shas)}"
        )

    events, direct_blobs, direct_objects, scan_rows = owner.collect_broad_events(
        root, base, broad
    )
    del events, direct_objects

    proof_cache = {}
    pairing_rows = []
    failures = []
    occurrences = collections.Counter()
    for row in paired_data["ownerRows"]:
        ps = row["pixelShaderSha256"]
        vs = row["resolvedVertexShaderSha256"]
        occurrences[ps] += 1
        if vs not in proof_cache:
            blob = direct_blobs["vs"].get(vs)
            if blob is None:
                proof_cache[vs] = {
                    "ok": False,
                    "error": f"resolved VS payload absent: {vs}",
                }
            else:
                try:
                    proof_cache[vs] = {
                        "ok": True,
                        **prove_vs_roles(paired, base, blob),
                    }
                except Exception as e:
                    proof_cache[vs] = {"ok": False, "error": str(e)}
        proof = proof_cache[vs]
        out = {
            "pixelShaderSha256": ps,
            "vertexShaderSha256": vs,
            "pixelRole": pixel_by_sha[ps],
            "techniqueSet": row["techniqueSet"],
            "worldVertFormat": row["worldVertFormat"],
            "slot": row["slot"],
            "passIndex": row["passIndex"],
            "vertexResolutionSources": row["vertexResolutionSources"],
            "physicalProof": proof,
        }
        pairing_rows.append(out)
        if not proof["ok"]:
            failures.append(out)

    if set(occurrences) != set(target_shas) or any(v < 1 for v in occurrences.values()):
        raise ValueError("one or more sphere target shaders have no retained owner occurrence")
    if failures:
        raise ValueError(f"sphere physical owner failures {len(failures)}")

    promoted_rows = [
        {
            "pixelShaderSha256": h,
            "ownerOccurrenceCount": occurrences[h],
            "formulaA": "normalize(TEXCOORD2.xyz)",
            "formulaB": "normalize(TEXCOORD0.xyz)",
        }
        for h in target_shas
    ]
    summary = {
        "targetShaderCount": EXPECTED_TARGETS,
        "targetFetchCount": EXPECTED_TARGETS,
        "pixelFamilyClassificationCount": len(pixel_rows),
        "ownerOccurrenceCount": len(pairing_rows),
        "physicalVertexShaderIdentityCount": len(proof_cache),
        "failedOwnerOccurrenceCount": 0,
        "promotedShaderCount": len(promoted_rows),
        "promotionApproved": True,
        "pixelRowsSha256": jhash(pixel_rows),
        "pairingRowsSha256": jhash(pairing_rows),
        "promotedRowsSha256": jhash(promoted_rows),
        "scanRowsSha256": jhash(scan_rows),
    }
    return {
        "format": "t6-retail-reflection-probe-sphere-elec-tc2-tc0-physical-closure-v2",
        "producer": "tools/t6_retail_reflection_probe_sphere_elec_tc2_tc0_physical_closure_v2.py",
        "correction": {
            "supersedes": "tools/t6_retail_reflection_probe_sphere_elec_physical_closure_v1.py",
            "reason": "v1 joined the named sphere-electric bank to the distinct already-closed 24-fetch TEMP_OP50/TEXCOORD0 shifted-TBN population; v2 proves the unresolved sphere bank itself is the TC2/TC0 family before physical promotion",
        },
        "sources": {
            "packedPixelOwnerProbe": str(owner_probe_path),
            "pairedVertexProbe": str(paired_probe_path),
            "packedVertexAlias": str(packed_vs_alias_path),
            "pixelFamilyClassifier": str(base_path),
            "closureLedger": "manifests/render/T6_RETAIL_REFLECTION_PROBE_CLOSURE_LEDGER_V2.json",
        },
        "equations": {
            "surfaceNormal": "N=normalize(TEXCOORD2.xyz)=normalize(worldMatrix3x3*decoded_NORMAL0)",
            "opposingVector": "V=normalize(TEXCOORD0.xyz)=normalize((worldMatrix*float4(POSITION0.xyz,1)).xyz)",
            "reflection": "cubeCoord=V-2*N*dot(N,V)",
        },
        "pixelRows": pixel_rows,
        "pairingRows": pairing_rows,
        "promotedRows": promoted_rows,
        "summary": summary,
        "proofBoundary": (
            "All-or-nothing retained-byte closure of the exact 24 named Tomb sphere-electric PS objects. Names locate "
            "objects only. Every target PS payload must independently classify as one A=normalize(TEXCOORD2.xyz), "
            "B=normalize(TEXCOORD0.xyz) reflection fetch. Every physically retained owner occurrence must resolve to a "
            "paired VS whose direct SM4 proves TEXCOORD2 from normalized NORMAL0 through cb3/worldMatrix rows 0..2 and "
            "TEXCOORD0 from homogeneous POSITION0 through cb3/worldMatrix rows 0..2. The distinct 24-fetch shifted-TBN "
            "population is not consumed or counted by this gate."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument(
        "--owner-probe",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v1.py"),
    )
    ap.add_argument(
        "--paired-probe",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py"),
    )
    ap.add_argument(
        "--base-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py"),
    )
    ap.add_argument(
        "--broad-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py"),
    )
    ap.add_argument(
        "--packed-vs-alias",
        type=Path,
        default=Path("manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json"),
    )
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = build(
        a.root,
        a.owner_probe,
        a.paired_probe,
        a.base_verifier,
        a.broad_verifier,
        a.packed_vs_alias,
    )
    a.out.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
    print(json.dumps(d["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
