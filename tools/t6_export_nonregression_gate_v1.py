#!/usr/bin/env python3
"""Fail-closed non-regression gate for T6 GLB exports.

The checker is intentionally asset-agnostic.  Map/model-specific expectations live
in JSON contracts, not in this tool.  A contract can partition the material table
(e.g. world vs placed XModels for a combined fixture) and assert monotonic floors or
exact invariants over the resulting metrics.

This exists to make it impossible for a later preview/release stage to silently
bypass an earlier proven stage while still being labelled an improvement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


class GateError(RuntimeError):
    pass


def read_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    if len(data) < 20:
        raise GateError(f"{path}: too small for GLB2")
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise GateError(f"{path}: invalid GLB2 header")
    off = 12
    document = None
    bin_payload = b""
    while off < len(data):
        if off + 8 > len(data):
            raise GateError(f"{path}: truncated GLB chunk header")
        length, kind = struct.unpack_from("<I4s", data, off)
        off += 8
        end = off + length
        if end > len(data):
            raise GateError(f"{path}: truncated GLB chunk")
        payload = data[off:end]
        off = end
        if kind == b"JSON":
            if document is not None:
                raise GateError(f"{path}: duplicate JSON chunk")
            document = json.loads(payload.rstrip(b" \0"))
        elif kind == b"BIN\0":
            if bin_payload:
                raise GateError(f"{path}: multiple BIN chunks are unsupported")
            bin_payload = payload
    if document is None:
        raise GateError(f"{path}: missing JSON chunk")
    buffers = document.get("buffers", [])
    if bin_payload and (len(buffers) != 1 or int(buffers[0].get("byteLength", -1)) != len(bin_payload)):
        raise GateError(f"{path}: BIN byteLength mismatch")
    return document, data


def material_name(material: dict[str, Any]) -> str:
    t6 = ((material.get("extras") or {}).get("T6") or {})
    return str(t6.get("sourceMaterial") or material.get("name") or "")


def material_has_color(material: dict[str, Any]) -> bool:
    return (material.get("pbrMetallicRoughness") or {}).get("baseColorTexture") is not None


def material_has_normal(material: dict[str, Any]) -> bool:
    return material.get("normalTexture") is not None


def material_has_emissive(material: dict[str, Any]) -> bool:
    return material.get("emissiveTexture") is not None


def material_has_occlusion(material: dict[str, Any]) -> bool:
    return material.get("occlusionTexture") is not None


def partition_indices(spec: dict[str, Any], material_count: int) -> set[int]:
    start = int(spec.get("start", 0))
    end_value = spec.get("end")
    end = material_count if end_value is None else int(end_value)
    if start < 0 or end < start or end > material_count:
        raise GateError(f"invalid material partition [{start},{end}) for {material_count} materials")
    return set(range(start, end))


def primitive_material_usage(document: dict[str, Any]) -> dict[int, int]:
    usage: dict[int, int] = {}
    materials = document.get("materials", [])
    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            material = primitive.get("material")
            if material is None:
                continue
            if not isinstance(material, int) or not 0 <= material < len(materials):
                raise GateError(
                    f"mesh {mesh_index} primitive {primitive_index}: invalid material index {material!r}"
                )
            usage[material] = usage.get(material, 0) + 1
    return usage


def collect_partition_metrics(
    document: dict[str, Any],
    indices: set[int],
    usage: dict[int, int],
    generic_prefixes: tuple[str, ...],
) -> dict[str, Any]:
    materials = document.get("materials", [])
    rows = [(i, materials[i]) for i in sorted(indices)]
    referenced = [(i, m) for i, m in rows if usage.get(i, 0) > 0]

    def is_generic(m: dict[str, Any]) -> bool:
        name = material_name(m)
        return any(name.startswith(prefix) for prefix in generic_prefixes)

    generic_refs = sum(usage.get(i, 0) for i, m in referenced if is_generic(m))
    return {
        "materialCount": len(rows),
        "referencedMaterialCount": len(referenced),
        "baseColorTexturedMaterials": sum(1 for _, m in rows if material_has_color(m)),
        "normalTexturedMaterials": sum(1 for _, m in rows if material_has_normal(m)),
        "colorAndNormalTexturedMaterials": sum(
            1 for _, m in rows if material_has_color(m) and material_has_normal(m)
        ),
        "emissiveTexturedMaterials": sum(1 for _, m in rows if material_has_emissive(m)),
        "occlusionTexturedMaterials": sum(1 for _, m in rows if material_has_occlusion(m)),
        "nonOpaqueMaterials": sum(1 for _, m in rows if m.get("alphaMode", "OPAQUE") != "OPAQUE"),
        "doubleSidedMaterials": sum(1 for _, m in rows if m.get("doubleSided") is True),
        "genericMaterialCount": sum(1 for _, m in rows if is_generic(m)),
        "genericReferencedMaterialCount": sum(1 for _, m in referenced if is_generic(m)),
        "genericPrimitiveReferences": generic_refs,
        "primitiveReferences": sum(usage.get(i, 0) for i in indices),
    }


def collect_metrics(document: dict[str, Any], glb_bytes: bytes, contract: dict[str, Any]) -> dict[str, Any]:
    materials = document.get("materials", [])
    usage = primitive_material_usage(document)
    scenes = document.get("scenes", [])
    scene_index = int(document.get("scene", 0)) if scenes else 0
    if scenes and not 0 <= scene_index < len(scenes):
        raise GateError(f"default scene index {scene_index} is invalid")
    top = list(scenes[scene_index].get("nodes", [])) if scenes else []
    nodes = document.get("nodes", [])
    if any(not isinstance(i, int) or not 0 <= i < len(nodes) for i in top):
        raise GateError("scene contains invalid top-level node index")

    generic_prefixes = tuple(str(x) for x in contract.get("genericMaterialPrefixes", ["material_surface_"]))
    all_indices = set(range(len(materials)))
    metrics: dict[str, Any] = {
        "glb": {
            "bytes": len(glb_bytes),
            "sha256": hashlib.sha256(glb_bytes).hexdigest(),
            "materialCount": len(materials),
            "imageCount": len(document.get("images", [])),
            "textureCount": len(document.get("textures", [])),
            "meshCount": len(document.get("meshes", [])),
            "nodeCount": len(nodes),
            "accessorCount": len(document.get("accessors", [])),
            "bufferViewCount": len(document.get("bufferViews", [])),
        },
        "scene": {
            "topLevelNodes": len(top),
            "topLevelNodesWithChildren": sum(1 for i in top if nodes[i].get("children")),
            "meshNodes": sum(1 for n in nodes if "mesh" in n),
        },
        "materials": collect_partition_metrics(document, all_indices, usage, generic_prefixes),
        "partitions": {},
    }
    for name, spec in (contract.get("materialPartitions") or {}).items():
        indices = partition_indices(spec, len(materials))
        metrics["partitions"][str(name)] = collect_partition_metrics(
            document, indices, usage, generic_prefixes
        )
    return metrics


def get_path(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for piece in path.split("."):
        if not isinstance(value, dict) or piece not in value:
            raise GateError(f"metric path not found: {path}")
        value = value[piece]
    return value


def evaluate_rule(actual: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "ge":
        return actual >= expected
    if op == "gt":
        return actual > expected
    if op == "le":
        return actual <= expected
    if op == "lt":
        return actual < expected
    raise GateError(f"unsupported comparison operator {op!r}")


def run(glb_path: Path, contract_path: Path, report_path: Path | None = None) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("format") != "t6-export-nonregression-contract-v1":
        raise GateError(f"{contract_path}: unsupported contract format")
    document, glb_bytes = read_glb(glb_path)
    metrics = collect_metrics(document, glb_bytes, contract)
    results = []
    failures = []
    for rule in contract.get("rules", []):
        path = str(rule["path"])
        op = str(rule["op"])
        expected = rule["value"]
        actual = get_path(metrics, path)
        passed = evaluate_rule(actual, op, expected)
        row = {
            "name": str(rule.get("name") or path),
            "path": path,
            "op": op,
            "expected": expected,
            "actual": actual,
            "passed": passed,
        }
        results.append(row)
        if not passed:
            failures.append(row)
    report = {
        "format": "t6-export-nonregression-report-v1",
        "asset": contract.get("asset"),
        "candidate": str(glb_path),
        "contract": str(contract_path),
        "metrics": metrics,
        "rules": results,
        "passed": not failures,
        "failureCount": len(failures),
        "failures": failures,
        "policy": (
            "A candidate may extend a fixture, but it may not cross below any retained exact "
            "or monotonic floor encoded by its contract. Map/model-specific floors belong in "
            "contracts; exporter logic remains generic."
        ),
    }
    if report_path is not None:
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failures:
        raise GateError(json.dumps({"failureCount": len(failures), "failures": failures}, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = run(args.glb, args.contract, args.report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
