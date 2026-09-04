#!/usr/bin/env python3
"""Run and account the pending T6 reflection-normal closure stages in one pass.

The driver is intentionally orchestration-only. Each proof remains its own
fail-closed verifier and writes its own deterministic JSON. This driver executes
all stages even if one fails, records stdout/stderr/return code, hashes every
successfully produced stage manifest, and computes closure only from proven,
disjoint shader/fetch sets.

Baseline before the mixed-writer TEMP15 proof is 5,808 / 5,888. Pending work is:
  15 mixed-writer TEMP normals;
  24 Tomb sphere-electric physical owners;
  21 TC2/TC1 residual identities;
  20 TC3/TC1 residual identities.

The latter 41 are attempted first by exact packed-PS cross-map aliases and then by
serializer-differential candidate-set bounds. Differential promotion is required to
be disjoint from exact packed-PS promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

TOTAL_FETCHES = 5888
BASELINE_CLOSED = 5808
TEMP15_COUNT = 15
SPHERE_COUNT = 24
RESIDUAL_PRIOR = {
    "TEXCOORD2/TEXCOORD1": 21,
    "TEXCOORD3/TEXCOORD1": 20,
}


def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def promoted_exact_sets(data):
    out = {k: set() for k in RESIDUAL_PRIOR}
    if not data:
        return out
    for family, fd in data.get("families", {}).items():
        if family not in out:
            continue
        for row in fd.get("rows", []):
            if row.get("allOwnerOccurrencesProven"):
                out[family].add(row["pixelShaderSha256"])
    return out


def promoted_differential_sets(data):
    out = {k: set() for k in RESIDUAL_PRIOR}
    if not data:
        return out
    for row in data.get("promotedClusters", []):
        family = row.get("family")
        if family not in out:
            continue
        sets = row.get("candidateSets", [])
        if len(sets) != 1:
            raise ValueError("promoted differential cluster is not uniquely bounded")
        out[family].update(sets[0].get("shaderSha256", []))
    return out


def account(stage_data, stage_ok):
    temp_closed = 0
    if stage_ok.get("temp15"):
        s = stage_data["temp15"].get("summary", {})
        if s.get("targetFetchCount") != TEMP15_COUNT:
            raise ValueError("TEMP15 successful stage has wrong target count")
        temp_closed = TEMP15_COUNT

    sphere_closed = 0
    if stage_ok.get("spherePhysical"):
        s = stage_data["spherePhysical"].get("summary", {})
        if not s.get("promotionApproved") or s.get("promotedShaderCount") != SPHERE_COUNT:
            raise ValueError("sphere successful stage is not approved 24/24 closure")
        sphere_closed = SPHERE_COUNT

    exact = promoted_exact_sets(
        stage_data.get("residualExact") if stage_ok.get("residualExact") else None
    )
    diff = promoted_differential_sets(
        stage_data.get("residualDifferential")
        if stage_ok.get("residualDifferential")
        else None
    )
    for family in RESIDUAL_PRIOR:
        overlap = exact[family] & diff[family]
        if overlap:
            raise ValueError(
                f"{family}: exact/differential promotion overlap {sorted(overlap)}"
            )
        if len(exact[family] | diff[family]) > RESIDUAL_PRIOR[family]:
            raise ValueError(f"{family}: promoted more than prior residual population")

    residual_promoted = sum(len(exact[f] | diff[f]) for f in RESIDUAL_PRIOR)
    closed = BASELINE_CLOSED + temp_closed + sphere_closed + residual_promoted
    if closed > TOTAL_FETCHES:
        raise ValueError(f"closure overflow {closed}/{TOTAL_FETCHES}")

    family_rows = {}
    for family, prior in RESIDUAL_PRIOR.items():
        family_rows[family] = {
            "priorResidualCount": prior,
            "exactPackedPsPromotedCount": len(exact[family]),
            "serializerDifferentialPromotedCount": len(diff[family]),
            "promotedCount": len(exact[family] | diff[family]),
            "remainingCount": prior - len(exact[family] | diff[family]),
            "promotedShaderSha256": sorted(exact[family] | diff[family]),
        }

    return {
        "baselineClosedFetchCount": BASELINE_CLOSED,
        "tempComponentClosedFetchCount": temp_closed,
        "sphereElectricClosedFetchCount": sphere_closed,
        "residualFamilyPromotedFetchCount": residual_promoted,
        "closedFetchCount": closed,
        "totalFetchCount": TOTAL_FETCHES,
        "remainingFetchCount": TOTAL_FETCHES - closed,
        "closedPercent": closed * 100.0 / TOTAL_FETCHES,
        "closureComplete": closed == TOTAL_FETCHES,
        "unclosedPendingFamilies": {
            "TEMP_COMPONENT": TEMP15_COUNT - temp_closed,
            "SPHERE_ELECTRIC": SPHERE_COUNT - sphere_closed,
            **{f: r["remainingCount"] for f, r in family_rows.items()},
        },
        "residualFamilies": family_rows,
    }


def run_stage(name, cmd, out_path):
    cp = subprocess.run(cmd, text=True, capture_output=True)
    row = {
        "name": name,
        "command": cmd,
        "returnCode": cp.returncode,
        "stdout": cp.stdout,
        "stderr": cp.stderr,
        "output": str(out_path),
        "outputExists": out_path.exists(),
    }
    data = None
    if cp.returncode == 0:
        if not out_path.exists():
            row["returnCode"] = 97
            row["stderr"] += "\nverifier returned success but output file is absent"
        else:
            try:
                data = json.loads(out_path.read_text())
                row["outputSha256"] = sha256_file(out_path)
            except Exception as e:
                row["returnCode"] = 98
                row["stderr"] += f"\noutput parse failure: {e}"
                data = None
    return row, data


def script(repo: Path, name: str):
    return str(repo / "tools" / name)


def build_commands(repo: Path, root: Path, out: Path):
    py = sys.executable
    common = ["--root", str(root)]
    physical_deps = [
        "--tangent-verifier",
        script(repo, "t6_retail_reflection_probe_tangent_basis_normal_v1.py"),
        "--coordinate-verifier",
        script(repo, "t6_retail_reflection_probe_coordinate_v1.py"),
        "--weight-verifier",
        script(repo, "t6_retail_reflection_probe_weight_v1.py"),
        "--shared-verifier",
        script(repo, "t6_retail_reflection_probe_shared_parameter_v1.py"),
        "--surface-verifier",
        script(repo, "t6_retail_reflection_probe_surface_normal_v1.py"),
        "--guard",
        script(repo, "t6_retail_lightmap_secondary_rdef_guard_v1.py"),
        "--mip-verifier",
        script(repo, "t6_retail_reflection_probe_mip_v1.py"),
        "--angular-verifier",
        script(repo, "t6_retail_reflection_probe_angular_v1.py"),
        "--semantic-verifier",
        script(repo, "t6_retail_reflection_probe_material_semantics_v1.py"),
    ]
    return [
        (
            "temp15",
            [
                py,
                script(repo, "t6_retail_reflection_probe_temp_component_normal_v1.py"),
                *common,
                "--out",
                str(out / "T6_RETAIL_REFLECTION_PROBE_TEMP_COMPONENT_NORMAL_V1.json"),
            ],
            out / "T6_RETAIL_REFLECTION_PROBE_TEMP_COMPONENT_NORMAL_V1.json",
        ),
        (
            "sphereOwner",
            [
                py,
                script(repo, "t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v1.py"),
                *common,
                "--out",
                str(out / "T6_RETAIL_REFLECTION_PROBE_SPHERE_ELEC_PACKED_PS_V1.json"),
            ],
            out / "T6_RETAIL_REFLECTION_PROBE_SPHERE_ELEC_PACKED_PS_V1.json",
        ),
        (
            "spherePairedVs",
            [
                py,
                script(repo, "t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py"),
                *common,
                "--out",
                str(out / "T6_RETAIL_REFLECTION_PROBE_SPHERE_ELEC_PAIRED_VS_V1.json"),
            ],
            out / "T6_RETAIL_REFLECTION_PROBE_SPHERE_ELEC_PAIRED_VS_V1.json",
        ),
        (
            "spherePhysical",
            [
                py,
                script(repo, "t6_retail_reflection_probe_sphere_elec_physical_closure_v1.py"),
                *common,
                *physical_deps,
                "--out",
                str(out / "T6_RETAIL_REFLECTION_PROBE_SPHERE_ELEC_PHYSICAL_CLOSURE_V1.json"),
            ],
            out / "T6_RETAIL_REFLECTION_PROBE_SPHERE_ELEC_PHYSICAL_CLOSURE_V1.json",
        ),
        (
            "residualExact",
            [
                py,
                script(repo, "t6_retail_reflection_probe_residual_packed_ps_extension_v1.py"),
                *common,
                "--out",
                str(out / "T6_RETAIL_REFLECTION_PROBE_RESIDUAL_PACKED_PS_EXTENSION_V1.json"),
            ],
            out / "T6_RETAIL_REFLECTION_PROBE_RESIDUAL_PACKED_PS_EXTENSION_V1.json",
        ),
        (
            "residualDifferential",
            [
                py,
                script(repo, "t6_retail_reflection_probe_residual_packed_ps_differential_v1.py"),
                *common,
                "--out",
                str(out / "T6_RETAIL_REFLECTION_PROBE_RESIDUAL_PACKED_PS_DIFFERENTIAL_V1.json"),
            ],
            out / "T6_RETAIL_REFLECTION_PROBE_RESIDUAL_PACKED_PS_DIFFERENTIAL_V1.json",
        ),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--summary-out", type=Path)
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    summary_out = a.summary_out or (
        a.out_dir / "T6_RETAIL_REFLECTION_PROBE_FINAL_CLOSURE_RUN_V1.json"
    )

    stages = []
    data = {}
    ok = {}
    for name, cmd, out_path in build_commands(a.repo, a.root, a.out_dir):
        row, parsed = run_stage(name, cmd, out_path)
        stages.append(row)
        ok[name] = row["returnCode"] == 0 and parsed is not None
        if parsed is not None:
            data[name] = parsed

    accounting_error = None
    try:
        closure = account(data, ok)
    except Exception as e:
        closure = None
        accounting_error = str(e)

    result = {
        "format": "t6-retail-reflection-probe-final-closure-run-v1",
        "producer": "tools/t6_retail_reflection_probe_final_closure_driver_v1.py",
        "root": str(a.root),
        "stages": stages,
        "stageSuccess": ok,
        "closureAccounting": closure,
        "accountingError": accounting_error,
        "proofBoundary": (
            "Orchestration/accounting only. Each counted closure contribution comes from a successful independent "
            "retained-byte verifier output. Failed or absent stages contribute zero. Exact packed-PS and serializer-"
            "differential residual promotions are required to be SHA-disjoint before accounting. The driver preserves "
            "all stage diagnostics and does not convert a failed proof into a partial semantic claim."
        ),
    }
    summary_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stageSuccess": ok, "closureAccounting": closure, "accountingError": accounting_error}, indent=2, sort_keys=True))
    if accounting_error or not all(ok.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
