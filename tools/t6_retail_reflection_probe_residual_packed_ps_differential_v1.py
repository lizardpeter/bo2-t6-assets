#!/usr/bin/env python3
"""Serializer-differential fallback for unanchored packed PS residual families.

This stage is intentionally downstream of the exact cross-map packed-PS extension.
It addresses only packed PS pointers that do not have an exact cross-map PS SHA
anchor. The proof mirrors the already committed packed-VS set-bounding strategy:

  * calibrate packed-PS pointer-spacing vs direct-PS object-spacing independently
    per map/block using exact structural PS aliases whose direct object is physically
    present in that same map;
  * consider only unresolved packed PS pointers whose paired VS resolves exactly and
    directly proves one residual family's NORMAL0/POSITION0 producer semantics;
  * require at least two pointers in one retained TechniqueSet/block cluster;
  * compare the complete pointer-spacing pattern against physically present direct
    PS objects belonging to the still-unmapped committed target set;
  * accept only one candidate target-SHA set within the independently measured
    maximum differential drift;
  * require candidate sets and pointer sets to be disjoint across promoted clusters.

The sorted pointer/object permutation need not be claimed: every member of an
accepted candidate object set is already independently in the same exhaustive pixel
family, and every pointer in the owning cluster has the same physically proven VS
roles. The proof promotes the unique set as a whole, never an invented 1:1 alias.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

EXPECTED_STRUCTURAL_PS_ANCHORS = 76


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


def calibration_rows(owner, structural_ps, direct_by_map):
    rows = []
    for p, sha in sorted(structural_ps.items()):
        if p[0] != "ptr":
            continue
        _, mapname, block, offset = p
        direct = direct_by_map.get(mapname, [])
        pos = owner.choose_unique_object_position(direct, sha)
        if pos is None:
            continue
        rows.append(
            {
                "map": mapname,
                "block": block,
                "offset": offset,
                "sha256": sha,
                "fixedStart": pos,
                "delta": pos - offset,
            }
        )
    return rows


def calibration_bounds(rows):
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["map"], r["block"])].append(r)
    out = {}
    for key, controls in sorted(by.items()):
        if len(controls) < 2:
            continue
        drifts = []
        for a, b in itertools.combinations(controls, 2):
            drifts.append(
                abs(
                    (b["fixedStart"] - a["fixedStart"])
                    - (b["offset"] - a["offset"])
                )
            )
        out[key] = {
            "controlCount": len(controls),
            "pairwiseCount": len(drifts),
            "maxPairwiseDifferentialDriftBytes": max(drifts),
            "controlRowsSha256": jhash(controls),
        }
    return out


def max_spacing_residual(pointer_offsets, object_positions):
    po = sorted(pointer_offsets)
    oo = sorted(object_positions)
    if len(po) != len(oo) or len(po) < 2:
        raise ValueError("spacing comparison requires equal populations of at least two")
    basep, baseo = po[0], oo[0]
    return max(abs((p - basep) - (o - baseo)) for p, o in zip(po, oo))


def matching_object_sets(pointer_offsets, object_rows, max_drift):
    n = len(set(pointer_offsets))
    if n < 2:
        return []
    uniq = {}
    for r in object_rows:
        uniq.setdefault(r["sha256"], []).append(r)
    objects = []
    for sha, rows in sorted(uniq.items()):
        starts = sorted({r["fixedStart"] for r in rows})
        if len(starts) == 1:
            objects.append((sha, starts[0]))
    matches = []
    for combo in itertools.combinations(objects, n):
        positions = [x[1] for x in combo]
        residual = max_spacing_residual(pointer_offsets, positions)
        if residual <= max_drift:
            matches.append(
                {
                    "shaderSha256": sorted(x[0] for x in combo),
                    "objectStarts": sorted(positions),
                    "maxDifferentialResidualBytes": residual,
                }
            )
    # Collapse duplicate SHA sets defensively.
    byset = {}
    for m in matches:
        key = tuple(m["shaderSha256"])
        old = byset.get(key)
        if old is None or m["maxDifferentialResidualBytes"] < old["maxDifferentialResidualBytes"]:
            byset[key] = m
    return sorted(byset.values(), key=lambda x: (x["maxDifferentialResidualBytes"], x["shaderSha256"]))


def resolved_vs_family(base, broad, paired, direct_vs_blobs, structural_vs, committed_vs, node):
    vh, sources = paired.resolve_vs_node(node, structural_vs, committed_vs)
    if vh is None:
        return None, None, sources, "paired VS unresolved"
    blob = direct_vs_blobs.get(vh)
    if blob is None:
        return None, vh, sources, f"resolved VS payload absent: {vh}"
    hits = []
    proofs = {}
    try:
        proofs["TEXCOORD2/TEXCOORD1"] = base.prove_vs(blob)
        hits.append("TEXCOORD2/TEXCOORD1")
    except Exception:
        pass
    try:
        proofs["TEXCOORD3/TEXCOORD1"] = broad.prove_vs_tc3(base, blob)
        hits.append("TEXCOORD3/TEXCOORD1")
    except Exception:
        pass
    if len(hits) != 1:
        return None, vh, sources, f"paired VS family proof count {len(hits)}"
    family = hits[0]
    return family, vh, sources, proofs[family]


def build(
    root: Path,
    structural_extension_path: Path,
    owner_probe_path: Path,
    paired_probe_path: Path,
    base_path: Path,
    broad_path: Path,
    packed_vs_alias_path: Path,
    tc2_target_set_path: Path,
):
    ext = load(structural_extension_path, "diff_ext")
    owner = load(owner_probe_path, "diff_owner")
    paired = load(paired_probe_path, "diff_paired")
    base = load(base_path, "diff_base")
    broad = load(broad_path, "diff_broad")

    tc2 = ext.load_tc2_targets(tc2_target_set_path)
    tc3_rows, _, tc3_fetches = broad.global_target(root, base)
    tc3 = set(tc3_rows)
    if tc3_fetches != len(tc3):
        raise ValueError("TC3 target fetch/shader census drift")
    targets = {
        "TEXCOORD2/TEXCOORD1": tc2,
        "TEXCOORD3/TEXCOORD1": tc3,
    }

    events, direct_blobs, direct_objects_unused, scan_rows = owner.collect_broad_events(
        root, base, broad
    )
    del direct_objects_unused
    structural_ps, all_ps_ptrs, _ = owner.structural_aliases(events, "ps")
    if len(structural_ps) != EXPECTED_STRUCTURAL_PS_ANCHORS:
        raise ValueError(f"structural packed PS anchor count {len(structural_ps)}")
    structural_vs, _, _ = owner.structural_aliases(events, "vs")
    committed_vs = paired.load_committed_packed_vs(packed_vs_alias_path)

    # Scan all physically direct named pixel-shader objects. Names locate the object
    # boundary only; family membership always comes from target SHA identity.
    direct_by_map = {}
    for mapname, cfg in base.MAPS.items():
        data = (root / cfg["rel"]).read_bytes()
        blocks = base.front(data)
        direct_by_map[mapname] = owner.scan_named_direct_ps_objects(
            data, blocks, base
        )

    controls = calibration_rows(owner, structural_ps, direct_by_map)
    bounds = calibration_bounds(controls)

    # Recover what the exact packed-PS stage already maps so this differential stage
    # touches only genuinely unanchored pixel pointers/target SHAs.
    recovered_by_family = {k: set() for k in targets}
    direct_prior_by_family = {k: set() for k in targets}
    for mapname, evs in events.items():
        for e in evs:
            dh = ext.direct_ps_hash(e["ps"])
            rh, _ = ext.resolved_ps_hash(e["ps"], structural_ps)
            for family, target in targets.items():
                if dh in target:
                    direct_prior_by_family[family].add(dh)
                if rh in target:
                    recovered_by_family[family].add(rh)

    # Classify unanchored packed pointers only through their physical paired VS.
    ptr_occ = collections.defaultdict(list)
    vs_cache = {}
    for mapname, evs in events.items():
        for e in evs:
            p = e["ps"]
            if p is None or p[0] != "ptr" or p in structural_ps:
                continue
            vkey = tuple(e["vs"]) if e["vs"] is not None else None
            if vkey not in vs_cache:
                vs_cache[vkey] = resolved_vs_family(
                    base,
                    broad,
                    paired,
                    direct_blobs["vs"],
                    structural_vs,
                    committed_vs,
                    e["vs"],
                )
            family, vh, sources, proof_or_error = vs_cache[vkey]
            ptr_occ[p].append(
                {
                    "map": mapname,
                    "ti": e["ti"],
                    "techniqueSet": e["ts"],
                    "worldVertFormat": e["fmt"],
                    "slot": e["slot"],
                    "passIndex": e["pass"],
                    "family": family,
                    "resolvedVertexShaderSha256": vh,
                    "vertexResolutionSources": sources,
                    "vertexProofOrError": proof_or_error,
                }
            )

    clean_ptr_family = {}
    rejected_ptrs = []
    for p, rows in sorted(ptr_occ.items()):
        fams = {r["family"] for r in rows}
        if len(fams) == 1 and None not in fams:
            clean_ptr_family[p] = next(iter(fams))
        else:
            rejected_ptrs.append(
                {
                    "pointer": list(p),
                    "occurrenceCount": len(rows),
                    "families": sorted(str(x) for x in fams),
                }
            )

    # Group by one physical TechniqueSet ordinal and serializer block. A pointer may
    # appear multiple times; candidate matching operates on unique pointer identities.
    clusters = collections.defaultdict(set)
    for p, family in clean_ptr_family.items():
        for r in ptr_occ[p]:
            clusters[(p[1], r["ti"], p[2], family)].add(p)

    candidate_rows = []
    for (mapname, ti, block, family), pointers in sorted(clusters.items(), key=str):
        if len(pointers) < 2:
            continue
        bound = bounds.get((mapname, block))
        if bound is None:
            continue
        residual_targets = targets[family] - recovered_by_family[family]
        objects = [
            r
            for r in direct_by_map[mapname]
            if r["sha256"] in residual_targets
        ]
        offsets = sorted(p[3] for p in pointers)
        matches = matching_object_sets(
            offsets, objects, bound["maxPairwiseDifferentialDriftBytes"]
        )
        candidate_rows.append(
            {
                "map": mapname,
                "techniqueSetOrdinal": ti,
                "block": block,
                "family": family,
                "pointerOffsets": offsets,
                "pointerOccurrenceCounts": [
                    sum(len(ptr_occ[p]) for p in pointers if p[3] == off)
                    for off in offsets
                ],
                "calibrationControlCount": bound["controlCount"],
                "calibrationPairwiseCount": bound["pairwiseCount"],
                "calibrationMaxDifferentialDriftBytes": bound[
                    "maxPairwiseDifferentialDriftBytes"
                ],
                "candidateSetCount": len(matches),
                "candidateSets": matches,
            }
        )

    # Promote only unique candidate sets, and only when target SHA sets and pointer
    # identities are disjoint across every promoted cluster.
    provisional = [r for r in candidate_rows if r["candidateSetCount"] == 1]
    sha_use = collections.Counter()
    ptr_use = collections.Counter()
    for r in provisional:
        for h in r["candidateSets"][0]["shaderSha256"]:
            sha_use[(r["family"], h)] += 1
        for off in r["pointerOffsets"]:
            ptr_use[(r["map"], r["block"], off)] += 1

    promoted_rows = []
    promoted_by_family = {k: set() for k in targets}
    for r in provisional:
        hs = r["candidateSets"][0]["shaderSha256"]
        pkeys = [(r["map"], r["block"], off) for off in r["pointerOffsets"]]
        if any(sha_use[(r["family"], h)] != 1 for h in hs):
            continue
        if any(ptr_use[p] != 1 for p in pkeys):
            continue
        promoted_by_family[r["family"]].update(hs)
        promoted_rows.append(r)

    if promoted_by_family["TEXCOORD2/TEXCOORD1"] & recovered_by_family[
        "TEXCOORD2/TEXCOORD1"
    ]:
        raise ValueError("TC2 differential promotion overlaps exact PS recovery")
    if promoted_by_family["TEXCOORD3/TEXCOORD1"] & recovered_by_family[
        "TEXCOORD3/TEXCOORD1"
    ]:
        raise ValueError("TC3 differential promotion overlaps exact PS recovery")

    fam_summary = {}
    for family in targets:
        unresolved_before = targets[family] - recovered_by_family[family]
        promoted = promoted_by_family[family]
        fam_summary[family] = {
            "globalTargetCount": len(targets[family]),
            "priorDirectMappedCount": len(direct_prior_by_family[family]),
            "exactPackedPsRecoveredCount": len(recovered_by_family[family] - direct_prior_by_family[family]),
            "unresolvedBeforeDifferentialCount": len(unresolved_before),
            "serializerDifferentialPromotedCount": len(promoted),
            "remainingAfterDifferentialCount": len(unresolved_before - promoted),
            "promotedShaderSetSha256": jhash(sorted(promoted)),
        }

    total_promoted = sum(len(x) for x in promoted_by_family.values())
    summary = {
        "structurallyAnchoredPackedPixelPointerCount": len(structural_ps),
        "allPackedPixelPointerCount": len(all_ps_ptrs),
        "packedPixelCalibrationControlCount": len(controls),
        "calibratedMapBlockCount": len(bounds),
        "cleanUnanchoredPackedPointerCount": len(clean_ptr_family),
        "rejectedUnanchoredPackedPointerCount": len(rejected_ptrs),
        "candidateClusterCount": len(candidate_rows),
        "uniqueCandidateClusterCount": len(provisional),
        "disjointPromotedClusterCount": len(promoted_rows),
        "serializerDifferentialPromotedShaderCount": total_promoted,
        "familySummarySha256": jhash(fam_summary),
        "calibrationRowsSha256": jhash(controls),
        "candidateRowsSha256": jhash(candidate_rows),
        "promotedRowsSha256": jhash(promoted_rows),
        "scanRowsSha256": jhash(scan_rows),
    }
    return {
        "format": "t6-retail-reflection-probe-residual-packed-ps-differential-v1",
        "producer": "tools/t6_retail_reflection_probe_residual_packed_ps_differential_v1.py",
        "sources": {
            "exactPackedPsExtension": str(structural_extension_path),
            "packedPixelOwnerProbe": str(owner_probe_path),
            "pairedVertexResolver": str(paired_probe_path),
            "packedVertexAlias": str(packed_vs_alias_path),
            "tc2Tc1TargetSet": str(tc2_target_set_path),
            "tc3Tc1FamilyVerifier": str(broad_path),
        },
        "calibrationBounds": [
            {
                "map": k[0],
                "block": k[1],
                **v,
            }
            for k, v in sorted(bounds.items())
        ],
        "rejectedPointerRows": rejected_ptrs,
        "candidateClusters": candidate_rows,
        "promotedClusters": promoted_rows,
        "familySummary": fam_summary,
        "summary": summary,
        "proofBoundary": (
            "Serializer-differential ownership proof only. Packed PS differential bounds are calibrated solely from "
            "independently exact cross-map PS aliases whose direct PS object is physically present in the same retained "
            "map/block. An unanchored pointer cluster is considered only when every pointer occurrence has one exact "
            "paired-VS family proof. At least two pointer identities are required. Candidate direct pixel objects are "
            "restricted by SHA to the still-unmapped committed family target set, and a cluster promotes only when one "
            "candidate SHA set lies within the calibrated complete spacing residual and promoted SHA/pointer sets are "
            "globally disjoint. Exact pointer-to-SHA permutation is intentionally not claimed."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/mnt/data/t6_xanim_corpus"))
    ap.add_argument(
        "--structural-extension",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_residual_packed_ps_extension_v1.py"),
    )
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
    ap.add_argument(
        "--tc2-target-set",
        type=Path,
        default=Path("manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_TARGET_SET_V1.json"),
    )
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = build(
        a.root,
        a.structural_extension,
        a.owner_probe,
        a.paired_probe,
        a.base_verifier,
        a.broad_verifier,
        a.packed_vs_alias,
        a.tc2_target_set,
    )
    a.out.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
    print(json.dumps(d["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
