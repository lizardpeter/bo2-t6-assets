#!/usr/bin/env python3
"""One-command audited T6 GfxWorld + OAT Material components/DDS -> textured GLB v2.

v2 extends the native-OAT path with source-closed Treyarch layered-material
identity reconstruction. A generated world material such as
``*22n_14(wpc/base:wpc/decal)`` no longer requires its own OAT JSON file:
component OAT Material JSONs are resolved from the encoded names, every `n`
normal-map expectation is validated, and Material_CreateLayered texture-table
order is reconstructed exactly. The layered technique/shader blend itself is
still not approximated into core glTF; the full dependency graph is preserved
in material extras and standardPreview remains empty for compounds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_dds_texture_stage_v1 import stage_dds
from t6_oat_material_manifest_v2 import build_manifest
from t6_world_export_pipeline_v1 import run_pipeline
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_textured_gltf_export_v1 import export_textured


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
    write_gltf: bool = False,
    allow_unresolved_world_materials: bool = False,
    allow_missing_oat_materials: bool = False,
    allow_missing_dds: bool = False,
    allow_missing_preview_textures: bool = False,
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

    gltf1, raw1 = export_textured(
        normalized,
        material_manifest,
        stage_manifest,
        stage_root=texture_dir,
        material_manifest_sha256=material_sha,
        allow_missing_preview_textures=allow_missing_preview_textures,
    )
    glb1 = glb_bytes(gltf1, raw1)
    gltf2, raw2 = export_textured(
        normalized,
        material_manifest,
        stage_manifest,
        stage_root=texture_dir,
        material_manifest_sha256=material_sha,
        allow_missing_preview_textures=allow_missing_preview_textures,
    )
    glb2 = glb_bytes(gltf2, raw2)
    if raw2 != raw1 or glb2 != glb1:
        raise OatTexturedPipelineError(
            "OAT layered-textured GLB regeneration was not byte-identical"
        )

    textured_glb_path = output_dir / f"{stem}.world_oat_textured_v2.glb"
    textured_glb_path.write_bytes(glb1)
    outputs = {
        "oatMaterialTextureManifest": _file_record(material_path, material_bytes),
        "ddsTextureStageManifest": _file_record(stage_path, stage_bytes),
        "oatTexturedGlb": _file_record(textured_glb_path, glb1),
    }

    gltf_deterministic = None
    if write_gltf:
        gltf_payload1 = gltf_bytes(gltf1, raw1)
        gltf_payload2 = gltf_bytes(gltf2, raw2)
        if gltf_payload1 != gltf_payload2:
            raise OatTexturedPipelineError(
                "OAT layered-textured glTF regeneration was not byte-identical"
            )
        gltf_deterministic = True
        gltf_path = output_dir / f"{stem}.world_oat_textured_v2.gltf"
        gltf_path.write_bytes(gltf_payload1)
        outputs["oatTexturedGltf"] = _file_record(gltf_path, gltf_payload1)

    textured_stats = gltf1["extras"]["T6"]["exportStats"]
    oat_stats = material_manifest["stats"]
    manifest = {
        "format": "t6-oat-world-textured-export-pipeline-manifest-v2",
        "map": map_name,
        "inputs": {
            "baseWorldPipelineManifest": base["manifest"],
            "materialCatalog": _file_record(catalog_path, catalog_raw),
            "oatMaterialRoot": str(oat_material_root),
            "ddsRoot": str(dds_root),
        },
        "outputs": outputs,
        "validation": {
            "baseWorldPipeline": base["validation"],
            "missingOatMaterialCount": oat_stats["missingMaterialCount"],
            "compoundMaterialCount": oat_stats["compoundMaterialCount"],
            "reconstructedCompoundMaterialCount": oat_stats[
                "reconstructedCompoundMaterialCount"
            ],
            "compoundLayerNormalValidationCount": oat_stats[
                "compoundLayerNormalValidationCount"
            ],
            "missingDdsCount": stage_manifest["stats"]["missingTextureCount"],
            "unsupportedDdsCount": stage_manifest["stats"][
                "unsupportedTextureCount"
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
            "oatTexturedGlbRegenerationByteIdentical": True,
            "oatTexturedGltfRegenerationByteIdentical": gltf_deterministic,
        },
        "stats": {
            "baseWorld": base["stats"],
            "oatMaterials": oat_stats,
            "ddsStage": stage_manifest["stats"],
            "texturedGltf": textured_stats,
        },
        "policies": {
            "ordinaryMaterialJoin": (
                "exact GfxWorld catalog name == relative OAT Material JSON path"
            ),
            "compoundMaterialJoin": (
                "parse source-closed *BSP-index[n]_... component identity, then exact "
                "join each component name to OAT Material JSON"
            ),
            "compoundNormalValidation": (
                "n marker must equal real component Material_HasNormalMap; "
                "$identitynormalmap is not a real normal map"
            ),
            "compoundTextureTable": (
                "component texture tables concatenate in encoded layer order, matching "
                "Material_CreateLayered"
            ),
            "compoundPreview": (
                "no standard preview binding until layered technique/shader composition "
                "is source-closed; dependency graph is preserved in extras"
            ),
            "textureSemantics": (
                "OAT textures[].semantic only; no filename/table-order inference"
            ),
            "imageJoin": (
                "OAT image asset + literal .dds extension; exact basename under ddsRoot"
            ),
            "ddsPreview": (
                "first mip decoded to deterministic PNG; source DDS hash/mips/format retained"
            ),
            "bc5Normals": (
                "positive Z reconstructed only for manifest-approved normalTexture use; "
                "no Y inversion"
            ),
            "geometryReference": (
                "base untextured audited world GLB retained beside textured output"
            ),
        },
    }
    payload = _json_bytes(manifest)
    manifest_path = output_dir / f"{stem}.world_oat_textured_export_manifest_v2.json"
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
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--write-gltf", action="store_true")
    parser.add_argument("--allow-unresolved-world-materials", action="store_true")
    parser.add_argument("--allow-missing-oat-materials", action="store_true")
    parser.add_argument("--allow-missing-dds", action="store_true")
    parser.add_argument("--allow-missing-preview-textures", action="store_true")
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
        output_dir=args.out_dir,
        write_gltf=args.write_gltf,
        allow_unresolved_world_materials=args.allow_unresolved_world_materials,
        allow_missing_oat_materials=args.allow_missing_oat_materials,
        allow_missing_dds=args.allow_missing_dds,
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
