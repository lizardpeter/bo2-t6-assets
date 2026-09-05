#!/usr/bin/env python3
"""Generated layered-normal paired VS basis probe v2: exact TC2 binormal math.

v1 directly profiles paired slot-4 VS outputs and promotes only the roles already
closed by the existing VS proof: TC1 from NORMAL0 and TC3 from TANGENT0. v2 adds
an algebraic straight-line SM4 comparison for TC2:

    TC2.xyz == cross(TC1.xyz, TC3.xyz) * TANGENT0.w

The comparison uses the actual paired VS output DAG, with commutative add/mul
canonicalization but no semantic-name inference. Reversed cross order is reported
separately and is not promoted as the expected T6 binormal convention.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import t6_generated_layered_normal_vs_basis_probe_v1 as v1
from t6_vertex_output_symbolic_v1 import (
    classify_cross_handedness,
    symbolic_vertex,
)


FORMAT = "t6-generated-layered-normal-vs-basis-probe-v2"


class LayeredNormalVsProbeV2Error(RuntimeError):
    pass


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise LayeredNormalVsProbeV2Error(f"cannot load verifier {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _semantic_register(base, blob: bytes, tag: bytes, semantic: tuple[str, int]) -> int:
    mapping = base.signature(blob, tag)
    matches = [int(reg) for reg, value in mapping.items() if tuple(value) == semantic]
    if len(matches) != 1:
        raise LayeredNormalVsProbeV2Error(
            f"{tag.decode(errors='ignore')} semantic {semantic} matched registers {matches}"
        )
    return matches[0]


def _output_vec(symbolic: dict, register: int, label: str) -> tuple[int, int, int]:
    outputs = symbolic["outputs"]
    try:
        return tuple(int(outputs[(register, lane)]) for lane in range(3))
    except KeyError as exc:
        raise LayeredNormalVsProbeV2Error(
            f"{label} output register o{register} lacks complete xyz symbolic writers"
        ) from exc


def build(
    recipe_manifest: dict,
    *,
    oat_root: Path,
    paired_vs_probe_path: Path,
    base_verifier_path: Path,
    opcode_path: Path,
    operand_path: Path,
) -> dict:
    base_doc = v1.build(
        recipe_manifest,
        oat_root=oat_root,
        paired_vs_probe_path=paired_vs_probe_path,
        base_verifier_path=base_verifier_path,
    )
    base = _load(base_verifier_path, "t6_layered_normal_vs_base_v2")
    opcode = _load(opcode_path, "t6_layered_normal_vs_opcode")
    operand = _load(operand_path, "t6_layered_normal_vs_operand")

    profiles = []
    expected_binormal = 0
    reversed_binormal = 0
    unresolved = 0
    for source in base_doc["profiles"]:
        row = dict(source)
        vs_path = Path(oat_root) / str(row["vertexShaderFile"])
        blob = vs_path.read_bytes()
        if hashlib.sha256(blob).hexdigest() != row["vertexShaderSha256"]:
            raise LayeredNormalVsProbeV2Error(
                f"{row['techniqueSet']!r}: paired VS payload SHA changed"
            )
        if not row["directRoleMatches"]["baseIsWorldNormalFromNormal0"]:
            raise LayeredNormalVsProbeV2Error(
                f"{row['techniqueSet']!r}: TC1 base is not directly proven world NORMAL0"
            )
        if not row["directRoleMatches"]["xBasisIsWorldTangentFromTangent0"]:
            raise LayeredNormalVsProbeV2Error(
                f"{row['techniqueSet']!r}: TC3 X basis is not directly proven world TANGENT0"
            )

        tc1 = _semantic_register(base, blob, b"OSGN", ("TEXCOORD", 1))
        tc2 = _semantic_register(base, blob, b"OSGN", ("TEXCOORD", 2))
        tc3 = _semantic_register(base, blob, b"OSGN", ("TEXCOORD", 3))
        tangent_input = _semantic_register(base, blob, b"ISGN", ("TANGENT", 0))

        symbolic = symbolic_vertex(blob, operand, opcode)
        dag = symbolic["dag"]
        normal = _output_vec(symbolic, tc1, "TC1/world normal")
        candidate = _output_vec(symbolic, tc2, "TC2/Y basis")
        tangent = _output_vec(symbolic, tc3, "TC3/world tangent")
        handedness = dag.add("symbol", name=f"v{tangent_input}.w")
        comparison = classify_cross_handedness(
            dag,
            normal=normal,
            tangent=tangent,
            handedness=handedness,
            candidate=candidate,
        )
        match = comparison["uniqueMatch"]
        if match == "cross(normal,tangent)*handedness":
            status = "exact-binormal"
            expected_binormal += 1
        elif match == "cross(tangent,normal)*handedness":
            status = "reversed-cross"
            reversed_binormal += 1
        else:
            status = "unresolved"
            unresolved += 1

        row["binormalAlgebra"] = {
            "status": status,
            "handednessInput": f"TANGENT0.w (v{tangent_input}.w)",
            "comparison": comparison,
            "symbolicNodeCount": symbolic["nodeCount"],
        }
        row["directRoleMatches"] = {
            **row["directRoleMatches"],
            "yBasisPhysicalRole": "worldBinormal" if status == "exact-binormal" else "unpromoted",
            "yBasisExactCrossHandedness": status == "exact-binormal",
        }
        profiles.append(row)

    count = len(profiles)
    summary = {
        **base_doc["summary"],
        "exactBinormalTechniqueSetCount": expected_binormal,
        "reversedCrossTechniqueSetCount": reversed_binormal,
        "unresolvedBinormalTechniqueSetCount": unresolved,
        "allThreeBasisRolesExact": expected_binormal == count and reversed_binormal == 0 and unresolved == 0,
        "profilesV2Sha256": _jhash(profiles),
    }
    return {
        "format": FORMAT,
        "producer": "tools/t6_generated_layered_normal_vs_basis_probe_v2.py",
        "supersedesProbe": base_doc["format"],
        "pixelProof": base_doc["pixelProof"],
        "profiles": profiles,
        "summary": summary,
        "proofBoundary": (
            "Exact v1 paired-VS ownership/direct NORMAL0/TANGENT0 role proof plus straight-line retained-VS "
            "symbolic equality for TC2.xyz against cross(TC1.xyz,TC3.xyz)*TANGENT0.w. Only the exact normal-" 
            "tangent cross orientation is promoted to worldBinormal; reversed or unmatched expressions remain "
            "unpromoted. Renderer normal-map decode/composition is still a separate integration stage."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", type=Path, required=True)
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument(
        "--paired-vs-probe",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py"),
    )
    parser.add_argument(
        "--base-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py"),
    )
    parser.add_argument(
        "--opcode",
        type=Path,
        default=Path("tools/t6_retail_special_shdr_opcode_census_v1.py"),
    )
    parser.add_argument(
        "--operand",
        type=Path,
        default=Path("tools/t6_retail_special_shdr_operand_census_v1.py"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    recipes = json.loads(args.recipes.read_text(encoding="utf-8"))
    doc = build(
        recipes,
        oat_root=args.oat_root,
        paired_vs_probe_path=args.paired_vs_probe,
        base_verifier_path=args.base_verifier,
        opcode_path=args.opcode,
        operand_path=args.operand,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
