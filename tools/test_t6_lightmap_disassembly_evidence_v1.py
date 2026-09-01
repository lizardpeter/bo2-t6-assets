#!/usr/bin/env python3
"""Regression for exact T6 lightmap disassembly instruction-context extraction."""
from __future__ import annotations

import copy
import hashlib
import tempfile
from pathlib import Path

from t6_lightmap_disassembly_evidence_v1 import (
    LightmapDisassemblyEvidenceError,
    build_evidence,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dxbc_manifest() -> dict:
    return {
        "format": "t6-lightmap-shader-dxbc-manifest-v1",
        "provenance": [
            {
                "material": "wpc/wall",
                "techniqueSet": "world",
                "technique": "world_lm",
                "techniqueTypes": ["lit"],
                "passIndex": 0,
                "pixelShader": "world_lm",
                "shaderModel": "4.0",
                "shaderPresent": True,
                "resolvedLightmapBindings": [
                    {
                        "codeSampler": "lightmapSamplerPrimary",
                        "shaderResource": "lmP",
                        "textureRegister": "t3",
                        "bindPoint": 3,
                        "bindCount": 1,
                        "returnType": "FLOAT",
                        "dimension": "TEXTURE2D",
                        "rdefResourceIndex": 0,
                    },
                    {
                        "codeSampler": "lightmapSamplerSecondary",
                        "shaderResource": "lmS",
                        "textureRegister": "t7",
                        "bindPoint": 7,
                        "bindCount": 1,
                        "returnType": "FLOAT",
                        "dimension": "TEXTURE2D",
                        "rdefResourceIndex": 1,
                    },
                ],
            }
        ],
    }


def _expect_error(fn, needle: str) -> None:
    try:
        fn()
    except LightmapDisassemblyEvidenceError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r} in {str(exc)!r}") from exc
    else:
        raise AssertionError(
            f"expected LightmapDisassemblyEvidenceError containing {needle!r}"
        )


def main() -> int:
    text = b'''// ps_4_0\n// Resource Bindings:\ndcl_resource_texture2d (float,float,float,float) t3\ndcl_resource_texture2d (float,float,float,float) t7\ndcl_sampler s0\ndcl_sampler s1\nsample r0.xyzw, v0.xyxx, t3.xyzw, s0\nmul r1.xyz, r0.xyzx, cb0[0].xyzx\nsample_l r2.xyzw, v0.xyxx, t7.xyzw, s1, l(0.000000)\nmad r0.xyz, r2.wwww, r1.xyzx, r2.xyzx\nret\n'''
    archive = {
        "format": "t6-dxbc-disassembly-archive-v1",
        "disassembler": {"kind": "fxc", "sha256": "toolhash"},
        "shaders": [
            {
                "pixelShader": "world_lm",
                "shaderSha256": "shaderhash",
                "disassemblyFile": "ps_world_lm.fxc.dumpbin.txt",
                "disassemblyBytes": len(text),
                "disassemblySha256": _sha256(text),
            }
        ],
    }

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "ps_world_lm.fxc.dumpbin.txt").write_bytes(text)
        doc = build_evidence(
            _dxbc_manifest(),
            archive,
            disassembly_root=root,
            context_lines=1,
            require_executable_use=True,
        )
        assert doc["format"] == "t6-lightmap-disassembly-evidence-v1"
        assert doc["stats"] == {
            "provenanceEdgeCount": 1,
            "uniqueRegisterReferenceCount": 4,
            "executableReferenceCount": 2,
            "samplingInstructionCount": 2,
            "bindingsWithoutExecutableUseCount": 0,
        }
        edge = doc["provenance"][0]
        primary, secondary = edge["bindings"]
        assert primary["referenceCount"] == 2
        assert primary["declarationReferenceCount"] == 1
        assert primary["executableReferenceCount"] == 1
        assert primary["samplingInstructionCount"] == 1
        assert primary["references"][0]["opcode"] == "dcl_resource_texture2d"
        assert primary["references"][0]["isDeclaration"] is True
        assert primary["references"][1]["opcode"] == "sample"
        assert primary["references"][1]["isSamplingInstruction"] is True
        assert primary["references"][1]["textureReferences"] == [
            {"bindPoint": 3, "textureRegister": "t3", "swizzle": "xyzw"}
        ]
        assert secondary["references"][1]["opcode"] == "sample_l"
        assert secondary["references"][1]["lineNumber"] == 9
        assert secondary["references"][1]["contextStartLine"] == 8
        assert secondary["references"][1]["contextEndLine"] == 10
        assert doc["bindingsWithoutExecutableUse"] == []

        # Deterministic output.
        doc2 = build_evidence(
            copy.deepcopy(_dxbc_manifest()),
            copy.deepcopy(archive),
            disassembly_root=root,
            context_lines=1,
            require_executable_use=True,
        )
        import json
        assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
            doc2, sort_keys=True, separators=(",", ":")
        )

        # Changed disassembly is rejected from its archive hash.
        path = root / "ps_world_lm.fxc.dumpbin.txt"
        path.write_bytes(text + b"// changed\n")
        _expect_error(
            lambda: build_evidence(
                _dxbc_manifest(), archive, disassembly_root=root
            ),
            "disassembly artifact changed",
        )
        path.write_bytes(text)

        # Declaration-only binding is recorded but can be required to fail.
        declaration_only = text.replace(
            b"sample r0.xyzw, v0.xyxx, t3.xyzw, s0\n",
            b"mov r0.xyzw, l(1,1,1,1)\n",
        )
        path.write_bytes(declaration_only)
        declaration_archive = copy.deepcopy(archive)
        declaration_archive["shaders"][0]["disassemblyBytes"] = len(declaration_only)
        declaration_archive["shaders"][0]["disassemblySha256"] = _sha256(declaration_only)
        relaxed = build_evidence(
            _dxbc_manifest(), declaration_archive, disassembly_root=root
        )
        assert relaxed["stats"]["bindingsWithoutExecutableUseCount"] == 1
        assert relaxed["bindingsWithoutExecutableUse"][0]["codeSampler"] == "lightmapSamplerPrimary"
        _expect_error(
            lambda: build_evidence(
                _dxbc_manifest(),
                declaration_archive,
                disassembly_root=root,
                require_executable_use=True,
            ),
            "no executable disassembly reference",
        )

        _expect_error(
            lambda: build_evidence(
                _dxbc_manifest(),
                declaration_archive,
                disassembly_root=root,
                context_lines=51,
            ),
            "context_lines outside",
        )

    print("PASS t6_lightmap_disassembly_evidence_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
