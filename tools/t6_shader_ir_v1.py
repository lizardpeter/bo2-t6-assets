#!/usr/bin/env python3
"""Generate a proof-rich, fail-closed T6 material/shader IR from native OAT dumps.

This is the source representation shared by downstream Blender and engine
adapters.  It deliberately preserves T6 technique-indexed pipeline state and
OAT's exact TechniqueSet/technique/pass/resource graph instead of inventing PBR
parameters.

The material and its TechniqueSet may come from different FastFiles.  That is a
normal T6 dependency pattern (for example Nuketown Car01 glass: map Material,
shared common_mp TechniqueSet), so provenance records both sources separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-shader-ir-v1"

# Exact pinned T6 technique-type order from
# OpenAssetTools src/ObjCommon/Game/T6/Techset/TechsetConstantsT6.h.
TECHNIQUE_TYPES = (
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require_sha256(label: str, value: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ValueError(f"{label} must be a 64-character SHA-256 hex digest")


def source(name: str, sha256: str) -> dict[str, str]:
    require_sha256(f"{name} sha256", sha256)
    return {"fastFile": name, "sha256": sha256.lower()}


def find_technique_binding(techset: dict[str, Any], technique_type: str) -> str:
    matches = []
    for row in techset.get("techniqueTypeBindings", []):
        if technique_type in row.get("types", []):
            matches.append(row.get("technique"))
    matches = [m for m in matches if isinstance(m, str) and m]
    if len(matches) != 1:
        raise ValueError(
            f"TechniqueSet {techset.get('name')!r}: expected exactly one binding "
            f"for technique type {technique_type!r}, got {matches!r}"
        )
    return matches[0]


def normalize_shader(shader: dict[str, Any]) -> dict[str, Any]:
    kind = shader.get("kind")
    if kind == "vertexShader":
        stage = "vertex"
    elif kind == "pixelShader":
        stage = "pixel"
    else:
        raise ValueError(f"unsupported shader kind {kind!r}")

    binary = shader.get("binary")
    if not isinstance(binary, dict):
        raise ValueError(f"{shader.get('name')}: missing exact shader binary")
    sha = binary.get("sha256")
    if not isinstance(sha, str):
        raise ValueError(f"{shader.get('name')}: missing binary SHA-256")
    require_sha256(f"{shader.get('name')} binary sha256", sha)

    args = shader.get("arguments", [])
    if not isinstance(args, list):
        raise ValueError(f"{shader.get('name')}: arguments is not an array")

    return {
        "stage": stage,
        "assetName": shader.get("name"),
        "shaderModel": shader.get("model"),
        "dxbc": {
            "path": binary.get("path"),
            "bytes": binary.get("size"),
            "sha256": sha.lower(),
        },
        "arguments": args,
    }


def build_ir(
    *,
    material_name: str,
    material_path: Path,
    shader_manifest_path: Path,
    technique_type: str,
    material_source: dict[str, str],
    shader_source: dict[str, str],
) -> dict[str, Any]:
    if technique_type not in TECHNIQUE_TYPES:
        raise ValueError(f"unknown T6 technique type {technique_type!r}")
    type_index = TECHNIQUE_TYPES.index(technique_type)

    material_bytes = material_path.read_bytes()
    material = json.loads(material_bytes)
    if material.get("_game") != "t6" or material.get("_type") != "material":
        raise ValueError("material JSON is not a native OAT T6 Material dump")

    techset_name = material.get("techniqueSet")
    if not isinstance(techset_name, str) or not techset_name:
        raise ValueError("material has no resolved techniqueSet")

    state_entry = material.get("stateBitsEntry")
    state_bits = material.get("stateBits")
    if not isinstance(state_entry, list) or len(state_entry) != len(TECHNIQUE_TYPES):
        raise ValueError(
            f"material stateBitsEntry must have {len(TECHNIQUE_TYPES)} T6 entries"
        )
    if not isinstance(state_bits, list):
        raise ValueError("material stateBits is not an array")
    state_index = state_entry[type_index]
    if not isinstance(state_index, int) or state_index < 0:
        raise ValueError(
            f"material does not provide pipeline state for technique type {technique_type!r}"
        )
    if state_index >= len(state_bits):
        raise ValueError(
            f"stateBitsEntry[{type_index}]={state_index} exceeds stateBits length {len(state_bits)}"
        )
    pipeline_state = state_bits[state_index]
    if not isinstance(pipeline_state, dict):
        raise ValueError("selected stateBits record is not an object")

    shader_manifest = json.loads(shader_manifest_path.read_bytes())
    if shader_manifest.get("format") != "t6-oat-techset-binding-manifest-v1":
        raise ValueError("unexpected shader binding manifest format")
    errors = shader_manifest.get("errors")
    # A combined manifest may contain an unrelated missing shared TechniqueSet.
    # Permit only errors whose named TechniqueSet is not the one being selected.
    if errors:
        relevant = [
            e
            for e in errors
            if isinstance(e, dict)
            and (e.get("name") == techset_name or e.get("scope") not in {"techset", "technique"})
        ]
        if relevant:
            raise ValueError(f"shader manifest has relevant errors: {relevant!r}")

    techsets = [t for t in shader_manifest.get("techsets", []) if t.get("name") == techset_name]
    if len(techsets) != 1:
        raise ValueError(
            f"expected exactly one dumped TechniqueSet {techset_name!r}, got {len(techsets)}"
        )
    techset = techsets[0]
    technique_name = find_technique_binding(techset, technique_type)

    techniques = [
        t for t in shader_manifest.get("techniques", []) if t.get("name") == technique_name
    ]
    if len(techniques) != 1:
        raise ValueError(
            f"expected exactly one dumped technique {technique_name!r}, got {len(techniques)}"
        )
    technique = techniques[0]

    passes = []
    for p in technique.get("passes", []):
        shaders = [normalize_shader(s) for s in p.get("shaders", [])]
        stages = [s["stage"] for s in shaders]
        if stages.count("vertex") != 1 or stages.count("pixel") != 1:
            raise ValueError(
                f"technique {technique_name!r} pass {p.get('index')} does not have "
                "exactly one vertex and one pixel shader"
            )
        passes.append(
            {
                "index": p.get("index"),
                "stateMap": p.get("stateMap"),
                "vertexRoutes": p.get("vertexRouting", []),
                "shaders": shaders,
            }
        )
    if not passes:
        raise ValueError(f"technique {technique_name!r} has no dumped passes")

    material_inputs = {
        "textures": material.get("textures", []),
        "constants": material.get("constants", []),
        "textureAtlas": material.get("textureAtlas"),
    }

    oat_commit = (
        shader_manifest.get("sourceBindingManifest", {}).get("openAssetToolsCommit")
    )
    if not isinstance(oat_commit, str) or len(oat_commit) != 40:
        raise ValueError("shader manifest does not carry a valid pinned OAT commit")

    return {
        "format": FORMAT,
        "proofBoundary": (
            "Native OAT Material -> TechniqueSet pointer resolution, exact T6 "
            "technique-type index -> stateBitsEntry selection, exact dumped "
            "TechniqueSet/technique/pass/shader graph, and exact Material inputs. "
            "No PBR, shader-equation, register-binding, or lighting inference."
        ),
        "provenance": {
            "openAssetToolsCommit": oat_commit,
            "materialSource": material_source,
            "shaderSource": shader_source,
            "materialJsonSha256": sha256_bytes(material_bytes),
            "shaderBindingManifestSha256": sha256_file(shader_manifest_path),
        },
        "material": {
            "name": material_name,
            "cameraRegion": material.get("cameraRegion"),
            "sortKey": material.get("sortKey"),
        },
        "techniqueSet": techset_name,
        "techniqueType": technique_type,
        "techniqueTypeIndex": type_index,
        "technique": technique_name,
        "stateBitsIndex": state_index,
        "pipelineState": pipeline_state,
        "materialInputs": material_inputs,
        "passes": passes,
        "semanticEquations": [],
        "spirvReflection": None,
        "unresolved": [
            "SPIR-V descriptor/resource reflection has not been merged into this IR instance",
            "shader arithmetic/lighting equations have not been semantically named in this IR instance",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--material-name", required=True)
    parser.add_argument("--material-json", type=Path, required=True)
    parser.add_argument("--shader-binding-manifest", type=Path, required=True)
    parser.add_argument("--technique-type", required=True)
    parser.add_argument("--material-fast-file", required=True)
    parser.add_argument("--material-fast-file-sha256", required=True)
    parser.add_argument("--shader-fast-file", required=True)
    parser.add_argument("--shader-fast-file-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    ir = build_ir(
        material_name=args.material_name,
        material_path=args.material_json,
        shader_manifest_path=args.shader_binding_manifest,
        technique_type=args.technique_type,
        material_source=source(args.material_fast_file, args.material_fast_file_sha256),
        shader_source=source(args.shader_fast_file, args.shader_fast_file_sha256),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ir, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(ir, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
