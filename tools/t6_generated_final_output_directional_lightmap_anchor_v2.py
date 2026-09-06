#!/usr/bin/env python3
"""Semantic DAG anchor for the exact T6 directional secondary-lightmap equation.

The retained DXBC proof distinguishes two compiler materializations:
- explicit row0/row1 normalization before the final MAD;
- row0 normalization folded into the final MAD.

The full-output symbolic engine lowers the exact SM4 MAD instruction semantics
to ``add(mul(a,b),c)``.  At that expression-DAG level the two compiler
materializations can therefore converge *without* algebraic rewriting.

This v2 promotion reuses the exact row/sample/epsilon/direction/dot/final-form
matcher from probe v1, but treats matches as semantic equation anchors rather
than instruction-encoding labels.  Strict mode requires every shader to expose
exactly one or two anchored equations, matching the separately committed
retained corpus invariant (15 one-equation shaders, 158 two-equation shaders
across the five retained worlds; zero shader failures).

It does not claim which compiler encoding produced a matched DAG and does not
connect the equation to final material shading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import t6_generated_final_output_directional_lightmap_anchor_probe_v1 as probe
import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3

FORMAT = "t6-generated-final-output-directional-lightmap-anchor-v2"


class DirectionalLightmapAnchorV2Error(probe.DirectionalLightmapAnchorProbeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def build(final_output: dict, *, strict: bool = True) -> dict:
    if final_output.get("format") != symbolic_v3.FORMAT:
        raise DirectionalLightmapAnchorV2Error(
            f"unsupported final-output format {final_output.get('format')!r}"
        )
    base = probe.build(final_output)
    if base.get("format") != probe.FORMAT:
        raise DirectionalLightmapAnchorV2Error(
            f"unexpected probe result {base.get('format')!r}"
        )

    rows = []
    zero = one = two = other = 0
    equation_count = 0
    normal_hashes = set()
    for source in base.get("shaders", []):
        equations = []
        for raw in source.get("equations", []):
            eq = dict(raw)
            eq["expressionEncoding"] = "symbolic-sm4-expression-dag"
            eq["compilerMaterialization"] = "not inferred from expression DAG"
            eq.pop("encoding", None)
            equations.append(eq)
            normal_hashes.add(str(eq.get("normalSha256") or ""))
        count = len(equations)
        equation_count += count
        if count == 0:
            zero += 1
        elif count == 1:
            one += 1
        elif count == 2:
            two += 1
        else:
            other += 1
        if strict and count not in (1, 2):
            raise DirectionalLightmapAnchorV2Error(
                f"shader {source.get('sha256')}: directional equation count {count} outside retained 1..2 invariant"
            )
        rows.append({
            "sha256": source.get("sha256"),
            "techniqueSets": source.get("techniqueSets", []),
            "rowTripletCount": int(source.get("rowTripletCount", 0)),
            "directionalEquationCount": count,
            "equations": equations,
            "anchored": count in (1, 2),
        })

    summary = {
        "shaderCount": len(rows),
        "directionalEquationCount": equation_count,
        "zeroEquationShaderCount": zero,
        "oneEquationShaderCount": one,
        "twoEquationShaderCount": two,
        "threeOrMoreEquationShaderCount": other,
        "anchoredShaderCount": one + two,
        "uniqueNormalCounterpartHashCount": len({x for x in normal_hashes if x}),
        "strict": bool(strict),
        "rowsSha256": _jhash(rows),
    }
    if strict and summary["anchoredShaderCount"] != summary["shaderCount"]:
        raise DirectionalLightmapAnchorV2Error("strict directional-lightmap anchoring incomplete")

    return {
        "format": FORMAT,
        "sourceFormat": symbolic_v3.FORMAT,
        "sourceProbeFormat": probe.FORMAT,
        "shaders": rows,
        "summary": summary,
        "retainedCorpusInvariant": {
            "source": "manifests/render/T6_RETAIL_LAYERED_DIRECTIONAL_LIGHTMAP_V1.json",
            "retainedMapCount": 5,
            "uniqueSlot4ShaderCount": 173,
            "directionalEquationCount": 331,
            "oneEquationShaderCount": 15,
            "twoEquationShaderCount": 158,
            "shaderFailureCount": 0,
            "compilerEquationEncodingCounts": {"explicit": 316, "folded": 15},
        },
        "symbolicNormalizationPolicy": (
            "SM4 MAD is lowered only by its exact instruction semantics to add(mul(a,b),c); this can erase the "
            "compiler's explicit-vs-folded materialization distinction at expression-DAG level. No commutative/"
            "associative or other algebraic rewrite is introduced by this promotion."
        ),
        "proofBoundary": (
            "Exact semantic anchor for the separately source-closed directional secondary-lightmap equation inside "
            "complete generated slot-4 final-output expression DAGs. Strict mode requires one or two equation anchors "
            "per shader. Compiler materialization is deliberately not inferred from the normalized expression DAG; "
            "downstream final material/light/reflection composition remains separate."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--final-output", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--relaxed", action="store_true")
    a = p.parse_args()
    source = json.loads(a.final_output.read_text(encoding="utf-8"))
    result = build(source, strict=not a.relaxed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
