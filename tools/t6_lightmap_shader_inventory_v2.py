#!/usr/bin/env python3
"""T6 lightmap shader inventory v2: preserve code-sampler -> shader-resource mapping.

v1 proves the stock OAT Material -> Techset -> Technique -> pixel shader chain
and selects passes that reference T6 lightmap code samplers. v2 additionally
records the destination shader resource accessor from each OAT technique line:

    <shaderResource> = sampler.lightmapSamplerPrimary;
    <shaderResource> = sampler.lightmapSamplerSecondary;

The OAT debug form

    // Omitted due to matching accessors: lightmapSamplerPrimary = sampler.lightmapSamplerPrimary;

is parsed identically. This destination name is the exact bridge to the DXBC
RDEF bound-resource table and therefore to a texture bind point t#.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from t6_lightmap_shader_inventory_v1 import (
    LightmapShaderInventoryError,
    PIXEL_SHADER_RE,
    _extract_braced_block,
    _safe_relative_identity,
    build_inventory as build_inventory_v1,
)


SAMPLER_BIND_RE = re.compile(
    r'([A-Za-z_][A-Za-z0-9_\[\]\.]*?)\s*=\s*sampler\.'
    r'(lightmapSamplerPrimary|lightmapSamplerSecondary)\s*;'
)


def parse_lightmap_pixel_shaders_v2(text: str) -> list[dict]:
    lines = text.splitlines()
    found: list[dict] = []
    i = 0
    pass_index = -1
    depth = 0
    while i < len(lines):
        stripped = lines[i].strip()
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
            bindings: list[dict] = []
            for body_line in body:
                for binding_match in SAMPLER_BIND_RE.finditer(body_line):
                    resource = binding_match.group(1)
                    code_sampler = binding_match.group(2)
                    bindings.append(
                        {
                            "codeSampler": code_sampler,
                            "shaderResource": resource,
                            "sourceLine": body_line.strip(),
                        }
                    )
            if bindings:
                dedup: list[dict] = []
                seen: set[tuple[str, str]] = set()
                for binding in bindings:
                    key = (binding["codeSampler"], binding["shaderResource"])
                    if key not in seen:
                        seen.add(key)
                        dedup.append(binding)
                found.append(
                    {
                        "passIndex": pass_index,
                        "shaderModel": f"{match.group(1)}.{match.group(2)}",
                        "pixelShader": _safe_relative_identity(
                            match.group(3), "pixel shader"
                        ),
                        "usesPrimary": any(
                            x["codeSampler"] == "lightmapSamplerPrimary" for x in dedup
                        ),
                        "usesSecondary": any(
                            x["codeSampler"] == "lightmapSamplerSecondary" for x in dedup
                        ),
                        "samplers": [
                            name
                            for name in (
                                "lightmapSamplerPrimary",
                                "lightmapSamplerSecondary",
                            )
                            if any(x["codeSampler"] == name for x in dedup)
                        ],
                        "lightmapBindings": dedup,
                    }
                )
            i = next_i
            continue

        depth += lines[i].count("{") - lines[i].count("}")
        if depth < 0:
            raise LightmapShaderInventoryError("malformed technique brace depth")
        i += 1
    return found


def build_inventory(
    *,
    material_root: Path,
    techset_root: Path,
    technique_root: Path,
    shader_root: Path,
    allow_missing_shaders: bool = False,
) -> dict:
    doc = build_inventory_v1(
        material_root=material_root,
        techset_root=techset_root,
        technique_root=technique_root,
        shader_root=shader_root,
        allow_missing_shaders=allow_missing_shaders,
    )

    detail_cache: dict[str, dict[tuple[int, str], dict]] = {}
    primary_edges = 0
    secondary_edges = 0
    destinations: set[str] = set()
    shader_destinations: dict[str, set[str]] = {}
    shader_code_samplers: dict[str, set[str]] = {}

    for edge in doc.get("provenance", []):
        technique = str(edge["technique"])
        if technique not in detail_cache:
            path = technique_root / f"{technique}.tech"
            if not path.is_file():
                raise LightmapShaderInventoryError(
                    f"missing exact technique file {path}"
                )
            details = parse_lightmap_pixel_shaders_v2(
                path.read_text(encoding="utf-8")
            )
            keyed: dict[tuple[int, str], dict] = {}
            for detail in details:
                key = (int(detail["passIndex"]), str(detail["pixelShader"]))
                if key in keyed:
                    raise LightmapShaderInventoryError(
                        f"duplicate lightmap pixel-shader pass key in {path}: {key!r}"
                    )
                keyed[key] = detail
            detail_cache[technique] = keyed

        key = (int(edge["passIndex"]), str(edge["pixelShader"]))
        detail = detail_cache[technique].get(key)
        if detail is None:
            raise LightmapShaderInventoryError(
                f"v1/v2 parser disagreement for technique {technique!r} pass/shader {key!r}"
            )
        if bool(edge["usesPrimary"]) != bool(detail["usesPrimary"]) or bool(
            edge["usesSecondary"]
        ) != bool(detail["usesSecondary"]):
            raise LightmapShaderInventoryError(
                f"v1/v2 lightmap sampler disagreement for {technique!r} {key!r}"
            )

        edge["lightmapBindings"] = detail["lightmapBindings"]
        for binding in detail["lightmapBindings"]:
            code_sampler = binding["codeSampler"]
            resource = binding["shaderResource"]
            destinations.add(resource)
            shader_destinations.setdefault(edge["pixelShader"], set()).add(resource)
            shader_code_samplers.setdefault(edge["pixelShader"], set()).add(code_sampler)
            if code_sampler == "lightmapSamplerPrimary":
                primary_edges += 1
            else:
                secondary_edges += 1

    for shader in doc.get("uniqueLightmapPixelShaders", []):
        name = shader["pixelShader"]
        shader["lightmapCodeSamplers"] = sorted(shader_code_samplers.get(name, set()))
        shader["lightmapShaderResources"] = sorted(shader_destinations.get(name, set()))

    doc["format"] = "t6-lightmap-shader-inventory-v2"
    doc.setdefault("source", {})["producer"] = "t6_lightmap_shader_inventory_v2.py"
    doc.setdefault("policy", {})["resourceBridge"] = (
        "exact OAT technique assignment destination <shaderResource> = sampler.<T6 code sampler>"
    )
    doc["policy"]["matchingAccessorComment"] = (
        "OAT debug 'Omitted due to matching accessors' line is parsed as an exact resource binding"
    )
    doc.setdefault("stats", {})["primaryBindingCount"] = primary_edges
    doc["stats"]["secondaryBindingCount"] = secondary_edges
    doc["stats"]["distinctLightmapShaderResourceCount"] = len(destinations)
    return doc


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
    args.out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.out), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
