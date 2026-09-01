#!/usr/bin/env python3
"""Regression for T6 DXBC external-disassembler archival stage."""
from __future__ import annotations

import copy
import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace

import t6_dxbc_disassemble_v1 as dis
from t6_dxbc_disassemble_v1 import DxbcDisassembleError, build_command, disassemble_manifest


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest(shader: bytes) -> dict:
    return {
        "format": "t6-lightmap-shader-dxbc-manifest-v1",
        "pixelShaders": [
            {
                "pixelShader": "world_lm",
                "file": "ps_world_lm.cso",
                "present": True,
                "bytes": len(shader),
                "sha256": _sha256(shader),
            }
        ],
    }


def _expect_error(fn, needle: str) -> None:
    try:
        fn()
    except DxbcDisassembleError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r} in {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected DxbcDisassembleError containing {needle!r}")


def main() -> int:
    assert build_command("fxc", Path("C:/fxc.exe"), Path("x.cso")) == [
        "C:/fxc.exe", "/dumpbin", "x.cso"
    ]
    assert build_command("dxc", Path("C:/dxc.exe"), Path("x.cso")) == [
        "C:/dxc.exe", "-dumpbin", "x.cso"
    ]
    _expect_error(
        lambda: build_command("other", Path("x.exe"), Path("x.cso")),
        "unsupported disassembler kind",
    )

    shader = b"DXBC" + b"shader-fixture"
    stdout = b"// ps_4_0\n// Resource Bindings:\n// lmP texture t3\nsample r0.xyzw, v0.xyxx, t3.xyzw, s1\n"
    stderr = b"fixture warning\n"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        shader_root = root / "shaders"
        output_dir = root / "out"
        shader_root.mkdir()
        tool = root / "fxc.exe"
        tool.write_bytes(b"fake-fxc-binary")
        (shader_root / "ps_world_lm.cso").write_bytes(shader)
        manifest = _manifest(shader)

        original_run = dis.subprocess.run
        calls = []
        try:
            def fake_run(command, stdout=None, stderr=None, check=None):
                calls.append(list(command))
                return SimpleNamespace(returncode=0, stdout=globals()["stdout"], stderr=globals()["stderr"])

            dis.subprocess.run = fake_run
            doc = disassemble_manifest(
                manifest,
                shader_root=shader_root,
                executable=tool,
                tool_kind="fxc",
                output_dir=output_dir,
            )
        finally:
            dis.subprocess.run = original_run

        assert calls == [[str(tool), "/dumpbin", str(shader_root / "ps_world_lm.cso")]]
        assert doc["format"] == "t6-dxbc-disassembly-archive-v1"
        assert doc["disassembler"]["kind"] == "fxc"
        assert doc["disassembler"]["sha256"] == _sha256(tool.read_bytes())
        assert doc["stats"] == {
            "disassembledPixelShaderCount": 1,
            "inputPixelShaderCount": 1,
        }
        item = doc["shaders"][0]
        assert item["shaderSha256"] == _sha256(shader)
        assert item["disassemblySha256"] == _sha256(stdout)
        assert item["stderrSha256"] == _sha256(stderr)
        assert (output_dir / item["disassemblyFile"]).read_bytes() == stdout
        assert (output_dir / item["stderrFile"]).read_bytes() == stderr

        # Changed shader bytes are caught before invoking the external tool.
        (shader_root / "ps_world_lm.cso").write_bytes(shader + b"changed")
        _expect_error(
            lambda: disassemble_manifest(
                manifest,
                shader_root=shader_root,
                executable=tool,
                tool_kind="fxc",
                output_dir=output_dir,
            ),
            "no longer matches DXBC manifest",
        )
        (shader_root / "ps_world_lm.cso").write_bytes(shader)

        # Nonzero exit code and empty stdout both fail closed.
        try:
            dis.subprocess.run = lambda *a, **k: SimpleNamespace(
                returncode=2, stdout=b"", stderr=b"failure"
            )
            _expect_error(
                lambda: disassemble_manifest(
                    manifest,
                    shader_root=shader_root,
                    executable=tool,
                    tool_kind="fxc",
                    output_dir=output_dir,
                ),
                "exit code 2",
            )

            dis.subprocess.run = lambda *a, **k: SimpleNamespace(
                returncode=0, stdout=b"\r\n", stderr=b""
            )
            _expect_error(
                lambda: disassemble_manifest(
                    manifest,
                    shader_root=shader_root,
                    executable=tool,
                    tool_kind="dxc",
                    output_dir=output_dir,
                ),
                "empty disassembly",
            )
        finally:
            dis.subprocess.run = original_run

        missing_tool = root / "missing.exe"
        _expect_error(
            lambda: disassemble_manifest(
                manifest,
                shader_root=shader_root,
                executable=missing_tool,
                tool_kind="fxc",
                output_dir=output_dir,
            ),
            "does not exist",
        )

        bad_format = copy.deepcopy(manifest)
        bad_format["format"] = "wrong"
        _expect_error(
            lambda: disassemble_manifest(
                bad_format,
                shader_root=shader_root,
                executable=tool,
                tool_kind="fxc",
                output_dir=output_dir,
            ),
            "unsupported DXBC manifest",
        )

    print("PASS t6_dxbc_disassemble_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
