#!/usr/bin/env python3
"""Conservative component lineage over fxc/dxc DXBC assembly for T6 lightmaps.

This stage answers a narrower question than shader decompilation:

    Which sampled primary/secondary lightmap channels can reach each output
    register component in a straight-line dumpbin instruction stream?

Known T6 primary/secondary texture registers come from
`t6-lightmap-shader-dxbc-manifest-v1`. Sample/load destinations are tagged with
source atoms such as `primary.x@L123`. Tags are propagated through temporary
register writes. `mov` preserves component mapping; other arithmetic uses a
conservative union of all referenced temp/output source components.

This is intentionally NOT an algebraic decompiler. If shader control flow is
observed, the result is marked non-closure-grade because v1 does not perform
full CFG/SSA merge analysis. Even without control flow, dependency lineage does
not prove the exact combine equation or physical meaning of a channel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


class LightmapLineageError(RuntimeError):
    pass


DEST_RE = re.compile(r"^(r|o)(\d+)(?:\.([xyzw]{1,4}))?$")
SOURCE_RE = re.compile(r"(?<![A-Za-z0-9_])(?:-|\+)?(?:abs\()?([ro])(\d+)(?:\.([xyzw]{1,4}))?\)?")
TEXTURE_RE = re.compile(r"\bt(\d+)(?:\.([xyzw]{1,4}))?\b")
OPCODE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\b(?:\s+(.*))?$")
COMPONENTS = "xyzw"
CONTROL_FLOW_PREFIXES = (
    "if",
    "else",
    "endif",
    "loop",
    "endloop",
    "switch",
    "case",
    "default",
    "endswitch",
    "break",
    "continue",
    "call",
    "label",
    "retc",
)
NO_DEST_PREFIXES = CONTROL_FLOW_PREFIXES + ("ret", "discard", "sync")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _split_operands(text: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char == '(':
            depth += 1
        elif char == ')':
            depth = max(0, depth - 1)
        elif char == ',' and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        result.append(tail)
    return result


def _dest(operand: str) -> tuple[str, int, str] | None:
    match = DEST_RE.match(operand.strip())
    if not match:
        return None
    return match.group(1), int(match.group(2)), match.group(3) or COMPONENTS


def _source_components(swizzle: str | None) -> list[str]:
    if not swizzle:
        return list(COMPONENTS)
    return list(swizzle)


def _source_lineage(
    operand: str,
    state: dict[tuple[str, int, str], set[tuple[str, str, int, int]]],
) -> set[tuple[str, str, int, int]]:
    result: set[tuple[str, str, int, int]] = set()
    for match in SOURCE_RE.finditer(operand):
        kind = match.group(1)
        index = int(match.group(2))
        for component in _source_components(match.group(3)):
            result.update(state.get((kind, index, component), set()))
    return result


def _mov_component_sources(
    operand: str,
    count: int,
    state: dict[tuple[str, int, str], set[tuple[str, str, int, int]]],
) -> list[set[tuple[str, str, int, int]]] | None:
    matches = list(SOURCE_RE.finditer(operand))
    if len(matches) != 1:
        return None
    match = matches[0]
    kind = match.group(1)
    index = int(match.group(2))
    swizzle = match.group(3) or COMPONENTS
    if len(swizzle) == 1:
        sequence = swizzle * count
    elif len(swizzle) >= count:
        sequence = swizzle[:count]
    else:
        return None
    return [set(state.get((kind, index, component), set())) for component in sequence]


def _sample_channels(swizzle: str | None, count: int) -> list[str]:
    sequence = swizzle or COMPONENTS
    if len(sequence) == 1:
        return list(sequence * count)
    if len(sequence) >= count:
        return list(sequence[:count])
    # An unusual shortened resource swizzle is ambiguous for dependency proof.
    raise LightmapLineageError(
        f"texture swizzle {sequence!r} cannot map {count} destination components"
    )


def _atom_record(atom: tuple[str, str, int, int]) -> dict:
    role, channel, line, bind_point = atom
    return {
        "role": role,
        "channel": channel,
        "source": f"{role}.{channel}",
        "sampleLineNumber": line,
        "textureRegister": f"t{bind_point}",
        "bindPoint": bind_point,
    }


def trace_shader(
    text: str,
    *,
    primary_bind_points: set[int],
    secondary_bind_points: set[int],
) -> dict:
    overlap = primary_bind_points.intersection(secondary_bind_points)
    if overlap:
        raise LightmapLineageError(
            f"primary/secondary roles overlap texture bind points: {sorted(overlap)!r}"
        )
    role_by_texture = {x: "primary" for x in primary_bind_points}
    role_by_texture.update({x: "secondary" for x in secondary_bind_points})

    state: dict[tuple[str, int, str], set[tuple[str, str, int, int]]] = {}
    lines = text.splitlines()
    control_flow: list[dict] = []
    sampled: list[dict] = []
    propagated_instructions = 0
    unsupported_writes: list[dict] = []

    for line_index, original in enumerate(lines):
        line_number = line_index + 1
        stripped = original.strip()
        if not stripped or stripped.startswith("//"):
            continue
        # Drop an inline // comment without altering archived source text.
        code = original.split("//", 1)[0].strip()
        if not code:
            continue
        match = OPCODE_RE.match(code)
        if not match:
            continue
        opcode = match.group(1)
        operand_text = match.group(2) or ""
        operands = _split_operands(operand_text)

        if opcode.startswith("dcl_") or opcode.startswith("ps_"):
            continue
        if opcode.startswith(CONTROL_FLOW_PREFIXES):
            control_flow.append({"lineNumber": line_number, "opcode": opcode, "line": original})
        if opcode.startswith(NO_DEST_PREFIXES):
            continue
        if not operands:
            continue
        destination = _dest(operands[0])
        if destination is None:
            # Instruction classes with non-r/o destinations are retained as an
            # explicit limitation rather than guessed.
            if any(SOURCE_RE.search(x) for x in operands[1:]):
                unsupported_writes.append(
                    {"lineNumber": line_number, "opcode": opcode, "line": original}
                )
            continue
        dest_kind, dest_index, dest_components = destination
        source_operands = operands[1:]

        is_sample = (
            opcode.startswith("sample")
            or opcode.startswith("gather")
            or opcode.startswith("ld")
        )
        texture_matches = [
            (int(m.group(1)), m.group(2))
            for operand in source_operands
            for m in TEXTURE_RE.finditer(operand)
        ]
        mapped_textures = [x for x in texture_matches if x[0] in role_by_texture]

        if is_sample and mapped_textures:
            if len(mapped_textures) != 1:
                raise LightmapLineageError(
                    f"line {line_number}: sampling instruction references multiple mapped lightmap textures"
                )
            bind_point, texture_swizzle = mapped_textures[0]
            role = role_by_texture[bind_point]
            channels = _sample_channels(texture_swizzle, len(dest_components))
            # Coordinate/temp dependencies are kept in addition to the direct
            # sampled channel, conservatively preserving indirect dependence.
            inherited: set[tuple[str, str, int, int]] = set()
            for operand in source_operands:
                inherited.update(_source_lineage(operand, state))
            for component, channel in zip(dest_components, channels):
                atom = (role, channel, line_number, bind_point)
                state[(dest_kind, dest_index, component)] = set(inherited) | {atom}
            sampled.append(
                {
                    "lineNumber": line_number,
                    "opcode": opcode,
                    "line": original,
                    "role": role,
                    "textureRegister": f"t{bind_point}",
                    "bindPoint": bind_point,
                    "resourceSwizzle": texture_swizzle,
                    "destination": operands[0],
                    "taggedChannels": [f"{role}.{x}" for x in channels],
                }
            )
            propagated_instructions += 1
            continue

        if opcode in ("mov", "mov_sat") and len(source_operands) == 1:
            component_sources = _mov_component_sources(
                source_operands[0], len(dest_components), state
            )
            if component_sources is not None:
                for component, lineage in zip(dest_components, component_sources):
                    state[(dest_kind, dest_index, component)] = set(lineage)
                propagated_instructions += 1
                continue

        # Conservative arithmetic/general write: every written destination
        # component receives the union of all lightmap lineage referenced by
        # source temp/output operands. This may over-approximate channel mixing,
        # but must not invent a channel absent from all sources.
        union: set[tuple[str, str, int, int]] = set()
        for operand in source_operands:
            union.update(_source_lineage(operand, state))
        for component in dest_components:
            state[(dest_kind, dest_index, component)] = set(union)
        propagated_instructions += 1

    outputs: list[dict] = []
    output_keys = sorted(
        (key for key, lineage in state.items() if key[0] == "o" and lineage),
        key=lambda key: (key[1], COMPONENTS.index(key[2])),
    )
    for kind, index, component in output_keys:
        lineage = state[(kind, index, component)]
        atoms = sorted(lineage, key=lambda x: (x[0], x[1], x[2], x[3]))
        dependencies = sorted({f"{role}.{channel}" for role, channel, _, _ in atoms})
        outputs.append(
            {
                "output": f"o{index}.{component}",
                "register": f"o{index}",
                "component": component,
                "dependencies": dependencies,
                "origins": [_atom_record(atom) for atom in atoms],
            }
        )

    return {
        "sampledLightmapInstructions": sampled,
        "sampledLightmapInstructionCount": len(sampled),
        "propagatedInstructionCount": propagated_instructions,
        "controlFlowObserved": bool(control_flow),
        "controlFlow": control_flow,
        "unsupportedWriteCount": len(unsupported_writes),
        "unsupportedWrites": unsupported_writes,
        "outputsWithLightmapDependency": outputs,
        "outputDependencyCount": len(outputs),
        "closureUsable": not control_flow and not unsupported_writes,
    }


def build_lineage_manifest(
    dxbc_manifest: dict,
    disassembly_archive: dict,
    *,
    disassembly_root: Path,
) -> dict:
    if dxbc_manifest.get("format") != "t6-lightmap-shader-dxbc-manifest-v1":
        raise LightmapLineageError(
            f"unsupported DXBC manifest {dxbc_manifest.get('format')!r}"
        )
    if disassembly_archive.get("format") != "t6-dxbc-disassembly-archive-v1":
        raise LightmapLineageError(
            f"unsupported disassembly archive {disassembly_archive.get('format')!r}"
        )
    archive_by_shader = {
        str(x["pixelShader"]): x for x in disassembly_archive.get("shaders", [])
    }
    text_cache: dict[str, str] = {}

    results: list[dict] = []
    closure_usable = 0
    control_flow_count = 0
    output_dependency_count = 0
    sample_count = 0
    for edge in dxbc_manifest.get("provenance", []):
        if not edge.get("shaderPresent"):
            continue
        shader_name = str(edge["pixelShader"])
        archive_item = archive_by_shader.get(shader_name)
        if archive_item is None:
            raise LightmapLineageError(
                f"no disassembly archive entry for shader {shader_name!r}"
            )
        if shader_name not in text_cache:
            file_name = str(archive_item.get("disassemblyFile") or "")
            if not file_name or Path(file_name).name != file_name:
                raise LightmapLineageError(
                    f"unsafe disassembly filename for {shader_name!r}: {file_name!r}"
                )
            path = disassembly_root / file_name
            if not path.is_file():
                raise LightmapLineageError(f"missing disassembly {path}")
            raw = path.read_bytes()
            if int(archive_item.get("disassemblyBytes", -1)) != len(raw) or str(
                archive_item.get("disassemblySha256") or ""
            ) != _sha256(raw):
                raise LightmapLineageError(
                    f"disassembly artifact changed for shader {shader_name!r}"
                )
            try:
                text_cache[shader_name] = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise LightmapLineageError(
                    f"disassembly is not UTF-8/ASCII for {shader_name!r}"
                ) from exc

        primary = {
            int(x["bindPoint"])
            for x in edge.get("resolvedLightmapBindings", [])
            if x["codeSampler"] == "lightmapSamplerPrimary"
        }
        secondary = {
            int(x["bindPoint"])
            for x in edge.get("resolvedLightmapBindings", [])
            if x["codeSampler"] == "lightmapSamplerSecondary"
        }
        traced = trace_shader(
            text_cache[shader_name],
            primary_bind_points=primary,
            secondary_bind_points=secondary,
        )
        closure_usable += int(traced["closureUsable"])
        control_flow_count += int(traced["controlFlowObserved"])
        output_dependency_count += traced["outputDependencyCount"]
        sample_count += traced["sampledLightmapInstructionCount"]
        results.append(
            {
                "material": edge.get("material"),
                "techniqueSet": edge.get("techniqueSet"),
                "technique": edge.get("technique"),
                "techniqueTypes": edge.get("techniqueTypes"),
                "passIndex": edge.get("passIndex"),
                "pixelShader": shader_name,
                "shaderModel": edge.get("shaderModel"),
                "primaryTextureBindPoints": sorted(primary),
                "secondaryTextureBindPoints": sorted(secondary),
                "disassemblyFile": archive_item.get("disassemblyFile"),
                "disassemblySha256": archive_item.get("disassemblySha256"),
                "trace": traced,
            }
        )

    return {
        "format": "t6-lightmap-dxbc-lineage-v1",
        "source": {
            "dxbcManifestFormat": dxbc_manifest.get("format"),
            "disassemblyArchiveFormat": disassembly_archive.get("format"),
            "disassemblyRoot": str(disassembly_root),
        },
        "policy": {
            "sampleOrigins": "known primary/secondary RDEF t# bind points",
            "movPropagation": "component mapped",
            "arithmeticPropagation": "conservative union of referenced lightmap source components",
            "controlFlow": "detected but not CFG-merged in v1; such traces are not closure-usable",
            "unsupportedWrites": "recorded and make trace non-closure-usable",
            "channelPhysicalMeaning": "not inferred",
            "algebraicCombineEquation": "not reconstructed",
        },
        "stats": {
            "provenanceTraceCount": len(results),
            "closureUsableStraightLineTraceCount": closure_usable,
            "controlFlowTraceCount": control_flow_count,
            "sampledLightmapInstructionCount": sample_count,
            "outputComponentDependencyCount": output_dependency_count,
        },
        "provenance": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dxbc_manifest_json", type=Path)
    parser.add_argument("disassembly_archive_json", type=Path)
    parser.add_argument("--disassembly-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    dxbc = json.loads(args.dxbc_manifest_json.read_text(encoding="utf-8"))
    archive = json.loads(args.disassembly_archive_json.read_text(encoding="utf-8"))
    doc = build_lineage_manifest(
        dxbc,
        archive,
        disassembly_root=args.disassembly_root,
    )
    args.out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.out), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
