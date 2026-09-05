#!/usr/bin/env python3
"""Probe paired slot-4 VS producers for the T6 generated layered-normal basis.

Pixel-side retained DXBC already proves, for all 107 unique layered-normal PSs:

    rawN = TEXCOORD1.xyz + X * TEXCOORD3.xyz + Y * TEXCOORD2.xyz

This stage consumes a canonical generated recipe manifest carrying exact paired
``vertexShaderArchetype`` identities (recovery v5), resolves the same slot-4 OAT
VS payload, and applies the existing direct VS role proof used by reflection
closure. It reports whether TEXCOORD1 is directly proven from NORMAL0 and whether
TEXCOORD3 is directly proven from TANGENT0. TEXCOORD2 is profiled exhaustively
but is NOT named binormal until a separate exact cross/handedness proof succeeds.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from t6_generated_shader_recipe_contract_v1 import validate_manifest
from t6_oat_slot_shader_resolver_v2 import resolve_slot_shaders


FORMAT = "t6-generated-layered-normal-vs-basis-probe-v1"


class LayeredNormalVsProbeError(RuntimeError):
    pass


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise LayeredNormalVsProbeError(f"cannot load verifier {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _has_normal_layer(recipe: dict) -> bool:
    program = recipe.get("layerProgram", [])
    return any(bool(step.get("hasNormal")) for step in program)


def _role_semantics(rows: list[dict]) -> set[str]:
    return {str(row.get("semantic") or "") for row in rows}


def build(
    recipe_manifest: dict,
    *,
    oat_root: Path,
    paired_vs_probe_path: Path,
    base_verifier_path: Path,
) -> dict:
    recipes = validate_manifest(recipe_manifest)
    paired = _load(paired_vs_probe_path, "t6_layered_normal_paired_vs")
    base = _load(base_verifier_path, "t6_layered_normal_vs_base")

    normal_rows = [row for row in recipes.values() if _has_normal_layer(row)]
    if not normal_rows:
        raise LayeredNormalVsProbeError("recipe manifest contains no generated layered-normal materials")
    techsets = sorted({str(row["techniqueSet"]) for row in normal_rows})
    by_techset: dict[str, list[dict]] = {}
    for row in normal_rows:
        by_techset.setdefault(str(row["techniqueSet"]), []).append(row)

    profiles: list[dict] = []
    direct_base_normal_count = 0
    direct_x_tangent_count = 0
    exact_pair_count = 0
    for techset in techsets:
        owners = by_techset[techset]
        vertex_ids = {str(row.get("vertexShaderArchetype") or "") for row in owners}
        pixel_ids = {str(row.get("pixelShaderArchetype") or "") for row in owners}
        if len(vertex_ids) != 1 or not next(iter(vertex_ids)).startswith("sha256:"):
            raise LayeredNormalVsProbeError(
                f"{techset!r}: owner recipes do not share one exact paired VS identity"
            )
        if len(pixel_ids) != 1 or not next(iter(pixel_ids)).startswith("sha256:"):
            raise LayeredNormalVsProbeError(
                f"{techset!r}: owner recipes do not share one exact PS identity"
            )
        expected_vs = next(iter(vertex_ids))[7:]
        expected_ps = next(iter(pixel_ids))[7:]

        resolved = resolve_slot_shaders(
            oat_root,
            techset,
            slot_index=4,
            require_single_vertex_shader=True,
            require_single_pixel_shader=True,
        )
        vs = resolved["vertexShaders"][0]
        ps = resolved["pixelShaders"][0]
        if vs["sha256"] != expected_vs or ps["sha256"] != expected_ps:
            raise LayeredNormalVsProbeError(
                f"{techset!r}: OAT slot-4 VS/PS pair disagrees with canonical owner recipes"
            )
        blob = (Path(oat_root) / vs["relativeFile"]).read_bytes()
        if hashlib.sha256(blob).hexdigest() != expected_vs:
            raise LayeredNormalVsProbeError(f"{techset!r}: VS payload changed after exact resolution")

        roles = paired.exact_role_candidates(base, blob)
        base_normals = _role_semantics(roles.get("worldNormal", []))
        tangents = _role_semantics(roles.get("worldTangent", []))
        base_ok = "TEXCOORD1" in base_normals
        tangent_ok = "TEXCOORD3" in tangents
        direct_base_normal_count += int(base_ok)
        direct_x_tangent_count += int(tangent_ok)
        exact_pair_count += int(base_ok and tangent_ok)

        components = {}
        for tc in (1, 2, 3):
            rows = paired.component_profile(base, blob, tc)
            if rows is None:
                raise LayeredNormalVsProbeError(
                    f"{techset!r}: paired VS lacks TEXCOORD{tc} required by proven pixel basis"
                )
            components[f"TEXCOORD{tc}"] = rows

        profiles.append({
            "techniqueSet": techset,
            "materialOwnerCount": len(owners),
            "vertexShaderSha256": expected_vs,
            "pixelShaderSha256": expected_ps,
            "vertexShaderAsset": vs["asset"],
            "vertexShaderFile": vs["relativeFile"],
            "exactRoleCandidates": roles,
            "pixelBasis": {
                "base": "TEXCOORD1.xyz",
                "xBasis": "TEXCOORD3.xyz",
                "yBasis": "TEXCOORD2.xyz",
            },
            "directRoleMatches": {
                "baseIsWorldNormalFromNormal0": base_ok,
                "xBasisIsWorldTangentFromTangent0": tangent_ok,
                "yBasisPhysicalRole": "unpromoted",
            },
            "basisComponentAncestry": components,
        })

    summary = {
        "materialOwnerCount": len(normal_rows),
        "techniqueSetCount": len(techsets),
        "pairedVertexShaderIdentityCount": len({row["vertexShaderSha256"] for row in profiles}),
        "directBaseNormalTechniqueSetCount": direct_base_normal_count,
        "directXBasisTangentTechniqueSetCount": direct_x_tangent_count,
        "directBaseAndXPairTechniqueSetCount": exact_pair_count,
        "yBasisPromotedTechniqueSetCount": 0,
        "allPairedVsPayloadsExact": True,
        "profilesSha256": _jhash(profiles),
    }
    return {
        "format": FORMAT,
        "producer": "tools/t6_generated_layered_normal_vs_basis_probe_v1.py",
        "pixelProof": "manifests/render/T6_RETAIL_LAYERED_NORMAL_RECONSTRUCTION_V1.json",
        "profiles": profiles,
        "summary": summary,
        "proofBoundary": (
            "Exact canonical generated Material -> TechniqueSet -> paired slot-4 VS/PS identities, then direct "
            "retained-VS output-role profiling. TEXCOORD1/TEXCOORD3 are promoted only when the existing SM4 "
            "proof directly traces them to NORMAL0/TANGENT0 world-matrix forms. TEXCOORD2 remains explicitly "
            "unpromoted regardless of input ancestry until its full cross/handedness equation is separately proved."
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
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.recipes.read_text(encoding="utf-8"))
    doc = build(
        manifest,
        oat_root=args.oat_root,
        paired_vs_probe_path=args.paired_vs_probe,
        base_verifier_path=args.base_verifier,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
