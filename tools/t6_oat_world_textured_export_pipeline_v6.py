#!/usr/bin/env python3
"""Registry-gated one-command audited T6 GfxWorld export pipeline v6.

v6 is the production trust-boundary revision. Before entering the established
v5 deterministic geometry/material/DDS/lightmap pipeline it independently runs
the retail world-vertex audit and requires every observed `worldVertFormat` to
be export-enabled by an authoritative `t6-world-vertex-format-registry-v1`.

This preserves old research fixtures while preventing formula-known but
retail-unproven formats from entering production normalized output. When raw
retail evidence later promotes formats 4/5/7/8, regenerating the registry is
sufficient; the production exporter does not need another format-specific edit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v5 as v5
from t6_world_mesh_normalize_v2 import validate_registry_for_proof
from t6_world_vertex_audit_v2 import audit


class OatTexturedPipelineV6Error(RuntimeError):
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
        raise OatTexturedPipelineV6Error(
            f"v5 staging output is missing during v6 promotion: {source}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return _file_record(destination)


def _load_registry(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise OatTexturedPipelineV6Error(
            f"cannot parse format registry {path}: {exc}"
        ) from exc
    if not isinstance(doc, dict):
        raise OatTexturedPipelineV6Error("format registry top level must be an object")
    return doc, raw


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
    format_registry_path: Path,
    lightmap_catalog_path: Path | None = None,
    write_gltf: bool = False,
    allow_unresolved_world_materials: bool = False,
    allow_missing_oat_materials: bool = False,
    allow_missing_dds: bool = False,
    allow_missing_preview_textures: bool = False,
    allow_missing_dependency_textures: bool = False,
    allow_missing_lightmap_dds: bool = False,
) -> dict:
    registry, registry_raw = _load_registry(format_registry_path)

    # Preflight uses the same exact retail sidecars but does not write geometry.
    # The registry gate therefore fails before the expensive texture/lightmap
    # stages if this map contains an unapproved format.
    proof = audit(
        map_name=map_name,
        surfaces_path=surfaces_path,
        vd0_path=vd0_path,
        vd1_path=vd1_path,
        materials_path=materials_path,
        catalog_path=catalog_path,
        prefix_path=prefix_path,
        asset_pointer_array_virtual_base=asset_pointer_array_virtual_base,
    )
    if int(proof.get("badGroupCount", 0)) != 0:
        raise OatTexturedPipelineV6Error(
            f"preflight world vertex audit failed with {proof.get('badGroupCount')} bad groups"
        )
    try:
        gate = validate_registry_for_proof(proof, registry)
    except Exception as exc:
        raise OatTexturedPipelineV6Error(
            f"world vertex format production gate rejected {map_name}: {exc}"
        ) from exc

    result = v5.run_oat_textured_pipeline(
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
    if result.get("format") != "t6-oat-world-textured-export-pipeline-manifest-v5":
        raise OatTexturedPipelineV6Error(
            f"unexpected v5 base manifest {result.get('format')!r}"
        )

    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise OatTexturedPipelineV6Error("v5 result lacks outputs")

    glb = outputs.get("oatPortableTexturedGlb")
    if not isinstance(glb, dict):
        raise OatTexturedPipelineV6Error("v5 result lacks final GLB output")
    outputs["oatPortableTexturedGlb"] = _promote_file(
        str(glb["path"]),
        output_dir / f"{map_name}.world_oat_portable_textured_v6.glb",
    )
    if "oatPortableTexturedGltf" in outputs:
        gltf = outputs["oatPortableTexturedGltf"]
        outputs["oatPortableTexturedGltf"] = _promote_file(
            str(gltf["path"]),
            output_dir / f"{map_name}.world_oat_portable_textured_v6.gltf",
        )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        old_path = Path(str(old_manifest.get("path") or ""))
        if old_path.is_file():
            old_path.unlink()

    registry_record = _file_record(format_registry_path, registry_raw)
    proof_bytes = _json_bytes(proof)
    proof_path = output_dir / f"{map_name}.world_vertex_preflight_v6.json"
    proof_path.write_bytes(proof_bytes)
    outputs["worldVertexPreflightV6"] = _file_record(proof_path, proof_bytes)
    outputs["worldVertexFormatRegistry"] = registry_record

    result["format"] = "t6-oat-world-textured-export-pipeline-manifest-v6"
    validation = result.setdefault("validation", {})
    validation.update(
        {
            "worldVertexFormatRegistryGate": True,
            "worldVertexFormatRegistryFormat": registry.get("format"),
            "worldVertexFormatRegistrySha256": registry_record["sha256"],
            "observedWorldVertFormatsPreflight": gate["observedFormats"],
            "allObservedWorldVertFormatsExportEnabled": gate[
                "allObservedFormatsExportEnabled"
            ],
            "registryExportEnabledFormats": gate["registryExportEnabledFormats"],
            "allNineWorldVertFormatsExportEnabled": gate[
                "registryAllFormatsExportEnabled"
            ],
            "worldVertexPreflightBadGroups": int(proof.get("badGroupCount", 0)),
        }
    )

    policies = result.setdefault("policies", {})
    policies["worldVertexFormatProductionGate"] = (
        "preflight exact retail vertex proof must contain only formats marked "
        "exportEnabled by t6-world-vertex-format-registry-v1; formula knowledge "
        "alone cannot authorize production vd1 decoding"
    )
    policies["worldVertexFormatPromotion"] = (
        "pending formats are promoted by regenerating the registry from clean "
        "t6-world-vd1-raw-census-v2 evidence; contradictory retail stride evidence "
        "is a hard disable"
    )

    result.setdefault("stats", {})["worldVertexFormatGate"] = {
        "observedFormatCount": len(gate["observedFormats"]),
        "observedFormats": gate["observedFormats"],
        "registryExportEnabledCount": len(gate["registryExportEnabledFormats"]),
        "registryExportEnabledFormats": gate["registryExportEnabledFormats"],
    }

    payload = _json_bytes(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v6.json"
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
    parser.add_argument("--asset-pointer-base", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--oat-material-root", type=Path, required=True)
    parser.add_argument("--dds-root", type=Path, required=True)
    parser.add_argument("--format-registry", type=Path, required=True)
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
        output_dir=args.out_dir,
        format_registry_path=args.format_registry,
        lightmap_catalog_path=args.lightmap_catalog,
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
                "worldVertexFormatGate": manifest["stats"]["worldVertexFormatGate"],
                "texturedStats": manifest["stats"]["texturedGltf"],
                "lightmapStats": manifest["stats"].get("lightmaps"),
                "lightmapArchiveStats": manifest["stats"].get("lightmapArchive"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
