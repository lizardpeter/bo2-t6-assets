#!/usr/bin/env python3
"""Build an exact T6 lightmap pixel-shader provenance/disassembly worklist.

Consumes stock OpenAssetTools T6 output:

  materials/**/*.json
    -> techniqueSet
  techsets/<name>.techset
    -> technique names
  techniques/<name>.tech
    -> per-pass pixelShader + sampler bindings
  shader_bin/ps_<shader-name>.cso
    -> exact retail DXBC bytes

Only pixel-shader blocks that explicitly mention the T6 code sampler accessors
`lightmapSamplerPrimary` and/or `lightmapSamplerSecondary` are selected.
Sampler mentions inside OAT debug comments count: an exact-accessor assignment is
normally omitted by the dumper because the shader resource already has the same
name, and the comment is therefore evidence of the binding.

This tool inventories and hashes bytecode. It does NOT interpret shader
instructions or assign primary/secondary channel meaning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


class LightmapShaderInventoryError(RuntimeError):
    pass


PIXEL_SHADER_RE = re.compile(r'^\s*pixelShader\s+(\d+)\.(\d+)\s+"([^"]+)"\s*$')
TECHSET_TYPE_RE = re.compile(r'^\s*"([^"]+)"\s*:\s*$')
TECHSET_VALUE_RE = re.compile(r'^\s*([^;\s][^;]*?)\s*;\s*$')
PRIMARY = "lightmapSamplerPrimary"
SECONDARY = "lightmapSamplerSecondary"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative_identity(value: str, kind: str) -> str:
    if not value or value in (".", "..") or "\0" in value:
        raise LightmapShaderInventoryError(f"invalid {kind} identity {value!r}")
    p = Path(value)
    if p.is_absolute() or any(part == ".." for part in p.parts):
        raise LightmapShaderInventoryError(f"unsafe {kind} identity {value!r}")
    return value.replace("\\", "/")


def _read_text(path: Path, kind: str) -> str:
    if not path.is_file():
        raise LightmapShaderInventoryError(f"missing exact {kind} file {path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise LightmapShaderInventoryError(f"invalid UTF-8 {kind} file {path}") from exc


def parse_techset(text: str) -> list[dict]:
    """Parse OAT's simple technique-set mapping while preserving type aliases."""
    current_types: list[str] = []
    techniques: list[dict] = []
    seen: dict[str, int] = {}
    for line in text.splitlines():
        type_match = TECHSET_TYPE_RE.match(line)
        if type_match:
            current_types.append(type_match.group(1))
            continue
        value_match = TECHSET_VALUE_RE.match(line)
        if not value_match:
            if line.strip():
                raise LightmapShaderInventoryError(
                    f"unrecognized techset line {line!r}"
                )
            continue
        name = _safe_relative_identity(value_match.group(1).strip(), "technique")
        if not current_types:
            raise LightmapShaderInventoryError(
                f"technique value {name!r} has no preceding technique type"
            )
        if name in seen:
            techniques[seen[name]]["techniqueTypes"].extend(current_types)
        else:
            seen[name] = len(techniques)
            techniques.append(
                {"technique": name, "techniqueTypes": list(current_types)}
            )
        current_types = []
    if current_types:
        raise LightmapShaderInventoryError(
            f"techset ended with technique types lacking a value: {current_types!r}"
        )
    return techniques


def _extract_braced_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """Return lines inside the block opened at/after start and next line index."""
    depth = 0
    opened = False
    body: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        opens = line.count("{")
        closes = line.count("}")
        if not opened:
            if opens:
                opened = True
                depth += opens - closes
                if depth <= 0:
                    return [], i + 1
            i += 1
            continue
        new_depth = depth + opens - closes
        if new_depth < 0:
            raise LightmapShaderInventoryError("malformed technique braces")
        if new_depth == 0:
            return body, i + 1
        body.append(line)
        depth = new_depth
        i += 1
    raise LightmapShaderInventoryError("unterminated technique block")


