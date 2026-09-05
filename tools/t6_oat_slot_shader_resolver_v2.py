#!/usr/bin/env python3
"""Exact T6 OAT TechniqueSet slot -> vertex/pixel shader payload resolver v2.

v1 closed the slot -> technique -> pixelShader -> verbatim DX11 bytecode chain.
v2 retains that contract and additionally resolves every unique ``vertexShader``
asset declared by the same exact OAT ``.tech`` pass file to
``shader_bin/vs_<asset>.cso``.

No shader is inferred from a TechniqueSet or material name. The textual OAT
asset references are the join keys and the emitted CSO bytes are hashed exactly.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import t6_oat_slot_shader_resolver_v1 as v1


VERTEX_RE = re.compile(r'\bvertexShader\s+\d+\.\d+\s+"([^"]+)"')


class OatSlotShaderV2Error(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def vertex_shader_assets(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for name in VERTEX_RE.findall(text):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _shader_record(root: Path, prefix: str, asset: str, stage: str) -> dict:
    path = v1._safe_asset_path(root / "shader_bin", prefix, asset, ".cso")
    if not path.is_file():
        raise OatSlotShaderV2Error(
            f"missing exact OAT {stage} shader {asset!r}: {path}"
        )
    data = path.read_bytes()
    if not data:
        raise OatSlotShaderV2Error(f"empty OAT {stage} shader payload: {path}")
    return {
        "asset": asset,
        "relativeFile": path.relative_to(root.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": _sha256(data),
    }


def resolve_slot_shaders(
    oat_root: Path,
    technique_set: str,
    *,
    slot_index: int = 4,
    require_single_vertex_shader: bool = True,
    require_single_pixel_shader: bool = True,
) -> dict:
    base = v1.resolve_slot_shader(
        oat_root,
        technique_set,
        slot_index=slot_index,
        require_single_pixel_shader=require_single_pixel_shader,
    )
    root = Path(oat_root)
    technique_path = root / base["techniqueFile"]
    technique_text = technique_path.read_text(encoding="utf-8", errors="strict")
    assets = vertex_shader_assets(technique_text)
    if not assets:
        raise OatSlotShaderV2Error(
            f"slot {slot_index} technique {base['techniqueAsset']!r} has no vertexShader declaration"
        )
    if require_single_vertex_shader and len(assets) != 1:
        raise OatSlotShaderV2Error(
            f"slot {slot_index} technique {base['techniqueAsset']!r} resolves to "
            f"{len(assets)} unique vertex shaders, expected exactly one"
        )
    vertex = [_shader_record(root, "vs_", asset, "vertex") for asset in assets]
    return {
        **base,
        "vertexShaders": vertex,
        "proof": (
            "Exact OAT T6 TechniqueSet slot -> technique -> vertexShader/pixelShader asset -> "
            "verbatim DX11 shader_bin payloads; no material/TechniqueSet-name shader inference"
        ),
    }
