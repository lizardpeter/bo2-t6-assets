#!/usr/bin/env python3
"""Stage retail T6 world lightmap shader evidence for the research pipeline.

This tool consumes an OpenAssetTools output tree from a hash-pinned retail T6
map dump. It does not guess technique families or shader semantics. Instead it:

1. indexes T6 Material JSONs, .techset files, .tech files and pixel-shader .cso;
2. identifies materials whose exact technique graph references
   lightmapSamplerPrimary and/or lightmapSamplerSecondary;
3. copies only the required provenance chain into a compact retained bundle;
4. hashes every source artifact;
5. writes a deterministic worklist suitable for
   t6_lightmap_shader_research_pipeline_v2.py.

The actual arithmetic/channel semantics remain a downstream proof target.
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
TECHSET_NAME_RE = re.compile(r'"?([^"\s]+)"?')


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_record(path: Path, root: Path) -> dict:
    data = path.read_bytes()
    return {
        "relative": path.relative_to(root).as_posix(),
        "bytes": len(data),
        "sha256": _sha256(data),
    }


def _copy_exact(src: Path, src_root: Path, dst_root: Path) -> dict:
    rel = src.relative_to(src_root)
    dst = dst_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    a = src.read_bytes()
    b = dst.read_bytes()
    if a != b:
        raise RetailLightmapStageError(f"copy mismatch for {src}")
    return {
        "source": _file_record(src, src_root),
        "staged": _file_record(dst, dst_root),
    }


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
    # OAT techset files contain exact referenced technique names. We remain
    # syntax-conservative: retain tokens ending in .tech if present, otherwise
    # quoted/non-whitespace names that correspond to files are resolved later.
    names: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r'"([^"]+\.tech)"|([^\s=;{}]+\.tech)', text):
        value = raw[0] or raw[1]
        base = Path(value).name
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
    for material_path in sorted(material_root.rglob("*.json")):
        doc = _load_material(material_path)
        if doc is None:
            continue
        techset_name = _techset_reference(doc)
        techset_file = techsets.get(Path(techset_name).name + ("" if techset_name.endswith(".techset") else ".techset"))
        if techset_file is None:
            # Some OAT outputs store techniqueSet with path-like identity; fall
            # back only to an exact basename match, never fuzzy substitution.
            techset_file = techsets.get(Path(techset_name).name)
        if techset_file is None:
            raise RetailLightmapStageError(
                f"material {material_path} references missing techniqueSet {techset_name!r}"
            )
        techset_text = techset_file.read_text(encoding="utf-8", errors="strict")
        technique_names = _parse_techset_techniques(techset_text)
        if not technique_names:
            # Retain candidate discovery fail-closed; a missing parse cannot be
            # treated as no lightmap usage.
            continue

        local_techniques: list[dict] = []
        material_has_lightmap = False
        for technique_name in technique_names:
            technique_file = techniques.get(Path(technique_name).name)
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
                shader_records.append({
                    "name": shader_name,
                    "file": _file_record(shader_file, oat_root),
                })
                retained_paths.add(shader_file)
            if roles:
                material_has_lightmap = True
            local_techniques.append({
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
        "proofBoundary": (
            "This stage proves exact retained Material -> TechniqueSet -> Technique -> pixel-shader provenance "
            "for OAT output and sampler-name presence. It does not prove lightmap channel meaning or shader arithmetic."
        ),
    }
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    out = output_dir / "t6_retail_lightmap_shader_stage_v1.json"
    out.write_text(payload, encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--map", required=True)
    parser.add_argument("--retail-ff-sha256")
    args = parser.parse_args()
    doc = build_stage(
        oat_root=args.oat_root,
        output_dir=args.out_dir,
        map_name=args.map,
        retail_ff_sha256=args.retail_ff_sha256,
    )
    print(json.dumps({"map": doc["map"], **doc["stats"], "stagedRoot": doc["stagedRoot"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
