#!/usr/bin/env python3
"""Exact resource ancestry census for generated slot-4 final output DAGs.

Consumes ``t6-generated-slot4-final-output-symbolic-v3`` and independently
recomputes sampled-texture ancestry for every written output lane from the full
serialized DAG.  Stored lane ancestry must match exactly.

Resource grouping uses only exact reflected T6 names:
- colorMapSampler[1..3]
- normalMapSampler[1..3]
- specularMapSampler[1..3]
- lightmapSamplerPrimary
- lightmapSamplerSecondary
- reflectionProbeSampler

Unknown reflected names remain explicit and are never force-classified.  This
is an output-dependency proof, not a final lighting-equation proof.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3

FORMAT = "t6-generated-final-output-resource-ancestry-v1"
GENERATED_RE = re.compile(r"^(colorMapSampler|normalMapSampler|specularMapSampler)([1-3])?$")
EXACT_ROLES = {
    "lightmapSamplerPrimary": "lightmapPrimary",
    "lightmapSamplerSecondary": "lightmapSecondary",
    "reflectionProbeSampler": "reflectionProbe",
}


class GeneratedFinalOutputResourceAncestryError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _classify(name: str) -> dict:
    exact = EXACT_ROLES.get(name)
    if exact is not None:
        return {"resource": name, "class": exact, "layerIndex": None, "known": True}
    match = GENERATED_RE.fullmatch(name)
    if match:
        base = match.group(1)
        layer = int(match.group(2) or 0)
        role = {
            "colorMapSampler": "generatedColor",
            "normalMapSampler": "generatedNormal",
            "specularMapSampler": "generatedSpecular",
        }[base]
        return {"resource": name, "class": role, "layerIndex": layer, "known": True}
    return {"resource": name, "class": "unclassified", "layerIndex": None, "known": False}


def _recompute_resources(nodes: list[dict], root: int) -> set[str]:
    cache: dict[int, frozenset[str]] = {}
    visiting: set[int] = set()

    def walk(node_id: int) -> set[str]:
        if node_id in cache:
            return set(cache[node_id])
        if node_id in visiting:
            raise GeneratedFinalOutputResourceAncestryError(
                f"output DAG contains a cycle at node {node_id}"
            )
        if node_id < 0 or node_id >= len(nodes):
            raise GeneratedFinalOutputResourceAncestryError(
                f"output DAG references invalid node {node_id}"
            )
        visiting.add(node_id)
        node = nodes[node_id]
        if int(node.get("id", node_id)) != node_id:
            raise GeneratedFinalOutputResourceAncestryError(
                f"non-dense node identity at {node_id}: {node.get('id')!r}"
            )
        out = set()
        if node.get("kind") == "textureSample":
            resource = str(node.get("resource") or "")
            if not resource:
                raise GeneratedFinalOutputResourceAncestryError(
                    f"textureSample node {node_id} has empty RDEF resource identity"
                )
            out.add(resource)
        for child in node.get("args", []):
            out.update(walk(int(child)))
        visiting.remove(node_id)
        cache[node_id] = frozenset(out)
        return out

    return walk(int(root))


def _o0(shader: dict) -> dict:
    matches = [row for row in shader.get("outputs", []) if int(row.get("register", -1)) == 0]
    if len(matches) != 1:
        raise GeneratedFinalOutputResourceAncestryError(
            f"shader {shader.get('sha256')}: expected exactly one o0 output row, found {len(matches)}"
        )
    row = matches[0]
    lanes = row.get("lanes")
    if not isinstance(lanes, list) or len(lanes) != 4:
        raise GeneratedFinalOutputResourceAncestryError(
            f"shader {shader.get('sha256')}: o0 does not serialize exactly four lanes"
        )
    if [lane.get("channel") for lane in lanes] != list("xyzw"):
        raise GeneratedFinalOutputResourceAncestryError(
            f"shader {shader.get('sha256')}: o0 lane order is not xyzw"
        )
    return row


def build(final_output: dict, *, strict_nuketown: bool = False) -> dict:
    if final_output.get("format") != symbolic_v3.FORMAT:
        raise GeneratedFinalOutputResourceAncestryError(
            f"unsupported final-output manifest {final_output.get('format')!r}"
        )
    shaders = final_output.get("shaders")
    materials = final_output.get("materials")
    if not isinstance(shaders, list) or not isinstance(materials, list):
        raise GeneratedFinalOutputResourceAncestryError("final-output manifest lacks shaders/materials lists")

    resource_use = collections.Counter()
    output_resource_use = collections.Counter()
    class_shader_use = collections.Counter()
    unknown_resources: set[str] = set()
    signatures = collections.Counter()
    rows = []
    ancestry_checks = 0

    for shader in shaders:
        sha = str(shader.get("sha256") or "")
        nodes = shader.get("nodes")
        samples = shader.get("samples")
        if not sha or not isinstance(nodes, list) or not isinstance(samples, list):
            raise GeneratedFinalOutputResourceAncestryError(
                f"malformed shader row {sha!r}"
            )
        sample_names = []
        for sample in samples:
            resource = str(sample.get("resource") or "")
            if not resource:
                raise GeneratedFinalOutputResourceAncestryError(
                    f"shader {sha}: sample lacks exact RDEF resource name"
                )
            sample_names.append(resource)
            resource_use[resource] += 1

        o0 = _o0(shader)
        lane_rows = []
        rgb_sets = []
        all_output_resources = set()
        for lane in o0["lanes"]:
            written = bool(lane.get("written"))
            if not written:
                if lane.get("node") is not None or lane.get("resources") not in ([], None):
                    raise GeneratedFinalOutputResourceAncestryError(
                        f"shader {sha} o0.{lane['channel']}: unwritten lane carries node/resources"
                    )
                resources = []
            else:
                if lane.get("node") is None:
                    raise GeneratedFinalOutputResourceAncestryError(
                        f"shader {sha} o0.{lane['channel']}: written lane lacks root node"
                    )
                resources = sorted(_recompute_resources(nodes, int(lane["node"])))
                stored = sorted(str(x) for x in lane.get("resources", []))
                ancestry_checks += 1
                if resources != stored:
                    raise GeneratedFinalOutputResourceAncestryError(
                        f"shader {sha} o0.{lane['channel']}: recomputed resources {resources} != stored {stored}"
                    )
            all_output_resources.update(resources)
            for resource in resources:
                output_resource_use[resource] += 1
            lane_rows.append({
                "channel": lane["channel"],
                "written": written,
                "rootNode": lane.get("node"),
                "resources": resources,
                "resourceSetSha256": _jhash(resources),
            })
            if lane["channel"] in "xyz":
                rgb_sets.append(set(resources))

        if not all(row["written"] for row in lane_rows[:3]):
            raise GeneratedFinalOutputResourceAncestryError(
                f"shader {sha}: incomplete o0.rgb"
            )
        rgb_union = sorted(set().union(*rgb_sets))
        rgb_intersection = sorted(set.intersection(*rgb_sets)) if rgb_sets else []
        classified = [_classify(name) for name in sorted(all_output_resources)]
        classes = sorted({row["class"] for row in classified})
        for cls in classes:
            class_shader_use[cls] += 1
        unknown_resources.update(row["resource"] for row in classified if not row["known"])
        signature = {
            "rgbUnion": rgb_union,
            "rgbIntersection": rgb_intersection,
            "alpha": lane_rows[3]["resources"] if lane_rows[3]["written"] else [],
        }
        signature_sha = _jhash(signature)
        signatures[signature_sha] += 1
        rows.append({
            "sha256": sha,
            "techniqueSets": sorted(str(x) for x in shader.get("techniqueSets", [])),
            "o0": lane_rows,
            "rgbResourceUnion": rgb_union,
            "rgbResourceIntersection": rgb_intersection,
            "classifiedOutputResources": classified,
            "ancestryClasses": classes,
            "ancestrySignatureSha256": signature_sha,
        })

    if strict_nuketown:
        summary = final_output.get("summary", {})
        strict = final_output.get("strictNuketown")
        if not isinstance(strict, dict) or strict.get("map") != symbolic_v3.MAP:
            raise GeneratedFinalOutputResourceAncestryError(
                "strict Nuketown ancestry requires v3 strictNuketown proof block"
            )
        if len(materials) != 120 or len(shaders) != 34:
            raise GeneratedFinalOutputResourceAncestryError(
                f"strict Nuketown population changed materials={len(materials)} shaders={len(shaders)}"
            )
        if int(summary.get("canonicalShaderIdentityMismatchCount", -1)) != 0:
            raise GeneratedFinalOutputResourceAncestryError(
                "strict Nuketown ancestry refuses nonzero canonical shader identity mismatch"
            )

    signature_rows = [
        {"signatureSha256": key, "shaderCount": value}
        for key, value in sorted(signatures.items())
    ]
    classifications = [_classify(name) for name in sorted(resource_use)]
    return {
        "format": FORMAT,
        "sourceFormat": symbolic_v3.FORMAT,
        "shaders": rows,
        "resourceClassifications": classifications,
        "ancestrySignatures": signature_rows,
        "summary": {
            "materialCount": len(materials),
            "shaderCount": len(shaders),
            "sampleCount": sum(resource_use.values()),
            "sampleResourceCounts": dict(sorted(resource_use.items())),
            "outputLaneResourceUseCounts": dict(sorted(output_resource_use.items())),
            "ancestryClassShaderCounts": dict(sorted(class_shader_use.items())),
            "unknownOutputResources": sorted(unknown_resources),
            "unknownOutputResourceCount": len(unknown_resources),
            "outputAncestryCheckCount": ancestry_checks,
            "outputAncestryMismatchCount": 0,
            "ancestrySignatureCount": len(signature_rows),
            "shaderRowsSha256": _jhash(rows),
            "signatureRowsSha256": _jhash(signature_rows),
            "strictNuketown": bool(strict_nuketown),
        },
        "proofBoundary": (
            "Independent graph walk from every written o0 lane to exact RDEF-named textureSample atoms, with exact "
            "agreement against the ancestry stored by final-output symbolic v3. Resource classes are assigned only for "
            "known exact T6 reflected names; unknown names remain explicit. This proves dependencies, not the arithmetic "
            "or physical meaning of the final lighting equation."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--final-output", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--strict-nuketown", action="store_true")
    a = p.parse_args()
    source = json.loads(a.final_output.read_text(encoding="utf-8"))
    result = build(source, strict_nuketown=a.strict_nuketown)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
