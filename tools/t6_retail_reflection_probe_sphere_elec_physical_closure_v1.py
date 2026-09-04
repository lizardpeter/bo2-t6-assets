#!/usr/bin/env python3
"""Fail-closed physical promotion gate for the 24 Tomb sphere-electric shaders.

This composes three independently retained proofs:
  * packed PS ownership -> actual Tomb pass owners;
  * paired VS resolution -> actual retained vertex payloads;
  * shifted tangent-basis pixel math -> per-PS base/tangent TEXCOORD roles.

A target is promotable only when every owner occurrence has a resolved paired VS
whose retained SM4 proves the physical producers required by the pixel equation:
  * TEXCOORD0.xyz <- POSITION0 transformed by cb3 rows 0..2;
  * base.xyz      <- NORMAL0 transformed by cb3 rows 0..2 (raw or normalized;
                     the pixel shader itself is already proved to normalize base);
  * tangent.xyz   <- TANGENT0 transformed by cb3 rows 0..2 (raw or normalized);
  * tangent.w ancestry is exclusively TANGENT0.

No shader-name semantics are used. No partial promotion is emitted: all 24 unique
pixel shaders and all of their retained owner occurrences must pass.
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
EXPECTED_PATTERNS = {
    ("TEXCOORD1", "TEXCOORD2"): 12,
    ("TEXCOORD2", "TEXCOORD3"): 12,
}
PRIOR_CLOSED = 5823
TOTAL_FETCHES = 5888


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


def tc_index(semantic: str) -> int:
    if not semantic.startswith("TEXCOORD"):
        raise ValueError(f"not TEXCOORD semantic: {semantic}")
    return int(semantic[len("TEXCOORD") :])


def classify_shifted_target(shifted, ctx, blob, res):
    C, T, coord, weight, shared, surf, guard, mip, angular, sem = ctx
    sig = surf.input_signature(blob)
    w = coord.get_program_words(blob)
    inst = list(coord.walk(w))
    parsed, latest, _ = shared.prep_shader(coord, weight, w, inst)
    del parsed
    hits = []
    for si, (p, op, ln, tok) in enumerate(inst):
        del ln, tok
        if op not in coord.SAMPLE_OPS:
            continue
        O, _ = coord.parse_sample(w, p, op)
        rr, ss = O[2], O[3]
        if not (
            rr["type"] == 7
            and ss["type"] == 6
            and rr["idx"] == [15]
            and ss["idx"] == [15]
        ):
            continue
        roles = surf.formula_roles(coord, w, inst, latest, si, p, op)
        if not roles:
            continue
        A = surf.normalized_raw(
            coord, w, inst, latest, roles["dotIndex"], roles["A"]
        )
        Opp = surf.normalized_raw(
            coord, w, inst, latest, roles["dotIndex"], roles["B"]
        )
        if not A or not Opp:
            continue
        classes = (
            C.raw_class(T, coord, surf, sig, latest, A),
            C.raw_class(T, coord, surf, sig, latest, Opp),
        )
        if classes != ("TEMP_OP50", "TEXCOORD0.xyz"):
            continue
        q = shifted.match(
            C,
            T,
            coord,
            weight,
            shared,
            surf,
            guard,
            mip,
            angular,
            sem,
            blob,
            res,
            si,
            p,
            op,
        )
        if q is None:
            raise ValueError(f"shifted target at instruction {si} failed committed matcher")
        hits.append({"sampleInstructionIndex": si, **q})
    if len(hits) != 1:
        raise ValueError(f"expected exactly one shifted reflection fetch, got {len(hits)}")
    return hits[0]


def prove_world_normal(paired, base, blob, tc):
    try:
        q = paired.normalized_raw_direction(base, blob, tc, "NORMAL")
        return {**q, "producerNormalization": "vertex"}
    except Exception as normalized_error:
        try:
            q = paired.raw_world_direction(base, blob, tc, "NORMAL")
            return {
                **q,
                "producerNormalization": "pixel",
                "vertexNormalizedAttempt": str(normalized_error),
            }
        except Exception as raw_error:
            raise ValueError(
                f"TEXCOORD{tc} is not world NORMAL0: normalized={normalized_error}; raw={raw_error}"
            )


def prove_world_tangent(paired, base, blob, tc):
    attempts = []
    for label, fn in (
        ("vertex", paired.normalized_raw_direction),
        ("raw", paired.raw_world_direction),
    ):
        try:
            q = fn(base, blob, tc, "TANGENT")
            direction = {**q, "producerNormalization": label}
            break
        except Exception as e:
            attempts.append(f"{label}={e}")
    else:
        raise ValueError(f"TEXCOORD{tc} is not world TANGENT0: {'; '.join(attempts)}")

    prof = paired.component_profile(base, blob, tc)
    if prof is None:
        raise ValueError(f"TEXCOORD{tc}: missing component profile")
    wrows = [r for r in prof if r["component"] == "w"]
    if len(wrows) != 1:
        raise ValueError(f"TEXCOORD{tc}.w writer count {len(wrows)}")
    if wrows[0]["inputLeaves"] != [["TANGENT", 0]]:
        raise ValueError(
            f"TEXCOORD{tc}.w ancestry {wrows[0]['inputLeaves']} != TANGENT0"
        )
    return {**direction, "wInputLeaves": wrows[0]["inputLeaves"]}


def tomb_shifted_rows(root, shifted, shifted_ctx, target_shas):
    C, T, coord, weight, shared, surf, guard, mip, angular, sem = shifted_ctx
    del C, T, coord, weight, shared, surf, mip, angular, sem
    rel, expected_sha = guard.SOURCES[TARGET_MAP]
    path = root / rel
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha:
        raise ValueError(f"{TARGET_MAP}: source mismatch {actual}")
    valid, _ = guard.scan_map(path)
    missing = sorted(set(target_shas) - set(valid))
    if missing:
        raise ValueError(f"target PS payloads absent from retained Tomb scan: {missing}")
    rows = {}
    patterns = collections.Counter()
    for h in sorted(target_shas):
        blob, res = valid[h]
        q = classify_shifted_target(shifted, shifted_ctx, blob, res)
        rows[h] = q
        patterns[(q["baseSemantic"], q["tangentSemantic"])] += 1
    if dict(patterns) != EXPECTED_PATTERNS:
        raise ValueError(f"shifted target pattern mismatch {patterns}")
    return rows


def build(
    root: Path,
    owner_probe_path: Path,
    paired_probe_path: Path,
    base_path: Path,
    broad_path: Path,
    packed_vs_alias_path: Path,
    shifted_path: Path,
    closure_path: Path,
    tangent_path: Path,
    coordinate_path: Path,
    weight_path: Path,
    shared_path: Path,
    surface_path: Path,
    guard_path: Path,
    mip_path: Path,
    angular_path: Path,
    semantic_path: Path,
):
    owner = load(owner_probe_path, "sphere_owner")
    paired = load(paired_probe_path, "sphere_paired")
    base = load(base_path, "sphere_base")
    broad = load(broad_path, "sphere_broad")
    shifted = load(shifted_path, "sphere_shifted")

    paired_data = paired.build(
        root, owner_probe_path, base_path, broad_path, packed_vs_alias_path
    )
    if not paired_data["summary"]["allPairedVertexPayloadsResolved"]:
        raise ValueError("paired VS stage is not fully resolved")

    target_shas = sorted({r["pixelShaderSha256"] for r in paired_data["ownerRows"]})
    if len(target_shas) != EXPECTED_TARGETS:
        raise ValueError(f"owned target shader count {len(target_shas)}")

    shifted_ctx = shifted.configure(
        closure_path,
        tangent_path,
        coordinate_path,
        weight_path,
        shared_path,
        surface_path,
        guard_path,
        mip_path,
        angular_path,
        semantic_path,
    )
    pixel_rows = tomb_shifted_rows(root, shifted, shifted_ctx, target_shas)

    events, direct_blobs, direct_objects, scan_rows = owner.collect_broad_events(
        root, base, broad
    )
    del events, direct_objects

    proof_cache = {}
    pairing_rows = []
    failures = []
    for row in paired_data["ownerRows"]:
        ps = row["pixelShaderSha256"]
        vs = row["resolvedVertexShaderSha256"]
        pix = pixel_rows[ps]
        key = (vs, pix["baseSemantic"], pix["tangentSemantic"])
        if key not in proof_cache:
            blob = direct_blobs["vs"].get(vs)
            if blob is None:
                proof_cache[key] = {
                    "ok": False,
                    "error": f"resolved VS payload absent: {vs}",
                }
            else:
                try:
                    p0 = paired.prove_world_position(base, blob, 0)
                    n = prove_world_normal(
                        paired, base, blob, tc_index(pix["baseSemantic"])
                    )
                    t = prove_world_tangent(
                        paired, base, blob, tc_index(pix["tangentSemantic"])
                    )
                    proof_cache[key] = {
                        "ok": True,
                        "worldPosition": p0,
                        "worldNormal": n,
                        "worldTangent": t,
                    }
                except Exception as e:
                    proof_cache[key] = {"ok": False, "error": str(e)}
        q = proof_cache[key]
        out = {
            "pixelShaderSha256": ps,
            "vertexShaderSha256": vs,
            "baseSemantic": pix["baseSemantic"],
            "tangentSemantic": pix["tangentSemantic"],
            "sampleInstructionIndex": pix["sampleInstructionIndex"],
            "techniqueSet": row["techniqueSet"],
            "worldVertFormat": row["worldVertFormat"],
            "slot": row["slot"],
            "passIndex": row["passIndex"],
            "physicalProof": q,
        }
        pairing_rows.append(out)
        if not q["ok"]:
            failures.append(out)

    covered = {r["pixelShaderSha256"] for r in pairing_rows if r["physicalProof"]["ok"]}
    approved = not failures and covered == set(target_shas)
    if not approved:
        raise ValueError(
            f"sphere-electric physical closure rejected: failures={len(failures)} "
            f"covered={len(covered)}/{len(target_shas)}"
        )

    promoted_rows = []
    for ps in target_shas:
        owners = [r for r in pairing_rows if r["pixelShaderSha256"] == ps]
        promoted_rows.append(
            {
                "pixelShaderSha256": ps,
                "baseSemantic": pixel_rows[ps]["baseSemantic"],
                "tangentSemantic": pixel_rows[ps]["tangentSemantic"],
                "ownerOccurrenceCount": len(owners),
                "pairedVertexShaderSha256": sorted(
                    {r["vertexShaderSha256"] for r in owners}
                ),
            }
        )

    new_closed = PRIOR_CLOSED + EXPECTED_TARGETS
    remaining = TOTAL_FETCHES - new_closed
    summary = {
        "targetShaderCount": EXPECTED_TARGETS,
        "promotedShaderCount": len(promoted_rows),
        "ownerOccurrenceCount": len(pairing_rows),
        "failedOwnerOccurrenceCount": 0,
        "physicalPairingIdentityCount": len(proof_cache),
        "baseTangentPatternCounts": {
            f"{a}/{b}": n for (a, b), n in sorted(EXPECTED_PATTERNS.items())
        },
        "promotionApproved": True,
        "priorClosedFetchCount": PRIOR_CLOSED,
        "newlyClosedFetchCount": EXPECTED_TARGETS,
        "closedFetchCount": new_closed,
        "totalFetchCount": TOTAL_FETCHES,
        "remainingFetchCount": remaining,
        "closedPercent": new_closed * 100.0 / TOTAL_FETCHES,
        "pairingRowsSha256": jhash(pairing_rows),
        "promotedRowsSha256": jhash(promoted_rows),
        "scanRowsSha256": jhash(scan_rows),
    }
    return {
        "format": "t6-retail-reflection-probe-sphere-elec-physical-closure-v1",
        "producer": "tools/t6_retail_reflection_probe_sphere_elec_physical_closure_v1.py",
        "sources": {
            "packedPixelOwnerProbe": str(owner_probe_path),
            "pairedVertexProbe": str(paired_probe_path),
            "packedVertexAlias": str(packed_vs_alias_path),
            "shiftedTangentBasisPixelProof": str(shifted_path),
        },
        "equations": {
            "surfaceNormal": "N=normalize(normalize(worldNormal)+NormalMap.x*worldTangent+NormalMap.y*(cross(normalize(worldNormal),worldTangent)*tangent.w))",
            "reflection": "cubeCoord=normalize(worldPosition)-2*N*dot(N,normalize(worldPosition))",
        },
        "promotedRows": promoted_rows,
        "pairingRows": pairing_rows,
        "summary": summary,
        "proofBoundary": (
            "All-or-nothing retained-byte physical closure for the 24 Tomb sphere-electric reflection fetches. "
            "Pixel base/tangent roles are re-derived with the already committed shifted-TBN matcher on each physically "
            "owned PS payload. Every retained owner occurrence must resolve to a paired VS whose direct SM4 proves "
            "TEXCOORD0 from POSITION0/cb3 rows 0..2, the pixel-selected base semantic from NORMAL0/cb3 rows 0..2, "
            "and the pixel-selected tangent semantic from TANGENT0/cb3 rows 0..2 with tangent.w ancestry exclusively "
            "to TANGENT0. Raw world normal/tangent producers are accepted only because the committed pixel equation "
            "explicitly normalizes the base and uses the retained transformed tangent direction. No role is inferred "
            "from shader names, and no partial target population is promoted."
        ),
    }


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--root", type=Path, required=True)
    a.add_argument(
        "--owner-probe",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v1.py"),
    )
    a.add_argument(
        "--paired-probe",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py"),
    )
    a.add_argument(
        "--base-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py"),
    )
    a.add_argument(
        "--broad-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py"),
    )
    a.add_argument(
        "--packed-vs-alias",
        type=Path,
        default=Path("manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json"),
    )
    a.add_argument(
        "--shifted-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_shifted_tangent_basis_normal_v1.py"),
    )
    a.add_argument(
        "--closure-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_temp_mad_texcoord1_closure_v1.py"),
    )
    for n in (
        "tangent-verifier",
        "coordinate-verifier",
        "weight-verifier",
        "shared-verifier",
        "surface-verifier",
        "guard",
        "mip-verifier",
        "angular-verifier",
        "semantic-verifier",
    ):
        a.add_argument("--" + n, type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    q = a.parse_args()
    d = build(
        q.root,
        q.owner_probe,
        q.paired_probe,
        q.base_verifier,
        q.broad_verifier,
        q.packed_vs_alias,
        q.shifted_verifier,
        q.closure_verifier,
        q.tangent_verifier,
        q.coordinate_verifier,
        q.weight_verifier,
        q.shared_verifier,
        q.surface_verifier,
        q.guard,
        q.mip_verifier,
        q.angular_verifier,
        q.semantic_verifier,
    )
    q.out.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
    print(json.dumps(d["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
