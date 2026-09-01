#!/usr/bin/env python3
"""Exact straight-line symbolic reconstruction for T6 lightmap DXBC usage.

This stage is intentionally narrower than HLSL decompilation. For a shader that
`t6_lightmap_dxbc_lineage_v2` already marks closure-usable (no control flow,
unsupported writes, or unparsed candidate instructions), it reconstructs an
assembly-level expression DAG for output components that depend on known T6
lightmap primary/secondary texture registers.

Rules:
- mapped lightmap samples become exact atoms primary.{xyzw}/secondary.{xyzw};
- other inputs remain explicit symbols (v#, cb#, other texture samples, etc.);
- supported arithmetic preserves operand/component order exactly;
- unknown operations are allowed only when their inputs contain no lightmap
  dependency, in which case their result is an opaque external symbol;
- an unknown operation consuming a lightmap-derived value is a hard blocker;
- any control flow is a hard blocker.

The output equation therefore never invents a T6 combine formula.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from t6_lightmap_dxbc_lineage_v1 import COMPONENTS, TEXTURE_RE, _dest, _sample_channels, _split_operands
from t6_lightmap_dxbc_lineage_v2 import CONTROL_FLOW_PREFIXES, NO_DEST_PREFIXES, _parse_instruction


class LightmapSymbolicError(RuntimeError):
    pass


REG_RE = re.compile(r"^\s*([+-]?)\s*(abs\()?\|?([rov])(\d+)(?:\.([xyzw]{1,4}))?\|?\)?\s*$")
CB_RE = re.compile(r"^\s*([+-]?)\s*(abs\()?\|?(cb\d+\[[^\]]+\])(?:\.([xyzw]{1,4}))?\|?\)?\s*$")
LITERAL_RE = re.compile(r"^\s*l\((.*)\)\s*$")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Dag:
    def __init__(self):
        self.nodes: list[dict[str, Any]] = []
        self.by_key: dict[str, int] = {}

    def add(self, kind: str, **payload: Any) -> int:
        record = {"kind": kind, **payload}
        key = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        existing = self.by_key.get(key)
        if existing is not None:
            return existing
        node_id = len(self.nodes)
        record["id"] = node_id
        self.nodes.append(record)
        self.by_key[key] = node_id
        return node_id

    def deps(self, node_id: int) -> set[str]:
        node = self.nodes[node_id]
        if node["kind"] == "lightmap":
            return {f"{node['role']}.{node['channel']}"}
        result: set[str] = set()
        for child in node.get("args", []):
            result.update(self.deps(int(child)))
        return result


def _sequence(swizzle: str | None, count: int) -> list[str]:
    value = swizzle or COMPONENTS
    if len(value) == 1:
        return list(value * count)
    if len(value) < count:
        raise LightmapSymbolicError(f"swizzle {value!r} cannot supply {count} components")
    return list(value[:count])


def _apply_modifier(dag: Dag, node: int, sign: str, has_abs: bool) -> int:
    out = node
    if has_abs:
        out = dag.add("op", op="abs", args=[out])
    if sign == "-":
        out = dag.add("op", op="neg", args=[out])
    return out


def _literal_vector(dag: Dag, operand: str, count: int) -> list[int] | None:
    m = LITERAL_RE.match(operand)
    if not m:
        return None
    raw_values = _split_operands(m.group(1))
    if not raw_values:
        return None
    values = [dag.add("literal", text=value.strip()) for value in raw_values]
    if len(values) == 1:
        return values * count
    if len(values) < count:
        return None
    return values[:count]


def _source_vector(
    dag: Dag,
    operand: str,
    count: int,
    state: dict[tuple[str, int, str], int],
    blockers: list[dict],
    line_number: int,
) -> list[int]:
    lit = _literal_vector(dag, operand, count)
    if lit is not None:
        return lit

    match = REG_RE.match(operand)
    if match:
        sign, abs_marker, kind, index_text, swizzle = match.groups()
        index = int(index_text)
        sequence = _sequence(swizzle, count)
        result: list[int] = []
        for component in sequence:
            key = (kind, index, component)
            if kind in ("r", "o"):
                node = state.get(key)
                if node is None:
                    blockers.append({
                        "lineNumber": line_number,
                        "reason": "read-before-symbolic-write",
                        "operand": operand,
                        "component": f"{kind}{index}.{component}",
                    })
                    node = dag.add("symbol", name=f"UNDEFINED({kind}{index}.{component})")
            else:
                node = dag.add("symbol", name=f"{kind}{index}.{component}")
            result.append(_apply_modifier(dag, node, sign, abs_marker is not None or "|" in operand))
        return result

    match = CB_RE.match(operand)
    if match:
        sign, abs_marker, base, swizzle = match.groups()
        sequence = _sequence(swizzle, count)
        return [
            _apply_modifier(dag, dag.add("symbol", name=f"{base}.{component}"), sign, abs_marker is not None or "|" in operand)
            for component in sequence
        ]

    # Samplers/resources are handled by sample instructions. Other exact syntax
    # is retained as an opaque external symbol, component-qualified so later
    # vector arithmetic remains deterministic.
    return [dag.add("symbol", name=f"{operand}#{i}") for i in range(count)]


def _binary(dag: Dag, op: str, a: list[int], b: list[int]) -> list[int]:
    return [dag.add("op", op=op, args=[x, y]) for x, y in zip(a, b)]


def _unary(dag: Dag, op: str, a: list[int]) -> list[int]:
    return [dag.add("op", op=op, args=[x]) for x in a]


def _supported_arithmetic(
    dag: Dag,
    opcode: str,
    source_vectors: list[list[int]],
    dest_count: int,
) -> list[int] | None:
    saturated = opcode.endswith("_sat")
    base = opcode[:-4] if saturated else opcode
    out: list[int] | None = None
    if base == "mov" and len(source_vectors) == 1:
        out = list(source_vectors[0])
    elif base in ("add", "mul", "min", "max", "div") and len(source_vectors) == 2:
        out = _binary(dag, base, source_vectors[0], source_vectors[1])
    elif base == "mad" and len(source_vectors) == 3:
        out = [
            dag.add("op", op="add", args=[dag.add("op", op="mul", args=[a, b]), c])
            for a, b, c in zip(source_vectors[0], source_vectors[1], source_vectors[2])
        ]
    elif base in ("sqrt", "rsq", "rcp", "exp", "log", "frc", "round_ne", "round_ni", "round_pi", "round_z") and len(source_vectors) == 1:
        out = _unary(dag, base, source_vectors[0])
    elif base in ("eq", "ne", "lt", "ge") and len(source_vectors) == 2:
        out = _binary(dag, base, source_vectors[0], source_vectors[1])
    elif base in ("dp2", "dp3", "dp4") and len(source_vectors) == 2:
        n = int(base[-1])
        if len(source_vectors[0]) < n or len(source_vectors[1]) < n:
            return None
        products = [dag.add("op", op="mul", args=[source_vectors[0][i], source_vectors[1][i]]) for i in range(n)]
        dot = products[0]
        for value in products[1:]:
            dot = dag.add("op", op="add", args=[dot, value])
        out = [dot] * dest_count
    elif base == "dp2add" and len(source_vectors) == 3:
        products = [dag.add("op", op="mul", args=[source_vectors[0][i], source_vectors[1][i]]) for i in range(2)]
        total = dag.add("op", op="add", args=[products[0], products[1]])
        total = dag.add("op", op="add", args=[total, source_vectors[2][0]])
        out = [total] * dest_count
    elif base == "movc" and len(source_vectors) == 3:
        out = [dag.add("op", op="select", args=[c, a, b]) for c, a, b in zip(source_vectors[0], source_vectors[1], source_vectors[2])]

    if out is not None and saturated:
        out = [dag.add("op", op="saturate", args=[node]) for node in out]
    return out


def reconstruct_shader(text: str, *, primary_bind_points: set[int], secondary_bind_points: set[int]) -> dict:
    overlap = primary_bind_points & secondary_bind_points
    if overlap:
        raise LightmapSymbolicError(f"primary/secondary texture registers overlap: {sorted(overlap)}")
    role_by_texture = {index: "primary" for index in primary_bind_points}
    role_by_texture.update({index: "secondary" for index in secondary_bind_points})
    dag = Dag()
    state: dict[tuple[str, int, str], int] = {}
    blockers: list[dict] = []
    samples: list[dict] = []

    for line_index, original in enumerate(text.splitlines()):
        line_number = line_index + 1
        stripped = original.strip()
        if not stripped or stripped.startswith("//"):
            continue
        parsed = _parse_instruction(original)
        if parsed is None:
            continue
        opcode = str(parsed["opcode"])
        operands = _split_operands(str(parsed["operandText"]))
        if opcode.startswith("dcl_") or opcode.startswith("ps_"):
            continue
        if opcode.startswith(CONTROL_FLOW_PREFIXES):
            blockers.append({"lineNumber": line_number, "reason": "control-flow", "opcode": opcode, "line": original})
        if opcode.startswith(NO_DEST_PREFIXES):
            continue
        if not operands:
            continue
        destination = _dest(operands[0])
        if destination is None:
            continue
        dest_kind, dest_index, dest_components = destination
        count = len(dest_components)
        source_operands = operands[1:]

        is_sample = opcode.startswith("sample") or opcode.startswith("gather") or opcode.startswith("ld")
        texture_matches = [
            (int(m.group(1)), m.group(2))
            for operand in source_operands
            for m in TEXTURE_RE.finditer(operand)
        ]
        mapped = [item for item in texture_matches if item[0] in role_by_texture]
        values: list[int] | None = None
        if is_sample and mapped:
            if len(mapped) != 1:
                blockers.append({"lineNumber": line_number, "reason": "multiple-mapped-lightmap-textures", "line": original})
                continue
            bind_point, swizzle = mapped[0]
            role = role_by_texture[bind_point]
            channels = _sample_channels(swizzle, count)
            values = [
                dag.add("lightmap", role=role, channel=channel, textureRegister=f"t{bind_point}", lineNumber=line_number)
                for channel in channels
            ]
            samples.append({
                "lineNumber": line_number,
                "opcode": opcode,
                "role": role,
                "bindPoint": bind_point,
                "destination": operands[0],
                "channels": channels,
            })
        elif is_sample:
            # Exact non-lightmap texture sample remains a symbolic input to the
            # lightmap equation. Resource + instruction text are retained.
            values = [
                dag.add("textureSample", instruction=original.strip(), channel=component)
                for component in dest_components
            ]
        else:
            source_vectors = [
                _source_vector(dag, operand, count, state, blockers, line_number)
                for operand in source_operands
            ]
            values = _supported_arithmetic(dag, opcode, source_vectors, count)
            if values is None:
                deps: set[str] = set()
                for vector in source_vectors:
                    for node in vector:
                        deps.update(dag.deps(node))
                if deps:
                    blockers.append({
                        "lineNumber": line_number,
                        "reason": "unsupported-lightmap-consuming-opcode",
                        "opcode": opcode,
                        "dependencies": sorted(deps),
                        "line": original,
                    })
                    values = [dag.add("symbol", name=f"UNRESOLVED@L{line_number}.{component}") for component in dest_components]
                else:
                    values = [
                        dag.add("externalOp", opcode=opcode, instruction=original.strip(), component=component)
                        for component in dest_components
                    ]

        if len(values) != count:
            raise LightmapSymbolicError(
                f"line {line_number}: reconstructed value count {len(values)} != destination components {count}"
            )
        for component, node in zip(dest_components, values):
            state[(dest_kind, dest_index, component)] = node

    outputs: list[dict] = []
    for (kind, index, component), node in sorted(
        state.items(), key=lambda item: (item[0][0], item[0][1], COMPONENTS.index(item[0][2]))
    ):
        if kind != "o":
            continue
        deps = sorted(dag.deps(node))
        if deps:
            outputs.append({
                "output": f"o{index}.{component}",
                "node": node,
                "lightmapDependencies": deps,
            })

    closure_usable = bool(outputs) and not blockers
    return {
        "nodes": dag.nodes,
        "sampledLightmapInstructions": samples,
        "outputs": outputs,
        "blockers": blockers,
        "closureUsable": closure_usable,
        "stats": {
            "nodeCount": len(dag.nodes),
            "sampleCount": len(samples),
            "outputCount": len(outputs),
            "blockerCount": len(blockers),
        },
    }


def build_manifest(lineage: dict, disassembly_archive: dict, *, disassembly_root: Path) -> dict:
    if lineage.get("format") != "t6-lightmap-dxbc-lineage-v2":
        raise LightmapSymbolicError(f"unsupported lineage {lineage.get('format')!r}")
    archive_by_shader = {str(item["pixelShader"]): item for item in disassembly_archive.get("shaders", [])}
    results: list[dict] = []
    closure_count = 0
    blocker_count = 0
    for edge in lineage.get("provenance", []):
        shader = str(edge.get("pixelShader") or "")
        trace = edge.get("trace", {})
        if not trace.get("closureUsable"):
            results.append({
                "material": edge.get("material"), "technique": edge.get("technique"),
                "passIndex": edge.get("passIndex"), "pixelShader": shader,
                "closureUsable": False,
                "blockers": [{"reason": "lineage-v2-not-closure-usable"}],
            })
            blocker_count += 1
            continue
        archive = archive_by_shader.get(shader)
        if archive is None:
            raise LightmapSymbolicError(f"missing disassembly archive entry for {shader!r}")
        file_name = str(archive.get("disassemblyFile") or "")
        if Path(file_name).name != file_name:
            raise LightmapSymbolicError(f"unsafe disassembly filename {file_name!r}")
        path = disassembly_root / file_name
        raw = path.read_bytes()
        if len(raw) != int(archive.get("disassemblyBytes", -1)) or _sha256(raw) != str(archive.get("disassemblySha256") or ""):
            raise LightmapSymbolicError(f"disassembly changed for {shader!r}")
        text = raw.decode("utf-8")
        primary = set(map(int, edge.get("primaryTextureBindPoints", [])))
        secondary = set(map(int, edge.get("secondaryTextureBindPoints", [])))
        reconstructed = reconstruct_shader(text, primary_bind_points=primary, secondary_bind_points=secondary)
        closure_count += int(reconstructed["closureUsable"])
        blocker_count += int(not reconstructed["closureUsable"])
        results.append({
            "material": edge.get("material"),
            "techniqueSet": edge.get("techniqueSet"),
            "technique": edge.get("technique"),
            "techniqueTypes": edge.get("techniqueTypes"),
            "passIndex": edge.get("passIndex"),
            "pixelShader": shader,
            "shaderModel": edge.get("shaderModel"),
            "primaryTextureBindPoints": sorted(primary),
            "secondaryTextureBindPoints": sorted(secondary),
            "disassemblyFile": file_name,
            "disassemblySha256": archive.get("disassemblySha256"),
            **reconstructed,
        })
    return {
        "format": "t6-lightmap-dxbc-symbolic-v1",
        "provenance": results,
        "stats": {
            "edgeCount": len(results),
            "closureUsableEdgeCount": closure_count,
            "blockedEdgeCount": blocker_count,
            "allEdgesClosureUsable": len(results) > 0 and closure_count == len(results),
        },
        "policy": {
            "controlFlow": "hard blocker",
            "unsupportedOpcodeWithLightmapDependency": "hard blocker",
            "unsupportedOpcodeWithoutLightmapDependency": "opaque external symbol",
            "equationLevel": "DXBC assembly expression DAG; not reconstructed HLSL",
        },
        "proofBoundary": (
            "closureUsable proves that the observed straight-line DXBC path from mapped lightmap samples to output "
            "was reconstructed using supported instruction semantics. It does not assign human physical names to channels."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lineage", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--disassembly-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    lineage = json.loads(args.lineage.read_text(encoding="utf-8"))
    archive = json.loads(args.archive.read_text(encoding="utf-8"))
    result = build_manifest(lineage, archive, disassembly_root=args.disassembly_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), **result["stats"]}, indent=2))
    return 0 if result["stats"]["allEdgesClosureUsable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
