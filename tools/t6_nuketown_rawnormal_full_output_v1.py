#!/usr/bin/env python3
"""Compile every exact Nuketown raw-normal lit pixel shader to a complete SM4 o0 DAG.

The target is deliberately finite: the one native Nuketown Material classified by
the retained special-family census as `rawnormal_special`.  Its exact native OAT
Technique selection supplies 22 lit technique-type entries and 20 unique pixel
shader payloads.

Straight-line payloads reuse the fail-closed full-output compiler. Payloads that
contain SM4 IF use the already-proven branch state model, but this adapter retains
all final pixel outputs instead of filtering to lightmap-dependent outputs.
Unsupported opcodes, read-before-write, unmatched control flow, discard, shader
SHA disagreement, or population drift fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-rawnormal-full-output-v1"
SPECIAL_FORMAT = "t6-nuketown-special-material-census-v1"
TARGET_MATERIAL = "wpc/glass_clear_wall_opaque_white"
TARGET_FAMILY = "rawnormal_special"
EXPECTED_LIT_PROGRAMS = 22
EXPECTED_UNIQUE_PIXEL_SHADERS = 20


class RawNormalError(RuntimeError):
    pass


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def jdigest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RawNormalError(f"expected JSON object in {path}")
    return obj


def shader_has_if(raw: bytes, operand, opcode) -> bool:
    payload = opcode.shdr_payload(raw)
    dwords = struct.unpack("<%dI" % (len(payload) // 4), payload)
    i = 2
    while i < dwords[1]:
        row = operand.parse_instruction(dwords, i, opcode.OPCODES)
        if row["opcode"] == "if":
            return True
        i += row["lengthDwords"]
    if i != dwords[1]:
        raise RawNormalError("instruction walk did not terminate at declared end")
    return False


def branch_full(shader: dict[str, Any], branch, straight, operand, opcode) -> dict[str, Any]:
    payload = opcode.shdr_payload(shader["data"])
    dwords = struct.unpack("<%dI" % (len(payload) // 4), payload)
    i = 2
    state = {}
    dag = branch.CachedDag(straight)
    blockers = []
    stack = []
    discards = []
    ifs = []
    else_count = 0
    max_depth = 0

    while i < dwords[1]:
        row = operand.parse_instruction(dwords, i, opcode.OPCODES)
        op = row["opcode"]
        O = row["operands"]
        sat = bool(dwords[i] & 0x2000)

        if op.startswith("dcl_") or op == "ret":
            i += row["lengthDwords"]
            continue
        if op == "if":
            src = straight.source_nodes(O[0], [0], state, dag, blockers, i)[0]
            mode = branch.if_mode(dwords[i])
            cond = branch.test_node(dag, src, mode)
            deps = sorted(dag.deps(cond))
            stack.append({"entry": dict(state), "cond": cond, "then": None, "inThen": True, "atDword": i})
            max_depth = max(max_depth, len(stack))
            ifs.append({"atDword": i, "mode": mode, "depth": len(stack), "lightmapDependencies": deps})
            i += row["lengthDwords"]
            continue
        if op == "else":
            if not stack or not stack[-1]["inThen"]:
                raise RawNormalError(f"unmatched else at DWORD {i}")
            frame = stack[-1]
            frame["then"] = dict(state)
            frame["inThen"] = False
            state = dict(frame["entry"])
            else_count += 1
            i += row["lengthDwords"]
            continue
        if op == "endif":
            if not stack:
                raise RawNormalError(f"unmatched endif at DWORD {i}")
            frame = stack.pop()
            if frame["inThen"]:
                then_state, else_state = dict(state), dict(frame["entry"])
            else:
                then_state, else_state = frame["then"], dict(state)
            state = branch.merge_state(dag, frame["cond"], then_state, else_state)
            i += row["lengthDwords"]
            continue
        if op == "discard":
            src = straight.source_nodes(O[0], [0], state, dag, blockers, i)[0]
            mode = branch.if_mode(dwords[i])
            cond = branch.test_node(dag, src, mode)
            path = branch.path_node(dag, stack)
            discards.append({"atDword": i, "mode": mode, "conditionNode": cond, "pathNode": path})
            i += row["lengthDwords"]
            continue
        if op == "sincos":
            for dest, which in zip(O[:2], ("sin", "cos")):
                lanes = straight.dest_lanes(dest)
                vals = straight.op1(dag, which, straight.source_nodes(O[2], lanes, state, dag, blockers, i))
                reg = straight.idx(dest)
                for lane, val in zip(lanes, vals):
                    state[(dest["type"], reg, lane)] = val
            i += row["lengthDwords"]
            continue

        dest = O[0]
        lanes = straight.dest_lanes(dest)
        reg = straight.idx(dest)
        n = len(lanes)
        vals = None

        if op.startswith("sample"):
            coords = straight.source_nodes(O[1], list(range(4)), state, dag, blockers, i)
            resource = straight.idx(O[2])
            sampler = straight.idx(O[3])
            extra = []
            for q in O[4:]:
                extra.extend(straight.source_nodes(q, [0], state, dag, blockers, i))
            args = coords + extra
            argdeps = set().union(*(dag.deps(v) for v in args)) if args else set()
            if argdeps:
                blockers.append({
                    "reason": "lightmap-dependent-sample-input",
                    "atDword": i,
                    "resource": resource,
                    "dependencies": sorted(argdeps),
                })
            channels = straight.source_components(O[2], lanes)
            if resource == 13:
                vals = [
                    dag.add(
                        "lightmapSample",
                        role="secondary",
                        channel=straight.COMP[c],
                        textureRegister=13,
                        samplerRegister=sampler,
                        opcode=op,
                        instructionDword=i,
                        args=args,
                    )
                    for c in channels
                ]
            else:
                vals = [
                    dag.add(
                        "textureSample",
                        resourceRegister=resource,
                        samplerRegister=sampler,
                        opcode=op,
                        instructionDword=i,
                        channel=straight.COMP[c],
                        args=args,
                    )
                    for c in channels
                ]
        elif op in ("dp2", "dp3", "dp4"):
            width = int(op[-1])
            a = straight.source_nodes(O[1], list(range(width)), state, dag, blockers, i)
            b = straight.source_nodes(O[2], list(range(width)), state, dag, blockers, i)
            products = [dag.add("op", op="mul", args=[x, y]) for x, y in zip(a, b)]
            value = products[0]
            for q in products[1:]:
                value = dag.add("op", op="add", args=[value, q])
            vals = [value] * n
        else:
            src = [straight.source_nodes(q, lanes, state, dag, blockers, i) for q in O[1:]]
            if op == "mov":
                vals = src[0]
            elif op in ("add", "mul", "div", "min", "max", "lt", "ge", "and", "or"):
                vals = straight.op2(dag, op, src[0], src[1])
            elif op == "mad":
                vals = [
                    dag.add("op", op="add", args=[dag.add("op", op="mul", args=[a, b]), c])
                    for a, b, c in zip(*src)
                ]
            elif op in ("sqrt", "rsq", "exp", "log", "frc", "round_ni"):
                vals = straight.op1(dag, op, src[0])
            elif op == "movc":
                vals = [dag.add("op", op="select", args=[c, a, b]) for c, a, b in zip(*src)]
            else:
                raise RawNormalError(f"unsupported branch-aware opcode {op} at DWORD {i}")

        if sat:
            vals = [dag.add("op", op="saturate", args=[v]) for v in vals]
        for lane, val in zip(lanes, vals):
            state[(dest["type"], reg, lane)] = val
        i += row["lengthDwords"]

    if stack:
        raise RawNormalError("unterminated IF stack")
    outputs = [
        {"output": f"o{reg}.{straight.COMP[lane]}", "node": node}
        for (typ, reg, lane), node in sorted(state.items())
        if typ == "output"
    ]
    return {
        "nodes": dag.nodes,
        "outputs": outputs,
        "ifs": ifs,
        "elseCount": else_count,
        "maxNestingDepth": max_depth,
        "discards": discards,
        "blockers": blockers,
    }


def sample_sites(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sites: dict[tuple[Any, ...], set[str]] = {}
    for node in nodes:
        kind = node.get("kind")
        if kind == "textureSample":
            key = (
                kind,
                node.get("instructionDword"),
                node.get("resourceRegister"),
                node.get("samplerRegister"),
                node.get("opcode"),
            )
            sites.setdefault(key, set()).add(str(node.get("channel")))
        elif kind == "lightmapSample":
            key = (
                kind,
                node.get("instructionDword"),
                node.get("textureRegister"),
                node.get("samplerRegister"),
                node.get("opcode"),
            )
            sites.setdefault(key, set()).add(str(node.get("channel")))
    return [
        {
            "kind": k[0],
            "instructionDword": k[1],
            "resourceRegister": k[2],
            "samplerRegister": k[3],
            "opcode": k[4],
            "channels": sorted(v),
        }
        for k, v in sorted(sites.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][3], kv[0][0]))
    ]


def build(
    special_path: Path,
    straight_tool: Path,
    branch_tool: Path,
    full_tool: Path,
    operand_tool: Path,
    opcode_tool: Path,
) -> dict[str, Any]:
    special = load_json(special_path)
    if special.get("format") != SPECIAL_FORMAT:
        raise RawNormalError(f"unexpected special census format {special.get('format')!r}")
    if int(special.get("summary", {}).get("pcServerDuplicateParentSelectionDependencyCount", -1)) != 0:
        raise RawNormalError("special population unexpectedly depends on duplicate-parent selection")

    material_hits = [m for m in special.get("materials", []) if m.get("material") == TARGET_MATERIAL]
    if len(material_hits) != 1 or material_hits[0].get("family") != TARGET_FAMILY:
        raise RawNormalError(f"raw-normal target Material population changed: {material_hits}")
    material = material_hits[0]
    programs = [p for p in material.get("programs", []) if str(p.get("techniqueType") or "").startswith("lit")]
    if len(programs) != EXPECTED_LIT_PROGRAMS:
        raise RawNormalError(f"lit program count {len(programs)} != {EXPECTED_LIT_PROGRAMS}")

    groups = {str(g["groupKey"]): g for g in special.get("shaderGroups", [])}
    straight = load(straight_tool, "rawnormal_straight")
    branch = load(branch_tool, "rawnormal_branch")
    full = load(full_tool, "rawnormal_full_straight")
    operand = load(operand_tool, "rawnormal_operand")
    opcode = load(opcode_tool, "rawnormal_opcode")

    shader_defs: dict[str, dict[str, Any]] = {}
    program_rows = []
    for program in programs:
        key = str(program.get("groupKey") or "")
        group = groups.get(key)
        if not group:
            raise RawNormalError(f"missing exact group {key}")
        passes = group.get("passes", [])
        if len(passes) != 1:
            raise RawNormalError(f"{program.get('technique')}: pass count {len(passes)}")
        ps = [s for s in passes[0].get("stages", []) if s.get("kind") == "pixelShader"]
        if len(ps) != 1:
            raise RawNormalError(f"{program.get('technique')}: pixel shader stages {len(ps)}")
        stage = ps[0]
        hh = str(stage.get("sha256") or "").lower()
        owner = Path(str(program.get("techniqueOwner") or ""))
        rel = str(stage.get("relativeFile") or "")
        path = owner / rel
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != hh:
            raise RawNormalError(f"{path}: SHA-256 {actual} != census {hh}")
        old = shader_defs.get(hh)
        if old is not None and old["data"] != raw:
            raise RawNormalError(f"shader {hh}: byte disagreement")
        shader_defs.setdefault(
            hh,
            {
                "data": raw,
                "asset": stage.get("asset"),
                "relativeFile": rel,
                "owner": str(owner),
            },
        )
        program_rows.append(
            {
                "techniqueType": program.get("techniqueType"),
                "technique": program.get("technique"),
                "groupKey": key,
                "pixelShaderSha256": hh,
                "materialArguments": [
                    a for a in stage.get("arguments", []) if isinstance(a, dict) and a.get("sourceClass") == "material"
                ],
            }
        )

    if len(shader_defs) != EXPECTED_UNIQUE_PIXEL_SHADERS:
        raise RawNormalError(f"unique pixel shader count {len(shader_defs)} != {EXPECTED_UNIQUE_PIXEL_SHADERS}")

    shader_rows = []
    branch_count = straight_count = node_count = output_count = sample_count = if_count = 0
    for hh, shader in sorted(shader_defs.items()):
        has_if = shader_has_if(shader["data"], operand, opcode)
        if has_if:
            q = branch_full(shader, branch, straight, operand, opcode)
            branch_count += 1
        else:
            q = full.symbolic_full(shader, operand, opcode, straight)
            q.setdefault("ifs", [])
            q.setdefault("elseCount", 0)
            q.setdefault("maxNestingDepth", 0)
            q.setdefault("discards", q.get("sideEffects", []))
            straight_count += 1
        if q.get("blockers"):
            raise RawNormalError(f"{hh}: symbolic blockers {q['blockers'][:4]}")
        if q.get("discards"):
            raise RawNormalError(f"{hh}: discard/side effects not closed {q['discards'][:4]}")
        outputs = q.get("outputs", [])
        if len(outputs) != 4 or {x.get("output") for x in outputs} != {"o0.x", "o0.y", "o0.z", "o0.w"}:
            raise RawNormalError(f"{hh}: unexpected pixel outputs {outputs}")
        sites = sample_sites(q["nodes"])
        compact = {
            "nodes": q["nodes"],
            "outputs": outputs,
            "ifs": q.get("ifs", []),
            "sampleSites": sites,
        }
        row = {
            "sha256": hh,
            "asset": shader.get("asset"),
            "controlFlow": has_if,
            "nodeCount": len(q["nodes"]),
            "outputCount": len(outputs),
            "ifCount": len(q.get("ifs", [])),
            "elseCount": int(q.get("elseCount", 0)),
            "maxNestingDepth": int(q.get("maxNestingDepth", 0)),
            "sampleSiteCount": len(sites),
            "sampleSites": sites,
            "outputs": outputs,
            "nodes": q["nodes"],
            "dagSha256": jdigest(compact),
        }
        shader_rows.append(row)
        node_count += row["nodeCount"]
        output_count += row["outputCount"]
        sample_count += row["sampleSiteCount"]
        if_count += row["ifCount"]

    core = {"programs": program_rows, "shaderRows": shader_rows}
    return {
        "format": FORMAT,
        "producer": "tools/t6_nuketown_rawnormal_full_output_v1.py",
        "map": "mp_nuketown_2020",
        "material": TARGET_MATERIAL,
        "techniqueSet": material.get("techniqueSet"),
        "sourceSpecialCensusSha256": hashlib.sha256(special_path.read_bytes()).hexdigest(),
        "summary": {
            "litProgramCount": len(program_rows),
            "uniquePixelShaderCount": len(shader_rows),
            "straightShaderCount": straight_count,
            "branchShaderCount": branch_count,
            "symbolicBlockerCount": 0,
            "discardShaderCount": 0,
            "outputComponentCount": output_count,
            "sampleSiteCount": sample_count,
            "nodeCount": node_count,
            "ifCount": if_count,
            "uniqueDagCount": len({r["dagSha256"] for r in shader_rows}),
        },
        **core,
        "evidenceDigestSha256": jdigest(core),
        "proofBoundary": (
            "Complete o0.xyzw expression DAGs are reconstructed from the exact native-OAT-selected pixel shader bytes for all lit variants of Nuketown's single raw-normal special Material. "
            "Straight-line payloads and structured IF/ELSE/ENDIF payloads use the same fail-closed SM4 operand/arithmetic semantics; branch states are independently executed and merged with exact select nodes. "
            "Shader bytes are re-hashed against the native census. Unsupported opcodes, read-before-write, discard, malformed control flow or population drift fail closed. "
            "Technique material arguments are retained as exact source provenance, but binding them and non-material code/runtime inputs to Blender/Rust semantics is a separate closure layer."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--special-census", type=Path, required=True)
    ap.add_argument("--straight-tool", type=Path, default=Path("tools/t6_retail_special_shdr_symbolic_v1.py"))
    ap.add_argument("--branch-tool", type=Path, default=Path("tools/t6_retail_special_shdr_branch_symbolic_v1.py"))
    ap.add_argument("--full-tool", type=Path, default=Path("tools/t6_nuketown_special_full_output_symbolic_v1.py"))
    ap.add_argument("--operand-tool", type=Path, default=Path("tools/t6_retail_special_shdr_operand_census_v1.py"))
    ap.add_argument("--opcode-tool", type=Path, default=Path("tools/t6_retail_special_shdr_opcode_census_v1.py"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    doc = build(a.special_census, a.straight_tool, a.branch_tool, a.full_tool, a.operand_tool, a.opcode_tool)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    print(doc["evidenceDigestSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
