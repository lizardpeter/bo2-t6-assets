#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import t6_oat_slot_shader_resolver_v2 as resolver


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_oat_slot_v2_") as td:
        root = Path(td)
        for name in ("techsets", "techniques", "shader_bin"):
            (root / name).mkdir()
        techset = "lit_sm_fixture"
        technique = "fixture_lit"
        vs = "fixture_vs"
        ps = "fixture_ps"
        (root / "techsets" / f"{techset}.techset").write_text(
            '"lit":\n  fixture_lit;\n', encoding="utf-8"
        )
        (root / "techniques" / f"{technique}.tech").write_text(
            '{\n'
            f'  vertexShader 4.0 "{vs}"\n'
            f'  pixelShader 4.0 "{ps}"\n'
            '  {\n  }\n'
            '}\n',
            encoding="utf-8",
        )
        vs_bytes = b"DXBC-vertex-fixture"
        ps_bytes = b"DXBC-pixel-fixture"
        (root / "shader_bin" / f"vs_{vs}.cso").write_bytes(vs_bytes)
        (root / "shader_bin" / f"ps_{ps}.cso").write_bytes(ps_bytes)

        doc = resolver.resolve_slot_shaders(root, techset, slot_index=4)
        assert doc["slotLabel"] == "lit"
        assert doc["techniqueAsset"] == technique
        assert len(doc["vertexShaders"]) == 1
        assert len(doc["pixelShaders"]) == 1
        assert doc["vertexShaders"][0]["asset"] == vs
        assert doc["vertexShaders"][0]["sha256"] == hashlib.sha256(vs_bytes).hexdigest()
        assert doc["pixelShaders"][0]["asset"] == ps
        assert doc["pixelShaders"][0]["sha256"] == hashlib.sha256(ps_bytes).hexdigest()

        # Multiple unique VS declarations are an ambiguity in the simple
        # slot-level owner contract and must fail unless a caller explicitly
        # asks to inspect a multi-pass technique.
        (root / "techniques" / f"{technique}.tech").write_text(
            '{\n'
            '  vertexShader 4.0 "fixture_vs"\n'
            '  pixelShader 4.0 "fixture_ps"\n'
            '}\n'
            '{\n'
            '  vertexShader 4.0 "fixture_vs_alt"\n'
            '  pixelShader 4.0 "fixture_ps"\n'
            '}\n',
            encoding="utf-8",
        )
        (root / "shader_bin" / "vs_fixture_vs_alt.cso").write_bytes(b"DXBC-alt-vs")
        try:
            resolver.resolve_slot_shaders(root, techset, slot_index=4)
        except resolver.OatSlotShaderV2Error as exc:
            assert "2 unique vertex shaders" in str(exc)
        else:
            raise AssertionError("ambiguous slot vertex-shader population was accepted")

    print("PASS: exact T6 OAT slot vertex+pixel shader resolver v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
