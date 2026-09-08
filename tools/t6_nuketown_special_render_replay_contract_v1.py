#!/usr/bin/env python3
"""Emit an implementation-facing replay contract for Nuketown special Materials.

This does not approximate T6 rendering. It compacts already-proven shader DAG,
RDEF/Technique/Material bindings, and render state into a stable interface for
consumers. Static Material-owned inputs are separated from runtime-owned shader
inputs. Exact pixel arithmetic remains identified by the canonical DAG SHA in
the source full-output proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-special-render-replay-contract-v1"
CLOSURE_FORMAT = "t6-nuketown-special-render-closure-v1"
RAW_FORMAT = "t6-nuketown-rawnormal-full-output-v1"
RAW_BIND_FORMAT = "t6-nuketown-rawnormal-input-binding-v1"
SPECIAL_BIND_FORMAT = "t6-nuketown-special-material-input-binding-v1"
SHADOW_FORMAT = "t6-nuketown-shadowcaster-state-v1"
MAP = "mp_nuketown_2020"
RAW_MATERIAL = "wpc/glass_clear_wall_opaque_white"
INTERPOLANT_RE = re.compile(r"^v(\d+)\.([xyzw])$")


class ReplayContractError(RuntimeError):
    pass


def read(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ReplayContractError(f"expected JSON object in {path}")
    return obj


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def require_file_identity(closure: dict[str, Any], key: str, path: Path) -> None:
    expected = str(closure["generatedEvidence"][key]["fileSha256"])
    actual = sha(path)
    if actual != expected:
        raise ReplayContractError(f"{key}: file SHA {actual} != sealed closure {expected}")


def unique_rows(rows: list[dict[str, Any]], key_fn) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = json.dumps(key_fn(row), sort_keys=True, separators=(",", ":"), allow_nan=False)
        old = found.get(key)
        if old is not None and old != row:
            raise ReplayContractError(f"non-identical duplicate row for {key}")
        found[key] = row
    return [found[k] for k in sorted(found)]


def compact_raw_shader(raw_row: dict[str, Any], bind_row: dict[str, Any]) -> dict[str, Any]:
    if str(raw_row.get("sha256")) != str(bind_row.get("pixelShaderSha256")):
        raise ReplayContractError("raw/binding shader identity mismatch")

    material_textures = []
    engine_textures = []
    for b in bind_row.get("sampleBindings", []):
        base = {
            "textureRegister": int(b["rdefTexture"]["bindPoint"]),
            "textureName": str(b["rdefTexture"]["name"]),
            "samplerRegister": int(b["rdefSampler"]["bindPoint"]),
            "samplerName": str(b["rdefSampler"]["name"]),
        }
        if b.get("ownership") == "material":
            mt = b.get("materialTexture")
            if not isinstance(mt, dict):
                raise ReplayContractError("material-owned sample lacks Material texture")
            material_textures.append({
                **base,
                "materialArgumentNameHash": str(b.get("materialArgumentNameHash")),
                "materialProperty": str((b.get("techniqueArgument") or {}).get("materialProperty") or ""),
                "nativeMaterialName": str(mt.get("name") or ""),
                "semantic": mt.get("semantic"),
                "image": str(mt.get("image") or ""),
                "samplerState": mt.get("samplerState"),
            })
        elif b.get("ownership") == "engine_or_code":
            engine_textures.append(base)
        else:
            raise ReplayContractError(f"unknown sample ownership {b.get('ownership')!r}")

    material_constants = []
    runtime_variables: dict[tuple[Any, ...], dict[str, Any]] = {}
    for c in bind_row.get("constantLeaves", []):
        if c.get("ownership") == "material":
            mc = c.get("materialConstant")
            if not isinstance(mc, dict):
                raise ReplayContractError("material-owned constant leaf lacks Material constant")
            material_constants.append({
                "constantBuffer": str(c["constantBuffer"]),
                "variable": str(c["variable"]),
                "variableStartOffset": int(c["variableStartOffset"]),
                "variableSizeBytes": int(c["variableSizeBytes"]),
                "materialArgumentNameHash": str(c["materialArgumentNameHash"]),
                "materialProperty": str((c.get("techniqueArgument") or {}).get("materialProperty") or ""),
                "nativeMaterialName": str(mc.get("name") or ""),
                "literal": mc.get("literal"),
            })
        elif c.get("ownership") == "engine_or_code":
            key = (
                str(c["constantBuffer"]), str(c["variable"]), int(c["variableStartOffset"]),
                int(c["variableSizeBytes"]), int(c["cbRegister"]),
            )
            row = runtime_variables.setdefault(key, {
                "cbRegister": int(c["cbRegister"]),
                "constantBuffer": str(c["constantBuffer"]),
                "variable": str(c["variable"]),
                "variableStartOffset": int(c["variableStartOffset"]),
                "variableSizeBytes": int(c["variableSizeBytes"]),
                "usedSymbols": [],
            })
            row["usedSymbols"].append(str(c["symbol"]))
        else:
            raise ReplayContractError(f"unknown constant ownership {c.get('ownership')!r}")

    for row in runtime_variables.values():
        row["usedSymbols"] = sorted(set(row["usedSymbols"]))

    interpolants = sorted({
        str(n.get("name"))
        for n in raw_row.get("nodes", [])
        if isinstance(n, dict) and n.get("kind") == "symbol"
        and isinstance(n.get("name"), str) and INTERPOLANT_RE.match(str(n.get("name")))
    })

    outputs = []
    for o in raw_row.get("outputs", []):
        if not isinstance(o, dict) or not str(o.get("output") or "").startswith("o0."):
            raise ReplayContractError(f"unexpected raw output row {o}")
        outputs.append({"output": str(o["output"]), "node": int(o["node"])})
    if len(outputs) != 4:
        raise ReplayContractError(f"{raw_row.get('sha256')}: expected RGBA output roots")

    return {
        "pixelShaderSha256": str(raw_row["sha256"]),
        "asset": raw_row.get("asset"),
        "dagSha256": str(raw_row["dagSha256"]),
        "controlFlow": bool(raw_row["controlFlow"]),
        "ifCount": int(raw_row["ifCount"]),
        "nodeCount": int(raw_row["nodeCount"]),
        "outputRoots": sorted(outputs, key=lambda x: x["output"]),
        "pixelInterpolantSymbols": interpolants,
        "staticMaterialTextures": unique_rows(material_textures, lambda x: x),
        "staticMaterialConstants": unique_rows(material_constants, lambda x: x),
        "runtimeTextureBindings": unique_rows(engine_textures, lambda x: x),
        "runtimeConstantVariables": [runtime_variables[k] for k in sorted(runtime_variables)],
        "rdefDigestSha256": str(bind_row["rdefDigestSha256"]),
    }


def compact_special_materials(binding: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for mat in binding.get("materials", []):
        programs = []
        for p in mat.get("programBindings", []):
            tex = p.get("materialTexture")
            if not isinstance(tex, dict):
                raise ReplayContractError("special binding lacks Material texture")
            material_consts = []
            runtime_consts = []
            for c in p.get("constantSymbols", []):
                mc = c.get("materialConstant")
                base = {"constantBuffer": c.get("constantBuffer"), "variable": c.get("variable"), "symbol": c.get("symbol"), "absoluteByteOffset": c.get("absoluteByteOffset")}
                if mc is None:
                    runtime_consts.append(base)
                else:
                    material_consts.append({**base, "materialConstant": mc})
            programs.append({
                "techniqueType": p.get("techniqueType"), "technique": p.get("technique"), "groupKey": p.get("groupKey"),
                "pixelShaderSha256": p.get("pixelShaderSha256"), "staticMaterialTexture": tex,
                "staticMaterialConstants": material_consts, "runtimeConstantLeaves": runtime_consts,
            })
        rows.append({"material": mat.get("material"), "family": mat.get("family"), "techniqueSet": mat.get("techniqueSet"), "programs": sorted(programs, key=lambda x: (str(x["techniqueType"]), str(x["pixelShaderSha256"])))})
    return sorted(rows, key=lambda x: str(x["material"]))


def compact_shadow(shadow: dict[str, Any]) -> list[dict[str, Any]]:
    wanted = {"depth prepass", "build shadowmap depth"}
    rows = []
    for mat in shadow.get("materials", []):
        passes = []
        for slot in mat.get("slots", []):
            if slot.get("techniqueType") not in wanted:
                continue
            passes.append({
                "techniqueType": slot.get("techniqueType"), "technique": slot.get("technique"), "groupKey": slot.get("groupKey"),
                "depthShaderPair": slot.get("depthShaderPair"), "stateBitsIndex": slot.get("stateBitsIndex"), "stateBits": slot.get("stateBits"),
            })
        if len(passes) != 2:
            raise ReplayContractError(f"{mat.get('material')}: depth-pass count changed")
        rows.append({"material": mat.get("material"), "depthPasses": passes})
    if len(rows) != 2:
        raise ReplayContractError("shadowcaster Material count changed")
    return sorted(rows, key=lambda x: str(x["material"]))


def build(closure_path: Path, raw_path: Path, raw_binding_path: Path, special_binding_path: Path, shadow_path: Path) -> dict[str, Any]:
    closure = read(closure_path); raw = read(raw_path); raw_binding = read(raw_binding_path); special_binding = read(special_binding_path); shadow = read(shadow_path)
    if closure.get("format") != CLOSURE_FORMAT or closure.get("map") != MAP: raise ReplayContractError("closure identity changed")
    if raw.get("format") != RAW_FORMAT or raw.get("material") != RAW_MATERIAL: raise ReplayContractError("raw-normal source identity changed")
    if raw_binding.get("format") != RAW_BIND_FORMAT or raw_binding.get("material") != RAW_MATERIAL: raise ReplayContractError("raw-normal binding identity changed")
    if special_binding.get("format") != SPECIAL_BIND_FORMAT or special_binding.get("map") != MAP: raise ReplayContractError("special binding identity changed")
    if shadow.get("format") != SHADOW_FORMAT or shadow.get("map") != MAP: raise ReplayContractError("shadow identity changed")
    require_file_identity(closure, "rawnormalFullOutput", raw_path); require_file_identity(closure, "rawnormalInputBinding", raw_binding_path); require_file_identity(closure, "specialMaterialInputBinding", special_binding_path); require_file_identity(closure, "shadowcasterState", shadow_path)

    raw_rows = {str(r["sha256"]): r for r in raw.get("shaderRows", [])}; bind_rows = {str(r["pixelShaderSha256"]): r for r in raw_binding.get("shaderBindings", [])}
    if set(raw_rows) != set(bind_rows) or len(raw_rows) != 20: raise ReplayContractError("20-shader raw/binding population disagreement")
    shader_contracts = {hh: compact_raw_shader(raw_rows[hh], bind_rows[hh]) for hh in sorted(raw_rows)}

    programs = []
    for p in raw.get("programs", []):
        hh = str(p.get("pixelShaderSha256") or "")
        if hh not in shader_contracts: raise ReplayContractError(f"program references unknown shader {hh}")
        sc = shader_contracts[hh]
        programs.append({
            "techniqueType": p.get("techniqueType"), "technique": p.get("technique"), "groupKey": p.get("groupKey"), "pixelShaderSha256": hh,
            "dagSha256": sc["dagSha256"], "staticMaterialTextureCount": len(sc["staticMaterialTextures"]), "staticMaterialConstantCount": len(sc["staticMaterialConstants"]),
            "runtimeTextureBindingCount": len(sc["runtimeTextureBindings"]), "runtimeConstantVariableCount": len(sc["runtimeConstantVariables"]), "pixelInterpolantSymbolCount": len(sc["pixelInterpolantSymbols"]),
        })
    if len(programs) != 22: raise ReplayContractError("raw-normal program count changed")

    core = {"rawnormal": {"material": RAW_MATERIAL, "programs": sorted(programs, key=lambda x: str(x["techniqueType"])), "pixelShaders": [shader_contracts[k] for k in sorted(shader_contracts)]}, "unlitAndEmissiveSpecialMaterials": compact_special_materials(special_binding), "shadowcasters": compact_shadow(shadow)}
    return {
        "format": FORMAT, "producer": "tools/t6_nuketown_special_render_replay_contract_v1.py", "map": MAP,
        "sourceClosureManifestSha256": sha(closure_path),
        "sourceEvidence": {"rawnormalFullOutputSha256": sha(raw_path), "rawnormalInputBindingSha256": sha(raw_binding_path), "specialMaterialInputBindingSha256": sha(special_binding_path), "shadowcasterStateSha256": sha(shadow_path)},
        "summary": {
            "rawnormalProgramCount": len(programs), "rawnormalPixelShaderCount": len(shader_contracts), "specialMaterialCount": len(core["unlitAndEmissiveSpecialMaterials"]), "shadowcasterMaterialCount": len(core["shadowcasters"]),
            "rawnormalStaticMaterialImageCount": len({x["image"] for s in shader_contracts.values() for x in s["staticMaterialTextures"]}),
            "rawnormalRuntimeTextureIdentityCount": len({(x["textureRegister"], x["textureName"], x["samplerRegister"], x["samplerName"]) for s in shader_contracts.values() for x in s["runtimeTextureBindings"]}),
            "rawnormalRuntimeConstantVariableIdentityCount": len({(x["cbRegister"], x["constantBuffer"], x["variable"], x["variableStartOffset"], x["variableSizeBytes"]) for s in shader_contracts.values() for x in s["runtimeConstantVariables"]}),
        },
        **core, "contractDigestSha256": digest(core),
        "consumerModes": {
            "exactRuntimeReplay": "Consumer must evaluate the sealed DAG identified for the chosen Technique and provide every listed static Material input, runtime texture, runtime constant variable, and pixel interpolant with native semantics.",
            "evidenceScopedPortablePreview": "Consumer may approximate runtime-owned scene/light/shadow/probe inputs, but must label the result non-exact and must not replace static Material inputs or shader DAG identity by family/name heuristics."
        },
        "proofBoundary": "This contract is a lossless interface projection of already-sealed evidence, not new shader-semantic inference. Pixel arithmetic remains authoritative only through the exact full-output DAG evidence. Runtime-owned inputs are deliberately external and no default value is promoted as retail truth."
    }


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--closure", type=Path, required=True); ap.add_argument("--rawnormal", type=Path, required=True); ap.add_argument("--rawnormal-binding", type=Path, required=True); ap.add_argument("--special-binding", type=Path, required=True); ap.add_argument("--shadowcaster", type=Path, required=True); ap.add_argument("--out", type=Path, required=True); a = ap.parse_args()
    doc = build(a.closure, a.rawnormal, a.rawnormal_binding, a.special_binding, a.shadowcaster); a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps(doc["summary"], indent=2, sort_keys=True)); print(doc["contractDigestSha256"]); return 0


if __name__ == "__main__":
    raise SystemExit(main())
