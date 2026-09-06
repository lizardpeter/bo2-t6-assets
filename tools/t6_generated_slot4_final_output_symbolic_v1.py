#!/usr/bin/env python3
"""Exact generated-world slot-4 pixel-shader final-output symbolic DAG v1.

This is a forensic bridge between the already source-closed generated material
subgraphs (diffuse, normal, specular, directional lightmap, reflection pieces)
and the still-unpromoted final T6 output equation.

Inputs:
- canonical ``t6-generated-world-shader-recipe-manifest-v1``;
- exact OAT TechniqueSet/Technique/shader_bin dump tree.

For every exact slot-4 pixel shader used by the recipe manifest this tool:
- resolves TechniqueSet -> technique -> pixelShader -> verbatim CSO by OAT
  asset identity (never by material-name inference);
- parses RDEF and maps texture/sampler register bind points to exact reflected
  resource names;
- symbolically executes supported SM4 instructions, including structured
  IF/ELSE/ENDIF state merges;
- keeps *all* output-register writes instead of filtering for one known
  lightmap dependency;
- serializes every o0.xyzw lane explicitly, including unwritten lanes;
- preserves full expression DAGs and exact per-output sampled-resource ancestry.

This tool deliberately does NOT name the final equation physically.  A later
proof may match already-proven subgraphs into these output DAGs.  Unsupported
instructions, unresolved RDEF register identities, malformed control flow,
read-before-write, or other ambiguity fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import t6_dxbc_inspect_v1 as dxbc
import t6_generated_shader_recipe_contract_v1 as recipe_contract
import t6_oat_slot_shader_resolver_v1 as slot_resolver
import t6_retail_special_shdr_opcode_census_v1 as opcode
import t6_retail_special_shdr_operand_census_v1 as operand
import t6_retail_special_shdr_symbolic_v1 as straight

FORMAT = "t6-generated-slot4-final-output-symbolic-v1"
SLOT_INDEX = 4
COMP = "xyzw"
NUKETOWN = "mp_nuketown_2020"


class GeneratedFinalOutputSymbolicError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


class Dag:
    def __init__(self) -> None:
        self.nodes: list[dict] = []
        self.by: dict[str, int] = {}
        self._resource_cache: dict[int, frozenset[str]] = {}

    def add(self, kind: str, **kwargs) -> int:
        record = {"kind": kind, **kwargs}
        key = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        existing = self.by.get(key)
        if existing is not None:
            return existing
        node_id = len(self.nodes)
        self.by[key] = node_id
        self.nodes.append({"id": node_id, **record})
        return node_id

    def resources(self, node_id: int) -> set[str]:
        cached = self._resource_cache.get(node_id)
        if cached is not None:
            return set(cached)
        node = self.nodes[node_id]
        out: set[str] = set()
        if node.get("kind") == "textureSample":
            out.add(str(node["resource"]))
        for child in node.get("args", []):
            out.update(self.resources(int(child)))
        self._resource_cache[node_id] = frozenset(out)
        return out


def _if_mode(token: int) -> str:
    return "nonzero" if ((token >> 18) & 1) else "zero"


def _test_node(dag: Dag, node: int, mode: str) -> int:
    return dag.add("op", op=f"test_{mode}", args=[node])


def _bool_not(dag: Dag, node: int) -> int:
    return dag.add("op", op="not_bool", args=[node])


def _bool_and(dag: Dag, a: int, b: int) -> int:
    return dag.add("op", op="and_bool", args=[a, b])


def _path_node(dag: Dag, stack: list[dict]) -> int | None:
    result = None
    for frame in stack:
        cond = frame["cond"] if frame["inThen"] else _bool_not(dag, frame["cond"])
        result = cond if result is None else _bool_and(dag, result, cond)
    return result


def _merge_state(dag: Dag, cond: int, then_state: dict, else_state: dict) -> dict:
    out = {}
    for key in sorted(set(then_state) | set(else_state), key=str):
        a = then_state.get(key)
        b = else_state.get(key)
        if a is None:
            a = dag.add("undefined", name=f"branch-missing:{key}")
        if b is None:
            b = dag.add("undefined", name=f"branch-missing:{key}")
        out[key] = a if a == b else dag.add("op", op="select", args=[cond, a, b])
    return out


def _resource_maps(blob: bytes) -> tuple[dict[int, str], dict[int, str], dict]:
    inspected = dxbc.inspect_dxbc(blob)
    if inspected.get("program", {}).get("programType") != "pixel":
        raise GeneratedFinalOutputSymbolicError("slot-4 payload is not a pixel shader")
    textures: dict[int, str] = {}
    samplers: dict[int, str] = {}
    for row in inspected["reflection"]["boundResources"]:
        typ = str(row.get("inputType") or "")
        bind = int(row["bindPoint"])
        count = int(row.get("bindCount", 1))
        name = str(row.get("name") or "")
        if count != 1:
            # T6 generated slot-4 shaders are expected to expose individual
            # named bindings. Refuse to invent array-element names.
            if typ in ("TEXTURE", "SAMPLER"):
                raise GeneratedFinalOutputSymbolicError(
                    f"RDEF {typ} {name!r} has bindCount={count}; array binding unsupported"
                )
            continue
        target = textures if typ == "TEXTURE" else samplers if typ == "SAMPLER" else None
        if target is None:
            continue
        if bind in target and target[bind] != name:
            raise GeneratedFinalOutputSymbolicError(
                f"RDEF bind point {bind} aliases {target[bind]!r} and {name!r}"
            )
        target[bind] = name
    return textures, samplers, inspected


def _named_sample_nodes(
    O: list[dict],
    lanes: list[int],
    state: dict,
    dag: Dag,
    blockers: list[dict],
    at: int,
    op: str,
    textures: dict[int, str],
    samplers: dict[int, str],
) -> tuple[list[int], dict]:
    coords = straight.source_nodes(O[1], list(range(4)), state, dag, blockers, at)
    resource_register = straight.idx(O[2])
    sampler_register = straight.idx(O[3])
    if resource_register is None or resource_register not in textures:
        raise GeneratedFinalOutputSymbolicError(
            f"sample at DWORD {at}: texture register {resource_register!r} absent from RDEF"
        )
    if sampler_register is None or sampler_register not in samplers:
        raise GeneratedFinalOutputSymbolicError(
            f"sample at DWORD {at}: sampler register {sampler_register!r} absent from RDEF"
        )
    extra: list[int] = []
    for source in O[4:]:
        extra.extend(straight.source_nodes(source, [0], state, dag, blockers, at))
    args = coords + extra
    channels = straight.source_components(O[2], lanes)
    if any(channel is None for channel in channels):
        raise GeneratedFinalOutputSymbolicError(
            f"sample at DWORD {at}: unresolved resource channel selection"
        )
    resource = textures[resource_register]
    sampler = samplers[sampler_register]
    values = [
        dag.add(
            "textureSample",
            resource=resource,
            channel=COMP[int(channel)],
            textureRegister=resource_register,
            sampler=sampler,
            samplerRegister=sampler_register,
            opcode=op,
            instructionDword=at,
            args=args,
        )
        for channel in channels
    ]
    return values, {
        "atDword": at,
        "opcode": op,
        "resource": resource,
        "textureRegister": resource_register,
        "sampler": sampler,
        "samplerRegister": sampler_register,
        "channels": [COMP[int(channel)] for channel in channels],
        "coordinateNodes": coords,
        "extraOperandNodes": extra,
    }


def symbolic(blob: bytes) -> dict:
    textures, samplers, inspected = _resource_maps(blob)
    payload = opcode.shdr_payload(blob)
    words = struct.unpack("<%dI" % (len(payload) // 4), payload)
    if len(words) < 2 or int(words[1]) != len(words):
        raise GeneratedFinalOutputSymbolicError("SHDR/SHEX declared DWORD length mismatch")

    i = 2
    state: dict = {}
    dag = Dag()
    blockers: list[dict] = []
    samples: list[dict] = []
    stack: list[dict] = []
    branches: list[dict] = []
    discards: list[dict] = []
    unsupported: list[dict] = []
    max_depth = 0
    else_count = 0

    unary = {"sqrt", "rsq", "exp", "log", "frc", "round_ni", "round_ne", "round_pi", "round_z", "rcp"}
    binary = {"add", "mul", "div", "min", "max", "lt", "ge", "eq", "ne", "and", "or"}

    while i < int(words[1]):
        parsed = operand.parse_instruction(words, i, opcode.OPCODES)
        op = parsed["opcode"]
        O = parsed["operands"]
        saturated = bool(words[i] & 0x2000)
        length = int(parsed["lengthDwords"])
        if length <= 0:
            raise GeneratedFinalOutputSymbolicError(f"instruction at DWORD {i} has nonpositive length")

        if op.startswith("dcl_") or op == "ret":
            i += length
            continue
        if op == "if":
            source = straight.source_nodes(O[0], [0], state, dag, blockers, i)[0]
            mode = _if_mode(words[i])
            cond = _test_node(dag, source, mode)
            stack.append({
                "entry": dict(state),
                "cond": cond,
                "then": None,
                "inThen": True,
                "atDword": i,
            })
            branches.append({"atDword": i, "mode": mode, "conditionNode": cond, "depth": len(stack)})
            max_depth = max(max_depth, len(stack))
            i += length
            continue
        if op == "else":
            if not stack or not stack[-1]["inThen"]:
                raise GeneratedFinalOutputSymbolicError(f"unmatched ELSE at DWORD {i}")
            frame = stack[-1]
            frame["then"] = dict(state)
            frame["inThen"] = False
            state = dict(frame["entry"])
            else_count += 1
            i += length
            continue
        if op == "endif":
            if not stack:
                raise GeneratedFinalOutputSymbolicError(f"unmatched ENDIF at DWORD {i}")
            frame = stack.pop()
            if frame["inThen"]:
                then_state = dict(state)
                else_state = dict(frame["entry"])
            else:
                then_state = frame["then"]
                else_state = dict(state)
            state = _merge_state(dag, frame["cond"], then_state, else_state)
            i += length
            continue
        if op == "discard":
            source = straight.source_nodes(O[0], [0], state, dag, blockers, i)[0]
            mode = _if_mode(words[i])
            cond = _test_node(dag, source, mode)
            path = _path_node(dag, stack)
            discards.append({
                "atDword": i,
                "mode": mode,
                "conditionNode": cond,
                "pathNode": path,
                "resources": sorted(dag.resources(cond) | (dag.resources(path) if path is not None else set())),
            })
            i += length
            continue
        if op == "sincos":
            if len(O) < 3:
                raise GeneratedFinalOutputSymbolicError(f"malformed SINCOS at DWORD {i}")
            for dest, which in zip(O[:2], ("sin", "cos")):
                lanes = straight.dest_lanes(dest)
                values = straight.op1(
                    dag,
                    which,
                    straight.source_nodes(O[2], lanes, state, dag, blockers, i),
                )
                register = straight.idx(dest)
                for lane, value in zip(lanes, values):
                    state[(dest["type"], register, lane)] = value
            i += length
            continue

        if not O:
            unsupported.append({"atDword": i, "opcode": op, "reason": "no operands"})
            i += length
            continue
        dest = O[0]
        lanes = straight.dest_lanes(dest)
        register = straight.idx(dest)
        width = len(lanes)
        values = None

        if op.startswith("sample"):
            values, sample = _named_sample_nodes(
                O, lanes, state, dag, blockers, i, op, textures, samplers
            )
            sample["branchDepth"] = len(stack)
            samples.append(sample)
        elif op in ("dp2", "dp3", "dp4"):
            dot_width = int(op[-1])
            a = straight.source_nodes(O[1], list(range(dot_width)), state, dag, blockers, i)
            b = straight.source_nodes(O[2], list(range(dot_width)), state, dag, blockers, i)
            products = [dag.add("op", op="mul", args=[x, y]) for x, y in zip(a, b)]
            value = products[0]
            for product in products[1:]:
                value = dag.add("op", op="add", args=[value, product])
            values = [value] * width
        else:
            sources = [
                straight.source_nodes(source, lanes, state, dag, blockers, i)
                for source in O[1:]
            ]
            if op == "mov":
                values = sources[0]
            elif op in binary:
                values = straight.op2(dag, op, sources[0], sources[1])
            elif op == "mad":
                values = [
                    dag.add("op", op="add", args=[dag.add("op", op="mul", args=[a, b]), c])
                    for a, b, c in zip(*sources)
                ]
            elif op in unary:
                values = straight.op1(dag, op, sources[0])
            elif op == "movc":
                values = [
                    dag.add("op", op="select", args=[cond, a, b])
                    for cond, a, b in zip(*sources)
                ]
            else:
                unsupported.append({"atDword": i, "opcode": op, "operandCount": len(O)})

        if values is not None:
            if saturated:
                values = [dag.add("op", op="saturate", args=[value]) for value in values]
            for lane, value in zip(lanes, values):
                state[(dest["type"], register, lane)] = value
        i += length

    if stack:
        raise GeneratedFinalOutputSymbolicError("unterminated IF stack")
    if blockers:
        raise GeneratedFinalOutputSymbolicError(
            f"symbolic read/dataflow blockers: {blockers[:4]}"
        )
    if unsupported:
        raise GeneratedFinalOutputSymbolicError(
            f"unsupported SM4 instructions: {unsupported[:8]}"
        )

    outputs = []
    for register in sorted({int(key[1]) for key in state if key[0] == "output" and key[1] is not None}):
        lanes = []
        for lane in range(4):
            node = state.get(("output", register, lane))
            lanes.append({
                "channel": COMP[lane],
                "written": node is not None,
                "node": node,
                "resources": [] if node is None else sorted(dag.resources(int(node))),
            })
        outputs.append({"register": register, "lanes": lanes})

    o0 = next((row for row in outputs if row["register"] == 0), None)
    if o0 is None:
        raise GeneratedFinalOutputSymbolicError("pixel shader has no o0 writes")
    if not all(row["written"] for row in o0["lanes"][:3]):
        raise GeneratedFinalOutputSymbolicError("pixel shader does not write complete o0.rgb")

    compact = {
        "nodes": dag.nodes,
        "outputs": outputs,
        "samples": samples,
        "branches": branches,
        "discards": discards,
    }
    return {
        "nodes": dag.nodes,
        "outputs": outputs,
        "samples": samples,
        "branches": branches,
        "elseCount": else_count,
        "maxBranchDepth": max_depth,
        "discards": discards,
        "textureBindings": [{"register": k, "name": v} for k, v in sorted(textures.items())],
        "samplerBindings": [{"register": k, "name": v} for k, v in sorted(samplers.items())],
        "dagSha256": _jhash(compact),
        "rdefResourceTableSha256": _jhash(inspected["reflection"]["boundResources"]),
        "shaderModel": inspected["program"]["shaderModel"],
    }


def build(recipe_manifest: dict, *, oat_root: Path, strict_nuketown: bool = False) -> dict:
    try:
        recipes = recipe_contract.validate_manifest(recipe_manifest)
    except Exception as exc:
        raise GeneratedFinalOutputSymbolicError(f"invalid canonical recipe manifest: {exc}") from exc
    if not recipes:
        raise GeneratedFinalOutputSymbolicError("canonical recipe manifest contains no materials")

    technique_cache: dict[str, dict] = {}
    shader_rows: dict[str, dict] = {}
    materials = []

    for material, recipe in sorted(recipes.items()):
        technique = str(recipe["techniqueSet"])
        resolved = technique_cache.get(technique)
        if resolved is None:
            resolved = slot_resolver.resolve_slot_shader(
                oat_root,
                technique,
                slot_index=SLOT_INDEX,
                require_single_pixel_shader=True,
            )
            technique_cache[technique] = resolved
        ps = resolved["pixelShaders"][0]
        path = Path(oat_root) / ps["relativeFile"]
        blob = path.read_bytes()
        actual_sha = hashlib.sha256(blob).hexdigest()
        if actual_sha != ps["sha256"]:
            raise GeneratedFinalOutputSymbolicError(
                f"{technique!r}: exact OAT pixel-shader SHA changed during read"
            )
        expected = str(recipe.get("pixelShaderArchetype") or "")
        # Recovery manifests use exact SHA-256 as archetype when source-closed.
        # If an older caller carries a non-SHA label, preserve it but do not
        # pretend it is byte identity.
        if len(expected) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in expected):
            if expected.lower() != actual_sha:
                raise GeneratedFinalOutputSymbolicError(
                    f"{material!r}: canonical pixelShaderArchetype {expected} != exact OAT SHA {actual_sha}"
                )

        row = shader_rows.get(actual_sha)
        if row is None:
            sym = symbolic(blob)
            row = {
                "sha256": actual_sha,
                "asset": ps["asset"],
                "bytes": int(ps["bytes"]),
                "relativeFile": ps["relativeFile"],
                "techniqueSets": [],
                **sym,
            }
            shader_rows[actual_sha] = row
        if technique not in row["techniqueSets"]:
            row["techniqueSets"].append(technique)
        materials.append({
            "material": material,
            "techniqueSet": technique,
            "pixelShaderSha256": actual_sha,
            "pixelShaderAsset": ps["asset"],
        })

    rows = []
    for sha, row in sorted(shader_rows.items()):
        row["techniqueSets"] = sorted(row["techniqueSets"])
        rows.append(row)

    if strict_nuketown:
        if len(materials) != 120:
            raise GeneratedFinalOutputSymbolicError(
                f"Nuketown strict material count {len(materials)} != 120"
            )
        if len(rows) != 34:
            raise GeneratedFinalOutputSymbolicError(
                f"Nuketown strict unique slot-4 shader count {len(rows)} != 34"
            )

    o0_alpha_written = sum(
        1 for row in rows
        if next(out for out in row["outputs"] if out["register"] == 0)["lanes"][3]["written"]
    )
    sample_resource_counts: dict[str, int] = {}
    for row in rows:
        for sample in row["samples"]:
            key = str(sample["resource"])
            sample_resource_counts[key] = sample_resource_counts.get(key, 0) + 1

    return {
        "format": FORMAT,
        "slotIndex": SLOT_INDEX,
        "slotLabel": slot_resolver.TECHNIQUE_TYPE_NAMES[SLOT_INDEX],
        "materials": materials,
        "shaders": rows,
        "summary": {
            "materialCount": len(materials),
            "techniqueSetCount": len(technique_cache),
            "uniquePixelShaderCount": len(rows),
            "o0RgbCompleteShaderCount": len(rows),
            "o0AlphaWrittenShaderCount": o0_alpha_written,
            "sampleCount": sum(len(row["samples"]) for row in rows),
            "branchCount": sum(len(row["branches"]) for row in rows),
            "discardCount": sum(len(row["discards"]) for row in rows),
            "sampleResourceCounts": dict(sorted(sample_resource_counts.items())),
            "materialRowsSha256": _jhash(materials),
            "shaderIdentityRowsSha256": _jhash([
                {
                    "sha256": row["sha256"],
                    "asset": row["asset"],
                    "bytes": row["bytes"],
                    "techniqueSets": row["techniqueSets"],
                    "dagSha256": row["dagSha256"],
                    "rdefResourceTableSha256": row["rdefResourceTableSha256"],
                }
                for row in rows
            ]),
            "dagSetSha256": _jhash(sorted(row["dagSha256"] for row in rows)),
            "strictNuketown": bool(strict_nuketown),
        },
        "proofBoundary": (
            "Exact OAT slot-4 PS byte identity + strict DXBC/RDEF register naming + supported SM4 assembly-level "
            "symbolic execution through all written outputs. This is a final-output expression graph, not a physical "
            "lighting interpretation. Subgraph-to-T6-semantic matching and final material/lightmap/specular/reflection "
            "equation promotion remain separate proofs."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", type=Path, required=True)
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--strict-nuketown", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.recipes.read_text(encoding="utf-8"))
    result = build(manifest, oat_root=args.oat_root, strict_nuketown=args.strict_nuketown)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
