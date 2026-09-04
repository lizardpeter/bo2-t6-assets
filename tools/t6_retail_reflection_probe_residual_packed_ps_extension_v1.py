#!/usr/bin/env python3
"""Packed-pixel-shader ownership extension for the final TC2/TC1 and TC3/TC1 residuals.

The committed family proofs physically map 54/75 A=TEXCOORD2,B=TEXCOORD1 shaders
and 22/42 A=TEXCOORD3,B=TEXCOORD1 shaders. Their broad pass joins intentionally
record a pixel shader identity only when the PS object is inline/direct. Packed PS
nodes therefore remain invisible to those family joins.

This probe reuses the independently built packed-PS graph from the sphere-electric
work. It resolves packed PS pointers only through exact cross-map
TechniqueSet/slot/pass/worldVertFormat identity. For any newly recovered target PS
identity, *every* retained owner occurrence must also resolve its paired VS through
an exact direct/cross-map/committed packed-VS alias and the resulting direct VS
payload must prove the physical roles already required by the corresponding family:

  TC2/TC1: TEXCOORD2 = normalized world NORMAL0; TEXCOORD1 = world POSITION0
  TC3/TC1: TEXCOORD3 = normalized world NORMAL0; TEXCOORD1 = world POSITION0

This is an extension probe, not a count assumption. It reports exactly what the
retained packed-PS aliases recover and fails closed per shader identity when any
owner occurrence lacks a resolvable/proven paired VS.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path

EXPECTED_TC2_GLOBAL = 75
EXPECTED_TC2_PRIOR_MAPPED = 54
EXPECTED_TC3_GLOBAL = 42
EXPECTED_TC3_PRIOR_MAPPED = 22
EXPECTED_STRUCTURAL_PS_ANCHORS = 76
TOTAL_REFLECTION_FETCHES = 5888


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


def load_tc2_targets(path: Path):
    d = json.loads(path.read_text())
    rows = d.get("shaderSha256", [])
    if len(rows) != EXPECTED_TC2_GLOBAL or len(set(rows)) != EXPECTED_TC2_GLOBAL:
        raise ValueError(f"TC2/TC1 target-set count {len(rows)}")
    return set(rows)


def direct_ps_hash(node):
    if node is not None and node[0] == "sha":
        return node[1]
    return None


def resolved_ps_hash(node, structural_ps):
    h = direct_ps_hash(node)
    if h is not None:
        return h, ["direct"]
    if node is not None and node[0] == "ptr" and node in structural_ps:
        return structural_ps[node], ["crossMapPassKey"]
    return None, []


def prove_family_vs(family, base, broad, blob):
    if family == "TEXCOORD2/TEXCOORD1":
        return base.prove_vs(blob)
    if family == "TEXCOORD3/TEXCOORD1":
        return broad.prove_vs_tc3(base, blob)
    raise ValueError(f"unknown family {family}")


def build(
    root: Path,
    owner_probe_path: Path,
    paired_probe_path: Path,
    base_path: Path,
    broad_path: Path,
    packed_vs_alias_path: Path,
    tc2_target_set_path: Path,
):
    owner = load(owner_probe_path, "residual_owner")
    paired = load(paired_probe_path, "residual_paired")
    base = load(base_path, "residual_base")
    broad = load(broad_path, "residual_broad")

    tc2 = load_tc2_targets(tc2_target_set_path)
    tc3_rows, _, tc3_fetches = broad.global_target(root, base)
    tc3 = set(tc3_rows)
    if len(tc3) != EXPECTED_TC3_GLOBAL or tc3_fetches != EXPECTED_TC3_GLOBAL:
        raise ValueError(f"TC3/TC1 global target census {len(tc3)}/{tc3_fetches}")
    if tc2 & tc3:
        raise ValueError("TC2/TC1 and TC3/TC1 target sets overlap")

    events, direct_blobs, direct_objects, scan_rows = owner.collect_broad_events(
        root, base, broad
    )
    del direct_objects
    structural_ps, all_ps_ptrs, _ = owner.structural_aliases(events, "ps")
    if len(structural_ps) != EXPECTED_STRUCTURAL_PS_ANCHORS:
        raise ValueError(
            f"structural packed PS anchors {len(structural_ps)} != {EXPECTED_STRUCTURAL_PS_ANCHORS}"
        )
    structural_vs, all_vs_ptrs, _ = owner.structural_aliases(events, "vs")
    committed_vs = paired.load_committed_packed_vs(packed_vs_alias_path)

    families = {
        "TEXCOORD2/TEXCOORD1": (tc2, EXPECTED_TC2_PRIOR_MAPPED),
        "TEXCOORD3/TEXCOORD1": (tc3, EXPECTED_TC3_PRIOR_MAPPED),
    }
    family_outputs = {}
    all_promoted = set()

    for family, (targets, expected_prior) in families.items():
        direct_prior = set()
        resolved_occurrences = collections.defaultdict(list)
        packed_target_ptrs = set()
        for mapname, evs in events.items():
            for e in evs:
                dh = direct_ps_hash(e["ps"])
                if dh in targets:
                    direct_prior.add(dh)
                h, ps_sources = resolved_ps_hash(e["ps"], structural_ps)
                if h not in targets:
                    continue
                if e["ps"][0] == "ptr":
                    packed_target_ptrs.add(e["ps"])
                resolved_occurrences[h].append((mapname, e, ps_sources))

        if len(direct_prior) != expected_prior:
            raise ValueError(
                f"{family}: direct-PS mapped count {len(direct_prior)} != prior {expected_prior}"
            )

        recovered = set(resolved_occurrences)
        newly_recovered = recovered - direct_prior
        rows = []
        promoted = set()
        rejected = []
        proof_cache = {}

        for h in sorted(newly_recovered):
            owner_rows = []
            failures = []
            for mapname, e, ps_sources in resolved_occurrences[h]:
                vh, vs_sources = paired.resolve_vs_node(
                    e["vs"], structural_vs, committed_vs
                )
                proof = None
                error = None
                if vh is None:
                    error = "paired VS unresolved"
                else:
                    key = (family, vh)
                    if key not in proof_cache:
                        blob = direct_blobs["vs"].get(vh)
                        if blob is None:
                            proof_cache[key] = (None, f"resolved VS payload absent: {vh}")
                        else:
                            try:
                                proof_cache[key] = (
                                    prove_family_vs(family, base, broad, blob),
                                    None,
                                )
                            except Exception as ex:
                                proof_cache[key] = (None, str(ex))
                    proof, error = proof_cache[key]
                r = {
                    "map": mapname,
                    "techniqueSet": e["ts"],
                    "worldVertFormat": e["fmt"],
                    "slot": e["slot"],
                    "passIndex": e["pass"],
                    "pixelNode": list(e["ps"]),
                    "pixelResolutionSources": ps_sources,
                    "pairedVertexNode": list(e["vs"]) if e["vs"] is not None else None,
                    "resolvedVertexShaderSha256": vh,
                    "vertexResolutionSources": vs_sources,
                    "vertexRoleProof": proof,
                    "error": error,
                }
                owner_rows.append(r)
                if error is not None:
                    failures.append(r)
            ok = bool(owner_rows) and not failures
            row = {
                "pixelShaderSha256": h,
                "ownerOccurrenceCount": len(owner_rows),
                "allOwnerOccurrencesProven": ok,
                "ownerRows": owner_rows,
            }
            rows.append(row)
            if ok:
                promoted.add(h)
            else:
                rejected.append(row)

        # No direct-PS identity may be called "new" through a second packed occurrence.
        if promoted & direct_prior:
            raise ValueError(f"{family}: promoted set overlaps prior direct-mapped set")
        all_promoted |= promoted

        family_outputs[family] = {
            "globalTargetShaderCount": len(targets),
            "priorDirectMappedShaderCount": len(direct_prior),
            "packedAliasRecoveredShaderCount": len(newly_recovered),
            "physicallyPromotedShaderCount": len(promoted),
            "rejectedRecoveredShaderCount": len(rejected),
            "stillUnmappedAfterStructuralPackedPsCount": len(targets - recovered),
            "uniquePackedTargetPointerCount": len(packed_target_ptrs),
            "priorDirectMappedShaderSetSha256": jhash(sorted(direct_prior)),
            "newlyRecoveredShaderSetSha256": jhash(sorted(newly_recovered)),
            "promotedShaderSetSha256": jhash(sorted(promoted)),
            "rowsSha256": jhash(rows),
            "rows": rows,
        }

    summary = {
        "structurallyAnchoredPackedPixelPointerCount": len(structural_ps),
        "allPackedPixelPointerCount": len(all_ps_ptrs),
        "structurallyAnchoredPackedVertexPointerCount": len(structural_vs),
        "allPackedVertexPointerCount": len(all_vs_ptrs),
        "committedPackedVertexAliasCount": len(committed_vs),
        "tc2Texcoord1PriorUnmappedCount": EXPECTED_TC2_GLOBAL - EXPECTED_TC2_PRIOR_MAPPED,
        "tc3Texcoord1PriorUnmappedCount": EXPECTED_TC3_GLOBAL - EXPECTED_TC3_PRIOR_MAPPED,
        "residualFamilyPriorUnmappedCount": (
            EXPECTED_TC2_GLOBAL
            - EXPECTED_TC2_PRIOR_MAPPED
            + EXPECTED_TC3_GLOBAL
            - EXPECTED_TC3_PRIOR_MAPPED
        ),
        "newlyPhysicallyPromotedShaderCount": len(all_promoted),
        "remainingResidualFamilyShaderCount": 41 - len(all_promoted),
        "scanRowsSha256": jhash(scan_rows),
        "familySummarySha256": jhash(
            {
                k: {kk: vv for kk, vv in v.items() if kk != "rows"}
                for k, v in family_outputs.items()
            }
        ),
    }
    return {
        "format": "t6-retail-reflection-probe-residual-packed-ps-extension-v1",
        "producer": "tools/t6_retail_reflection_probe_residual_packed_ps_extension_v1.py",
        "sources": {
            "tc2Tc1TargetSet": str(tc2_target_set_path),
            "tc3Tc1FamilyVerifier": str(broad_path),
            "packedPixelOwnerProbe": str(owner_probe_path),
            "pairedVertexResolver": str(paired_probe_path),
            "packedVertexAlias": str(packed_vs_alias_path),
            "closureLedger": "manifests/render/T6_RETAIL_REFLECTION_PROBE_CLOSURE_LEDGER_V1.json",
        },
        "families": family_outputs,
        "summary": summary,
        "proofBoundary": (
            "Ownership/producer extension only. Pixel-side reflect roles for both target populations are inherited from "
            "their committed exhaustive family proofs. A previously unmapped pixel shader is promoted here only when an "
            "exact cross-map pass-key identity resolves its packed PS pointer to that target SHA and every retained owner "
            "occurrence resolves to a paired VS payload that directly proves the family's NORMAL0/worldMatrix3x3 and "
            "POSITION0/worldMatrix producer roles. No pointer-spacing inference is used in this stage; unresolved packed "
            "PS pointers remain unresolved rather than being guessed."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/mnt/data/t6_xanim_corpus"))
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