def parse_lightmap_pixel_shaders(text: str) -> list[dict]:
    """Return per-pixel-shader blocks that reference either T6 lightmap sampler."""
    lines = text.splitlines()
    found: list[dict] = []
    i = 0
    pass_index = -1
    depth = 0
    while i < len(lines):
        stripped = lines[i].strip()
        # Top-level pass blocks are the only bare opening braces emitted by OAT.
        if stripped == "{" and depth == 0:
            pass_index += 1
            depth = 1
            i += 1
            continue
        if stripped == "}" and depth == 1:
            depth = 0
            i += 1
            continue

        match = PIXEL_SHADER_RE.match(lines[i])
        if match:
            if depth != 1:
                raise LightmapShaderInventoryError(
                    f"pixelShader outside a pass at line {i + 1}"
                )
            body, next_i = _extract_braced_block(lines, i + 1)
            joined = "\n".join(body)
            uses_primary = PRIMARY in joined
            uses_secondary = SECONDARY in joined
            if uses_primary or uses_secondary:
                found.append(
                    {
                        "passIndex": pass_index,
                        "shaderModel": f"{match.group(1)}.{match.group(2)}",
                        "pixelShader": _safe_relative_identity(match.group(3), "pixel shader"),
                        "usesPrimary": uses_primary,
                        "usesSecondary": uses_secondary,
                        "samplers": [
                            name
                            for name, used in (
                                (PRIMARY, uses_primary),
                                (SECONDARY, uses_secondary),
                            )
                            if used
                        ],
                    }
                )
            i = next_i
            continue

        # Track nested shader braces only enough to preserve pass depth.
        depth += lines[i].count("{") - lines[i].count("}")
        if depth < 0:
            raise LightmapShaderInventoryError("malformed technique brace depth")
        i += 1
    return found


def _material_index(material_root: Path) -> list[dict]:
    if not material_root.is_dir():
        raise LightmapShaderInventoryError(
            f"material root is not a directory: {material_root}"
        )
    result: list[dict] = []
    for path in sorted(material_root.rglob("*.json")):
        raw = path.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise LightmapShaderInventoryError(f"invalid material JSON {path}: {exc}") from exc
        if doc.get("_game") != "t6" or doc.get("_type") != "material":
            continue
        identity = path.relative_to(material_root).with_suffix("").as_posix()
        techset = str(doc.get("techniqueSet") or "")
        if not techset:
            continue
        result.append(
            {
                "material": identity,
                "materialFile": path.relative_to(material_root).as_posix(),
                "materialBytes": len(raw),
                "materialSha256": _sha256(raw),
                "techniqueSet": _safe_relative_identity(techset, "technique set"),
            }
        )
    return result


