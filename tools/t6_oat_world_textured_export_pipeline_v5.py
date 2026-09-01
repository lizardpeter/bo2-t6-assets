#!/usr/bin/env python3
"""One-command audited T6 GfxWorld export pipeline v5.

v5 promotes the production v4 material/world path while replacing the old
strict two-image lightmap assumption with the retail-correct nullable-role
contract:

  optional exact GfxWorld lightmap catalog
    -> lightmap manifest v3
       (primary/secondary GfxImage roles may independently be present or null)
    -> lightmap GLB archive v3
       (only present roles create DDS dependencies; null roles remain null)

The v4 implementation is reused for the already-audited base-world, material,
DDS staging, portable glTF, and byte-determinism orchestration. v5 temporarily
injects only the versioned v3 lightmap builder/archive functions, then restores
v4 module globals in a finally block. Output names and the top-level manifest
are promoted to v5 after the deterministic build completes.

No fallback texture is invented for a null retail GfxImage pointer and no T6
lightmap channel/combine equation is guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v4 as v4
from t6_world_lightmap_glb_embed_v3 import (
    ARCHIVE_FORMAT,
    embed_lightmap_dds as embed_lightmap_dds_v3,
)
from t6_world_lightmap_manifest_v3 import (
    build_manifest as build_lightmap_manifest_v3,
)


class OatTexturedPipelineV5Error(RuntimeError):
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


def _promote_file(path_value: str, destination: Path) -> dict:
    source = Path(path_value)
    if not source.is_file():
        raise OatTexturedPipelineV5Error(
            f"v4 staging output is missing during v5 promotion: {source}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return _file_record(destination)


def run_oat_textured_pipeline(
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
    oat_material_root: Path,
    dds_root: Path,
    output_dir: Path,
    lightmap_catalog_path: Path | None = None,
    write_gltf: bool = False,
    allow_unresolved_world_materials: bool = False,
    allow_missing_oat_materials: bool = False,
    allow_missing_dds: bool = False,
    allow_missing_preview_textures: bool = False,
    allow_missing_dependency_textures: bool = False,
    allow_missing_lightmap_dds: bool = False,
) -> dict:
    old_builder = v4.build_lightmap_manifest
    old_embedder = v4.embed_lightmap_dds
    try:
        v4.build_lightmap_manifest = build_lightmap_manifest_v3
        v4.embed_lightmap_dds = embed_lightmap_dds_v3
        result = v4.run_oat_textured_pipeline(
            map_name=map_name,
            surfaces_path=surfaces_path,
            vd0_path=vd0_path,
            vd1_path=vd1_path,
            indices_path=indices_path,
            materials_path=materials_path,
            catalog_path=catalog_path,
            prefix_path=prefix_path,
            asset_pointer_array_virtual_base=asset_pointer_array_virtual_base,
            oat_material_root=oat_material_root,
            dds_root=dds_root,
            output_dir=output_dir,
            lightmap_catalog_path=lightmap_catalog_path,
            write_gltf=write_gltf,
            allow_unresolved_world_materials=allow_unresolved_world_materials,
            allow_missing_oat_materials=allow_missing_oat_materials,
            allow_missing_dds=allow_missing_dds,
            allow_missing_preview_textures=allow_missing_preview_textures,
            allow_missing_dependency_textures=allow_missing_dependency_textures,
            allow_missing_lightmap_dds=allow_missing_lightmap_dds,
        )
    finally:
        v4.build_lightmap_manifest = old_builder
        v4.embed_lightmap_dds = old_embedder

    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v4":
        raise OatTexturedPipelineV5Error(
            f"unexpected v4 base manifest {result.get('format')!r}"
        )

    stem = map_name
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV5Error("v4 result lacks outputs")

    glb_record = outputs.get("oatPortableTexturedGlb")
    if not isinstance(glb_record, dict):
        raise OatTexturedPipelineV5Error("v4 result lacks final GLB output")
    outputs["oatPortableTexturedGlb"] = _promote_file(
        str(glb_record["path"]),
        output_dir / f"{stem}.world_oat_portable_textured_v5.glb",
    )

    if "oatPortableTexturedGltf" in outputs:
        gltf_record = outputs["oatPortableTexturedGltf"]
        outputs["oatPortableTexturedGltf"] = _promote_file(
            str(gltf_record["path"]),
            output_dir / f"{stem}.world_oat_portable_textured_v5.gltf",
        )

    lightmap_stats = result.get("stats", {}).get("lightmaps")
    archive_stats = result.get("stats", {}).get("lightmapArchive")
    if lightmap_catalog_path is not None:
        lm_record = outputs.get("worldLightmapManifest")
        if not isinstance(lm_record, dict):
            raise OatTexturedPipelineV5Error(
                "v5 lightmap catalog was provided but no lightmap manifest was produced"
            )
        promoted_lm = output_dir / f"{stem}.world_lightmap_manifest_v3.json"
        outputs["worldLightmapManifest"] = _promote_file(
            str(lm_record["path"]), promoted_lm
        )
        lm_doc = json.loads(promoted_lm.read_text(encoding="utf-8"))
        if lm_doc.get("format") != "t6-world-lightmap-manifest-v3":
            raise OatTexturedPipelineV5Error(
                f"promoted lightmap manifest is {lm_doc.get('format')!r}, not v3"
            )
        if not isinstance(lightmap_stats, dict) or not isinstance(archive_stats, dict):
            raise OatTexturedPipelineV5Error(
                "v5 lightmap stats/archive stats are missing"
            )
    elif "worldLightmapManifest" in outputs:
        raise OatTexturedPipelineV5Error(
            "lightmap manifest was produced without a lightmap catalog"
        )

    old_manifest_record = result.pop("manifest", None)
    if isinstance(old_manifest_record, dict):
        old_path = Path(str(old_manifest_record.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    result["format"] = "t6-oat-world-textured-export-pipeline-manifest-v5"
    validation = result.setdefault("validation", {})
    validation["nullableRetailLightmapRoles"] = True
    validation["lightmapManifestFormat"] = (
        "t6-world-lightmap-manifest-v3"
        if lightmap_catalog_path is not None
        else None
    )
    validation["lightmapArchiveFormat"] = (
        ARCHIVE_FORMAT if lightmap_catalog_path is not None else None
    )
    if lightmap_catalog_path is not None:
        validation.update(
            {
                "lightmapDeclaredRoleCount": lightmap_stats["declaredRoleCount"],
                "lightmapPresentRoleDependencyUseCount": lightmap_stats[
                    "presentRoleDependencyUseCount"
                ],
                "lightmapPresentPrimaryImageCount": lightmap_stats[
                    "presentPrimaryImageCount"
                ],
                "lightmapAbsentPrimaryImageCount": lightmap_stats[
                    "absentPrimaryImageCount"
                ],
                "lightmapPresentSecondaryImageCount": lightmap_stats[
                    "presentSecondaryImageCount"
                ],
                "lightmapAbsentSecondaryImageCount": lightmap_stats[
                    "absentSecondaryImageCount"
                ],
                "lightmapArchivePresentDependencyUseCount": archive_stats[
                    "presentDependencyUseCount"
                ],
                "lightmapArchiveAbsentRoleCount": archive_stats[
                    "absentRoleCount"
                ],
            }
        )

    policies = result.setdefault("policies", {})
    policies["lightmaps"] = (
        "optional exact GfxSurface.lightmapIndex -> GfxLightmapArray graph; "
        "primary/secondary GfxImage roles are independently present/null; only "
        "present roles create exact raw OAT DDS archival bufferViews; code "
        "samplers 4/5 remain retained; no fallback image, channel meaning, or "
        "shader composition is guessed"
    )
    policies["lightmapRolePresence"] = (
        "retail null GfxImage pointer is preserved as an explicit absent role; "
        "absence is not treated as a missing DDS and is never synthesized"
    )
    policies["lightmapMissingAccounting"] = (
        "unique present T6 GfxImage identity only; absent roles do not enter "
        "missing accounting; present identity<->disk mapping must be bijective"
    )

    payload = _json_bytes(result)
    manifest_path = output_dir / f"{stem}.world_oat_textured_export_manifest_v5.json"
    manifest_path.write_bytes(payload)
    result["manifest"] = _file_record(manifest_path, payload)
    return result


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
        "--asset-pointer-base", type=lambda value: int(value, 0), required=True
    )
    parser.add_argument("--oat-material-root", type=Path, required=True)
    parser.add_argument("--dds-root", type=Path, required=True)
    parser.add_argument("--lightmap-catalog", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--write-gltf", action="store_true")
    parser.add_argument("--allow-unresolved-world-materials", action="store_true")
    parser.add_argument("--allow-missing-oat-materials", action="store_true")
    parser.add_argument("--allow-missing-dds", action="store_true")
    parser.add_argument("--allow-missing-preview-textures", action="store_true")
    parser.add_argument("--allow-missing-dependency-textures", action="store_true")
    parser.add_argument("--allow-missing-lightmap-dds", action="store_true")
    args = parser.parse_args()

    manifest = run_oat_textured_pipeline(
        map_name=args.map_name,
        surfaces_path=args.surfaces,
        vd0_path=args.vd0,
        vd1_path=args.vd1,
        indices_path=args.indices,
        materials_path=args.materials,
        catalog_path=args.catalog,
        prefix_path=args.prefix,
        asset_pointer_array_virtual_base=args.asset_pointer_base,
        oat_material_root=args.oat_material_root,
        dds_root=args.dds_root,
        lightmap_catalog_path=args.lightmap_catalog,
        output_dir=args.out_dir,
        write_gltf=args.write_gltf,
        allow_unresolved_world_materials=args.allow_unresolved_world_materials,
        allow_missing_oat_materials=args.allow_missing_oat_materials,
        allow_missing_dds=args.allow_missing_dds,
        allow_missing_preview_textures=args.allow_missing_preview_textures,
        allow_missing_dependency_textures=args.allow_missing_dependency_textures,
        allow_missing_lightmap_dds=args.allow_missing_lightmap_dds,
    )
    print(
        json.dumps(
            {
                "map": manifest["map"],
                "manifest": manifest["manifest"],
                "validation": manifest["validation"],
                "texturedStats": manifest["stats"]["texturedGltf"],
                "lightmapStats": manifest["stats"]["lightmaps"],
                "lightmapArchiveStats": manifest["stats"]["lightmapArchive"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
