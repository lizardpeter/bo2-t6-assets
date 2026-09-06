#!/usr/bin/env python3
"""Anchor canonical generated specular XYZW state inside exact slot-4 o0 DAGs.

Inputs:
- canonical generated recipe manifest whose specular-bearing recipes carry
  ``generatedSpecularStateV1`` (v21 contract);
- exact full-output symbolic manifest v3.

This verifier does NOT assign physical meanings to specular X/Y/Z/W.  It only
locates the already source-closed ordered T6 specular state in the complete
pixel-shader dataflow and proves whether the completed state is downstream-used
by final o0.

For each specular-bearing recipe:
- baseline is taken only from the canonical v21 attachment;
- explicit base/layer specular samples are matched by exact RDEF resource name
  and exact channel;
- blend steps must match
      prev + (layer - prev) * factor
  independently in all four channels, with one identical factor DAG shared by
  X/Y/Z/W;
- threshold steps must match
      select(condition, layer, prev)
  independently in all four channels, with one identical condition DAG shared
  by X/Y/Z/W;
- the completed channel roots are tested for exact ancestry to written o0 lanes.

The cross-channel shared factor is an independent final-output check of the
retained v21 contract.  It is not reinterpreted as roughness/metallic/F0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any

from t6_generated_shader_recipe_contract_v1 import validate_manifest

FORMAT = "t6-generated-final-output-specular-state-anchor-v1"
SPEC_KEY = "generatedSpecularStateV1"
FINAL_FORMAT = "t6-generated-slot4-final-output-symbolic-v3"
CHANNELS = "xyzw"
F02_BITS = "3e4ccccd"
ZERO_BITS = "00000000"


class SpecularFinalOutputAnchorError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _node_map(shader: dict) -> dict[int, dict]:
    rows = shader.get("nodes")
    if not isinstance(rows, list):
        raise SpecularFinalOutputAnchorError("shader has no symbolic nodes")
    out = {}
    for row in rows:
        node_id = int(row.get("id", -1))
        if node_id in out or node_id < 0:
            raise SpecularFinalOutputAnchorError(f"invalid/duplicate node id {node_id}")
        out[node_id] = row
    return out


def _parents(nodes: dict[int, dict]) -> dict[int, set[int]]:
    out: dict[int, set[int]] = defaultdict(set)
    for node_id, row in nodes.items():
        for child in row.get("args", []):
            child = int(child)
            if child not in nodes:
                raise SpecularFinalOutputAnchorError(
                    f"node {node_id} references missing child {child}"
                )
            out[child].add(node_id)
    return out


def _ancestors(nodes: dict[int, dict], root: int) -> set[int]:
    seen: set[int] = set()
    def walk(node_id: int) -> None:
        if node_id in seen:
            return
        seen.add(node_id)
        for child in nodes[node_id].get("args", []):
            walk(int(child))
    walk(root)
    return seen


def _output_roots(shader: dict) -> dict[str, int]:
    outputs = shader.get("outputs")
    if not isinstance(outputs, list):
        raise SpecularFinalOutputAnchorError("shader has no outputs")
    o0 = [row for row in outputs if int(row.get("register", -1)) == 0]
    if len(o0) != 1:
        raise SpecularFinalOutputAnchorError(f"shader has {len(o0)} o0 records")
    roots = {}
    for lane in o0[0].get("lanes", []):
        channel = str(lane.get("channel") or "")
        if channel not in CHANNELS:
            continue
        if bool(lane.get("written")):
            node = lane.get("node")
            if node is None:
                raise SpecularFinalOutputAnchorError(f"o0.{channel} written without node")
            roots[channel] = int(node)
    return roots


def _canonical(nodes: dict[int, dict], node_id: int, memo=None) -> Any:
    memo = {} if memo is None else memo
    if node_id in memo:
        return memo[node_id]
    row = nodes[node_id]
    kind = str(row.get("kind") or "")
    if kind == "op":
        op = str(row.get("op") or "")
        args = [_canonical(nodes, int(child), memo) for child in row.get("args", [])]
        # Only operations known commutative at the exact expression level are
        # sorted. select/div/neg etc preserve operand order.
        if op in {"add", "mul", "min", "max", "eq", "ne", "and", "or", "and_bool"}:
            args = sorted(args, key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")))
        value = ("op", op, tuple(args))
    elif kind == "textureSample":
        value = (
            "sample",
            str(row.get("resource") or ""),
            str(row.get("channel") or ""),
            str(row.get("sampler") or ""),
            tuple(_canonical(nodes, int(child), memo) for child in row.get("args", [])),
        )
    elif kind == "literal32":
        value = ("literal32", str(row.get("bits") or "").lower())
    else:
        payload = {
            key: row[key] for key in sorted(row)
            if key not in {"id", "args"}
        }
        value = (kind, tuple(sorted(payload.items())), tuple(
            _canonical(nodes, int(child), memo) for child in row.get("args", [])
        ))
    memo[node_id] = value
    return value


def _chash(nodes: dict[int, dict], node_id: int) -> str:
    return _jhash(_canonical(nodes, node_id))


def _sample_candidates(nodes: dict[int, dict], resource: str, channel: str) -> list[int]:
    return sorted(
        node_id for node_id, row in nodes.items()
        if row.get("kind") == "textureSample"
        and str(row.get("resource") or "") == resource
        and str(row.get("channel") or "") == channel
    )


def _literal_candidates(nodes: dict[int, dict], bits: str) -> list[int]:
    bits = bits.lower()
    return sorted(
        node_id for node_id, row in nodes.items()
        if row.get("kind") == "literal32"
        and str(row.get("bits") or "").lower() == bits
    )


def _neg_equiv(nodes: dict[int, dict], candidate: int, target: int) -> bool:
    row = nodes[candidate]
    if row.get("kind") == "op" and row.get("op") == "neg" and len(row.get("args", [])) == 1:
        return _chash(nodes, int(row["args"][0])) == _chash(nodes, target)
    # Some symbolic paths can materialize -x as x * -1.
    if row.get("kind") == "op" and row.get("op") == "mul" and len(row.get("args", [])) == 2:
        for a, b in (row["args"], row["args"][::-1]):
            a = int(a); b = int(b)
            br = nodes[b]
            if (
                _chash(nodes, a) == _chash(nodes, target)
                and br.get("kind") == "literal32"
                and str(br.get("bits") or "").lower() == "bf800000"
            ):
                return True
    return False


def _difference(nodes: dict[int, dict], node_id: int, layer: int, prev: int) -> bool:
    row = nodes[node_id]
    if row.get("kind") != "op" or row.get("op") != "add" or len(row.get("args", [])) != 2:
        return False
    for a, b in (row["args"], row["args"][::-1]):
        a = int(a); b = int(b)
        if _chash(nodes, a) == _chash(nodes, layer) and _neg_equiv(nodes, b, prev):
            return True
    return False


def _blend_candidates(
    nodes: dict[int, dict],
    prev: int,
    layer: int,
    ancestors_of_output: set[int],
) -> list[tuple[int, int]]:
    """Return (stateRoot,factorNode) exact recurrence candidates."""
    out = []
    prev_hash = _chash(nodes, prev)
    for root, row in nodes.items():
        if root not in ancestors_of_output:
            continue
        if row.get("kind") != "op" or row.get("op") != "add" or len(row.get("args", [])) != 2:
            continue
        for base, term in (row["args"], row["args"][::-1]):
            base = int(base); term = int(term)
            if _chash(nodes, base) != prev_hash:
                continue
            tr = nodes[term]
            if tr.get("kind") != "op" or tr.get("op") != "mul" or len(tr.get("args", [])) != 2:
                continue
            for diff, factor in (tr["args"], tr["args"][::-1]):
                diff = int(diff); factor = int(factor)
                if _difference(nodes, diff, layer, prev):
                    out.append((root, factor))
    return sorted(set(out))


def _threshold_candidates(
    nodes: dict[int, dict],
    prev: int,
    layer: int,
    ancestors_of_output: set[int],
) -> list[tuple[int, int]]:
    out = []
    hp = _chash(nodes, prev); hl = _chash(nodes, layer)
    for root, row in nodes.items():
        if root not in ancestors_of_output:
            continue
        if row.get("kind") != "op" or row.get("op") != "select" or len(row.get("args", [])) != 3:
            continue
        cond, yes, no = map(int, row["args"])
        if _chash(nodes, yes) == hl and _chash(nodes, no) == hp:
            out.append((root, cond))
    return sorted(set(out))


def _choose_shared(
    nodes: dict[int, dict],
    per_channel: dict[str, list[tuple[int, int]]],
    *,
    material: str,
    layer: int,
    operator: str,
) -> tuple[dict[str, int], int]:
    if any(not per_channel.get(ch) for ch in CHANNELS):
        missing = [ch for ch in CHANNELS if not per_channel.get(ch)]
        raise SpecularFinalOutputAnchorError(
            f"{material!r} layer {layer}: no {operator} recurrence candidate for channels {missing}"
        )
    common = None
    by_channel_hash: dict[str, dict[str, list[tuple[int, int]]]] = {}
    for ch in CHANNELS:
        groups: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for root, factor in per_channel[ch]:
            groups[_chash(nodes, factor)].append((root, factor))
        by_channel_hash[ch] = groups
        keys = set(groups)
        common = keys if common is None else common & keys
    if not common or len(common) != 1:
        raise SpecularFinalOutputAnchorError(
            f"{material!r} layer {layer}: shared {operator} factor/condition hash count "
            f"{0 if common is None else len(common)}"
        )
    shared_hash = next(iter(common))
    roots = {}
    factor_nodes = set()
    for ch in CHANNELS:
        rows = by_channel_hash[ch][shared_hash]
        root_hashes = defaultdict(list)
        for root, factor in rows:
            root_hashes[_chash(nodes, root)].append((root, factor))
        if len(root_hashes) != 1:
            raise SpecularFinalOutputAnchorError(
                f"{material!r} layer {layer} channel {ch}: ambiguous recurrence roots"
            )
        chosen = sorted(next(iter(root_hashes.values())))[0]
        roots[ch] = chosen[0]
        factor_nodes.add(chosen[1])
    # Nodes may be distinct IDs but must be the same canonical expression.
    if len({_chash(nodes, node) for node in factor_nodes}) != 1:
        raise SpecularFinalOutputAnchorError(
            f"{material!r} layer {layer}: factor IDs disagree semantically"
        )
    return roots, min(factor_nodes)


def _baseline_roots(nodes: dict[int, dict], attachment: dict, material: str) -> dict[str, int]:
    baseline = attachment.get("baseline")
    if not isinstance(baseline, dict):
        raise SpecularFinalOutputAnchorError(f"{material!r}: specular attachment has no baseline")
    mode = str(baseline.get("mode") or "")
    roots = {}
    if mode == "explicit_specular":
        for ch in CHANNELS:
            rows = _sample_candidates(nodes, "specularMapSampler", ch)
            if len(rows) != 1:
                raise SpecularFinalOutputAnchorError(
                    f"{material!r}: explicit base specular {ch} sample count {len(rows)}"
                )
            roots[ch] = rows[0]
        return roots
    if mode != "retail_fallback":
        raise SpecularFinalOutputAnchorError(f"{material!r}: unsupported baseline mode {mode!r}")
    for ch in "xyz":
        rows = _literal_candidates(nodes, F02_BITS)
        if not rows:
            raise SpecularFinalOutputAnchorError(f"{material!r}: no float32 0.2 literal for fallback")
        # Literal nodes are canonical/interchangeable; lowest stable ID is enough.
        roots[ch] = rows[0]
    alpha_mode = str(baseline.get("alphaMode") or "")
    if alpha_mode == "baseColorAlpha":
        rows = _sample_candidates(nodes, "colorMapSampler", "w")
        if len(rows) != 1:
            raise SpecularFinalOutputAnchorError(
                f"{material!r}: base-color-alpha fallback sample count {len(rows)}"
            )
        roots["w"] = rows[0]
    elif alpha_mode == "constantZero":
        rows = _literal_candidates(nodes, ZERO_BITS)
        if not rows:
            raise SpecularFinalOutputAnchorError(f"{material!r}: no float32 zero literal for fallback alpha")
        roots["w"] = rows[0]
    else:
        raise SpecularFinalOutputAnchorError(
            f"{material!r}: unsupported fallback alpha mode {alpha_mode!r}"
        )
    return roots


def _layer_samples(nodes: dict[int, dict], layer: int, material: str) -> dict[str, int]:
    resource = f"specularMapSampler{layer}"
    out = {}
    for ch in CHANNELS:
        rows = _sample_candidates(nodes, resource, ch)
        if len(rows) != 1:
            raise SpecularFinalOutputAnchorError(
                f"{material!r} layer {layer}: {resource}.{ch} sample count {len(rows)}"
            )
        out[ch] = rows[0]
    return out


def _material_rows(recipe_manifest: dict) -> dict[str, dict]:
    canonical = validate_manifest(recipe_manifest)
    return {str(name): row for name, row in canonical.items()}


def build(recipe_manifest: dict, final_output: dict, *, strict_downstream_use: bool = True) -> dict:
    if final_output.get("format") != FINAL_FORMAT:
        raise SpecularFinalOutputAnchorError(
            f"unexpected final-output format {final_output.get('format')!r}"
        )
    recipes = _material_rows(recipe_manifest)
    shaders = {str(row.get("sha256") or ""): row for row in final_output.get("shaders", [])}
    if len(shaders) != len(final_output.get("shaders", [])):
        raise SpecularFinalOutputAnchorError("duplicate shader SHA in final-output manifest")

    rows = []
    step_count = downstream_materials = 0
    factor_hashes: set[str] = set()
    for material, recipe in sorted(recipes.items()):
        attachment = recipe.get(SPEC_KEY)
        if not isinstance(attachment, dict):
            continue
        archetype = str(recipe.get("pixelShaderArchetype") or "")
        if not archetype.startswith("sha256:"):
            raise SpecularFinalOutputAnchorError(f"{material!r}: invalid shader archetype {archetype!r}")
        shader_sha = archetype.split(":", 1)[1]
        shader = shaders.get(shader_sha)
        if shader is None:
            raise SpecularFinalOutputAnchorError(
                f"{material!r}: final-output sidecar lacks shader {shader_sha}"
            )
        if str(attachment.get("pixelShaderArchetype") or "") != archetype:
            raise SpecularFinalOutputAnchorError(
                f"{material!r}: v21 specular attachment shader identity mismatch"
            )
        nodes = _node_map(shader)
        output_roots = _output_roots(shader)
        output_ancestor_union: set[int] = set()
        per_output_ancestors = {}
        for ch, root in output_roots.items():
            anc = _ancestors(nodes, root)
            per_output_ancestors[ch] = anc
            output_ancestor_union.update(anc)

        state = _baseline_roots(nodes, attachment, material)
        steps_out = []
        for step in attachment.get("steps", []):
            layer = int(step.get("layerIndex", -1))
            operator = str(step.get("operator") or "")
            layer_state = _layer_samples(nodes, layer, material)
            candidates = {}
            for ch in CHANNELS:
                if operator == "b":
                    candidates[ch] = _blend_candidates(
                        nodes, state[ch], layer_state[ch], output_ancestor_union
                    )
                elif operator == "t":
                    candidates[ch] = _threshold_candidates(
                        nodes, state[ch], layer_state[ch], output_ancestor_union
                    )
                else:
                    raise SpecularFinalOutputAnchorError(
                        f"{material!r} layer {layer}: unsupported operator {operator!r}"
                    )
            state, factor = _choose_shared(
                nodes, candidates, material=material, layer=layer, operator=operator
            )
            factor_hash = _chash(nodes, factor)
            factor_hashes.add(factor_hash)
            steps_out.append({
                "layerIndex": layer,
                "operator": operator,
                "stateNodes": dict(state),
                "stateSha256": {ch: _chash(nodes, state[ch]) for ch in CHANNELS},
                "sharedFactorNode": factor,
                "sharedFactorSha256": factor_hash,
                "factorBindingKind": step.get("factorBinding", {}).get("kind"),
            })
            step_count += 1

        downstream = {}
        for ch in CHANNELS:
            uses = sorted(out_ch for out_ch, anc in per_output_ancestors.items() if state[ch] in anc)
            downstream[ch] = uses
        used = any(downstream[ch] for ch in CHANNELS)
        if strict_downstream_use and not used:
            raise SpecularFinalOutputAnchorError(
                f"{material!r}: completed specular XYZW state has no exact o0 ancestry"
            )
        if used:
            downstream_materials += 1
        rows.append({
            "material": material,
            "techniqueSet": recipe.get("techniqueSet"),
            "shaderSha256": shader_sha,
            "baseline": attachment.get("baseline"),
            "steps": steps_out,
            "finalStateNodes": dict(state),
            "finalStateSha256": {ch: _chash(nodes, state[ch]) for ch in CHANNELS},
            "downstreamOutputLanes": downstream,
            "downstreamUsed": used,
        })

    summary = {
        "specularMaterialCount": len(rows),
        "specularStepCount": step_count,
        "downstreamUsedMaterialCount": downstream_materials,
        "uniqueSharedFactorDagCount": len(factor_hashes),
        "allCompletedStatesDownstreamUsed": downstream_materials == len(rows),
        "strictDownstreamUse": bool(strict_downstream_use),
    }
    result = {
        "format": FORMAT,
        "sourceFinalOutputFormat": FINAL_FORMAT,
        "sourceSpecularRecipeKey": SPEC_KEY,
        "materials": rows,
        "summary": summary,
        "proofBoundary": (
            "Exact canonical v21 specular baseline/layer/operator ownership matched directly in the complete "
            "slot-4 symbolic o0 DAG. All four XYZW recurrence channels must share one exact factor/condition "
            "per layer, and completed state ancestry to o0 is reported. No physical interpretation of XYZW "
            "or final lighting meaning is assigned."
        ),
    }
    result["rowsSha256"] = _jhash(rows)
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--recipes", type=Path, required=True)
    p.add_argument("--final-output", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--allow-unconsumed", action="store_true")
    a = p.parse_args()
    doc = build(
        json.loads(a.recipes.read_text(encoding="utf-8")),
        json.loads(a.final_output.read_text(encoding="utf-8")),
        strict_downstream_use=not a.allow_unconsumed,
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
