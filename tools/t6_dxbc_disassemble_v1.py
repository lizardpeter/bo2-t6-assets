#!/usr/bin/env python3
"""Archive DXBC disassembly for a T6 lightmap-shader manifest.

This stage intentionally delegates instruction decoding to an explicit Windows
SDK/DirectX compiler tool instead of reimplementing the D3D10/11 token ISA.
Supported command forms:

  fxc /dumpbin <shader.cso>
  dxc -dumpbin <shader.cso>

The caller supplies the exact executable path and tool kind. The executable is
SHA-256 hashed, raw stdout/stderr are retained, and each input shader is verified
against `t6-lightmap-shader-dxbc-manifest-v1` before invocation.

Disassembly text is evidence, not automatically a solved shader equation. A
separate semantic-analysis stage consumes it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


class DxbcDisassembleError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_file(value: str) -> str:
    if not value or Path(value).name != value or value in (".", "..") or "\0" in value:
        raise DxbcDisassembleError(f"unsafe filename {value!r}")
    return value


def build_command(tool_kind: str, executable: Path, shader: Path) -> list[str]:
    if tool_kind == "fxc":
        return [str(executable), "/dumpbin", str(shader)]
    if tool_kind == "dxc":
        return [str(executable), "-dumpbin", str(shader)]
    raise DxbcDisassembleError(f"unsupported disassembler kind {tool_kind!r}")


def disassemble_manifest(
    dxbc_manifest: dict,
    *,
    shader_root: Path,
    executable: Path,
    tool_kind: str,
    output_dir: Path,
) -> dict:
    if dxbc_manifest.get("format") != "t6-lightmap-shader-dxbc-manifest-v1":
        raise DxbcDisassembleError(
            f"unsupported DXBC manifest {dxbc_manifest.get('format')!r}"
        )
    if not executable.is_file():
        raise DxbcDisassembleError(f"disassembler executable does not exist: {executable}")
    exe_raw = executable.read_bytes()
    exe_record = {
        "kind": tool_kind,
        "path": str(executable),
        "bytes": len(exe_raw),
        "sha256": _sha256(exe_raw),
    }
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for shader in dxbc_manifest.get("pixelShaders", []):
        if not shader.get("present"):
            continue
        name = str(shader.get("pixelShader") or "")
        file_name = _safe_file(str(shader.get("file") or ""))
        path = shader_root / file_name
        if not path.is_file():
            raise DxbcDisassembleError(f"missing exact shader input {path}")
        raw = path.read_bytes()
        expected_bytes = int(shader.get("bytes", -1))
        expected_sha = str(shader.get("sha256") or "")
        actual_sha = _sha256(raw)
        if expected_bytes != len(raw) or expected_sha != actual_sha:
            raise DxbcDisassembleError(
                f"shader {name!r} no longer matches DXBC manifest"
            )

        command = build_command(tool_kind, executable, path)
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            raise DxbcDisassembleError(
                f"failed to launch {tool_kind} for {name!r}: {exc}"
            ) from exc
        stdout = bytes(completed.stdout)
        stderr = bytes(completed.stderr)
        if completed.returncode != 0:
            raise DxbcDisassembleError(
                f"{tool_kind} failed for {name!r} with exit code {completed.returncode}: "
                f"stderr_sha256={_sha256(stderr)}"
            )
        if not stdout.strip():
            raise DxbcDisassembleError(
                f"{tool_kind} produced empty disassembly for {name!r}"
            )

        out_name = _safe_file(Path(file_name).stem + f".{tool_kind}.dumpbin.txt")
        out_path = output_dir / out_name
        out_path.write_bytes(stdout)
        stderr_name = None
        if stderr:
            stderr_name = _safe_file(Path(file_name).stem + f".{tool_kind}.stderr.txt")
            (output_dir / stderr_name).write_bytes(stderr)

        results.append(
            {
                "pixelShader": name,
                "shaderFile": file_name,
                "shaderBytes": len(raw),
                "shaderSha256": actual_sha,
                "command": command,
                "returnCode": int(completed.returncode),
                "disassemblyFile": out_name,
                "disassemblyBytes": len(stdout),
                "disassemblySha256": _sha256(stdout),
                "stderrFile": stderr_name,
                "stderrBytes": len(stderr),
                "stderrSha256": _sha256(stderr),
            }
        )

    return {
        "format": "t6-dxbc-disassembly-archive-v1",
        "source": {
            "dxbcManifestFormat": dxbc_manifest.get("format"),
            "shaderRoot": str(shader_root),
        },
        "disassembler": exe_record,
        "policy": {
            "inputVerification": "exact byte count + SHA-256 from DXBC manifest",
            "stdout": "retained byte-for-byte as disassembly artifact",
            "stderr": "retained when non-empty",
            "semanticInterpretation": "none; disassembly is evidence for later analysis",
        },
        "stats": {
            "disassembledPixelShaderCount": len(results),
            "inputPixelShaderCount": len(dxbc_manifest.get("pixelShaders", [])),
        },
        "shaders": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dxbc_manifest_json", type=Path)
    parser.add_argument("--shader-root", type=Path, required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--tool-kind", choices=("fxc", "dxc"), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--out-manifest", type=Path, required=True)
    args = parser.parse_args()
    dxbc_manifest = json.loads(args.dxbc_manifest_json.read_text(encoding="utf-8"))
    doc = disassemble_manifest(
        dxbc_manifest,
        shader_root=args.shader_root,
        executable=args.tool,
        tool_kind=args.tool_kind,
        output_dir=args.out_dir,
    )
    args.out_manifest.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.out_manifest), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
