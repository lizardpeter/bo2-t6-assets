#!/usr/bin/env python3
"""Resolve T6 lightmap code-sampler provenance to exact DXBC RDEF registers.

Input: `t6-lightmap-shader-inventory-v2` from stock OAT dumps.
For every selected material/technique/pass edge this stage:

1. reopens the exact `shader_bin/ps_<name>.cso`;
2. verifies byte count + SHA-256 against the inventory;
3. validates/inspects the DXBC container;
4. checks the OAT technique shader-model declaration against DXBC SHDR/SHEX;
5. resolves each recorded shader resource destination through RDEF;
6. records the exact texture bind point (`t#`) and resource metadata.

This closes the code-sampler -> shader-resource -> texture-register provenance
bridge. It does not decode sample instructions, channel swizzles or the final
primary/secondary combine equation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from t6_dxbc_inspect_v1 import DxbcInspectError, inspect_dxbc


class LightmapShaderDxbcError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_file_name(value: str) -> str:
    if not value or Path(value).name != value or value in (".", "..") or "\0" in value:
        raise LightmapShaderDxbcError(f"unsafe shader filename {value!r}")
    return value


def build_manifest(
    inventory: dict,
    *,
    shader_root: Path,
    allow_missing_shaders: bool = False,
) -> dict:
    if inventory.get("format") != "t6-lightmap-shader-inventory-v2":
        raise LightmapShaderDxbcError(
            f"unsupported shader inventory {inventory.get('format')!r}"
        )
    if not shader_root.is_dir():
        raise LightmapShaderDxbcError(f"shader root is not a directory: {shader_root}")

    shader_docs: dict[str, dict] = {}
    missing: list[dict] = []
    for shader in inventory.get("uniqueLightmapPixelShaders", []):
        name = str(shader.get("pixelShader") or "")
        file_name = _safe_file_name(str(shader.get("file") or f"ps_{name}.cso"))
        path = shader_root / file_name
        expected_present = bool(shader.get("present", True))
        if not path.is_file():
            item = {"pixelShader": name, "file": file_name, "path": str(path)}
            missing.append(item)
            if expected_present and not allow_missing_shaders:
                raise LightmapShaderDxbcError(f"missing exact DXBC shader {path}")
            shader_docs[name] = {
                "pixelShader": name,
                "file": file_name,
                "present": False,
            }
            continue

        raw = path.read_bytes()
        expected_bytes = shader.get("bytes")
        expected_sha = shader.get("sha256")
        if expected_bytes is not None and int(expected_bytes) != len(raw):
            raise LightmapShaderDxbcError(
                f"shader {name!r} byte count changed: inventory={expected_bytes} actual={len(raw)}"
            )
        actual_sha = _sha256(raw)
        if expected_sha and str(expected_sha) != actual_sha:
            raise LightmapShaderDxbcError(
                f"shader {name!r} SHA-256 changed: inventory={expected_sha} actual={actual_sha}"
            )
        try:
            inspected = inspect_dxbc(raw, name=file_name)
        except DxbcInspectError as exc:
            raise LightmapShaderDxbcError(
                f"shader {name!r} failed DXBC inspection: {exc}"
            ) from exc
        if inspected["program"]["programType"] != "pixel":
            raise LightmapShaderDxbcError(
                f"selected lightmap shader {name!r} is {inspected['program']['programType']}, not pixel"
            )
        shader_docs[name] = {
            "pixelShader": name,
            "file": file_name,
            "present": True,
            "bytes": len(raw),
            "sha256": actual_sha,
            "dxbc": inspected,
        }

    resolved_edges: list[dict] = []
    primary_registers: set[int] = set()
    secondary_registers: set[int] = set()
    both_edges = 0
    for input_edge in inventory.get("provenance", []):
        edge = copy.deepcopy(input_edge)
        shader_name = str(edge["pixelShader"])
        shader_doc = shader_docs.get(shader_name)
        if shader_doc is None:
            raise LightmapShaderDxbcError(
                f"provenance references shader absent from unique inventory: {shader_name!r}"
            )
        if not shader_doc.get("present"):
            if not allow_missing_shaders:
                raise LightmapShaderDxbcError(
                    f"provenance references missing shader {shader_name!r}"
                )
            edge["resolvedLightmapBindings"] = []
            edge["shaderPresent"] = False
            resolved_edges.append(edge)
            continue

        dxbc = shader_doc["dxbc"]
        if str(edge.get("shaderModel")) != str(dxbc["program"]["shaderModel"]):
            raise LightmapShaderDxbcError(
                f"shader-model disagreement for {shader_name!r}: "
                f"technique={edge.get('shaderModel')!r} DXBC={dxbc['program']['shaderModel']!r}"
            )
        resources = dxbc["reflection"]["boundResources"]
        by_name: dict[str, list[dict]] = {}
        for resource in resources:
            by_name.setdefault(str(resource["name"]), []).append(resource)

        resolved: list[dict] = []
        for binding in edge.get("lightmapBindings", []):
            resource_name = str(binding["shaderResource"])
            candidates = by_name.get(resource_name, [])
            if len(candidates) != 1:
                raise LightmapShaderDxbcError(
                    f"shader {shader_name!r} resource {resource_name!r} resolved to {len(candidates)} RDEF entries"
                )
            resource = candidates[0]
            if resource["inputType"] != "TEXTURE":
                raise LightmapShaderDxbcError(
                    f"shader {shader_name!r} lightmap resource {resource_name!r} is "
                    f"{resource['inputType']}, expected TEXTURE"
                )
            code_sampler = str(binding["codeSampler"])
            bind_point = int(resource["bindPoint"])
            if code_sampler == "lightmapSamplerPrimary":
                primary_registers.add(bind_point)
            elif code_sampler == "lightmapSamplerSecondary":
                secondary_registers.add(bind_point)
            else:
                raise LightmapShaderDxbcError(
                    f"unexpected lightmap code sampler {code_sampler!r}"
                )
            resolved.append(
                {
                    "codeSampler": code_sampler,
                    "shaderResource": resource_name,
                    "textureRegister": f"t{bind_point}",
                    "bindPoint": bind_point,
                    "bindCount": int(resource["bindCount"]),
                    "returnType": resource["returnType"],
                    "dimension": resource["dimension"],
                    "rdefResourceIndex": int(resource["index"]),
                }
            )
        edge["shaderPresent"] = True
        edge["shaderSha256Verified"] = True
        edge["resolvedLightmapBindings"] = resolved
        if edge.get("usesPrimary") and edge.get("usesSecondary"):
            both_edges += 1
        resolved_edges.append(edge)

    present_shader_docs = [x for x in shader_docs.values() if x.get("present")]
    return {
        "format": "t6-lightmap-shader-dxbc-manifest-v1",
        "source": {
            "inventoryFormat": inventory.get("format"),
            "inventoryProducer": inventory.get("source", {}).get("producer"),
            "shaderRoot": str(shader_root),
        },
        "policy": {
            "shaderIdentity": "exact pixelShader name + inventory byte count/SHA-256",
            "registerResolution": (
                "OAT technique destination resource must resolve to exactly one DXBC RDEF TEXTURE"
            ),
            "shaderModel": "OAT technique declaration must equal SHDR/SHEX program model",
            "instructionSemantics": "not decoded",
            "lightmapCombineEquation": "not inferred",
        },
        "stats": {
            "provenanceEdgeCount": len(resolved_edges),
            "presentPixelShaderCount": len(present_shader_docs),
            "missingPixelShaderCount": len({x["pixelShader"] for x in missing}),
            "bothPrimarySecondaryEdgeCount": both_edges,
            "primaryTextureRegisterCount": len(primary_registers),
            "secondaryTextureRegisterCount": len(secondary_registers),
        },
        "primaryTextureBindPoints": sorted(primary_registers),
        "secondaryTextureBindPoints": sorted(secondary_registers),
        "pixelShaders": [shader_docs[name] for name in sorted(shader_docs)],
        "provenance": resolved_edges,
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory_json", type=Path)
    parser.add_argument("--shader-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-missing-shaders", action="store_true")
    args = parser.parse_args()
    inventory = json.loads(args.inventory_json.read_text(encoding="utf-8"))
    doc = build_manifest(
        inventory,
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
