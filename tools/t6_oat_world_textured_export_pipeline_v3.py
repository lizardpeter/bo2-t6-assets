#!/usr/bin/env python3
"""One-command audited T6 GfxWorld export pipeline v3.

v3 promotes the strongest independently proven material/texture stages into the
production path and optionally archives exact surface -> GfxLightmapArray joins.

Pipeline:
  raw GfxWorld sidecars
    -> audited normalized world + geometry-only GLB
  exact OAT Material components
    -> ordinary + source-closed generated/layered dependency manifest v2
  exact DDS assets
    -> semantic-aware DDS staging v2 (including unbound layered normalMap BC5)
  normalized world + staged dependencies
    -> portable textured GLB v2 embedding every exact material dependency image
       while core glTF binds only independently safe preview semantics
  optional exact GfxWorld lightmap catalog
    -> surface lightmapIndex -> primary/secondary GfxImage dependency manifest

Primary/secondary lightmap shader composition is intentionally not invented.
This pipeline records the exact pair graph now so a later source-closed lightmap
shader/export stage can consume it without re-discovering provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_dds_texture_stage_v2 import stage_dds
from t6_oat_material_manifest_v2 import build_manifest
from t6_world_export_pipeline_v1 import run_pipeline
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_lightmap_manifest_v1 import build_manifest as build_lightmap_manifest
from t6_world_textured_gltf_export_v2 import export_textured


class OatTexturedPipelineError(RuntimeError):
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
    if (
        not map_name
        or map_name in (".", "..")
        or any(character in map_name for character in ("/", "\\", "\0"))
    ):
        raise OatTexturedPipelineError(f"invalid map name {map_name!r}")
    return map_name


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
) -> dict:
    stem = _safe_stem(map_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    base = run_pipeline(
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
        allow_unresolved_materials=allow_unresolved_world_materials,
    )

    catalog_raw = catalog_path.read_bytes()
    catalog_doc = json.loads(catalog_raw.decode("utf-8"))
    material_manifest = build_manifest(
        material_root=oat_material_root,
        catalog_doc=catalog_doc,
        source_texture_extension=".dds",
        allow_missing_materials=allow_missing_oat_materials,
    )
    material_bytes = _json_bytes(material_manifest)
    material_path = output_dir / f"{stem}.oat_material_texture_manifest_v2.json"
    material_path.write_bytes(material_bytes)
    material_sha = _sha256(material_bytes)

    texture_dir = output_dir / f"{stem}.dds_textures_v2"
    stage_manifest = stage_dds(
        material_manifest,
        texture_root=dds_root,
        output_dir=texture_dir,
        material_manifest_name=material_path.name,
        material_manifest_sha256=material_sha,
        allow_missing=allow_missing_dds,
    )
    stage_bytes = _json_bytes(stage_manifest)
    stage_path = output_dir / f"{stem}.dds_texture_stage_manifest_v2.json"
    stage_path.write_bytes(stage_bytes)

    normalized_path = Path(base["outputs"]["normalizedWorld"]["path"])
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))

    lightmap_manifest = None
    lightmap_bytes = None
    lightmap_path = None
    lightmap_catalog_input = None
    if lightmap_catalog_path is not None:
        lightmap_catalog_raw = lightmap_catalog_path.read_bytes()
        lightmap_catalog_doc = json.loads(lightmap_catalog_raw.decode("utf-8"))
        lightmap_manifest = build_lightmap_manifest(
            normalized,
            lightmap_catalog_doc,
            source_texture_extension=".dds",
        )
        lightmap_bytes = _json_bytes(lightmap_manifest)
        lightmap_path = output_dir / f"{stem}.world_lightmap_manifest_v1.json"
        lightmap_path.write_bytes(lightmap_bytes)
        lightmap_catalog_input = _file_record(
            lightmap_catalog_path, lightmap_catalog_raw
        )

    gltf1, raw1 = export_textured(
        normalized,
        material_manifest,
        stage_manifest,
        stage_root=texture_dir,
        material_manifest_sha256=material_sha,
        allow_missing_preview_textures=allow_missing_preview_textures,
        allow_missing_dependency_textures=allow_missing_dependency_textures,
    )
    glb1 = glb_bytes(gltf1, raw1)
    gltf2, raw2 = export_textured(
        normalized,
        material_manifest,
        stage_manifest,
        stage_root=texture_dir,
        material_manifest_sha256=material_sha,
        allow_missing_preview_textures=allow_missing_preview_textures,
        allow_missing_dependency_textures=allow_missing_dependency_textures,
    )
    glb2 = glb_bytes(gltf2, raw2)
    if raw2 != raw1 or glb2 != glb1:
        raise OatTexturedPipelineError(
            "OAT portable textured GLB regeneration was not byte-identical"
        )

    textured_glb_path = output_dir / f"{stem}.world_oat_portable_textured_v3.glb"
    textured_glb_path.write_bytes(glb1)
    outputs = {
        "oatMaterialTextureManifest": _file_record(material_path, material_bytes),
        "ddsTextureStageManifest": _file_record(stage_path, stage_bytes),
        "oatPortableTexturedGlb": _file_record(textured_glb_path, glb1),
    }
    if lightmap_path is not None and lightmap_bytes is not None:
        outputs["worldLightmapManifest"] = _file_record(
            lightmap_path, lightmap_bytes
        )

    gltf_deterministic = None
    if write_gltf:
        gltf_payload1 = gltf_bytes(gltf1, raw1)
        gltf_payload2 = gltf_bytes(gltf2, raw2)
        if gltf_payload1 != gltf_payload2:
            raise OatTexturedPipelineError(
                "OAT portable textured glTF regeneration was not byte-identical"
            )
        gltf_deterministic = True
        gltf_path = output_dir / f"{stem}.world_oat_portable_textured_v3.gltf"
        gltf_path.write_bytes(gltf_payload1)
        outputs["oatPortableTexturedGltf"] = _file_record(gltf_path, gltf_payload1)

    textured_stats = gltf1["extras"]["T6"]["exportStats"]
    oat_stats = material_manifest["stats"]
    stage_stats = stage_manifest["stats"]
    validation = {
        "baseWorldPipeline": base["validation"],
        "missingOatMaterialCount": oat_stats["missingMaterialCount"],
        "compoundMaterialCount": oat_stats["compoundMaterialCount"],
        "reconstructedCompoundMaterialCount": oat_stats[
            "reconstructedCompoundMaterialCount"
        ],
        "compoundLayerNormalValidationCount": oat_stats[
            "compoundLayerNormalValidationCount"
        ],
        "missingDdsCount": stage_stats["missingTextureCount"],
        "unsupportedDdsCount": stage_stats["unsupportedTextureCount"],
        "semanticNormalSourceCount": stage_stats["semanticNormalSourceCount"],
        "bc5NormalReconstructionCount": stage_stats[
            "bc5NormalReconstructionCount"
        ],
        "materialManifestMatchedCount": textured_stats[
            "materialManifestMatchedCount"
        ],
        "materialManifestUnmatchedCount": textured_stats[
            "materialManifestUnmatchedCount"
        ],
        "missingPreviewTextureCount": textured_stats[
            "missingPreviewTextureCount"
        ],
        "missingDependencyTextureCount": textured_stats[
            "missingDependencyTextureCount"
        ],
        "materialDependencySourceCount": textured_stats[
            "materialDependencySourceCount"
        ],
        "embeddedDependencyImageCount": textured_stats[
            "embeddedDependencyImageCount"
        ],
        "oatTexturedGlbRegenerationByteIdentical": True,
        "oatTexturedGltfRegenerationByteIdentical": gltf_deterministic,
        "lightmapCatalogJoined": lightmap_manifest is not None,
    }
    if lightmap_manifest is not None:
        validation.update(
            {
                "lightmapCount": lightmap_manifest["stats"]["lightmapCount"],
                "surfacesWithLightmap": lightmap_manifest["stats"][
                    "surfacesWithLightmap"
                ],
                "surfacesWithoutLightmap": lightmap_manifest["stats"][
                    "surfacesWithoutLightmap"
                ],
                "referencedLightmapCount": lightmap_manifest["stats"][
                    "referencedLightmapCount"
                ],
            }
        )

    manifest = {
        "format": "t6-oat-world-textured-export-pipeline-manifest-v3",
        "map": map_name,
        "inputs": {
            "baseWorldPipelineManifest": base["manifest"],
            "materialCatalog": _file_record(catalog_path, catalog_raw),
            "oatMaterialRoot": str(oat_material_root),
            "ddsRoot": str(dds_root),
            "lightmapCatalog": lightmap_catalog_input,
        },
        "outputs": outputs,
        "validation": validation,
        "stats": {
            "baseWorld": base["stats"],
            "oatMaterials": oat_stats,
            "ddsStage": stage_stats,
            "texturedGltf": textured_stats,
            "lightmaps": None if lightmap_manifest is None else lightmap_manifest["stats"],
        },
        "policies": {
            "ordinaryMaterialJoin": (
                "exact GfxWorld catalog name == relative OAT Material JSON path"
            ),
            "compoundMaterialJoin": (
                "parse source-closed BSP-index[n] generated identity, then exact join "
                "each encoded component name to OAT Material JSON"
            ),
            "compoundNormalValidation": (
                "n marker must equal real component Material_HasNormalMap; "
                "$identitynormalmap is not a real normal map"
            ),
            "compoundTextureTable": (
                "component texture tables concatenate in encoded layer order, matching "
                "Material_CreateLayered"
            ),
            "coreGltfBinding": (
                "only independently safe standardPreview semantics are core-glTF-bound"
            ),
            "dependencyPortability": (
                "all exact staged material dependency images are embedded in GLB even "
                "when their Treyarch shader semantics are not yet core-glTF representable"
            ),
            "bc5Normals": (
                "positive Z reconstructed from exact material normalMap semantics, including "
                "unbound layered normals; mixed BC5 semantic reuse fails closed; no Y inversion"
            ),
            "lightmaps": (
                "optional exact GfxSurface.lightmapIndex -> GfxLightmapArray primary/secondary "
                "dependency graph; no primary/secondary shader composition is guessed"
            ),
            "geometryReference": (
                "base untextured audited world GLB retained beside textured output"
            ),
        },
    }
    payload = _json_bytes(manifest)
    manifest_path = output_dir / f"{stem}.world_oat_textured_export_manifest_v3.json"
    manifest_path.write_bytes(payload)
    manifest["manifest"] = _file_record(manifest_path, payload)
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
    )
    print(
        json.dumps(
            {
                "map": manifest["map"],
                "manifest": manifest["manifest"],
                "validation": manifest["validation"],
                "texturedStats": manifest["stats"]["texturedGltf"],
                "lightmapStats": manifest["stats"]["lightmaps"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
