#!/usr/bin/env python3
"""Exact T6 OAT TechniqueSet slot -> pixel-shader bytecode resolver.

OpenAssetTools' T6 TechniqueSet dumper writes four linked artifact classes:

    techsets/<TechniqueSet>.techset
      -> techniques/<Technique>.tech
      -> pixelShader 4.0 "<PixelShader>"
      -> shader_bin/ps_<PixelShader>.cso

For T6/DX11 the dumped .cso payload is the exact ``prog.loadDef.program`` byte
range of length ``prog.loadDef.programSize``.  This module deliberately resolves
that chain by asset identity and hashes the exact emitted bytes; it does not
infer a shader from a compound material name.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path


TECHNIQUE_TYPE_NAMES = (
    "depth prepass",
    "build shadowmap depth",
    "unlit",
    "emissive",
    "lit",
    "lit sun",
    "lit sun shadow",
    "lit spot",
    "lit spot shadow",
    "lit spot square",
    "lit spot square shadow",
    "lit spot round",
    "lit spot round shadow",
    "lit omni",
    "lit omni shadow",
    "lit dlight glight",
    "lit sun dlight glight",
    "lit sun shadow dlight glight",
    "lit spot dlight glight",
    "lit spot shadow dlight glight",
    "lit spot square dlight glight",
    "lit spot square shadow dlight glight",
    "lit spot round dlight glight",
    "lit spot round shadow dlight glight",
    "lit omni dlight glight",
    "lit omni shadow dlight glight",
    "light spot",
    "light omni",
    "fakelight normal",
    "fakelight view",
    "sunlight preview",
    "case texture",
    "solid wireframe",
    "shaded wireframe",
    "debug bumpmap",
    "debug performance",
)

SLOT_LABEL_RE = re.compile(r'^\s*"([^"]+)"\s*:\s*(?://.*)?$')
SLOT_REF_RE = re.compile(r'^\s+([^;{}]+?)\s*;\s*(?://.*)?$')
PIXEL_RE = re.compile(r'\bpixelShader\s+\d+\.\d+\s+"([^"]+)"')


class OatSlotShaderError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_asset_path(root: Path, prefix: str, asset: str, suffix: str) -> Path:
    """Resolve OAT's literal asset-name filename rule without path escape."""
    if not asset or "\x00" in asset:
        raise OatSlotShaderError(f"invalid empty/NUL asset identity {asset!r}")
    root = root.resolve()
    candidate = (root / f"{prefix}{asset}{suffix}").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise OatSlotShaderError(f"asset identity escapes OAT root: {asset!r}") from exc
    return candidate


def parse_techset_slots(text: str) -> dict[str, str]:
    """Parse OAT's quoted technique-type label + indented asset reference grammar."""
    slots: dict[str, str] = {}
    pending: str | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("//"):
            continue
        label = SLOT_LABEL_RE.match(raw)
        if label:
            if pending is not None:
                raise OatSlotShaderError(
                    f"techset slot {pending!r} has no technique reference before line {lineno}"
                )
            pending = label.group(1)
            if pending in slots:
                raise OatSlotShaderError(f"duplicate techset slot label {pending!r}")
            continue
        ref = SLOT_REF_RE.match(raw)
        if ref and pending is not None:
            value = ref.group(1).strip()
            if not value or any(ch in value for ch in ('"', "'", "=", "{", "}")):
                raise OatSlotShaderError(
                    f"invalid technique asset reference for slot {pending!r}: {value!r}"
                )
            if value.endswith(".tech"):
                value = value[:-5]
            slots[pending] = value
            pending = None
            continue
        raise OatSlotShaderError(f"unrecognized .techset line {lineno}: {raw!r}")
    if pending is not None:
        raise OatSlotShaderError(f"techset slot {pending!r} has no technique reference at EOF")
    return slots


def pixel_shader_assets(text: str) -> list[str]:
    """Return ordered unique pixel-shader asset identities from an OAT .tech file."""
    out: list[str] = []
    seen: set[str] = set()
    for name in PIXEL_RE.findall(text):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def resolve_slot_shader(
    oat_root: Path,
    technique_set: str,
    *,
    slot_index: int = 4,
    require_single_pixel_shader: bool = True,
) -> dict:
    """Resolve one exact T6 technique slot through to its dumped shader bytes."""
    if not 0 <= slot_index < len(TECHNIQUE_TYPE_NAMES):
        raise OatSlotShaderError(f"T6 technique slot out of range: {slot_index}")
    root = Path(oat_root)
    if not root.is_dir():
        raise OatSlotShaderError(f"OAT root is not a directory: {root}")
    label = TECHNIQUE_TYPE_NAMES[slot_index]

    techset_path = _safe_asset_path(root / "techsets", "", technique_set, ".techset")
    if not techset_path.is_file():
        raise OatSlotShaderError(
            f"missing exact OAT TechniqueSet for {technique_set!r}: {techset_path}"
        )
    slots = parse_techset_slots(techset_path.read_text(encoding="utf-8", errors="strict"))
    technique_asset = slots.get(label)
    if not technique_asset:
        raise OatSlotShaderError(
            f"TechniqueSet {technique_set!r} has no T6 slot {slot_index} ({label!r})"
        )

    technique_path = _safe_asset_path(root / "techniques", "", technique_asset, ".tech")
    if not technique_path.is_file():
        raise OatSlotShaderError(
            f"missing exact OAT technique {technique_asset!r}: {technique_path}"
        )
    technique_text = technique_path.read_text(encoding="utf-8", errors="strict")
    shader_assets = pixel_shader_assets(technique_text)
    if not shader_assets:
        raise OatSlotShaderError(
            f"slot {slot_index} technique {technique_asset!r} has no pixelShader declaration"
        )
    if require_single_pixel_shader and len(shader_assets) != 1:
        raise OatSlotShaderError(
            f"slot {slot_index} technique {technique_asset!r} resolves to "
            f"{len(shader_assets)} unique pixel shaders, expected exactly one"
        )

    shaders: list[dict] = []
    for shader_asset in shader_assets:
        shader_path = _safe_asset_path(root / "shader_bin", "ps_", shader_asset, ".cso")
        if not shader_path.is_file():
            raise OatSlotShaderError(
                f"missing exact OAT pixel shader {shader_asset!r}: {shader_path}"
            )
        data = shader_path.read_bytes()
        if not data:
            raise OatSlotShaderError(f"empty OAT pixel shader payload: {shader_path}")
        shaders.append({
            "asset": shader_asset,
            "relativeFile": shader_path.relative_to(root.resolve()).as_posix(),
            "bytes": len(data),
            "sha256": _sha256(data),
        })

    return {
        "techniqueSet": technique_set,
        "slotIndex": slot_index,
        "slotLabel": label,
        "techsetFile": techset_path.relative_to(root.resolve()).as_posix(),
        "techniqueAsset": technique_asset,
        "techniqueFile": technique_path.relative_to(root.resolve()).as_posix(),
        "pixelShaders": shaders,
        "proof": (
            "Exact OAT T6 TechniqueSet slot -> technique -> pixelShader asset -> "
            "verbatim DX11 shader_bin payload; no material-name shader inference"
        ),
    }
