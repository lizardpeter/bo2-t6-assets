#!/usr/bin/env python3
"""Archive an exact native OAT Material -> TechniqueSet dependency bundle.

This tool is deliberately forensic rather than authoritative.  It copies the
physical OAT outputs needed to inspect one named Material without losing zone
provenance:

* every selected Material JSON that physically exists;
* every physical copy of each referenced TechniqueSet;
* every Technique named by those TechniqueSet texts, from every supplied root;
* every shader binary referenced by each parsable physical Technique copy.

Divergent duplicates are preserved rather than resolved.  The manifest records
bytes/SHA-256 and parsed bindings/pass-stage identities.  Ownership promotion is
left to the fail-closed v4 census + exact-owner closure; this bundle must never
be interpreted as zone precedence or as a global absence proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import t6_oat_material_shader_census_v3 as v3
import t6_oat_techset_binding_manifest_v1 as oat

FORMAT = "t6-oat-material-dependency-bundle-v1"


class BundleError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("root must be LABEL=PATH")
    label, raw = value.split("=", 1)
    label = label.strip()
    path = Path(raw).resolve()
    if not label or not path.is_dir():
        raise argparse.ArgumentTypeError(f"invalid root {value!r}")
    return label, path


def _safe_label(label: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in label)


def _copy_record(src: Path, root: Path, label: str, out: Path) -> dict:
    try:
        relative = src.relative_to(root)
    except ValueError as exc:
        raise BundleError(f"{src} is outside root {root}") from exc
    dst = out / "files" / _safe_label(label) / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {
        "rootLabel": label,
        "root": str(root),
        "relativeFile": relative.as_posix(),
        "bytes": src.stat().st_size,
        "sha256": _sha(src),
        "archivedRelativeFile": dst.relative_to(out).as_posix(),
    }


def build(
    material_roots: list[tuple[str, Path]],
    shader_roots: list[tuple[str, Path]],
    material_name: str,
    out: Path,
) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    material_rel = Path("materials") / f"{material_name}.json"
    material_rows = []
    techsets: set[str] = set()

    for label, root in material_roots:
        path = root / material_rel
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise BundleError(f"Material {path}: invalid JSON: {exc}") from exc
        techset = str(payload.get("techniqueSet") or "")
        if not techset:
            raise BundleError(f"Material {path}: empty techniqueSet")
        techsets.add(techset)
        material_rows.append({
            "material": material_name,
            "techniqueSet": techset,
            "physical": _copy_record(path, root, label, out),
        })

    if not material_rows:
        raise BundleError(f"Material {material_name!r}: no physical JSON in selected Material roots")

    techset_rows = []
    technique_names: set[str] = set()
    for techset in sorted(techsets):
        rel = Path("techsets") / f"{techset}.techset"
        physical = []
        for label, root in shader_roots:
            path = root / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="strict")
            bindings, errors = oat.parse_techset(text)
            if errors:
                raise BundleError(f"TechniqueSet {path}: parse errors {errors[:4]}")
            if not bindings:
                raise BundleError(f"TechniqueSet {path}: no bindings")
            for binding in bindings:
                technique = str(binding.get("technique") or "")
                if technique:
                    technique_names.add(technique)
            physical.append({
                **_copy_record(path, root, label, out),
                "bindings": bindings,
                "bindingIdentitySha256": hashlib.sha256(
                    json.dumps(bindings, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            })
        if not physical:
            raise BundleError(f"TechniqueSet {techset}: no physical .techset in selected shader roots")
        techset_rows.append({"techniqueSet": techset, "physicalCopies": physical})

    technique_rows = []
    for technique in sorted(technique_names):
        rel = Path("techniques") / f"{technique}.tech"
        copies = []
        for label, root in shader_roots:
            path = root / rel
            if not path.is_file():
                continue
            passes, file_record = v3._parse_passes_from_owner(root, technique)
            archived = _copy_record(path, root, label, out)
            stages = []
            for p in passes:
                for stage in p.get("stages", []):
                    relative = Path(str(stage.get("relativeFile") or ""))
                    if not relative.as_posix() or relative.is_absolute() or ".." in relative.parts:
                        raise BundleError(f"Technique {technique}: invalid shader relative file {relative}")
                    shader_path = root / relative
                    if not shader_path.is_file():
                        raise BundleError(f"Technique {technique}: missing referenced shader {shader_path}")
                    actual_bytes = shader_path.stat().st_size
                    actual_sha = _sha(shader_path)
                    if actual_bytes != int(stage.get("bytes", -1)) or actual_sha != str(stage.get("sha256") or "").lower():
                        raise BundleError(f"Technique {technique}: shader identity drift {shader_path}")
                    stages.append({
                        "passIndex": p.get("index"),
                        "kind": stage.get("kind"),
                        "asset": stage.get("asset"),
                        "physical": _copy_record(shader_path, root, label, out),
                    })
            copies.append({
                **archived,
                "parserFileRecord": file_record,
                "parsedPassStageIdentitySha256": hashlib.sha256(
                    json.dumps(passes, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
                "passes": passes,
                "archivedShaders": stages,
            })
        if not copies:
            raise BundleError(f"Technique {technique}: no physical .tech in selected shader roots")
        technique_rows.append({"technique": technique, "physicalCopies": copies})

    manifest = {
        "format": FORMAT,
        "materialName": material_name,
        "materialRoots": [{"label": label, "root": str(root)} for label, root in material_roots],
        "shaderRoots": [{"label": label, "root": str(root)} for label, root in shader_roots],
        "materials": material_rows,
        "techniqueSets": techset_rows,
        "techniques": technique_rows,
        "summary": {
            "materialPhysicalCopyCount": len(material_rows),
            "uniqueTechniqueSetCount": len(techset_rows),
            "uniqueDeclaredTechniqueCount": len(technique_rows),
            "techniquePhysicalCopyCount": sum(len(row["physicalCopies"]) for row in technique_rows),
            "shaderPhysicalCopyCount": sum(
                len(copy["archivedShaders"])
                for row in technique_rows
                for copy in row["physicalCopies"]
            ),
        },
        "proofBoundary": (
            "Forensic physical OAT-output archive only. Every archived file is byte/SHA identified and retains its source-root label. TechniqueSet bindings and Technique pass/stage identities are parsed, but duplicate definitions are deliberately preserved rather than resolved. This manifest does not establish runtime winner precedence, global absence, or Material ownership beyond the direct Material JSON techniqueSet field. Use the provenance-aware v4 census and exact-owner closure for authoritative ownership claims."
        ),
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--material-root", type=_parse_root, action="append", required=True, metavar="LABEL=PATH")
    p.add_argument("--shader-root", type=_parse_root, action="append", required=True, metavar="LABEL=PATH")
    p.add_argument("--material-name", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(a.material_root, a.shader_root, a.material_name, a.out.resolve())
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
