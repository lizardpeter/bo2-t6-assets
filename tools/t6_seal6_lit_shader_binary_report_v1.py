#!/usr/bin/env python3
"""Close exact ordinary-lit DXBC identities for the SEAL6 target families.

Input is the fail-closed physical TechniqueSet-owner report. For every physical
owner of the three SEAL6 target TechniqueSets this adapter selects only the exact
``lit`` binding, requires one pass with one vertex + one pixel stage, verifies the
referenced CSO against its OAT byte-count/SHA record, validates the DXBC container
and RDEF reflection, and optionally archives each unique CSO by exact SHA-256.

The report deliberately distinguishes:

* serialized parent/child/pass identity; and
* actual executable VS/PS DXBC byte identity.

That distinction matters for the hero head: divergent zone-owned Technique
metadata may still execute byte-identical shader programs. No retail-client
TechniqueSet winner is selected when physical parent definitions diverge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from t6_dxbc_inspect_v1 import inspect_dxbc

FORMAT = "t6-seal6-lit-shader-binary-report-v1"
OWNER_FORMAT = "t6-seal6-techset-physical-owner-report-v1"

TARGET_TECHSETS = (
    "mc_sw4_3d_char_skin_hero_9949fq1j",
    "mc_sw4_3d_char_skin_j92387z3",
    "mc_sw4_3d_char_eye_cornea_2eww29wu",
)


class Seal6LitShaderBinaryError(RuntimeError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("root must be LABEL=PATH")
    label, raw = value.split("=", 1)
    path = Path(raw).resolve()
    if not label.strip() or not path.is_dir():
        raise argparse.ArgumentTypeError(f"invalid root {value!r}")
    return label.strip(), path


def _safe_rel(value: Any) -> Path:
    text = str(value or "")
    path = Path(text)
    if not text or path.is_absolute() or ".." in path.parts:
        raise Seal6LitShaderBinaryError(f"unsafe shader relative path {text!r}")
    return path


def _stage_kind(value: Any) -> str:
    text = str(value or "")
    if text == "vertexShader":
        return "vertex"
    if text == "pixelShader":
        return "pixel"
    raise Seal6LitShaderBinaryError(f"unsupported ordinary-lit stage kind {text!r}")


def _material_arguments(stage: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for row in stage.get("arguments", []):
        if row.get("sourceClass") != "material":
            continue
        prop = str(row.get("materialProperty") or "")
        if not prop:
            raise Seal6LitShaderBinaryError("material stage argument has empty materialProperty")
        result.append(prop)
    if len(result) != len(set(result)):
        raise Seal6LitShaderBinaryError(f"duplicate Material arguments in shader stage: {result}")
    return result


def _registry_pairs(doc: dict[str, Any] | None) -> dict[tuple[str, str], list[str]]:
    if doc is None:
        return {}
    if doc.get("format") != "t6-retail-lprobe-lit-semantics-v1":
        raise Seal6LitShaderBinaryError(
            f"unsupported solved Blender semantics registry {doc.get('format')!r}"
        )
    out: dict[tuple[str, str], list[str]] = {}
    for family in doc.get("families", []):
        try:
            vs = str(family["vertexShader"]["dxbcSha256"]).lower()
            ps = str(family["pixelShader"]["dxbcSha256"]).lower()
            family_id = str(family["id"])
        except (KeyError, TypeError) as exc:
            raise Seal6LitShaderBinaryError("malformed solved Blender semantics family") from exc
        out.setdefault((vs, ps), []).append(family_id)
    return out


def _inspect_stage(
    root: Path,
    stage: dict[str, Any],
    *,
    archive_dir: Path | None,
) -> dict[str, Any]:
    kind = _stage_kind(stage.get("kind"))
    rel = _safe_rel(stage.get("relativeFile"))
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise Seal6LitShaderBinaryError(f"shader path escaped physical root: {path}") from exc
    if not path.is_file():
        raise Seal6LitShaderBinaryError(f"missing exact OAT shader binary: {path}")
    raw = path.read_bytes()
    expected_bytes = int(stage.get("bytes", -1))
    expected_sha = str(stage.get("sha256") or "").lower()
    actual_sha = _sha(raw)
    if expected_bytes != len(raw) or expected_sha != actual_sha:
        raise Seal6LitShaderBinaryError(
            f"{rel}: OAT stage identity drift bytes={len(raw)}/{expected_bytes} sha={actual_sha}/{expected_sha}"
        )
    inspected = inspect_dxbc(raw, name=rel.name)
    if inspected["program"]["programType"] != kind:
        raise Seal6LitShaderBinaryError(
            f"{rel}: DXBC program type {inspected['program']['programType']!r} != {kind!r}"
        )
    if str(inspected["program"]["shaderModel"]) != str(stage.get("shaderModel")):
        raise Seal6LitShaderBinaryError(
            f"{rel}: DXBC shader model {inspected['program']['shaderModel']!r} != OAT {stage.get('shaderModel')!r}"
        )

    archived = None
    if archive_dir is not None:
        archive_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".vs.cso" if kind == "vertex" else ".ps.cso"
        archived_path = archive_dir / f"{actual_sha}{suffix}"
        if archived_path.exists():
            if _sha(archived_path.read_bytes()) != actual_sha:
                raise Seal6LitShaderBinaryError(f"existing archive identity collision: {archived_path}")
        else:
            shutil.copyfile(path, archived_path)
        archived = str(archived_path)

    resources = [
        {
            "name": row["name"],
            "inputType": row["inputType"],
            "dimension": row["dimension"],
            "bindPoint": row["bindPoint"],
            "bindCount": row["bindCount"],
        }
        for row in inspected["reflection"]["boundResources"]
    ]
    return {
        "kind": kind,
        "asset": stage.get("asset"),
        "relativeFile": rel.as_posix(),
        "bytes": len(raw),
        "sha256": actual_sha,
        "shaderModel": inspected["program"]["shaderModel"],
        "materialArguments": _material_arguments(stage),
        "dxbc": {
            "format": inspected["format"],
            "chunkCount": inspected["chunkCount"],
            "programChunk": inspected["program"],
            "rdefCreator": inspected["reflection"]["creator"],
            "constantBufferCount": inspected["reflection"]["constantBufferCount"],
            "boundResourceCount": inspected["reflection"]["boundResourceCount"],
            "boundResources": resources,
            "chunkIdentity": [
                {"tag": row["tag"], "payloadBytes": row["payloadBytes"], "payloadSha256": row["payloadSha256"]}
                for row in inspected["chunks"]
            ],
        },
        "archivedFile": archived,
    }


def build(
    owner_report: dict[str, Any],
    roots: list[tuple[str, Path]],
    *,
    solved_semantics: dict[str, Any] | None = None,
    archive_dir: Path | None = None,
) -> dict[str, Any]:
    if owner_report.get("format") != OWNER_FORMAT:
        raise Seal6LitShaderBinaryError(f"unsupported owner report {owner_report.get('format')!r}")
    root_map = {label: root.resolve() for label, root in roots}
    if len(root_map) != len(roots):
        raise Seal6LitShaderBinaryError("duplicate root label")
    if len({str(root) for root in root_map.values()}) != len(root_map):
        raise Seal6LitShaderBinaryError("duplicate root path")
    registry = _registry_pairs(solved_semantics)

    by_ts = {str(row.get("techniqueSet") or ""): row for row in owner_report.get("techniqueSets", [])}
    missing = [name for name in TARGET_TECHSETS if name not in by_ts]
    if missing:
        raise Seal6LitShaderBinaryError(f"owner report missing target TechniqueSets: {missing}")

    families = []
    unique_vs: set[str] = set()
    unique_ps: set[str] = set()
    for techset in TARGET_TECHSETS:
        source = by_ts[techset]
        variants = []
        for owner in source.get("owners", []):
            label = str(owner.get("rootLabel") or "")
            root = root_map.get(label)
            if root is None:
                raise Seal6LitShaderBinaryError(f"{techset}: owner root label {label!r} not supplied")
            lit = [row for row in owner.get("bindings", []) if "lit" in row.get("types", [])]
            if len(lit) != 1:
                raise Seal6LitShaderBinaryError(f"{techset}@{label}: expected one lit binding, got {len(lit)}")
            binding = lit[0]
            passes = binding.get("passes")
            if not isinstance(passes, list) or len(passes) != 1:
                raise Seal6LitShaderBinaryError(f"{techset}@{label}: lit binding is not exactly one pass")
            render_pass = passes[0]
            stages = render_pass.get("stages")
            if not isinstance(stages, list) or len(stages) != 2:
                raise Seal6LitShaderBinaryError(f"{techset}@{label}: lit pass does not contain exactly two stages")
            closed = [_inspect_stage(root, stage, archive_dir=archive_dir) for stage in stages]
            by_kind = {row["kind"]: row for row in closed}
            if set(by_kind) != {"vertex", "pixel"}:
                raise Seal6LitShaderBinaryError(f"{techset}@{label}: lit stages are {sorted(by_kind)}")
            vs, ps = by_kind["vertex"], by_kind["pixel"]
            unique_vs.add(vs["sha256"])
            unique_ps.add(ps["sha256"])
            pair = (vs["sha256"], ps["sha256"])
            solved_ids = registry.get(pair, [])
            variants.append({
                "rootLabel": label,
                "parentBytes": owner.get("bytes"),
                "parentSha256": owner.get("sha256"),
                "parentChildSignatureSha256": owner.get("fullParentChildSignatureSha256"),
                "litTechnique": binding.get("technique"),
                "litParsedPassStageIdentitySha256": binding.get("parsedPassStageIdentitySha256"),
                "passStateMap": render_pass.get("stateMap"),
                "vertexRouting": render_pass.get("vertexRouting"),
                "vertexShader": vs,
                "pixelShader": ps,
                "dxbcPairSha256": _sha((vs["sha256"] + ":" + ps["sha256"]).encode("ascii")),
                "existingBlenderSolvedFamilyIds": solved_ids,
                "existingBlenderExactLoweringAvailable": len(solved_ids) == 1,
            })
        pairs = {(row["vertexShader"]["sha256"], row["pixelShader"]["sha256"]) for row in variants}
        stage_ids = {str(row["litParsedPassStageIdentitySha256"]) for row in variants}
        families.append({
            "techniqueSet": techset,
            "physicalOwnerCount": len(variants),
            "serializedLitPassIdentityInvariantAcrossOwners": len(stage_ids) == 1,
            "executableVsPsPairInvariantAcrossOwners": len(pairs) == 1,
            "executableVertexShaderInvariantAcrossOwners": len({row["vertexShader"]["sha256"] for row in variants}) == 1,
            "executablePixelShaderInvariantAcrossOwners": len({row["pixelShader"]["sha256"] for row in variants}) == 1,
            "variants": variants,
        })

    hero = next(row for row in families if row["techniqueSet"] == TARGET_TECHSETS[0])
    return {
        "format": FORMAT,
        "summary": {
            "techniqueSetFamilies": len(families),
            "physicalLitVariants": sum(len(row["variants"]) for row in families),
            "uniqueVertexDxbcPrograms": len(unique_vs),
            "uniquePixelDxbcPrograms": len(unique_ps),
            "heroSerializedLitPassIdentityInvariant": hero["serializedLitPassIdentityInvariantAcrossOwners"],
            "heroExecutableVsPsPairInvariant": hero["executableVsPsPairInvariantAcrossOwners"],
            "familiesAlreadyInExactBlenderRegistry": sum(
                all(v["existingBlenderExactLoweringAvailable"] for v in row["variants"])
                for row in families
            ),
        },
        "families": families,
        "uniqueDxbc": {
            "vertexSha256": sorted(unique_vs),
            "pixelSha256": sorted(unique_ps),
        },
        "proofBoundary": (
            "Exact ordinary-lit shader binaries are admitted only from the physical TechniqueSet-owner report and are reverified against OAT byte counts/SHA-256 before strict DXBC/RDEF parsing. Divergent serialized parent/pass metadata is kept distinct from executable DXBC byte identity. Exact VS/PS pair equality may make local shader arithmetic precedence-independent, but it does not resolve the active retail-client parent XAsset or unrelated Material fields such as thermalMaterial. Existing Blender support is recognized only by an exact VS+PS SHA pair in the supplied solved-family registry."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner-report", type=Path, required=True)
    ap.add_argument("--root", type=_parse_root, action="append", required=True, metavar="LABEL=PATH")
    ap.add_argument("--solved-semantics", type=Path)
    ap.add_argument("--archive-dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    owner = json.loads(a.owner_report.read_text(encoding="utf-8"))
    semantics = json.loads(a.solved_semantics.read_text(encoding="utf-8")) if a.solved_semantics else None
    result = build(owner, a.root, solved_semantics=semantics, archive_dir=a.archive_dir)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "summary": result["summary"],
        "families": [
            {
                "techniqueSet": row["techniqueSet"],
                "physicalOwnerCount": row["physicalOwnerCount"],
                "serializedLitPassIdentityInvariantAcrossOwners": row["serializedLitPassIdentityInvariantAcrossOwners"],
                "executableVsPsPairInvariantAcrossOwners": row["executableVsPsPairInvariantAcrossOwners"],
                "variants": [
                    {
                        "rootLabel": v["rootLabel"],
                        "litTechnique": v["litTechnique"],
                        "litPassIdentity": v["litParsedPassStageIdentitySha256"],
                        "vs": v["vertexShader"]["sha256"],
                        "ps": v["pixelShader"]["sha256"],
                        "existingBlenderSolvedFamilyIds": v["existingBlenderSolvedFamilyIds"],
                    }
                    for v in row["variants"]
                ],
            }
            for row in result["families"]
        ],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
