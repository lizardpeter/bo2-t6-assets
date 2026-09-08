#!/usr/bin/env python3
"""Compile exact Nuketown non-lightmapped special PS payloads to complete SM4 output DAGs.

Unlike t6_retail_special_shdr_symbolic_v1, this tool does not filter output
components by lightmap dependency.  It is deliberately scoped to exact native
OAT-selected `unlit` / `emissive` Technique groups from the sealed Nuketown
special census and retains every written pixel-shader output component.

Control flow, discard and unsupported dataflow fail closed.  Shader bytes are
read from the exact technique owner recorded by the complete native census and
must match the stage SHA-256 before parsing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
from typing import Any

COMP = "xyzw"
FORMAT = "t6-nuketown-special-full-output-symbolic-v1"
TARGET_TYPES = ("unlit", "emissive")
EXPECTED_UNIQUE_PIXEL_SHADERS = 5


class FullOutputError(RuntimeError):
    pass


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def symbolic_full(shader: dict[str, Any], operand, opcode, base):
    payload = opcode.shdr_payload(shader["data"])
    dwords = struct.unpack("<%dI" % (len(payload) // 4), payload)
    i = 2
    state = {}
    dag = base.Dag()
    blockers = []
    samples = []
    side_effects = []
    has_control_flow = False

    while i < dwords[1]:
        row = operand.parse_instruction(dwords, i, opcode.OPCODES)
        op = row["opcode"]
        operands = row["operands"]
        sat = bool(dwords[i] & 0x2000)

        if op.startswith("dcl_") or op == "ret":
            i += row["lengthDwords"]
            continue
        if op in ("if", "else", "endif"):
            has_control_flow = True
            i += row["lengthDwords"]
            continue
        if op == "discard":
            cond = base.source_nodes(operands[0], [0], state, dag, blockers, i)
            side_effects.append({"op": "discard", "atDword": i, "conditionNodes": cond})
            i += row["lengthDwords"]
            continue
        if op == "sincos":
            for dest, which in zip(operands[:2], ("sin", "cos")):
                lanes = base.dest_lanes(dest)
                vals = base.op1(
                    dag,
                    which,
                    base.source_nodes(operands[2], lanes, state, dag, blockers, i),
                )
                reg = base.idx(dest)
                for lane, val in zip(lanes, vals):
                    state[(dest["type"], reg, lane)] = val
            i += row["lengthDwords"]
            continue

        dest = operands[0]
        lanes = base.dest_lanes(dest)
        reg = base.idx(dest)
        lane_count = len(lanes)
        vals = None

        if op.startswith("sample"):
            coords = base.source_nodes(operands[1], list(range(4)), state, dag, blockers, i)
            resource = base.idx(operands[2])
            sampler = base.idx(operands[3])
            extra = []
            for q in operands[4:]:
                extra.extend(base.source_nodes(q, [0], state, dag, blockers, i))
            args = coords + extra
            channels = base.source_components(operands[2], lanes)
            vals = [
                dag.add(
                    "textureSample",
                    resourceRegister=resource,
                    samplerRegister=sampler,
                    opcode=op,
                    instructionDword=i,
                    channel=COMP[channel],
                    args=args,
                )
                for channel in channels
            ]
            samples.append(
                {
                    "atDword": i,
                    "opcode": op,
                    "resourceRegister": resource,
                    "samplerRegister": sampler,
                    "destLanes": [COMP[x] for x in lanes],
                    "channels": [COMP[x] for x in channels],
                    "argumentNodes": args,
                }
            )
        elif op in ("dp2", "dp3", "dp4"):
            width = int(op[-1])
            a = base.source_nodes(operands[1], list(range(width)), state, dag, blockers, i)
            b = base.source_nodes(operands[2], list(range(width)), state, dag, blockers, i)
            products = [dag.add("op", op="mul", args=[x, y]) for x, y in zip(a, b)]
            value = products[0]
            for q in products[1:]:
                value = dag.add("op", op="add", args=[value, q])
            vals = [value] * lane_count
        else:
            src = [base.source_nodes(q, lanes, state, dag, blockers, i) for q in operands[1:]]
            if op == "mov":
                vals = src[0]
            elif op in ("add", "mul", "div", "min", "max", "lt", "ge", "and", "or"):
                vals = base.op2(dag, op, src[0], src[1])
            elif op == "mad":
                vals = [
                    dag.add("op", op="add", args=[dag.add("op", op="mul", args=[a, b]), c])
                    for a, b, c in zip(*src)
                ]
            elif op in ("sqrt", "rsq", "exp", "log", "frc", "round_ni"):
                vals = base.op1(dag, op, src[0])
            elif op == "movc":
                vals = [dag.add("op", op="select", args=[c, a, b]) for c, a, b in zip(*src)]
            else:
                raise FullOutputError(f"unsupported straight-line opcode {op} at DWORD {i}")

        if sat:
            vals = [dag.add("op", op="saturate", args=[v]) for v in vals]
        for lane, value in zip(lanes, vals):
            state[(dest["type"], reg, lane)] = value
        i += row["lengthDwords"]

    outputs = []
    for (typ, reg, lane), node in sorted(state.items()):
        if typ == "output":
            outputs.append({"output": f"o{reg}.{COMP[lane]}", "node": node})
    return {
        "hasControlFlow": has_control_flow,
        "blockers": blockers,
        "sideEffects": side_effects,
        "samples": samples,
        "outputs": outputs,
        "nodes": dag.nodes,
    }


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise FullOutputError(f"expected object in {path}")
    return obj


def _selected_groups(census: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    group_by_key = {
        str(row.get("groupKey")): row
        for row in census.get("shaderGroups", [])
        if isinstance(row, dict) and row.get("groupKey")
    }
    owners: dict[str, set[str]] = {}
    selected: dict[str, dict[str, Any]] = {}
    for material in census.get("materials", []):
        if not isinstance(material, dict):
            continue
        for program in material.get("programs", []):
            if not isinstance(program, dict) or program.get("techniqueType") not in TARGET_TYPES:
                continue
            key = str(program.get("groupKey") or "")
            if key not in group_by_key:
                raise FullOutputError(f"missing exact shader group {key!r}")
            selected[key] = group_by_key[key]
            owners.setdefault(key, set()).add(str(program.get("techniqueOwner") or ""))
    owner_one = {}
    for key, vals in owners.items():
        vals.discard("")
        if len(vals) != 1:
            raise FullOutputError(f"group {key}: expected one exact technique owner, got {sorted(vals)}")
        owner_one[key] = next(iter(vals))
    if not selected:
        raise FullOutputError("no unlit/emissive groups selected")
    return selected, owner_one


def build(census_path: Path, symbolic_tool: Path, operand_tool: Path, opcode_tool: Path) -> dict[str, Any]:
    census = _load_json(census_path)
    if census.get("format") != "t6-nuketown-special-material-census-v1":
        raise FullOutputError(f"unexpected special census format {census.get('format')!r}")
    if int(census.get("summary", {}).get("pcServerDuplicateParentSelectionDependencyCount", -1)) != 0:
        raise FullOutputError("special population unexpectedly depends on duplicate-parent selection")

    base = load(symbolic_tool, "special_symbolic_base")
    operand = load(operand_tool, "special_operand")
    opcode = load(opcode_tool, "special_opcode")
    groups, owners = _selected_groups(census)

    shader_defs: dict[str, dict[str, Any]] = {}
    group_rows = []
    for key, group in sorted(groups.items()):
        owner = Path(owners[key])
        pass_rows = []
        for pass_row in group.get("passes", []):
            stages = []
            for stage in pass_row.get("stages", []):
                if stage.get("kind") != "pixelShader":
                    continue
                rel = str(stage.get("relativeFile") or "")
                expected = str(stage.get("sha256") or "").lower()
                path = owner / rel
                raw = path.read_bytes()
                actual = hashlib.sha256(raw).hexdigest()
                if actual != expected:
                    raise FullOutputError(f"{path}: SHA-256 {actual} != exact census {expected}")
                prior = shader_defs.get(expected)
                rec = {"data": raw, "asset": stage.get("asset"), "relativeFile": rel, "owner": str(owner)}
                if prior is not None and prior["data"] != raw:
                    raise FullOutputError(f"pixel shader {expected}: byte disagreement across exact groups")
                shader_defs[expected] = prior or rec
                stages.append({"sha256": expected, "asset": stage.get("asset"), "relativeFile": rel})
            pass_rows.append({"index": pass_row.get("index"), "stateMap": pass_row.get("stateMap"), "pixelShaders": stages})
        group_rows.append(
            {
                "groupKey": key,
                "techniqueType": group.get("techniqueType"),
                "techniqueOwner": str(owner),
                "techniqueSets": list(group.get("techniqueSets", [])),
                "techniques": list(group.get("techniques", [])),
                "passes": pass_rows,
            }
        )

    if len(shader_defs) != EXPECTED_UNIQUE_PIXEL_SHADERS:
        raise FullOutputError(
            f"unique unlit/emissive pixel shader count {len(shader_defs)} != {EXPECTED_UNIQUE_PIXEL_SHADERS}"
        )

    shader_rows = []
    total_nodes = total_samples = total_outputs = 0
    for hh, shader in sorted(shader_defs.items()):
        q = symbolic_full(shader, operand, opcode, base)
        if q["hasControlFlow"]:
            raise FullOutputError(f"{hh}: unexpected control flow in exact unlit/emissive shader")
        if q["blockers"]:
            raise FullOutputError(f"{hh}: symbolic blockers {q['blockers'][:4]}")
        if q["sideEffects"]:
            raise FullOutputError(f"{hh}: side effects are not yet modeled: {q['sideEffects'][:4]}")
        if not q["outputs"]:
            raise FullOutputError(f"{hh}: no pixel outputs reconstructed")
        if any(not row["output"].startswith("o0.") for row in q["outputs"]):
            raise FullOutputError(f"{hh}: unexpected non-o0 output {q['outputs']}")
        compact = {"nodes": q["nodes"], "outputs": q["outputs"], "samples": q["samples"]}
        row = {
            "sha256": hh,
            "asset": shader.get("asset"),
            "relativeFile": shader.get("relativeFile"),
            "nodeCount": len(q["nodes"]),
            "sampleCount": len(q["samples"]),
            "outputCount": len(q["outputs"]),
            "outputs": q["outputs"],
            "samples": q["samples"],
            "dagSha256": digest(compact),
            "nodes": q["nodes"],
        }
        shader_rows.append(row)
        total_nodes += row["nodeCount"]
        total_samples += row["sampleCount"]
        total_outputs += row["outputCount"]

    set_sha = digest([(r["sha256"], r["dagSha256"], r["nodeCount"], r["sampleCount"], r["outputCount"]) for r in shader_rows])
    return {
        "format": FORMAT,
        "producer": "tools/t6_nuketown_special_full_output_symbolic_v1.py",
        "map": "mp_nuketown_2020",
        "sourceSpecialCensusSha256": hashlib.sha256(census_path.read_bytes()).hexdigest(),
        "summary": {
            "selectedTechniqueGroupCount": len(group_rows),
            "uniquePixelShaderCount": len(shader_rows),
            "fullOutputSymbolicShaderCount": len(shader_rows),
            "symbolicBlockerCount": 0,
            "controlFlowShaderCount": 0,
            "sideEffectShaderCount": 0,
            "nodeCount": total_nodes,
            "textureSampleCount": total_samples,
            "outputComponentCount": total_outputs,
            "uniqueDagCount": len({r["dagSha256"] for r in shader_rows}),
        },
        "groups": group_rows,
        "shaderRows": shader_rows,
        "dagSetSha256": set_sha,
        "proofBoundary": (
            "Complete o0 dataflow is reconstructed directly from the exact native-OAT-selected SM4 pixel shader bytes for Nuketown unlit/emissive groups. "
            "Every shader file is SHA-256 checked against the native census before parsing. Control flow, discard, read-before-write and unsupported opcodes fail closed. "
            "This proves assembly-level arithmetic/dataflow only; texture/sampler meanings, Material argument ownership and D3D render-state behavior are separate closure layers."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", type=Path, required=True)
    ap.add_argument("--symbolic-tool", type=Path, default=Path("tools/t6_retail_special_shdr_symbolic_v1.py"))
    ap.add_argument("--operand-tool", type=Path, default=Path("tools/t6_retail_special_shdr_operand_census_v1.py"))
    ap.add_argument("--opcode-tool", type=Path, default=Path("tools/t6_retail_special_shdr_opcode_census_v1.py"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    doc = build(a.census, a.symbolic_tool, a.operand_tool, a.opcode_tool)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    print(doc["dagSetSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
