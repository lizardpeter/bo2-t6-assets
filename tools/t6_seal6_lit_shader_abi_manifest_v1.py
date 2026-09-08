#!/usr/bin/env python3
"""Build a fail-closed ABI manifest for the exact SEAL6 ordinary-lit shaders.

The adapter consumes the previously closed native lit shader binary report and the
five archived DXBC programs.  It joins exact OAT Material arguments to DXBC RDEF
resources / $Globals variables by symbolic identity and byte offset.  It does not
infer shader equations or texture meaning from filenames or register proximity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_dxbc_rdef_v1 import parse_rdef

FORMAT = "t6-seal6-lit-shader-abi-manifest-v1"
SOURCE_FORMAT = "t6-seal6-lit-shader-binary-report-v1"

EXPECTED = {
    "mc_sw4_3d_char_skin_hero_9949fq1j": {
        "vs": "b1bacc64d083fb8b2a60ab28e346e14bb6f0dd9cbf21930480f7dc647f42dabe",
        "ps": "dbad6541db6ffa00308d732ab2c07777dca960465ebcc9710823ab68b16c78ec",
    },
    "mc_sw4_3d_char_skin_j92387z3": {
        "vs": "b1bacc64d083fb8b2a60ab28e346e14bb6f0dd9cbf21930480f7dc647f42dabe",
        "ps": "785e8ef0f0936016ce9dd18f67cdcad1c15bdbed58c174e93049df3f46b79b98",
    },
    "mc_sw4_3d_char_eye_cornea_2eww29wu": {
        "vs": "db872ac90083aea7bd1cc0c53a3edd6f5c9bab2ece1a6616d86876169bb72cf5",
        "ps": "6d4913fd080a783f1c08e78124884c491725c5e69dfe93846bc27a2a78ada298",
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resource_rows(rdef: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": row["name"],
            "resourceType": row["resourceType"],
            "register": row["register"],
            "dimension": row["dimension"],
            "bindCount": row["bindCount"],
        }
        for row in rdef["resources"]
    ]


def _argument_bindings(arguments: list[str], rdef: dict[str, Any]) -> list[dict[str, Any]]:
    resources: dict[str, list[dict[str, Any]]] = {}
    for row in rdef["resources"]:
        resources.setdefault(row["name"], []).append(row)

    globals_rows: dict[str, dict[str, Any]] = {}
    for cb in rdef["constantBuffers"]:
        if cb["name"] != "$Globals":
            continue
        register = cb.get("register")
        if register is None:
            raise ValueError("$Globals has no RDEF cbuffer register")
        for variable in cb["variables"]:
            globals_rows[variable["name"]] = {
                "kind": "constant",
                "constantBuffer": "$Globals",
                "register": register,
                "byteOffset": variable["startOffset"],
                "byteSize": variable["size"],
            }

    out = []
    for name in arguments:
        matches = resources.get(name, [])
        resource_rows = [m for m in matches if m["resourceType"] in ("texture", "sampler")]
        if resource_rows:
            texture = [m for m in resource_rows if m["resourceType"] == "texture"]
            sampler = [m for m in resource_rows if m["resourceType"] == "sampler"]
            if len(texture) != 1 or len(sampler) != 1:
                raise ValueError(
                    f"material argument {name!r} expected exactly one texture and sampler, "
                    f"got textures={len(texture)} samplers={len(sampler)}"
                )
            out.append(
                {
                    "argument": name,
                    "kind": "sampled-texture",
                    "textureRegister": texture[0]["register"],
                    "textureDimension": texture[0]["dimension"],
                    "samplerRegister": sampler[0]["register"],
                }
            )
            continue
        constant = globals_rows.get(name)
        if constant is not None:
            out.append({"argument": name, **constant})
            continue
        raise ValueError(f"material argument {name!r} is absent from DXBC RDEF resources and $Globals")
    return out


def _load_shader(shader_dir: Path, digest: str, suffix: str) -> tuple[bytes, dict[str, Any], str]:
    path = shader_dir / f"{digest}.{suffix}.cso"
    if not path.is_file():
        raise ValueError(f"missing exact shader {path}")
    data = path.read_bytes()
    actual = sha256(data)
    if actual != digest:
        raise ValueError(f"shader SHA mismatch for {path.name}: {actual} != {digest}")
    return data, parse_rdef(data), path.name


def build(source: dict[str, Any], shader_dir: Path) -> dict[str, Any]:
    if source.get("format") != SOURCE_FORMAT:
        raise ValueError(f"unexpected source format {source.get('format')!r}")

    families = {row["techniqueSet"]: row for row in source.get("families", [])}
    if set(families) != set(EXPECTED):
        raise ValueError(f"unexpected TechniqueSet family set: {sorted(families)}")

    output_families = []
    unique_programs: dict[str, dict[str, Any]] = {}
    for techset, expected in EXPECTED.items():
        family = families[techset]
        variants = family.get("variants", [])
        if not variants:
            raise ValueError(f"{techset}: no physical variants")

        pairs = {(v["vertexShader"]["sha256"], v["pixelShader"]["sha256"]) for v in variants}
        if pairs != {(expected["vs"], expected["ps"])}:
            raise ValueError(f"{techset}: physical variants do not collapse to expected executable pair: {pairs}")

        vs_data, vs_rdef, vs_file = _load_shader(shader_dir, expected["vs"], "vs")
        ps_data, ps_rdef, ps_file = _load_shader(shader_dir, expected["ps"], "ps")
        first = variants[0]
        vs_args = list(first["vertexShader"].get("materialArguments", []))
        ps_args = list(first["pixelShader"].get("materialArguments", []))
        for variant in variants[1:]:
            if variant["vertexShader"].get("materialArguments", []) != vs_args:
                raise ValueError(f"{techset}: vertex material arguments differ across physical variants")
            if variant["pixelShader"].get("materialArguments", []) != ps_args:
                raise ValueError(f"{techset}: pixel material arguments differ across physical variants")

        for digest, kind, data, rdef, filename in (
            (expected["vs"], "vertex", vs_data, vs_rdef, vs_file),
            (expected["ps"], "pixel", ps_data, ps_rdef, ps_file),
        ):
            if digest not in unique_programs:
                unique_programs[digest] = {
                    "kind": kind,
                    "file": filename,
                    "bytes": len(data),
                    "sha256": digest,
                    "creator": rdef["creator"],
                    "resources": _resource_rows(rdef),
                    "constantBuffers": [
                        {
                            "name": cb["name"],
                            "register": cb.get("register"),
                            "size": cb["size"],
                            "variables": cb["variables"],
                        }
                        for cb in rdef["constantBuffers"]
                    ],
                }

        output_families.append(
            {
                "techniqueSet": techset,
                "physicalOwnerCount": family["physicalOwnerCount"],
                "serializedLitPassIdentityInvariantAcrossOwners": family[
                    "serializedLitPassIdentityInvariantAcrossOwners"
                ],
                "executableVsPsPairInvariantAcrossOwners": family[
                    "executableVsPsPairInvariantAcrossOwners"
                ],
                "vertexShaderSha256": expected["vs"],
                "pixelShaderSha256": expected["ps"],
                "vertexMaterialArguments": vs_args,
                "pixelMaterialArguments": ps_args,
                "vertexArgumentBindings": _argument_bindings(vs_args, vs_rdef),
                "pixelArgumentBindings": _argument_bindings(ps_args, ps_rdef),
            }
        )

    if len(unique_programs) != 5:
        raise ValueError(f"expected exactly five unique executable programs, got {len(unique_programs)}")

    return {
        "format": FORMAT,
        "proofBoundary": (
            "Exact SHA-pinned OAT-emitted SEAL6 ordinary-lit DXBC joined to exact OAT Material "
            "arguments through DXBC RDEF symbolic names/registers/byte offsets. This manifest "
            "does not infer equations, channel meanings, or retail-client duplicate precedence."
        ),
        "sourceShaderBinaryReport": {
            "format": source["format"],
            "summary": source["summary"],
        },
        "summary": {
            "techniqueSetFamilies": len(output_families),
            "uniquePrograms": len(unique_programs),
            "uniqueVertexPrograms": sum(1 for p in unique_programs.values() if p["kind"] == "vertex"),
            "uniquePixelPrograms": sum(1 for p in unique_programs.values() if p["kind"] == "pixel"),
            "allMaterialArgumentsClosedToRdef": True,
        },
        "families": output_families,
        "programs": [unique_programs[k] for k in sorted(unique_programs)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shader-binary-report", type=Path, required=True)
    parser.add_argument("--shader-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.shader_binary_report.read_text(encoding="utf-8"))
    out = build(source, args.shader_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
