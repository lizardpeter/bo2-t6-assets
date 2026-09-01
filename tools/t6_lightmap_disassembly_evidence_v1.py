#!/usr/bin/env python3
"""Extract exact disassembly evidence around T6 primary/secondary texture registers.

Inputs:
- `t6-lightmap-shader-dxbc-manifest-v1`: exact per-pass code-sampler -> RDEF t# mapping.
- `t6-dxbc-disassembly-archive-v1`: exact hashed fxc/dxc dumpbin artifacts.

For each provenance edge, this tool finds every non-comment disassembly line that
references the resolved primary/secondary texture registers and retains bounded
line context. Declarations and executable references are classified separately.

This deliberately stops short of claiming data-flow/channel/combine semantics.
The retained instruction slices are the evidence used by the next manual or
machine-assisted shader-semantic stage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


class LightmapDisassemblyEvidenceError(RuntimeError):
    pass


TREG_RE = re.compile(r"\bt(\d+)(?:\.([xyzw]{1,4}))?\b")
OPCODE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\b")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_file(value: str) -> str:
    if not value or Path(value).name != value or value in (".", "..") or "\0" in value:
        raise LightmapDisassemblyEvidenceError(f"unsafe disassembly filename {value!r}")
    return value


def _instruction_record(lines: list[str], index: int, register: int, context: int) -> dict:
    line = lines[index]
    stripped = line.strip()
    opcode_match = OPCODE_RE.match(stripped)
    opcode = opcode_match.group(1) if opcode_match else None
    refs = [
        {
            "bindPoint": int(match.group(1)),
            "textureRegister": f"t{int(match.group(1))}",
            "swizzle": match.group(2),
        }
        for match in TREG_RE.finditer(line)
    ]
    start = max(0, index - context)
    end = min(len(lines), index + context + 1)
    return {
        "lineNumber": index + 1,
        "line": line,
        "opcode": opcode,
        "isDeclaration": bool(opcode and opcode.startswith("dcl_")),
        "isSamplingInstruction": bool(
            opcode
            and (
                opcode.startswith("sample")
                or opcode.startswith("gather")
                or opcode.startswith("ld")
            )
        ),
        "targetTextureRegister": f"t{register}",
        "textureReferences": refs,
        "contextStartLine": start + 1,
        "contextEndLine": end,
        "context": [
            {"lineNumber": row + 1, "line": lines[row]}
            for row in range(start, end)
        ],
    }


def _references(lines: list[str], register: int, context: int) -> list[dict]:
    result: list[dict] = []
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("//"):
            continue
        matches = [int(match.group(1)) for match in TREG_RE.finditer(line)]
        if register in matches:
            result.append(_instruction_record(lines, index, register, context))
    return result


def build_evidence(
    dxbc_manifest: dict,
    disassembly_archive: dict,
    *,
    disassembly_root: Path,
    context_lines: int = 3,
    require_executable_use: bool = False,
) -> dict:
    if dxbc_manifest.get("format") != "t6-lightmap-shader-dxbc-manifest-v1":
        raise LightmapDisassemblyEvidenceError(
            f"unsupported DXBC manifest {dxbc_manifest.get('format')!r}"
        )
    if disassembly_archive.get("format") != "t6-dxbc-disassembly-archive-v1":
        raise LightmapDisassemblyEvidenceError(
            f"unsupported disassembly archive {disassembly_archive.get('format')!r}"
        )
    if context_lines < 0 or context_lines > 50:
        raise LightmapDisassemblyEvidenceError(
            f"context_lines outside 0..50: {context_lines}"
        )

    archive_by_shader = {
        str(item["pixelShader"]): item
        for item in disassembly_archive.get("shaders", [])
    }
    text_by_shader: dict[str, tuple[list[str], dict]] = {}
    for shader_name, item in archive_by_shader.items():
        file_name = _safe_file(str(item.get("disassemblyFile") or ""))
        path = disassembly_root / file_name
        if not path.is_file():
            raise LightmapDisassemblyEvidenceError(
                f"missing exact disassembly artifact {path}"
            )
        raw = path.read_bytes()
        if int(item.get("disassemblyBytes", -1)) != len(raw) or str(
            item.get("disassemblySha256") or ""
        ) != _sha256(raw):
            raise LightmapDisassemblyEvidenceError(
                f"disassembly artifact changed for shader {shader_name!r}"
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LightmapDisassemblyEvidenceError(
                f"disassembly is not UTF-8/ASCII for shader {shader_name!r}"
            ) from exc
        text_by_shader[shader_name] = (text.splitlines(), item)

    edges: list[dict] = []
    unique_ref_keys: set[tuple[str, str, int, int]] = set()
    executable_use_count = 0
    sampling_use_count = 0
    no_executable: list[dict] = []

    for provenance in dxbc_manifest.get("provenance", []):
        if not provenance.get("shaderPresent"):
            continue
        shader_name = str(provenance["pixelShader"])
        if shader_name not in text_by_shader:
            raise LightmapDisassemblyEvidenceError(
                f"no archived disassembly for present shader {shader_name!r}"
            )
        lines, archive_item = text_by_shader[shader_name]
        bindings: list[dict] = []
        for resolved in provenance.get("resolvedLightmapBindings", []):
            bind_point = int(resolved["bindPoint"])
            refs = _references(lines, bind_point, context_lines)
            executable = [x for x in refs if not x["isDeclaration"]]
            sampling = [x for x in executable if x["isSamplingInstruction"]]
            executable_use_count += len(executable)
            sampling_use_count += len(sampling)
            for ref in refs:
                unique_ref_keys.add(
                    (
                        shader_name,
                        str(resolved["codeSampler"]),
                        bind_point,
                        int(ref["lineNumber"]),
                    )
                )
            if not executable:
                issue = {
                    "pixelShader": shader_name,
                    "codeSampler": resolved["codeSampler"],
                    "textureRegister": f"t{bind_point}",
                    "material": provenance.get("material"),
                    "technique": provenance.get("technique"),
                    "passIndex": provenance.get("passIndex"),
                }
                no_executable.append(issue)
                if require_executable_use:
                    raise LightmapDisassemblyEvidenceError(
                        f"no executable disassembly reference for {shader_name!r} "
                        f"{resolved['codeSampler']} t{bind_point}"
                    )
            bindings.append(
                {
                    **resolved,
                    "referenceCount": len(refs),
                    "declarationReferenceCount": len(refs) - len(executable),
                    "executableReferenceCount": len(executable),
                    "samplingInstructionCount": len(sampling),
                    "references": refs,
                }
            )
        edges.append(
            {
                "material": provenance.get("material"),
                "techniqueSet": provenance.get("techniqueSet"),
                "technique": provenance.get("technique"),
                "techniqueTypes": provenance.get("techniqueTypes"),
                "passIndex": provenance.get("passIndex"),
                "pixelShader": shader_name,
                "shaderModel": provenance.get("shaderModel"),
                "shaderSha256": archive_item.get("shaderSha256"),
                "disassemblyFile": archive_item.get("disassemblyFile"),
                "disassemblySha256": archive_item.get("disassemblySha256"),
                "bindings": bindings,
            }
        )

    return {
        "format": "t6-lightmap-disassembly-evidence-v1",
        "source": {
            "dxbcManifestFormat": dxbc_manifest.get("format"),
            "disassemblyArchiveFormat": disassembly_archive.get("format"),
            "disassemblyRoot": str(disassembly_root),
            "disassembler": disassembly_archive.get("disassembler"),
        },
        "policy": {
            "registerSource": "resolved OAT code sampler -> RDEF TEXTURE bind point",
            "lineSelection": "all non-comment dumpbin lines containing exact t# token",
            "contextLinesEachSide": context_lines,
            "declarationsSeparatedFromExecutableUses": True,
            "samplingClassification": "opcode prefix sample/gather/ld",
            "dataflowMeaning": "not inferred",
            "channelMeaning": "not inferred",
            "combineEquation": "not inferred",
        },
        "stats": {
            "provenanceEdgeCount": len(edges),
            "uniqueRegisterReferenceCount": len(unique_ref_keys),
            "executableReferenceCount": executable_use_count,
            "samplingInstructionCount": sampling_use_count,
            "bindingsWithoutExecutableUseCount": len(no_executable),
        },
        "provenance": edges,
        "bindingsWithoutExecutableUse": no_executable,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dxbc_manifest_json", type=Path)
    parser.add_argument("disassembly_archive_json", type=Path)
    parser.add_argument("--disassembly-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--context-lines", type=int, default=3)
    parser.add_argument("--require-executable-use", action="store_true")
    args = parser.parse_args()
    dxbc = json.loads(args.dxbc_manifest_json.read_text(encoding="utf-8"))
    archive = json.loads(args.disassembly_archive_json.read_text(encoding="utf-8"))
    doc = build_evidence(
        dxbc,
        archive,
        disassembly_root=args.disassembly_root,
        context_lines=args.context_lines,
        require_executable_use=args.require_executable_use,
    )
    args.out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.out), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
