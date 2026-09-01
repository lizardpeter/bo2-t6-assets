#!/usr/bin/env python3
"""T6 lightmap DXBC symbolic reconstruction v2.

V2 retains v1's fail-closed straight-line expression DAG and fixes instruction
source-width semantics that differ from destination width. In particular,
scalar dp2/dp3/dp4 destinations still consume 2/3/4 source components, and
dp2add consumes 2,2,1 source components.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_lightmap_dxbc_lineage_v1 import COMPONENTS, TEXTURE_RE, _dest, _sample_channels, _split_operands
from t6_lightmap_dxbc_lineage_v2 import CONTROL_FLOW_PREFIXES, NO_DEST_PREFIXES, _parse_instruction
from t6_lightmap_dxbc_symbolic_v1 import (
    Dag,
    LightmapSymbolicError,
    _source_vector,
    _supported_arithmetic,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _base_opcode(opcode: str) -> str:
    return opcode[:-4] if opcode.endswith("_sat") else opcode


def _source_widths(opcode: str, dest_count: int, source_count: int) -> list[int]:
    base = _base_opcode(opcode)
    if base in ("dp2", "dp3", "dp4"):
        n = int(base[-1])
        return [n, n] if source_count == 2 else [dest_count] * source_count
    if base == "dp2add":
        return [2, 2, 1] if source_count == 3 else [dest_count] * source_count
    return [dest_count] * source_count


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
            # Lineage v2 separately catches plausible syntax misses. This stage
            # is intended to run only after lineage closureUsable=true.
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
        dest_count = len(dest_components)
        source_operands = operands[1:]

        is_sample = opcode.startswith("sample") or opcode.startswith("gather") or opcode.startswith("ld")
        texture_matches = [
            (int(match.group(1)), match.group(2))
            for operand in source_operands
            for match in TEXTURE_RE.finditer(operand)
        ]
        mapped = [item for item in texture_matches if item[0] in role_by_texture]
        values: list[int] | None = None
        if is_sample and mapped:
            if len(mapped) != 1:
                blockers.append({"lineNumber": line_number, "reason": "multiple-mapped-lightmap-textures", "line": original})
                continue
            bind_point, swizzle = mapped[0]
            role = role_by_texture[bind_point]
            channels = _sample_channels(swizzle, dest_count)
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
            values = [
                dag.add("textureSample", instruction=original.strip(), channel=component)
                for component in dest_components
            ]
        else:
            widths = _source_widths(opcode, dest_count, len(source_operands))
            source_vectors = [
                _source_vector(dag, operand, width, state, blockers, line_number)
                for operand, width in zip(source_operands, widths)
            ]
            values = _supported_arithmetic(dag, opcode, source_vectors, dest_count)
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
                    values = [
                        dag.add("symbol", name=f"UNRESOLVED@L{line_number}.{component}")
                        for component in dest_components
                    ]
                else:
                    values = [
                        dag.add("externalOp", opcode=opcode, instruction=original.strip(), component=component)
                        for component in dest_components
                    ]

        if len(values) != dest_count:
            raise LightmapSymbolicError(
                f"line {line_number}: reconstructed value count {len(values)} != destination components {dest_count}"
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
            outputs.append({"output": f"o{index}.{component}", "node": node, "lightmapDependencies": deps})

    return {
        "nodes": dag.nodes,
        "sampledLightmapInstructions": samples,
        "outputs": outputs,
        "blockers": blockers,
        "closureUsable": bool(outputs) and not blockers,
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
    if disassembly_archive.get("format") != "t6-dxbc-disassembly-archive-v1":
        raise LightmapSymbolicError(f"unsupported disassembly archive {disassembly_archive.get('format')!r}")
    archive_by_shader = {str(item["pixelShader"]): item for item in disassembly_archive.get("shaders", [])}
    results: list[dict] = []
    closure_count = 0
    blocked_count = 0
    for edge in lineage.get("provenance", []):
        shader = str(edge.get("pixelShader") or "")
        if not edge.get("trace", {}).get("closureUsable"):
            results.append({
                "material": edge.get("material"),
                "technique": edge.get("technique"),
                "passIndex": edge.get("passIndex"),
                "pixelShader": shader,
                "closureUsable": False,
                "blockers": [{"reason": "lineage-v2-not-closure-usable"}],
            })
            blocked_count += 1
            continue
        archive = archive_by_shader.get(shader)
        if archive is None:
            raise LightmapSymbolicError(f"missing disassembly archive entry for {shader!r}")
        file_name = str(archive.get("disassemblyFile") or "")
        if Path(file_name).name != file_name:
            raise LightmapSymbolicError(f"unsafe disassembly filename {file_name!r}")
        path = disassembly_root / file_name
        if not path.is_file():
            raise LightmapSymbolicError(f"missing disassembly {path}")
        raw = path.read_bytes()
        if len(raw) != int(archive.get("disassemblyBytes", -1)) or _sha256(raw) != str(archive.get("disassemblySha256") or ""):
            raise LightmapSymbolicError(f"disassembly changed for {shader!r}")
        primary = set(map(int, edge.get("primaryTextureBindPoints", [])))
        secondary = set(map(int, edge.get("secondaryTextureBindPoints", [])))
        reconstructed = reconstruct_shader(
            raw.decode("utf-8"),
            primary_bind_points=primary,
            secondary_bind_points=secondary,
        )
        closure_count += int(reconstructed["closureUsable"])
        blocked_count += int(not reconstructed["closureUsable"])
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
        "format": "t6-lightmap-dxbc-symbolic-v2",
        "provenance": results,
        "stats": {
            "edgeCount": len(results),
            "closureUsableEdgeCount": closure_count,
            "blockedEdgeCount": blocked_count,
            "allEdgesClosureUsable": len(results) > 0 and closure_count == len(results),
        },
        "policy": {
            "controlFlow": "hard blocker",
            "unsupportedOpcodeWithLightmapDependency": "hard blocker",
            "unsupportedOpcodeWithoutLightmapDependency": "opaque external symbol",
            "dotProductSourceWidth": "dpN consumes N source components regardless of destination mask",
            "equationLevel": "DXBC assembly expression DAG; not reconstructed HLSL",
        },
        "proofBoundary": (
            "closureUsable proves the straight-line DXBC expression from mapped T6 lightmap samples to outputs "
            "is represented by supported instruction semantics. Human physical channel labels are unnecessary for bytecode-equivalent playback and remain separate descriptive semantics."
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
