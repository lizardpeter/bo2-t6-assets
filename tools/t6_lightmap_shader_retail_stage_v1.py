#!/usr/bin/env python3
"""Stage retail T6 world lightmap shader evidence for the research pipeline.

Consumes a pinned OpenAssetTools T6 dump and retains exact Material ->
TechniqueSet -> Technique -> pixel-shader provenance for techniques that bind
lightmapSamplerPrimary and/or lightmapSamplerSecondary.

Pinned OAT T6 .techset grammar is explicitly supported:

    "lit sun shadow":
      example_lit_sun_shadow;

Technique references are bare asset names; the disk file is
techniques/<name>.tech. No fuzzy name substitution is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


class RetailLightmapStageError(RuntimeError):
    pass


LIGHTMAP_NAMES = ("lightmapSamplerPrimary", "lightmapSamplerSecondary")
PIXEL_RE = re.compile(r'\bpixelShader\s+\d+\.\d+\s+"([^"]+)"')
TECHSET_ENTRY_RE = re.compile(r'^\s{2,}([^\s;{}][^;{}]*?)\s*;\s*(?://.*)?$', re.MULTILINE)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_record(path: Path, root: Path) -> dict:
    data = path.read_bytes()
    return {"relative": path.relative_to(root).as_posix(), "bytes": len(data), "sha256": _sha256(data)}


def _copy_exact(src: Path, src_root: Path, dst_root: Path) -> dict:
    rel = src.relative_to(src_root)
    dst = dst_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    if src.read_bytes() != dst.read_bytes():
        raise RetailLightmapStageError(f"copy mismatch for {src}")
    return {"source": _file_record(src, src_root), "staged": _file_record(dst, dst_root)}


def _index_unique(root: Path, pattern: str) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in sorted(root.rglob(pattern)):
        key = path.name
        if key in out:
            raise RetailLightmapStageError(f"duplicate basename {key!r}: {out[key]} and {path}")
        out[key] = path
    return out


def _load_material(path: Path) -> dict | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RetailLightmapStageError(f"invalid material JSON {path}: {exc}") from exc
    if doc.get("_game") != "t6" or doc.get("_type") != "material":
        return None
    return doc


def _techset_reference(doc: dict) -> str:
    value = str(doc.get("techniqueSet") or "").strip()
    if not value:
        raise RetailLightmapStageError("T6 material has empty techniqueSet")
    return value


def _parse_techset_techniques(text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for match in TECHSET_ENTRY_RE.finditer(text):
        value = match.group(1).strip()
        if value.startswith('"') or ':' in value or value.startswith("//"):
            continue
        # OAT emits a bare technique asset identity followed by ';'. Accept an
        # optional .tech suffix for robustness, but normalize to disk basename.
        base = Path(value).name
        if base.endswith(".tech"):
            base = base[:-5]
        if not base or any(ch in base for ch in ('"', "'", "=", "{" , "}")):
            raise RetailLightmapStageError(f"unrecognized technique reference line: {match.group(0)!r}")
        if base not in seen:
            seen.add(base)
            names.append(base)
    return names


def _shader_names_from_tech(text: str) -> list[str]:
    return sorted(set(PIXEL_RE.findall(text)))


def build_stage(*, oat_root: Path, output_dir: Path, map_name: str, retail_ff_sha256: str | None = None) -> dict:
    if not oat_root.is_dir():
        raise RetailLightmapStageError(f"OAT root is not a directory: {oat_root}")
    material_root = oat_root / "materials"
    techset_root = oat_root / "techsets"
    technique_root = oat_root / "techniques"
    shader_root = oat_root / "shader_bin"
    for path in (material_root, techset_root, technique_root, shader_root):
        if not path.is_dir():
            raise RetailLightmapStageError(f"required OAT directory missing: {path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    staged_root = output_dir / "retained_oat"
    if staged_root.exists():
        shutil.rmtree(staged_root)
    staged_root.mkdir(parents=True)

    techsets = _index_unique(techset_root, "*.techset")
    techniques = _index_unique(technique_root, "*.tech")
    shaders = _index_unique(shader_root, "ps_*.cso")

    candidates: list[dict] = []
    retained_paths: set[Path] = set()
    parsed_techset_count = 0
    for material_path in sorted(material_root.rglob("*.json")):
        doc = _load_material(material_path)
        if doc is None:
            continue
        techset_name = _techset_reference(doc)
        techset_basename = Path(techset_name).name
        if not techset_basename.endswith(".techset"):
            techset_basename += ".techset"
        techset_file = techsets.get(techset_basename)
        if techset_file is None:
            raise RetailLightmapStageError(
                f"material {material_path} references missing techniqueSet {techset_name!r}"
            )
        techset_text = techset_file.read_text(encoding="utf-8", errors="strict")
        technique_names = _parse_techset_techniques(techset_text)
        if not technique_names:
            raise RetailLightmapStageError(
                f"could not parse any OAT technique references from {techset_file}"
            )
        parsed_techset_count += 1

        local_techniques: list[dict] = []
        material_has_lightmap = False
        for technique_name in technique_names:
            technique_file = techniques.get(technique_name + ".tech")
            if technique_file is None:
                raise RetailLightmapStageError(
                    f"techset {techset_file} references missing technique {technique_name!r}"
                )
            text = technique_file.read_text(encoding="utf-8", errors="strict")
            roles = [name for name in LIGHTMAP_NAMES if name in text]
            shader_names = _shader_names_from_tech(text)
            shader_records: list[dict] = []
            for shader_name in shader_names:
                file_name = f"ps_{shader_name}.cso"
                shader_file = shaders.get(file_name)
                if shader_file is None:
                    raise RetailLightmapStageError(
                        f"technique {technique_file} references missing pixel shader {shader_name!r}"
                    )
                shader_records.append({"name": shader_name, "file": _file_record(shader_file, oat_root)})
                retained_paths.add(shader_file)
            if roles:
                if not shader_records:
                    raise RetailLightmapStageError(
                        f"lightmap technique {technique_file} has no parsed pixelShader declaration"
                    )
                material_has_lightmap = True
            local_techniques.append({
                "techniqueAsset": technique_name,
                "technique": technique_file.relative_to(oat_root).as_posix(),
                "roles": roles,
                "pixelShaders": shader_records,
            })
            retained_paths.add(technique_file)

        if material_has_lightmap:
            retained_paths.add(material_path)
            retained_paths.add(techset_file)
            candidates.append({
                "material": material_path.relative_to(oat_root).as_posix(),
                "techniqueSet": techset_file.relative_to(oat_root).as_posix(),
                "techniques": local_techniques,
            })

    if not candidates:
        raise RetailLightmapStageError(
            "no lightmap-using material/technique chains found; refusing to emit an empty retail proof bundle"
        )

    copies = [_copy_exact(path, oat_root, staged_root) for path in sorted(retained_paths)]
    primary_edges = secondary_edges = both_edges = 0
    shader_names: set[str] = set()
    for candidate in candidates:
        for tech in candidate["techniques"]:
            roles = set(tech["roles"])
            primary_edges += int("lightmapSamplerPrimary" in roles)
            secondary_edges += int("lightmapSamplerSecondary" in roles)
            both_edges += int(set(LIGHTMAP_NAMES).issubset(roles))
            for shader in tech["pixelShaders"]:
                shader_names.add(shader["name"])

    manifest = {
        "format": "t6-retail-lightmap-shader-stage-v1",
        "map": map_name,
        "retailFastfileSha256": retail_ff_sha256,
        "oatRoot": str(oat_root),
        "stagedRoot": str(staged_root),
        "candidates": candidates,
        "copies": copies,
        "stats": {
            "parsedMaterialTechsetCount": parsed_techset_count,
            "materialChainCount": len(candidates),
            "retainedArtifactCount": len(copies),
            "uniquePixelShaderCount": len(shader_names),
            "primaryTechniqueEdgeCount": primary_edges,
            "secondaryTechniqueEdgeCount": secondary_edges,
            "bothRoleTechniqueEdgeCount": both_edges,
        },
        "researchPipelineArgs": {
            "materialRoot": str(staged_root / "materials"),
            "techsetRoot": str(staged_root / "techsets"),
            "techniqueRoot": str(staged_root / "techniques"),
            "shaderRoot": str(staged_root / "shader_bin"),
        },
        "sourceGrammar": {
            "oatCommit": "7d027e8f89118196713e955b0e11f8404149c54d",
            "techsetReference": "quoted technique type label followed by indented bare technique asset name and semicolon",
            "techniqueDiskRule": "techniques/<asset>.tech",
            "pixelShaderDiskRule": "shader_bin/ps_<pixelShader asset>.cso",
        },
        "proofBoundary": (
            "This stage proves exact retained Material -> TechniqueSet -> Technique -> pixel-shader provenance "
            "for OAT output and sampler-name presence. It does not prove lightmap channel meaning or shader arithmetic."
        ),
    }
    out = output_dir / "t6_retail_lightmap_shader_stage_v1.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--map", required=True)
    parser.add_argument("--retail-ff-sha256")
    args = parser.parse_args()
    doc = build_stage(oat_root=args.oat_root, output_dir=args.out_dir, map_name=args.map, retail_ff_sha256=args.retail_ff_sha256)
    print(json.dumps({"map": doc["map"], **doc["stats"], "stagedRoot": doc["stagedRoot"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