def build_inventory(
    *,
    material_root: Path,
    techset_root: Path,
    technique_root: Path,
    shader_root: Path,
    allow_missing_shaders: bool = False,
) -> dict:
    materials = _material_index(material_root)
    techset_cache: dict[str, tuple[bytes, list[dict]]] = {}
    technique_cache: dict[str, tuple[bytes, list[dict]]] = {}
    shader_cache: dict[str, dict] = {}
    selected: list[dict] = []
    missing: list[dict] = []

    for material in materials:
        ts_name = material["techniqueSet"]
        if ts_name not in techset_cache:
            ts_path = techset_root / f"{ts_name}.techset"
            ts_raw = _read_text(ts_path, "techset").encode("utf-8")
            techset_cache[ts_name] = (ts_raw, parse_techset(ts_raw.decode("utf-8")))
        ts_raw, mappings = techset_cache[ts_name]

        for mapping in mappings:
            tech_name = mapping["technique"]
            if tech_name not in technique_cache:
                tech_path = technique_root / f"{tech_name}.tech"
                tech_text = _read_text(tech_path, "technique")
                tech_raw = tech_text.encode("utf-8")
                technique_cache[tech_name] = (
                    tech_raw,
                    parse_lightmap_pixel_shaders(tech_text),
                )
            tech_raw, shaders = technique_cache[tech_name]
            for shader_use in shaders:
                shader_name = shader_use["pixelShader"]
                if shader_name not in shader_cache:
                    shader_path = shader_root / f"ps_{shader_name}.cso"
                    if not shader_path.is_file():
                        item = {
                            "pixelShader": shader_name,
                            "path": str(shader_path),
                        }
                        missing.append(item)
                        if not allow_missing_shaders:
                            raise LightmapShaderInventoryError(
                                f"missing exact T6 pixel shader {shader_path}"
                            )
                        shader_cache[shader_name] = {
                            "pixelShader": shader_name,
                            "file": shader_path.name,
                            "path": str(shader_path),
                            "present": False,
                        }
                    else:
                        shader_raw = shader_path.read_bytes()
                        if len(shader_raw) < 4 or shader_raw[:4] != b"DXBC":
                            raise LightmapShaderInventoryError(
                                f"T6 pixel shader is not a DXBC container: {shader_path}"
                            )
                        shader_cache[shader_name] = {
                            "pixelShader": shader_name,
                            "file": shader_path.name,
                            "path": str(shader_path),
                            "present": True,
                            "bytes": len(shader_raw),
                            "sha256": _sha256(shader_raw),
                            "magic": "DXBC",
                        }

                selected.append(
                    {
                        **material,
                        "techsetFile": f"{ts_name}.techset",
                        "techsetBytes": len(ts_raw),
                        "techsetSha256": _sha256(ts_raw),
                        "technique": tech_name,
                        "techniqueTypes": list(mapping["techniqueTypes"]),
                        "techniqueFile": f"{tech_name}.tech",
                        "techniqueBytes": len(tech_raw),
                        "techniqueSha256": _sha256(tech_raw),
                        **shader_use,
                        "shader": shader_cache[shader_name],
                    }
                )

    # Collapse exact duplicate provenance edges caused by multiple material
    # records reaching the same technique/pass through aliases only if every
    # identifying field matches; retain per-material edges otherwise.
    selected.sort(
        key=lambda x: (
            x["material"],
            x["techniqueSet"],
            x["technique"],
            int(x["passIndex"]),
            x["pixelShader"],
        )
    )
    unique_shader_names = sorted({item["pixelShader"] for item in selected})
    both = sum(1 for item in selected if item["usesPrimary"] and item["usesSecondary"])
    primary_only = sum(1 for item in selected if item["usesPrimary"] and not item["usesSecondary"])
    secondary_only = sum(1 for item in selected if item["usesSecondary"] and not item["usesPrimary"])

    return {
        "format": "t6-lightmap-shader-inventory-v1",
        "source": {
            "kind": "stock OpenAssetTools T6 material/techset/technique/shader dump",
            "oatCommit": "7d027e8f89118196713e955b0e11f8404149c54d",
            "materialRoot": str(material_root),
            "techsetRoot": str(techset_root),
            "techniqueRoot": str(technique_root),
            "shaderRoot": str(shader_root),
            "pixelShaderDiskRule": "shader_bin/ps_<MaterialPixelShader.name>.cso",
            "pixelShaderBytes": "exact prog.loadDef.program[0:programSize] for T6 DX11",
        },
        "policy": {
            "selection": (
                "pixelShader block must explicitly contain lightmapSamplerPrimary and/or lightmapSamplerSecondary"
            ),
            "oatMatchingAccessorCommentsCountAsBindings": True,
            "shaderContainerMagic": "DXBC",
            "instructionSemantics": "not interpreted by this inventory",
            "primarySecondaryChannelMeaning": "not inferred",
        },
        "stats": {
            "materialCount": len(materials),
            "techsetCount": len(techset_cache),
            "techniqueCount": len(technique_cache),
            "selectedProvenanceEdgeCount": len(selected),
            "uniqueLightmapPixelShaderCount": len(unique_shader_names),
            "primaryAndSecondaryEdgeCount": both,
            "primaryOnlyEdgeCount": primary_only,
            "secondaryOnlyEdgeCount": secondary_only,
            "missingPixelShaderCount": len({item["pixelShader"] for item in missing}),
        },
        "uniqueLightmapPixelShaders": [shader_cache[name] for name in unique_shader_names],
        "provenance": selected,
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--material-root", type=Path, required=True)
    parser.add_argument("--techset-root", type=Path, required=True)
    parser.add_argument("--technique-root", type=Path, required=True)
    parser.add_argument("--shader-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-missing-shaders", action="store_true")
    args = parser.parse_args()
    doc = build_inventory(
        material_root=args.material_root,
        techset_root=args.techset_root,
        technique_root=args.technique_root,
        shader_root=args.shader_root,
        allow_missing_shaders=args.allow_missing_shaders,
    )
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.write_text(payload, encoding="utf-8")
    print(json.dumps({"out": str(args.out), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
