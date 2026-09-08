#!/usr/bin/env python3
"""Bind exact Nuketown special full-output shader leaves to native Material inputs.

This stage joins four exact evidence layers produced from the same pinned OAT
run:

1. the finite Nuketown special Material census;
2. the complete full-output SM4 DAGs for exact unlit/emissive pixel shaders;
3. the exact dumped Technique text selected by each Material program; and
4. the native OAT Material JSON records from the SHA-pinned retail map.

For each selected Material program, the exact shader is re-opened from its exact
Technique owner, SHA-256 checked, and its DXBC RDEF chunk is parsed. Every used
texture/sampler register is resolved by reflected shader binding name. That exact
left-hand shader name must appear in the exact dumped Technique as a
`material.<name>` assignment. The right-hand Material texture name must then
resolve to exactly one native Material texture entry, whose image identity and
full sampler state are retained.

Used constant-buffer symbols are resolved to reflected cbuffer/variable names
and are joined to Material constants only when the names agree exactly.

No binding is guessed by stripping suffixes, semantic/family/material naming, or
register position.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-special-material-input-binding-v1"
SPECIAL_FORMAT = "t6-nuketown-special-material-census-v1"
SYMBOLIC_FORMAT = "t6-nuketown-special-full-output-symbolic-v1"
TARGET_TYPES = {"unlit", "emissive"}
CB_SYMBOL_RE = re.compile(r"^cb(\d+)\[(\d+)\]\.([xyzw])$")
# D3D_SHADER_INPUT_TYPE values used by SM4 RDEF.
INPUT_CBUFFER = 0
INPUT_TEXTURE = 2
INPUT_SAMPLER = 3
COMP_INDEX = {"x": 0, "y": 1, "z": 2, "w": 3}


class BindingError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise BindingError(f"expected JSON object in {path}")
    return obj


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _rdef_bytes(blob: bytes) -> bytes:
    if len(blob) < 32 or blob[:4] != b"DXBC":
        raise BindingError("shader is not a DXBC container")
    chunk_count = struct.unpack_from("<I", blob, 28)[0]
    table_end = 32 + 4 * chunk_count
    if table_end > len(blob):
        raise BindingError("DXBC chunk table overflow")
    for off in struct.unpack_from("<" + "I" * chunk_count, blob, 32):
        if off + 8 > len(blob):
            raise BindingError("DXBC chunk offset overflow")
        size = struct.unpack_from("<I", blob, off + 4)[0]
        end = off + 8 + size
        if end > len(blob):
            raise BindingError("DXBC chunk body overflow")
        if blob[off : off + 4] == b"RDEF":
            return blob[off + 8 : end]
    raise BindingError("RDEF chunk missing")


def _cstr(data: bytes, off: int) -> str:
    if off < 0 or off >= len(data):
        raise BindingError(f"RDEF string offset {off} outside chunk")
    end = data.find(b"\0", off)
    if end < 0:
        raise BindingError("unterminated RDEF string")
    return data[off:end].decode("utf-8")


def _parse_rdef(blob: bytes) -> dict[str, Any]:
    r = _rdef_bytes(blob)
    if len(r) < 24:
        raise BindingError("RDEF header too short")
    cb_count, cb_off, rb_count, rb_off = struct.unpack_from("<4I", r, 0)
    minor = r[16]
    major = r[17]
    rb_stride = 40 if (major, minor) >= (5, 1) else 32

    resources = []
    for i in range(rb_count):
        off = rb_off + i * rb_stride
        if off + 32 > len(r):
            raise BindingError("RDEF resource table overflow")
        name_off, input_type, return_type, dimension, num_samples, bind_point, bind_count, flags = struct.unpack_from(
            "<8I", r, off
        )
        resources.append(
            {
                "name": _cstr(r, name_off),
                "inputType": input_type,
                "returnType": return_type,
                "dimension": dimension,
                "numSamples": num_samples,
                "bindPoint": bind_point,
                "bindCount": bind_count,
                "flags": flags,
            }
        )

    cbuffers: dict[str, dict[str, Any]] = {}
    for i in range(cb_count):
        off = cb_off + i * 24
        if off + 24 > len(r):
            raise BindingError("RDEF constant-buffer table overflow")
        name_off, var_count, var_off, byte_size, flags, cb_type = struct.unpack_from("<6I", r, off)
        name = _cstr(r, name_off)
        variables = []
        for j in range(var_count):
            voff = var_off + j * 24
            if voff + 24 > len(r):
                raise BindingError("RDEF variable table overflow")
            vname_off, start, size, vflags, type_off, default_off = struct.unpack_from("<6I", r, voff)
            variables.append(
                {
                    "name": _cstr(r, vname_off),
                    "startOffset": start,
                    "sizeBytes": size,
                    "flags": vflags,
                    "typeOffset": type_off,
                    "defaultValueOffset": default_off,
                }
            )
        cbuffers[name] = {
            "name": name,
            "byteSize": byte_size,
            "flags": flags,
            "type": cb_type,
            "variables": variables,
        }
    return {"shaderModel": f"{major}.{minor}", "resources": resources, "constantBuffers": cbuffers}


def _one_resource(rdef: dict[str, Any], input_type: int, bind_point: int, label: str) -> dict[str, Any]:
    hits = [
        row
        for row in rdef["resources"]
        if row["inputType"] == input_type
        and row["bindPoint"] <= bind_point < row["bindPoint"] + max(1, row["bindCount"])
    ]
    if len(hits) != 1:
        raise BindingError(f"{label}{bind_point}: reflected resource hits {hits}")
    return hits[0]


def _resolve_cb_symbol(rdef: dict[str, Any], symbol: str) -> dict[str, Any]:
    m = CB_SYMBOL_RE.match(symbol)
    if not m:
        raise BindingError(f"invalid cbuffer symbol {symbol!r}")
    cbreg, element, component = int(m.group(1)), int(m.group(2)), m.group(3)
    binding = _one_resource(rdef, INPUT_CBUFFER, cbreg, "cb")
    cb_name = binding["name"]
    if cb_name not in rdef["constantBuffers"]:
        raise BindingError(f"cb{cbreg}: reflected binding {cb_name!r} has no cbuffer declaration")
    absolute = element * 16 + COMP_INDEX[component] * 4
    variables = rdef["constantBuffers"][cb_name]["variables"]
    hits = [v for v in variables if v["startOffset"] <= absolute < v["startOffset"] + v["sizeBytes"]]
    if len(hits) != 1:
        raise BindingError(f"{symbol}: variable hits {hits}")
    var = hits[0]
    return {
        "symbol": symbol,
        "cbRegister": cbreg,
        "constantBuffer": cb_name,
        "absoluteByteOffset": absolute,
        "variable": var["name"],
        "variableStartOffset": var["startOffset"],
        "variableSizeBytes": var["sizeBytes"],
        "byteOffsetWithinVariable": absolute - var["startOffset"],
    }


def _material_path(root: Path, name: str) -> Path:
    path = root / "materials" / (name + ".json")
    if not path.is_file():
        raise BindingError(f"missing exact native Material JSON {path}")
    return path


def _technique_material_texture_binding(owner: str, technique: str, shader_name: str) -> dict[str, Any]:
    """Resolve one reflected shader name through the exact dumped Technique text.

    OAT Technique syntax explicitly separates the shader variable on the left
    from the Material texture source on the right, e.g.
    `colorMapSampler = material.colorMap;`. We follow that exact assignment and
    require one unique RHS. No suffix rewrite is allowed.
    """
    if not owner or not technique or not shader_name:
        raise BindingError("incomplete Technique material-texture binding identity")
    path = Path(owner) / "techniques" / f"{technique}.tech"
    if not path.is_file():
        raise BindingError(f"missing exact dumped Technique {path}")
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?m)^\s*" + re.escape(shader_name) + r"\s*=\s*material\.([A-Za-z_][A-Za-z0-9_]*)\s*;\s*(?://.*)?$"
    )
    hits = sorted(set(pattern.findall(text)))
    if len(hits) != 1:
        raise BindingError(f"{technique}: shader binding {shader_name!r} -> material RHS hits {hits}")
    return {
        "technique": technique,
        "techniquePath": str(path),
        "techniqueSha256": _sha(path),
        "shaderBinding": shader_name,
        "materialTextureName": hits[0],
        "assignment": f"{shader_name} = material.{hits[0]}",
    }


def build(special_path: Path, symbolic_path: Path, material_root: Path) -> dict[str, Any]:
    special = _load_json(special_path)
    symbolic = _load_json(symbolic_path)
    if special.get("format") != SPECIAL_FORMAT:
        raise BindingError(f"unexpected special census format {special.get('format')!r}")
    if symbolic.get("format") != SYMBOLIC_FORMAT:
        raise BindingError(f"unexpected symbolic format {symbolic.get('format')!r}")
    if special.get("map") != "mp_nuketown_2020" or symbolic.get("map") != "mp_nuketown_2020":
        raise BindingError("map identity mismatch")
    if int(special.get("summary", {}).get("pcServerDuplicateParentSelectionDependencyCount", -1)) != 0:
        raise BindingError("special population unexpectedly depends on duplicate-parent selection")
    if int(symbolic.get("summary", {}).get("symbolicBlockerCount", -1)) != 0:
        raise BindingError("symbolic source is not fully closed")

    shader_rows = {str(r["sha256"]): r for r in symbolic.get("shaderRows", [])}
    if len(shader_rows) != 5:
        raise BindingError(f"symbolic shader count {len(shader_rows)} != 5")

    group_rows = {str(r["groupKey"]): r for r in symbolic.get("groups", [])}
    if len(group_rows) != int(symbolic["summary"]["selectedTechniqueGroupCount"]):
        raise BindingError("symbolic group-key uniqueness failure")

    # A shader can be used by more than one exact group. Its bytes/RDEF must agree.
    shader_owners: dict[str, set[tuple[str, str]]] = {}
    for group in group_rows.values():
        owner = str(group.get("techniqueOwner") or "")
        if not owner:
            raise BindingError(f"group {group['groupKey']}: missing exact technique owner")
        for p in group.get("passes", []):
            for stage in p.get("pixelShaders", []):
                hh = str(stage.get("sha256") or "")
                rel = str(stage.get("relativeFile") or "")
                if hh in shader_rows:
                    shader_owners.setdefault(hh, set()).add((owner, rel))

    reflected: dict[str, dict[str, Any]] = {}
    for hh, shader_row in sorted(shader_rows.items()):
        owners = shader_owners.get(hh, set())
        if not owners:
            raise BindingError(f"shader {hh}: no exact group owner")
        reflected_variants = []
        for owner, rel in sorted(owners):
            path = Path(owner) / rel
            if _sha(path) != hh:
                raise BindingError(f"{path}: shader SHA mismatch")
            reflected_variants.append((_parse_rdef(path.read_bytes()), str(path)))
        canonical = reflected_variants[0][0]
        for rdef, path in reflected_variants[1:]:
            if rdef != canonical:
                raise BindingError(f"shader {hh}: RDEF disagreement at {path}")

        samples = shader_row.get("samples", [])
        if len(samples) != 1:
            raise BindingError(f"shader {hh}: expected exactly one sample, got {len(samples)}")
        sample = samples[0]
        t = int(sample["resourceRegister"])
        s = int(sample["samplerRegister"])
        tex = _one_resource(canonical, INPUT_TEXTURE, t, "t")
        sampler = _one_resource(canonical, INPUT_SAMPLER, s, "s")
        cb_symbols = sorted(
            {
                str(n.get("name"))
                for n in shader_row.get("nodes", [])
                if isinstance(n, dict)
                and n.get("kind") == "symbol"
                and isinstance(n.get("name"), str)
                and CB_SYMBOL_RE.match(str(n.get("name")))
            }
        )
        constants = [_resolve_cb_symbol(canonical, symbol) for symbol in cb_symbols]
        reflected[hh] = {
            "pixelShaderSha256": hh,
            "asset": shader_row.get("asset"),
            "shaderModel": canonical["shaderModel"],
            "textureBinding": {
                "register": t,
                "name": tex["name"],
                "inputType": tex["inputType"],
                "returnType": tex["returnType"],
                "dimension": tex["dimension"],
                "bindCount": tex["bindCount"],
            },
            "samplerBinding": {
                "register": s,
                "name": sampler["name"],
                "inputType": sampler["inputType"],
                "bindCount": sampler["bindCount"],
            },
            "constantSymbols": constants,
            "rdefDigestSha256": _digest(canonical),
        }

    special_materials = {str(r["material"]): r for r in special.get("materials", [])}
    if len(special_materials) != 11:
        raise BindingError(f"special Material count {len(special_materials)} != 11")

    material_rows = []
    program_binding_count = 0
    exact_texture_match_count = 0
    exact_technique_assignment_count = 0
    material_constant_match_count = 0
    unresolved_constant_symbols: set[tuple[str, str, str]] = set()
    sampler_states = set()
    images = set()
    technique_hashes = set()

    for name, special_row in sorted(special_materials.items()):
        path = _material_path(material_root, name)
        material = _load_json(path)
        if material.get("_game") != "t6" or material.get("_type") != "material":
            raise BindingError(f"{name}: unexpected OAT Material schema identity")
        if material.get("techniqueSet") != special_row.get("techniqueSet"):
            raise BindingError(
                f"{name}: Material TechniqueSet {material.get('techniqueSet')!r} != exact census {special_row.get('techniqueSet')!r}"
            )
        textures = material.get("textures", [])
        constants = material.get("constants", [])
        if not isinstance(textures, list) or not isinstance(constants, list):
            raise BindingError(f"{name}: malformed Material texture/constant arrays")
        constant_by_name = {str(c.get("name")): c for c in constants if isinstance(c, dict) and c.get("name")}
        programs_out = []
        for program in special_row.get("programs", []):
            if not isinstance(program, dict) or program.get("techniqueType") not in TARGET_TYPES:
                continue
            gk = str(program.get("groupKey") or "")
            if gk not in group_rows:
                raise BindingError(f"{name}: selected group {gk!r} not present in full-output symbolic evidence")
            group = group_rows[gk]
            shader_hashes = []
            for p in group.get("passes", []):
                for stage in p.get("pixelShaders", []):
                    hh = str(stage.get("sha256") or "")
                    if hh:
                        shader_hashes.append(hh)
            shader_hashes = sorted(set(shader_hashes))
            if len(shader_hashes) != 1:
                raise BindingError(f"{name}/{program.get('techniqueType')}: pixel shader set {shader_hashes}")
            hh = shader_hashes[0]
            if hh not in reflected:
                raise BindingError(f"{name}: shader {hh} missing reflected evidence")
            rr = reflected[hh]
            resource_name = rr["textureBinding"]["name"]

            technique_binding = _technique_material_texture_binding(
                str(program.get("techniqueOwner") or ""),
                str(program.get("technique") or ""),
                resource_name,
            )
            exact_technique_assignment_count += 1
            technique_hashes.add(technique_binding["techniqueSha256"])
            material_texture_name = technique_binding["materialTextureName"]
            texture_hits = [t for t in textures if isinstance(t, dict) and t.get("name") == material_texture_name]
            if len(texture_hits) != 1:
                raise BindingError(
                    f"{name}: exact Technique maps RDEF {resource_name!r} to material.{material_texture_name}; "
                    f"native Material texture hits {texture_hits}"
                )
            tex = texture_hits[0]
            sampler_state = tex.get("samplerState")
            if not isinstance(sampler_state, dict):
                raise BindingError(f"{name}: exact texture {material_texture_name!r} lacks samplerState")
            image = str(tex.get("image") or "")
            if not image:
                raise BindingError(f"{name}: exact texture {material_texture_name!r} lacks image identity")
            sampler_states.add(json.dumps(sampler_state, sort_keys=True, separators=(",", ":")))
            images.add(image)
            exact_texture_match_count += 1

            cb_out = []
            for c in rr["constantSymbols"]:
                var = c["variable"]
                mc = constant_by_name.get(var)
                row = dict(c)
                if mc is not None:
                    literal = mc.get("literal")
                    if not isinstance(literal, list) or len(literal) != 4:
                        raise BindingError(f"{name}: Material constant {var!r} has malformed literal")
                    row["materialConstant"] = {"name": var, "literal": literal}
                    material_constant_match_count += 1
                else:
                    row["materialConstant"] = None
                    unresolved_constant_symbols.add((c["constantBuffer"], var, c["symbol"]))
                cb_out.append(row)

            programs_out.append(
                {
                    "techniqueType": program.get("techniqueType"),
                    "technique": program.get("technique"),
                    "groupKey": gk,
                    "pixelShaderSha256": hh,
                    "rdefTexture": rr["textureBinding"],
                    "rdefSampler": rr["samplerBinding"],
                    "techniqueMaterialTextureBinding": technique_binding,
                    "materialTexture": {
                        "name": tex.get("name"),
                        "semantic": tex.get("semantic"),
                        "image": image,
                        "isMatureContent": tex.get("isMatureContent"),
                        "samplerState": sampler_state,
                    },
                    "constantSymbols": cb_out,
                }
            )
            program_binding_count += 1

        if not programs_out:
            raise BindingError(f"{name}: no unlit/emissive exact program bindings")
        material_rows.append(
            {
                "material": name,
                "family": special_row.get("family"),
                "techniqueSet": special_row.get("techniqueSet"),
                "materialJsonSha256": _sha(path),
                "programBindings": programs_out,
                "stateBitsEntry": material.get("stateBitsEntry"),
                "stateBits": material.get("stateBits"),
            }
        )

    result_core = {
        "reflectedShaders": [reflected[k] for k in sorted(reflected)],
        "materials": material_rows,
    }
    return {
        "format": FORMAT,
        "producer": "tools/t6_nuketown_special_material_input_binding_v1.py",
        "map": "mp_nuketown_2020",
        "sourceSpecialCensusSha256": _sha(special_path),
        "sourceFullOutputSymbolicSha256": _sha(symbolic_path),
        "summary": {
            "materialCount": len(material_rows),
            "programBindingCount": program_binding_count,
            "reflectedPixelShaderCount": len(reflected),
            "exactRdefTechniqueAssignmentCount": exact_technique_assignment_count,
            "exactRdefToMaterialTextureMatchCount": exact_texture_match_count,
            "uniqueTechniqueFileCount": len(technique_hashes),
            "uniqueImageCount": len(images),
            "uniqueSamplerStateCount": len(sampler_states),
            "materialConstantMatchCount": material_constant_match_count,
            "unresolvedNonMaterialConstantLeafCount": len(unresolved_constant_symbols),
        },
        **result_core,
        "unresolvedNonMaterialConstantLeaves": [
            {"constantBuffer": cb, "variable": var, "symbol": symbol}
            for cb, var, symbol in sorted(unresolved_constant_symbols)
        ],
        "evidenceDigestSha256": _digest(result_core),
        "proofBoundary": (
            "Each used texture register is named by exact DXBC RDEF, then resolved through the exact dumped Technique assignment from that shader variable to material.<name>, then joined by that exact right-hand name to one native OAT Material texture entry. "
            "No RDEF-name suffix rewrite or semantic/name resemblance is used. Shader bytes, Technique text and Material JSON all come from the same pinned-OAT run over SHA-pinned retail FastFiles; shader bytes are re-hashed against the native census and Technique files are independently SHA-256 retained. "
            "Material samplerState is retained exactly from OAT. Constant-buffer symbols are named only by RDEF and are joined to Material constants only on exact variable-name equality. "
            "Unmatched constant leaves remain unresolved runtime/code/shader inputs and are not assigned semantics by register position or name resemblance."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--special-census", type=Path, required=True)
    ap.add_argument("--symbolic", type=Path, required=True)
    ap.add_argument("--material-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    doc = build(a.special_census, a.symbolic, a.material_root)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    print(doc["evidenceDigestSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
