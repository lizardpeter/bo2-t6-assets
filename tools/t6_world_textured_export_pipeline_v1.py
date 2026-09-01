#!/usr/bin/env python3
"""One-command audited T6 world -> textured glTF/GLB pipeline.

This composes the already source-closed layers rather than duplicating them:

  raw GfxWorld sidecars
    -> t6_world_export_pipeline_v1 (audit/material resolution/normalized geometry)
  exact material_texture_mapping.csv
    -> t6_material_texture_manifest_v1
    -> t6_texture_stage_v1 (exact TGA -> deterministic PNG)
  normalized world + both manifests
    -> t6_world_textured_gltf_export_v1

The untextured reference GLB from the base pipeline is retained beside the
textured GLB so geometry-only and material-enhanced outputs remain independently
comparable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_material_texture_manifest_v1 import normalize_mapping_csv
from t6_texture_stage_v1 import stage
from t6_world_export_pipeline_v1 import run_pipeline
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_textured_gltf_export_v1 import export_textured


class TexturedPipelineError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _file_record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(payload),
        "sha256": _sha256(payload),
    }


def _safe_stem(map_name: str) -> str:
    if not map_name or map_name in (".", ".."):
        raise TexturedPipelineError(f"invalid map name {map_name!r}")
    if any(character in map_name for character in ("/", "\\", "\0")):
        raise TexturedPipelineError(
            f"map name cannot contain path separators: {map_name!r}"
        )
    return map_name


def run_textured_pipeline(
    *,
    map_name: str,
    surfaces_path: Path,
    vd0_path: Path,
    vd1_path: Path,
    indices_path: Path,
    materials_path: Path,
    catalog_path: Path,
    prefix_path: Path,
    asset_pointer_array_virtual_base: int,
    material_texture_mapping_path: Path,
    texture_root: Path,
    output_dir: Path,
    write_gltf: bool = False,
    allow_unresolved_materials: bool = False,
    allow_missing_textures: bool = False,
    allow_missing_preview_textures: bool = False,
) -> dict:
    stem = _safe_stem(map_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_manifest = run_pipeline(
        map_name=map_name,
        surfaces_path=surfaces_path,
        vd0_path=vd0_path,
        vd1_path=vd1_path,
        indices_path=indices_path,
        materials_path=materials_path,
        catalog_path=catalog_path,
        prefix_path=prefix_path,
        asset_pointer_array_virtual_base=asset_pointer_array_virtual_base,
        output_dir=output_dir,
        write_gltf=write_gltf,
        allow_unresolved_materials=allow_unresolved_materials,
    )

    mapping_raw = material_texture_mapping_path.read_bytes()
    material_manifest = normalize_mapping_csv(material_texture_mapping_path)
    material_manifest_bytes = _json_bytes(material_manifest)
    material_manifest_path = output_dir / f"{stem}.material_texture_manifest.json"
    material_manifest_path.write_bytes(material_manifest_bytes)
    material_manifest_sha = _sha256(material_manifest_bytes)

    texture_dir = output_dir / f"{stem}.textures"
    texture_stage_manifest = stage(
        material_manifest,
        texture_root=texture_root,
        output_dir=texture_dir,
        material_manifest_name=material_manifest_path.name,
        material_manifest_sha256=material_manifest_sha,
        allow_missing=allow_missing_textures,
    )
    texture_stage_bytes = _json_bytes(texture_stage_manifest)
    texture_stage_path = output_dir / f"{stem}.texture_stage_manifest.json"
    texture_stage_path.write_bytes(texture_stage_bytes)

    normalized_path = Path(base_manifest["outputs"]["normalizedWorld"]["path"])
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))

    gltf1, raw1 = export_textured(
        normalized,
        material_manifest,
        texture_stage_manifest,
        stage_root=texture_dir,
        material_manifest_sha256=material_manifest_sha,
        allow_missing_preview_textures=allow_missing_preview_textures,
    )
    glb1 = glb_bytes(gltf1, raw1)

    gltf2, raw2 = export_textured(
        normalized,
        material_manifest,
        texture_stage_manifest,
        stage_root=texture_dir,
        material_manifest_sha256=material_manifest_sha,
        allow_missing_preview_textures=allow_missing_preview_textures,
    )
    glb2 = glb_bytes(gltf2, raw2)
    if raw2 != raw1 or glb2 != glb1:
        raise TexturedPipelineError(
            "textured world GLB regeneration was not byte-identical"
        )

    textured_glb_path = output_dir / f"{stem}.world_textured.glb"
    textured_glb_path.write_bytes(glb1)

    textured_gltf_path: Path | None = None
    textured_gltf_payload: bytes | None = None
    gltf_deterministic = None
    if write_gltf:
        textured_gltf_payload = gltf_bytes(gltf1, raw1)
        textured_gltf_payload2 = gltf_bytes(gltf2, raw2)
        if textured_gltf_payload2 != textured_gltf_payload:
            raise TexturedPipelineError(
                "textured world glTF regeneration was not byte-identical"
            )
        gltf_deterministic = True
        textured_gltf_path = output_dir / f"{stem}.world_textured.gltf"
        textured_gltf_path.write_bytes(textured_gltf_payload)

    textured_outputs = {
        "materialTextureManifest": _file_record(
            material_manifest_path, material_manifest_bytes
        ),
        "textureStageManifest": _file_record(
            texture_stage_path, texture_stage_bytes
        ),
        "texturedGlb": _file_record(textured_glb_path, glb1),
    }
    if textured_gltf_path is not None and textured_gltf_payload is not None:
        textured_outputs["texturedGltf"] = _file_record(
            textured_gltf_path, textured_gltf_payload
        )

    texture_stats = gltf1["extras"]["T6"]["exportStats"]
    manifest = {
        "format": "t6-world-textured-export-pipeline-manifest-v1",
        "map": map_name,
        "inputs": {
            "baseWorldPipelineManifest": base_manifest["manifest"],
            "materialTextureMapping": _file_record(
                material_texture_mapping_path, mapping_raw
            ),
            "textureRoot": str(texture_root),
        },
        "outputs": textured_outputs,
        "validation": {
            "baseWorldPipeline": base_manifest["validation"],
            "textureStageMissingCount": texture_stage_manifest["stats"][
                "missingTextureCount"
            ],
            "textureStageUnsupportedCount": texture_stage_manifest["stats"][
                "unsupportedTextureCount"
            ],
            "materialManifestMatchedCount": texture_stats[
                "materialManifestMatchedCount"
            ],
            "materialManifestUnmatchedCount": texture_stats[
                "materialManifestUnmatchedCount"
            ],
            "missingPreviewTextureCount": texture_stats[
                "missingPreviewTextureCount"
            ],
            "texturedGlbRegenerationByteIdentical": True,
            "texturedGltfRegenerationByteIdentical": gltf_deterministic,
        },
        "stats": {
            "baseWorld": base_manifest["stats"],
            "materialTextures": material_manifest["stats"],
            "textureStage": texture_stage_manifest["stats"],
            "texturedGltf": texture_stats,
        },
        "policies": {
            "materialTextureMapping": (
                "exact semantic role/layer/compositor mapping; no filename or "
                "table-position inference"
            ),
            "textureResolution": (
                "exact sourceTexture basename under textureRoot; fail closed "
                "unless explicitly allowed"
            ),
            "standardPreview": (
                "only material-manifest-approved colorMap/normalMap bindings; "
                "non-core Treyarch semantics preserved in extras"
            ),
            "geometryReference": (
                "base untextured world GLB is retained for independent comparison"
            ),
        },
    }
    manifest_bytes = _json_bytes(manifest)
    manifest_path = output_dir / f"{stem}.world_textured_export_manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    manifest["manifest"] = _file_record(manifest_path, manifest_bytes)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="map_name", required=True)
    parser.add_argument("--surfaces", type=Path, required=True)
    parser.add_argument("--vd0", type=Path, required=True)
    parser.add_argument("--vd1", type=Path, required=True)
    parser.add_argument("--indices", type=Path, required=True)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument(
        "--asset-pointer-base",
        type=lambda value: int(value, 0),
        required=True,
    )
    parser.add_argument("--material-texture-mapping", type=Path, required=True)
    parser.add_argument("--texture-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--write-gltf", action="store_true")
    parser.add_argument("--allow-unresolved-materials", action="store_true")
    parser.add_argument("--allow-missing-textures", action="store_true")
    parser.add_argument("--allow-missing-preview-textures", action="store_true")
    args = parser.parse_args()

    manifest = run_textured_pipeline(
        map_name=args.map_name,
        surfaces_path=args.surfaces,
        vd0_path=args.vd0,
        vd1_path=args.vd1,
        indices_path=args.indices,
        materials_path=args.materials,
        catalog_path=args.catalog,
        prefix_path=args.prefix,
        asset_pointer_array_virtual_base=args.asset_pointer_base,
        material_texture_mapping_path=args.material_texture_mapping,
        texture_root=args.texture_root,
        output_dir=args.out_dir,
        write_gltf=args.write_gltf,
        allow_unresolved_materials=args.allow_unresolved_materials,
        allow_missing_textures=args.allow_missing_textures,
        allow_missing_preview_textures=args.allow_missing_preview_textures,
    )
    print(
        json.dumps(
            {
                "map": manifest["map"],
                "manifest": manifest["manifest"],
                "validation": manifest["validation"],
                "texturedStats": manifest["stats"]["texturedGltf"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
