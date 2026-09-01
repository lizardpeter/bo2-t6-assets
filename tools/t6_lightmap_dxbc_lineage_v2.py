#!/usr/bin/env python3
"""Conservative component lineage over real fxc/dxc DXBC dumpbin syntax.

V2 hardens v1 against syntax observed in real SM4/SM5 disassembly:

- decorated opcodes such as
  `sample_indexable(texture2d)(float,float,float,float) ...`;
- optional numeric instruction prefixes such as `17: mad ...`;
- absolute-value source modifiers such as `|r3.x|` and `-|r3.x|`;
- discard instructions as control-flow/coverage blockers.

The semantic boundary is unchanged: this is dependency lineage, not algebraic
shader decompilation. General arithmetic conservatively unions referenced
lightmap atoms. Any observed control flow or unsupported destination write makes
a trace non-closure-usable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from t6_lightmap_dxbc_lineage_v1 import (
    COMPONENTS,
    LightmapLineageError,
    TEXTURE_RE,
    _atom_record,
    _dest,
    _sample_channels,
    _split_operands,
)


# Optional `17:` prefix; base opcode; zero or more no-whitespace parenthetical
# opcode decorations; then operands. Parenthetical payload is intentionally
# treated as syntax decoration, not an operand source.
INSTRUCTION_RE = re.compile(
    r"^\s*(?:(\d+)\s*:\s*)?"
    r"([A-Za-z_][A-Za-z0-9_]*)"
    r"((?:\([^\r\n)]*\))*)"
    r"(?:\s+(.*?))?\s*$"
)
SOURCE_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:[-+])?"
    r"(?:abs\()?"
    r"\|?"
    r"([ro])(\d+)"
    r"(?:\.([xyzw]{1,4}))?"
    r"\|?"
    r"\)?"
)
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
    "discard",
)
NO_DEST_PREFIXES = CONTROL_FLOW_PREFIXES + ("ret", "sync")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_components(swizzle: str | None) -> list[str]:
    return list(swizzle or COMPONENTS)


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
    return [set(state.get((kind, index, c), set())) for c in sequence]


def _parse_instruction(original: str) -> dict | None:
    code = original.split("//", 1)[0].strip()
    if not code:
        return None
    match = INSTRUCTION_RE.match(code)
    if not match:
        return None
    return {
        "displayIndex": None if match.group(1) is None else int(match.group(1)),
        "opcode": match.group(2),
        "decorations": match.group(3) or "",
        "operandText": match.group(4) or "",
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
    control_flow: list[dict] = []
    sampled: list[dict] = []
    unsupported_writes: list[dict] = []
    unparsed_instruction_candidates: list[dict] = []
    propagated_instructions = 0

    for line_index, original in enumerate(text.splitlines()):
        line_number = line_index + 1
        stripped = original.strip()
        if not stripped or stripped.startswith("//"):
            continue
        parsed = _parse_instruction(original)
        if parsed is None:
            # Preserve plausible assembly lines that contain a temp/output or
            # mapped texture token so a syntax miss cannot silently disappear.
            if SOURCE_RE.search(original) or TEXTURE_RE.search(original):
                unparsed_instruction_candidates.append(
                    {"lineNumber": line_number, "line": original}
                )
            continue
        opcode = str(parsed["opcode"])
        operands = _split_operands(str(parsed["operandText"]))

        if opcode.startswith("dcl_") or opcode.startswith("ps_"):
            continue
        if opcode.startswith(CONTROL_FLOW_PREFIXES):
            control_flow.append(
                {
                    "lineNumber": line_number,
                    "displayIndex": parsed["displayIndex"],
                    "opcode": opcode,
                    "line": original,
                }
            )
        if opcode.startswith(NO_DEST_PREFIXES):
            continue
        if not operands:
            continue

        destination = _dest(operands[0])
        if destination is None:
            if any(SOURCE_RE.search(x) for x in operands[1:]):
                unsupported_writes.append(
                    {
                        "lineNumber": line_number,
                        "displayIndex": parsed["displayIndex"],
                        "opcode": opcode,
                        "line": original,
                    }
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
            inherited: set[tuple[str, str, int, int]] = set()
            for operand in source_operands:
                inherited.update(_source_lineage(operand, state))
            for component, channel in zip(dest_components, channels):
                atom = (role, channel, line_number, bind_point)
                state[(dest_kind, dest_index, component)] = set(inherited) | {atom}
            sampled.append(
                {
                    "lineNumber": line_number,
                    "displayIndex": parsed["displayIndex"],
                    "opcode": opcode,
                    "opcodeDecorations": parsed["decorations"],
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
        outputs.append(
            {
                "output": f"o{index}.{component}",
                "register": f"o{index}",
                "component": component,
                "dependencies": sorted(
                    {f"{role}.{channel}" for role, channel, _, _ in atoms}
                ),
                "origins": [_atom_record(atom) for atom in atoms],
            }
        )

    closure_usable = not (
        control_flow or unsupported_writes or unparsed_instruction_candidates
    )
    return {
        "sampledLightmapInstructions": sampled,
        "sampledLightmapInstructionCount": len(sampled),
        "propagatedInstructionCount": propagated_instructions,
        "controlFlowObserved": bool(control_flow),
        "controlFlow": control_flow,
        "unsupportedWriteCount": len(unsupported_writes),
        "unsupportedWrites": unsupported_writes,
        "unparsedInstructionCandidateCount": len(unparsed_instruction_candidates),
        "unparsedInstructionCandidates": unparsed_instruction_candidates,
        "outputsWithLightmapDependency": outputs,
        "outputDependencyCount": len(outputs),
        "closureUsable": closure_usable,
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
    unsupported_count = 0
    unparsed_count = 0
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
        unsupported_count += int(traced["unsupportedWriteCount"])
        unparsed_count += int(traced["unparsedInstructionCandidateCount"])
        output_dependency_count += int(traced["outputDependencyCount"])
        sample_count += int(traced["sampledLightmapInstructionCount"])
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
        "format": "t6-lightmap-dxbc-lineage-v2",
        "source": {
            "dxbcManifestFormat": dxbc_manifest.get("format"),
            "disassemblyArchiveFormat": disassembly_archive.get("format"),
            "disassemblyRoot": str(disassembly_root),
            "producer": "t6_lightmap_dxbc_lineage_v2.py",
        },
        "policy": {
            "dumpbinSyntax": (
                "supports decorated SM4/SM5 opcode suffixes, optional numeric instruction prefixes, "
                "and |r#| absolute-value source modifiers"
            ),
            "sampleOrigins": "known primary/secondary RDEF t# bind points",
            "movPropagation": "component mapped",
            "arithmeticPropagation": "conservative union of referenced lightmap source components",
            "controlFlow": "detected but not CFG/SSA-merged; such traces are not closure-usable",
            "unsupportedWrites": "recorded and make trace non-closure-usable",
            "unparsedCandidates": "any plausible unparsed temp/output/texture instruction makes trace non-closure-usable",
            "channelPhysicalMeaning": "not inferred",
            "algebraicCombineEquation": "not reconstructed",
        },
        "stats": {
            "provenanceTraceCount": len(results),
            "closureUsableStraightLineTraceCount": closure_usable,
            "controlFlowTraceCount": control_flow_count,
            "unsupportedWriteCount": unsupported_count,
            "unparsedInstructionCandidateCount": unparsed_count,
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
    doc = build_lineage_manifest(dxbc, archive, disassembly_root=args.disassembly_root)
    args.out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.out), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
