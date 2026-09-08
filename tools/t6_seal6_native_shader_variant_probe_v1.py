#!/usr/bin/env python3
"""Resolve exact shader programs for physical SEAL6 Material/TechniqueSet variants.

A variant is ``LABEL=MATERIAL_ROOT::PARENT_ROOT::MATERIAL``. The native Material
JSON is read from the explicitly named physical Material root, staged alone, and
then resolved only against the explicitly named physical TechniqueSet/Technique
parent root. This is necessary because T6 Materials may reference TechniqueSets
owned by another FastFile, while same-name TechniqueSets may also have divergent
physical parent variants.

The parent-root choice must come from separate exact owner evidence. This probe
never derives it from root order, naming, patch assumptions, or server behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import t6_oat_material_shader_census_v4 as v4

FORMAT = "t6-seal6-native-shader-variant-probe-v1"


class VariantProbeError(RuntimeError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("shader root must be LABEL=PATH")
    label, raw = value.split("=", 1)
    path = Path(raw).resolve()
    if not label.strip() or not path.is_dir():
        raise argparse.ArgumentTypeError(f"invalid shader root {value!r}")
    return label.strip(), path


def _parse_variant(value: str) -> tuple[str, Path, Path, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("variant must be LABEL=MATERIAL_ROOT::PARENT_ROOT::MATERIAL")
    label, rest = value.split("=", 1)
    parts = rest.split("::", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("variant must be LABEL=MATERIAL_ROOT::PARENT_ROOT::MATERIAL")
    material_root = Path(parts[0]).resolve()
    parent_root = Path(parts[1]).resolve()
    material = parts[2]
    if not label.strip() or not material_root.is_dir() or not parent_root.is_dir() or not material:
        raise argparse.ArgumentTypeError(f"invalid variant {value!r}")
    return label.strip(), material_root, parent_root, material


def _owner_label(path: str, roots: dict[str, str]) -> str:
    resolved = str(Path(path).resolve())
    label = roots.get(resolved)
    if label is None:
        raise VariantProbeError(f"census returned owner outside supplied shader roots: {path}")
    return label


def _program_identity(row: dict[str, Any], roots: dict[str, str]) -> dict[str, Any]:
    return {
        "techniqueType": row.get("techniqueType"),
        "technique": row.get("technique"),
        "groupKey": row.get("groupKey"),
        "passStageIdentitySha256": row.get("passStageIdentitySha256"),
        "passCount": row.get("passCount"),
        "techniqueOwner": _owner_label(str(row.get("techniqueOwner") or ""), roots),
        "parentTechniqueSetOwners": [
            _owner_label(str(value), roots) for value in row.get("parentTechniqueSetOwners", [])
        ],
    }


def _canonical_shader_signature(material_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "techniqueSet": material_row.get("techniqueSet"),
        "declaredTechniqueTypes": material_row.get("declaredTechniqueTypes", []),
        "hasLitBinding": bool(material_row.get("hasLitBinding")),
        "programs": [
            {
                "techniqueType": p.get("techniqueType"),
                "technique": p.get("technique"),
                "groupKey": p.get("groupKey"),
                "passStageIdentitySha256": p.get("passStageIdentitySha256"),
                "passCount": p.get("passCount"),
            }
            for p in material_row.get("programs", [])
        ],
    }


def build(
    shader_roots: list[tuple[str, Path]],
    variants: list[tuple[str, Path, Path, str]],
) -> dict[str, Any]:
    if not shader_roots or not variants:
        raise VariantProbeError("shader roots and variants must be non-empty")
    root_labels = {str(root.resolve()): label for label, root in shader_roots}
    if len(root_labels) != len(shader_roots):
        raise VariantProbeError("duplicate shader root path")

    rows = []
    for label, material_root, parent_root, material in variants:
        material_key = str(material_root.resolve())
        parent_key = str(parent_root.resolve())
        material_root_label = root_labels.get(material_key)
        parent_root_label = root_labels.get(parent_key)
        if material_root_label is None:
            raise VariantProbeError(f"{label}: physical Material root is not in supplied root universe")
        if parent_root_label is None:
            raise VariantProbeError(f"{label}: physical parent root is not in supplied root universe")

        source = material_root / "materials" / f"{material}.json"
        if not source.is_file():
            raise VariantProbeError(f"{label}: physical Material missing: {source}")
        raw = source.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8-sig"))
        except Exception as exc:
            raise VariantProbeError(f"{label}: invalid Material JSON: {exc}") from exc
        if doc.get("_game") != "t6" or doc.get("_type") != "material":
            raise VariantProbeError(f"{label}: source is not native T6 Material JSON")

        techset = str(doc.get("techniqueSet") or "")
        if not techset:
            raise VariantProbeError(f"{label}: Material has empty techniqueSet")
        parent_file = parent_root / "techsets" / f"{techset}.techset"
        if not parent_file.is_file():
            raise VariantProbeError(
                f"{label}: explicitly selected parent root does not own TechniqueSet {techset!r}"
            )

        with tempfile.TemporaryDirectory(prefix=f"t6-seal6-{label}-") as td:
            staged_root = Path(td)
            staged = staged_root / "materials" / f"{material}.json"
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(raw)
            census = v4.build(staged_root, [parent_root])

        summary = census.get("summary") or {}
        if int(summary.get("unresolvedMaterialCount", -1)) != 0:
            raise VariantProbeError(f"{label}: explicit-parent v4 census unresolved Material dependency")
        if int(summary.get("divergentParentOwnedDependencyCount", -1)) != 0:
            raise VariantProbeError(f"{label}: explicit-parent v4 census has divergent parent-owned dependency")
        material_rows = [r for r in census.get("materials", []) if r.get("material") == material]
        if len(material_rows) != 1:
            raise VariantProbeError(f"{label}: expected one exact material row, got {len(material_rows)}")
        m = material_rows[0]
        if m.get("materialJsonSha256") != _sha(raw):
            raise VariantProbeError(f"{label}: staged Material identity drift")
        if str(m.get("techniqueSet") or "") != techset:
            raise VariantProbeError(f"{label}: TechniqueSet identity drift")

        owners = [_owner_label(str(value), root_labels) for value in m.get("techniqueSetOwners", [])]
        if owners != [parent_root_label]:
            raise VariantProbeError(f"{label}: explicit parent TechniqueSet owner drift: {owners!r}")
        programs = [_program_identity(p, root_labels) for p in m.get("programs", [])]
        if any(p["techniqueOwner"] != parent_root_label for p in programs):
            raise VariantProbeError(f"{label}: explicit parent Technique owner drift")

        signature = _canonical_shader_signature(m)
        rows.append({
            "variant": label,
            "material": material,
            "physicalMaterialRoot": material_key,
            "physicalMaterialRootLabel": material_root_label,
            "physicalParentRoot": parent_key,
            "physicalParentRootLabel": parent_root_label,
            "physicalMaterialBytes": len(raw),
            "physicalMaterialSha256": _sha(raw),
            "techniqueSet": techset,
            "techniqueSetOwners": owners,
            "declaredTechniqueTypes": m.get("declaredTechniqueTypes", []),
            "hasLitBinding": bool(m.get("hasLitBinding")),
            "programs": programs,
            "shaderSignature": signature,
            "shaderSignatureSha256": _sha(
                json.dumps(signature, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ),
            "v4Summary": summary,
        })

    by_material: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_material.setdefault(row["material"], []).append(row)
    comparisons = []
    for material, copies in sorted(by_material.items()):
        sigs = {row["shaderSignatureSha256"] for row in copies}
        comparisons.append({
            "material": material,
            "variantCount": len(copies),
            "shaderSignatureInvariantAcrossPhysicalVariants": len(sigs) == 1,
            "shaderSignatureSha256Values": sorted(sigs),
            "variants": [row["variant"] for row in copies],
        })

    return {
        "format": FORMAT,
        "shaderRoots": [{"label": label, "root": str(root)} for label, root in shader_roots],
        "variants": rows,
        "comparisons": comparisons,
        "summary": {
            "variantCount": len(rows),
            "materialCount": len(by_material),
            "allVariantsHaveLitBinding": all(row["hasLitBinding"] for row in rows),
            "materialsWithDivergentPhysicalShaderSignatures": sum(
                not row["shaderSignatureInvariantAcrossPhysicalVariants"] for row in comparisons
            ),
        },
        "proofBoundary": (
            "Each variant explicitly names both the physical Material root and the physical TechniqueSet/Technique parent root. The parent selection must come from separate exact physical-owner evidence. The staged Material is resolved only against that parent root through the parent-provenance-aware v4 census. No root order or runtime winner is inferred; divergent variants remain separate until retail t6mp.exe/runtime precedence is independently closed."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shader-root", action="append", type=_parse_root, required=True, metavar="LABEL=PATH")
    ap.add_argument(
        "--variant",
        action="append",
        type=_parse_variant,
        required=True,
        metavar="LABEL=MATERIAL_ROOT::PARENT_ROOT::MATERIAL",
    )
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    result = build(a.shader_root, a.variant)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "summary": result["summary"],
        "comparisons": result["comparisons"],
        "variants": [
            {
                "variant": r["variant"],
                "material": r["material"],
                "physicalMaterialRootLabel": r["physicalMaterialRootLabel"],
                "physicalParentRootLabel": r["physicalParentRootLabel"],
                "techniqueSet": r["techniqueSet"],
                "signature": r["shaderSignatureSha256"],
                "programs": r["programs"],
            }
            for r in result["variants"]
        ],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
