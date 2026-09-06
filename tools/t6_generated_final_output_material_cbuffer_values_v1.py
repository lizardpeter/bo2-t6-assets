#!/usr/bin/env python3
"""Resolve generated final-output material.* cbuffer bindings to retail literals.

Inputs:
- exact generated slot-4 final-output symbolic v3 (material -> exact PS SHA);
- exact final-output cbuffer RDEF/.tech signature v1;
- exact retained-world MaterialConstantDef archive v1.

For each material owner and each used cbuffer symbol whose exact `.tech`
assignment is ``material.<name>``:

  reflected source name
    -> T6 zero-seed R_HashString
    -> exactly one serialized MaterialConstantDef hash
    -> matching stored 12-byte name fragment
    -> exact float4 literal
    -> exact RDEF relative scalar component.

Values are resolved independently per generated Material even when several
materials share one TechniqueSet/CSO. `code.*`, unassigned, and other expression
sources remain explicitly unresolved here; no physical semantics are inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from t6_dxbc_material_constant_binding_v1 import t6_r_hash_string

FORMAT = "t6-generated-final-output-material-cbuffer-values-v1"
FINAL_FORMAT = "t6-generated-slot4-final-output-symbolic-v3"
CBUFFER_FORMAT = "t6-generated-final-output-cbuffer-signature-v1"
MATERIAL_CONSTANT_FORMAT = "t6-retail-world-material-constants-v1"


class FinalOutputMaterialCbufferValueError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _by_shader(doc: dict) -> dict[str, dict]:
    out = {}
    for row in doc.get("shaders", []):
        sha = str(row.get("sha256") or "")
        if not sha or sha in out:
            raise FinalOutputMaterialCbufferValueError(f"invalid/duplicate shader row {sha!r}")
        out[sha] = row
    return out


def _material_owners(final_doc: dict) -> dict[str, dict]:
    out = {}
    for row in final_doc.get("materials", []):
        material = str(row.get("material") or "")
        if not material or material in out:
            raise FinalOutputMaterialCbufferValueError(f"invalid/duplicate final-output material {material!r}")
        sha = str(row.get("pixelShaderSha256") or "").lower()
        technique = str(row.get("techniqueSet") or "")
        if not sha or not technique:
            raise FinalOutputMaterialCbufferValueError(f"{material!r}: missing exact shader/TechniqueSet identity")
        out[material] = {**row, "pixelShaderSha256": sha, "techniqueSet": technique}
    if not out:
        raise FinalOutputMaterialCbufferValueError("final-output sidecar has no material owners")
    return out


def _retail_materials(doc: dict) -> dict[str, dict]:
    out = {}
    for row in doc.get("materials", []):
        material = str(row.get("material") or "")
        if not material or material in out:
            raise FinalOutputMaterialCbufferValueError(f"invalid/duplicate retail material {material!r}")
        out[material] = row
    return out


def _assignment_for_technique(item: dict, technique: str) -> dict:
    matches = [
        row for row in item.get("techniqueAssignments", [])
        if str(row.get("techniqueSet") or "") == technique
    ]
    if len(matches) != 1:
        raise FinalOutputMaterialCbufferValueError(
            f"{item.get('symbol')}: TechniqueSet {technique!r} assignment count {len(matches)}, expected 1"
        )
    return matches[0]


def _constant_by_name(material_row: dict, name: str) -> dict:
    expected_hash = t6_r_hash_string(name, 0)
    candidates = [
        row for row in material_row.get("constants", [])
        if int(row.get("nameHash", -1)) == expected_hash
    ]
    if len(candidates) != 1:
        raise FinalOutputMaterialCbufferValueError(
            f"{material_row.get('material')!r}: material constant {name!r} hash 0x{expected_hash:08x} matched {len(candidates)} rows"
        )
    row = candidates[0]
    fragment = str(row.get("nameFragment") or "")
    expected_fragment = name[:12]
    if fragment != expected_fragment:
        raise FinalOutputMaterialCbufferValueError(
            f"{material_row.get('material')!r}: hash match for {name!r} has fragment {fragment!r} != {expected_fragment!r}"
        )
    literal = row.get("literal")
    if not isinstance(literal, list) or len(literal) != 4:
        raise FinalOutputMaterialCbufferValueError(
            f"{material_row.get('material')!r}: {name!r} does not carry an exact float4 literal"
        )
    return row


def build(final_doc: dict, cbuffer_doc: dict, material_constants_doc: dict) -> dict:
    if final_doc.get("format") != FINAL_FORMAT:
        raise FinalOutputMaterialCbufferValueError(f"unexpected final-output format {final_doc.get('format')!r}")
    if cbuffer_doc.get("format") != CBUFFER_FORMAT:
        raise FinalOutputMaterialCbufferValueError(f"unexpected cbuffer format {cbuffer_doc.get('format')!r}")
    if material_constants_doc.get("format") != MATERIAL_CONSTANT_FORMAT:
        raise FinalOutputMaterialCbufferValueError(
            f"unexpected MaterialConstantDef archive format {material_constants_doc.get('format')!r}"
        )

    owners = _material_owners(final_doc)
    shaders = _by_shader(cbuffer_doc)
    retail = _retail_materials(material_constants_doc)
    missing_retail = sorted(set(owners) - set(retail))
    if missing_retail:
        raise FinalOutputMaterialCbufferValueError(
            f"{len(missing_retail)} final-output materials absent from retail constant archive; first={missing_retail[0]!r}"
        )

    rows = []
    source_classes = Counter()
    resolved_count = material_source_count = 0
    unresolved_source_count = 0
    unique_names = set()
    unique_value_bits = set()
    by_shader_value_signatures: dict[str, set[str]] = defaultdict(set)

    for material in sorted(owners):
        owner = owners[material]
        sha = owner["pixelShaderSha256"]
        technique = owner["techniqueSet"]
        shader = shaders.get(sha)
        if shader is None:
            raise FinalOutputMaterialCbufferValueError(
                f"{material!r}: exact shader {sha} absent from cbuffer signature sidecar"
            )
        if technique not in [str(x) for x in shader.get("techniqueSets", [])]:
            raise FinalOutputMaterialCbufferValueError(
                f"{material!r}: TechniqueSet {technique!r} absent from shader {sha} cbuffer ownership"
            )
        retail_row = retail[material]
        bindings = []
        unresolved = []
        for item in shader.get("usedCbufferSymbols", []):
            assignment = _assignment_for_technique(item, technique)
            source_class = str(assignment.get("sourceClass") or "")
            source_classes[source_class] += 1
            base = {
                "symbol": item.get("symbol"),
                "nodeIds": sorted(int(x) for x in item.get("nodeIds", [])),
                "buffer": item.get("buffer"),
                "variable": item.get("variable"),
                "sourceClass": source_class,
                "sourceExpression": assignment.get("sourceExpression"),
                "sourceName": assignment.get("sourceName"),
            }
            if source_class != "material":
                unresolved.append(base)
                unresolved_source_count += 1
                continue
            material_source_count += 1
            source_name = str(assignment.get("sourceName") or "")
            if not source_name:
                raise FinalOutputMaterialCbufferValueError(
                    f"{material!r} {item.get('symbol')}: material source has no sourceName"
                )
            constant = _constant_by_name(retail_row, source_name)
            relative_scalar = int((item.get("variable") or {}).get("relativeScalarIndex", -1))
            if not 0 <= relative_scalar < 4:
                raise FinalOutputMaterialCbufferValueError(
                    f"{material!r} {item.get('symbol')}: relative scalar index {relative_scalar} cannot map to MaterialConstantDef float4"
                )
            literal = [float(x) for x in constant["literal"]]
            scalar = literal[relative_scalar]
            resolved = {
                **base,
                "materialConstant": {
                    "name": source_name,
                    "nameHash": int(constant["nameHash"]),
                    "nameHashHex": constant.get("nameHashHex", f"0x{int(constant['nameHash']):08x}"),
                    "nameFragment": constant.get("nameFragment"),
                    "constantIndex": int(constant.get("index", -1)),
                    "fileOffset": int(constant.get("fileOffset", -1)),
                    "serializedSha256": constant.get("serializedSha256"),
                    "literal": literal,
                    "literalComponentIndex": relative_scalar,
                    "scalarValue": scalar,
                },
            }
            bindings.append(resolved)
            resolved_count += 1
            unique_names.add(source_name)
            value_signature = _jhash({
                "nameHash": int(constant["nameHash"]),
                "literal": literal,
                "component": relative_scalar,
            })
            unique_value_bits.add(value_signature)
            by_shader_value_signatures[sha].add(value_signature)

        material_signature = _jhash([
            {
                "symbol": row["symbol"],
                "sourceName": row["sourceName"],
                "literal": row["materialConstant"]["literal"],
                "component": row["materialConstant"]["literalComponentIndex"],
            }
            for row in bindings
        ])
        rows.append({
            "material": material,
            "techniqueSet": technique,
            "pixelShaderSha256": sha,
            "materialIndex": retail_row.get("materialIndex"),
            "materialStart": retail_row.get("materialStart"),
            "materialArchiveSha256": retail_row.get("materialArchiveSha256"),
            "retailConstantCount": int(retail_row.get("constantCount", len(retail_row.get("constants", [])))),
            "resolvedMaterialBindingCount": len(bindings),
            "unresolvedNonMaterialBindingCount": len(unresolved),
            "resolvedMaterialBindings": bindings,
            "unresolvedNonMaterialBindings": unresolved,
            "materialResolvedValueSignatureSha256": material_signature,
        })

    summary = {
        "materialCount": len(rows),
        "materialSourceBindingOccurrenceCount": material_source_count,
        "resolvedMaterialSourceBindingOccurrenceCount": resolved_count,
        "unresolvedNonMaterialSourceBindingOccurrenceCount": unresolved_source_count,
        "uniqueMaterialConstantNameCount": len(unique_names),
        "uniqueResolvedValueSignatureCount": len(unique_value_bits),
        "techniqueAssignmentSourceClassCounts": dict(sorted(source_classes.items())),
        "shaderCountWithMaterialValueVariation": sum(
            1 for values in by_shader_value_signatures.values() if len(values) > 1
        ),
    }
    if resolved_count != material_source_count:
        raise FinalOutputMaterialCbufferValueError("not all exact material.* cbuffer bindings resolved")
    return {
        "format": FORMAT,
        "map": material_constants_doc.get("map"),
        "sourceFinalOutputFormat": FINAL_FORMAT,
        "sourceCbufferFormat": CBUFFER_FORMAT,
        "sourceMaterialConstantFormat": MATERIAL_CONSTANT_FORMAT,
        "materials": rows,
        "summary": summary,
        "rowsSha256": _jhash(rows),
        "proofBoundary": (
            "Per generated Material exact .tech material.* cbuffer assignment -> zero-seed T6 name hash -> one direct "
            "serialized retained-world MaterialConstantDef -> exact float4/scalar component. Shared shaders do not share "
            "values by assumption. code.*, unassigned, and other sources remain unresolved; names carry no physical meaning."
        ),
    }


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--cbuffer-signature',type=Path,required=True);p.add_argument('--material-constants',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.cbuffer_signature.read_text()),json.loads(a.material_constants.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
