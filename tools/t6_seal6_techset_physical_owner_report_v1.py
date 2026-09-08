#!/usr/bin/env python3
"""Enumerate exact physical SEAL6 TechniqueSet owners without precedence.

For each requested TechniqueSet, every physical OAT `.techset` copy in the
explicit root universe is parsed independently. Each declared child Technique is
then required to exist in that same parent-owner root (the OAT dumper provenance
contract) and its parsed pass/stage graph is hashed with the existing v4 census
helpers. The report compares physical parent definitions but never selects a
runtime winner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import t6_oat_material_shader_census_v4 as v4

FORMAT = "t6-seal6-techset-physical-owner-report-v1"


class TechsetOwnerReportError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("root must be LABEL=PATH")
    label, raw = value.split("=", 1)
    path = Path(raw).resolve()
    if not label.strip() or not path.is_dir():
        raise argparse.ArgumentTypeError(f"invalid root {value!r}")
    return label.strip(), path


def _binding_signature(bindings: list[dict[str, Any]]) -> str:
    canonical = [
        {
            "technique": row.get("technique"),
            "types": row.get("types", []),
        }
        for row in bindings
    ]
    return v4.v3._jhash(canonical)


def _owner_record(label: str, root: Path, techset: str) -> dict[str, Any]:
    relative = Path("techsets") / f"{techset}.techset"
    path = root / relative
    bindings, errors = v4.v3.v1.oat.parse_techset(path.read_text(encoding="utf-8", errors="strict"))
    if errors:
        raise TechsetOwnerReportError(f"{techset}@{label}: parse errors {errors[:4]}")
    if not bindings:
        raise TechsetOwnerReportError(f"{techset}@{label}: no technique bindings")

    children = []
    for row in bindings:
        technique = str(row.get("technique") or "")
        if not technique:
            raise TechsetOwnerReportError(f"{techset}@{label}: empty child Technique identity")
        child = root / "techniques" / f"{technique}.tech"
        if not child.is_file():
            raise TechsetOwnerReportError(
                f"{techset}@{label}: parent owner did not emit child {child.relative_to(root).as_posix()}"
            )
        passes, file_record = v4.v3._parse_passes_from_owner(root, technique)
        children.append({
            "technique": technique,
            "types": row.get("types", []),
            "parsedPassStageIdentitySha256": v4.v3._jhash(passes),
            "passCount": len(passes),
            "techniqueFile": file_record,
            "passes": passes,
        })

    signature = {
        "bindings": [
            {
                "technique": row["technique"],
                "types": row["types"],
                "parsedPassStageIdentitySha256": row["parsedPassStageIdentitySha256"],
                "passCount": row["passCount"],
            }
            for row in children
        ]
    }
    return {
        "rootLabel": label,
        "root": str(root),
        "relativeFile": relative.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
        "bindingStructureSha256": _binding_signature(bindings),
        "fullParentChildSignatureSha256": v4.v3._jhash(signature),
        "bindings": children,
    }


def build(roots: list[tuple[str, Path]], techsets: list[str]) -> dict[str, Any]:
    if not roots or not techsets:
        raise TechsetOwnerReportError("roots and techsets must be non-empty")
    if len({str(root.resolve()) for _label, root in roots}) != len(roots):
        raise TechsetOwnerReportError("duplicate physical root path")
    if len(set(techsets)) != len(techsets):
        raise TechsetOwnerReportError("duplicate requested TechniqueSet")

    rows = []
    for techset in techsets:
        owners = []
        relative = Path("techsets") / f"{techset}.techset"
        for label, root in roots:
            if (root / relative).is_file():
                owners.append(_owner_record(label, root, techset))
        if not owners:
            raise TechsetOwnerReportError(f"{techset}: no physical owner in supplied root universe")
        parent_ids = {(row["bytes"], row["sha256"]) for row in owners}
        binding_ids = {row["bindingStructureSha256"] for row in owners}
        full_ids = {row["fullParentChildSignatureSha256"] for row in owners}
        rows.append({
            "techniqueSet": techset,
            "physicalOwnerCount": len(owners),
            "parentTextByteIdenticalAcrossOwners": len(parent_ids) == 1,
            "bindingStructureInvariantAcrossOwners": len(binding_ids) == 1,
            "parentChildShaderSignatureInvariantAcrossOwners": len(full_ids) == 1,
            "owners": owners,
            "activeRetailClientOwnerResolved": len(full_ids) == 1,
            "activeRetailClientOwner": (
                "equivalent-parent-child-signature-no-winner-required" if len(full_ids) == 1 else None
            ),
        })

    return {
        "format": FORMAT,
        "roots": [{"label": label, "root": str(root)} for label, root in roots],
        "techniqueSets": rows,
        "summary": {
            "requestedTechniqueSets": len(rows),
            "physicalOwnerCopies": sum(row["physicalOwnerCount"] for row in rows),
            "multiOwnerTechniqueSets": sum(row["physicalOwnerCount"] > 1 for row in rows),
            "divergentParentChildSignatureTechniqueSets": sum(
                not row["parentChildShaderSignatureInvariantAcrossOwners"] for row in rows
            ),
            "unresolvedRetailClientOwnerTechniqueSets": sum(
                not row["activeRetailClientOwnerResolved"] for row in rows
            ),
        },
        "proofBoundary": (
            "Exact physical OAT TechniqueSet files and same-root child Technique/pass/shader outputs inside the explicitly supplied root universe. Physical variants are compared by exact serialized identity, binding structure, and parsed parent-child pass/stage signatures. No zone order, patch naming, server projection, or visual similarity selects a retail-client winner."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=_parse_root, action="append", required=True, metavar="LABEL=PATH")
    ap.add_argument("--techset", action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    result = build(a.root, a.techset)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact = {
        "summary": result["summary"],
        "techniqueSets": [
            {
                "techniqueSet": row["techniqueSet"],
                "physicalOwnerCount": row["physicalOwnerCount"],
                "parentTextByteIdenticalAcrossOwners": row["parentTextByteIdenticalAcrossOwners"],
                "bindingStructureInvariantAcrossOwners": row["bindingStructureInvariantAcrossOwners"],
                "parentChildShaderSignatureInvariantAcrossOwners": row["parentChildShaderSignatureInvariantAcrossOwners"],
                "activeRetailClientOwnerResolved": row["activeRetailClientOwnerResolved"],
                "owners": [
                    {
                        "rootLabel": owner["rootLabel"],
                        "bytes": owner["bytes"],
                        "sha256": owner["sha256"],
                        "bindingStructureSha256": owner["bindingStructureSha256"],
                        "fullParentChildSignatureSha256": owner["fullParentChildSignatureSha256"],
                        "bindings": [
                            {
                                "technique": child["technique"],
                                "types": child["types"],
                                "passCount": child["passCount"],
                                "parsedPassStageIdentitySha256": child["parsedPassStageIdentitySha256"],
                            }
                            for child in owner["bindings"]
                        ],
                    }
                    for owner in row["owners"]
                ],
            }
            for row in result["techniqueSets"]
        ],
    }
    print(json.dumps(compact, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
