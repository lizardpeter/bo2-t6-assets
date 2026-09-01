#!/usr/bin/env python3
"""One-command audited T6 GfxWorld -> normalized mesh -> GLB/glTF pipeline.

This joins the source-closed pieces of the world exporter without hiding any
proof boundary:

  exact sidecars
      -> t6_world_vertex_audit_v2
      -> exact material-pointer resolution
      -> t6_world_mesh_normalize_v1
      -> t6_world_gltf_export_v1

The pipeline writes all proof/intermediate artifacts beside the final GLB and a
hash manifest. GLB regeneration is performed twice in memory and must be
byte-identical before the run is accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_world_gltf_export_v1 import export as export_gltf
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_mesh_normalize_v1 import normalize
from t6_world_surface_material_enrich_v1 import enrich
from t6_world_vertex_audit_v2 import audit


class PipelineError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_record(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(payload),
        "sha256": _sha256(payload),
    }


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _safe_stem(map_name: str) -> str:
    if not map_name or map_name in (".", ".."):
        raise PipelineError(f"invalid map name {map_name!r}")
    if any(character in map_name for character in ("/", "\\", "\0")):
        raise PipelineError(f"map name cannot contain path separators: {map_name!r}")
    return map_name


def run_pipeline(
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
    output_dir: Path,
    write_gltf: bool = False,
    allow_unresolved_materials: bool = False,
) -> dict:
    stem = _safe_stem(map_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    surfaces_raw = surfaces_path.read_bytes()
    vd0 = vd0_path.read_bytes()
    vd1 = vd1_path.read_bytes()
    index_bytes = indices_path.read_bytes()
    materials_raw = materials_path.read_bytes()
    catalog_raw = catalog_path.read_bytes()
    prefix_raw = prefix_path.read_bytes()

    surfaces_doc = json.loads(surfaces_raw.decode("utf-8"))
    catalog_doc = json.loads(catalog_raw.decode("utf-8"))

    vertex_proof = audit(
        map_name=map_name,
        surfaces_path=surfaces_path,
        vd0_path=vd0_path,
        vd1_path=vd1_path,
        materials_path=materials_path,
        catalog_path=catalog_path,
        prefix_path=prefix_path,
        asset_pointer_array_virtual_base=asset_pointer_array_virtual_base,
    )
    if int(vertex_proof.get("badGroupCount", 0)) != 0:
        raise PipelineError(
            f"world vertex audit failed with {vertex_proof.get('badGroupCount')} bad groups"
        )

    vertex_proof_bytes = _json_bytes(vertex_proof)
    vertex_proof_path = output_dir / f"{stem}.world_vertex_proof.json"
    vertex_proof_path.write_bytes(vertex_proof_bytes)

    resolved_surfaces = enrich(
        surfaces_doc,
        catalog_doc,
        allow_unresolved=allow_unresolved_materials,
    )
    if (
        not allow_unresolved_materials
        and not resolved_surfaces["materialResolution"]["allSurfacesResolved"]
    ):
        raise PipelineError("strict material resolution did not resolve every surface")
    resolved_surfaces_bytes = _json_bytes(resolved_surfaces)
    resolved_surfaces_path = output_dir / f"{stem}.surfaces_material_resolved.json"
    resolved_surfaces_path.write_bytes(resolved_surfaces_bytes)

    source_meta = {
        "surfacesRaw": _file_record(surfaces_path, surfaces_raw),
        "vd0": _file_record(vd0_path, vd0),
        "vd1": _file_record(vd1_path, vd1),
        "indices": _file_record(indices_path, index_bytes),
        "materials": _file_record(materials_path, materials_raw),
        "materialCatalog": _file_record(catalog_path, catalog_raw),
        "prefix": _file_record(prefix_path, prefix_raw),
        "vertexProof": _file_record(vertex_proof_path, vertex_proof_bytes),
        "resolvedSurfaces": _file_record(
            resolved_surfaces_path,
            resolved_surfaces_bytes,
        ),
    }

    normalized = normalize(
        surfaces_doc=resolved_surfaces,
        vd0=vd0,
        vd1=vd1,
        index_bytes=index_bytes,
        proof=vertex_proof,
        source_meta=source_meta,
    )
    normalized_bytes = _json_bytes(normalized)
    normalized_path = output_dir / f"{stem}.world_mesh_normalized.json"
    normalized_path.write_bytes(normalized_bytes)

    gltf, raw = export_gltf(normalized)
    glb_payload = glb_bytes(gltf, raw)

    # Determinism is a release condition, not merely diagnostic metadata.
    gltf_second, raw_second = export_gltf(normalized)
    glb_second = glb_bytes(gltf_second, raw_second)
    if raw_second != raw or glb_second != glb_payload:
        raise PipelineError("world GLB regeneration was not byte-identical")

    glb_path = output_dir / f"{stem}.world.glb"
    glb_path.write_bytes(glb_payload)

    gltf_path: Path | None = None
    gltf_payload: bytes | None = None
    gltf_deterministic = None
    if write_gltf:
        gltf_payload = gltf_bytes(gltf, raw)
        gltf_second_payload = gltf_bytes(gltf_second, raw_second)
        if gltf_second_payload != gltf_payload:
            raise PipelineError("world glTF regeneration was not byte-identical")
        gltf_deterministic = True
        gltf_path = output_dir / f"{stem}.world.gltf"
        gltf_path.write_bytes(gltf_payload)

    outputs = {
        "vertexProof": _file_record(vertex_proof_path, vertex_proof_bytes),
        "resolvedSurfaces": _file_record(
            resolved_surfaces_path,
            resolved_surfaces_bytes,
        ),
        "normalizedWorld": _file_record(normalized_path, normalized_bytes),
        "glb": _file_record(glb_path, glb_payload),
    }
    if gltf_path is not None and gltf_payload is not None:
        outputs["gltf"] = _file_record(gltf_path, gltf_payload)

    manifest = {
        "format": "t6-world-export-pipeline-manifest-v1",
        "map": map_name,
        "inputs": {
            "surfaces": _file_record(surfaces_path, surfaces_raw),
            "vd0": _file_record(vd0_path, vd0),
            "vd1": _file_record(vd1_path, vd1),
            "indices": _file_record(indices_path, index_bytes),
            "materials": _file_record(materials_path, materials_raw),
            "materialCatalog": _file_record(catalog_path, catalog_raw),
            "prefix": _file_record(prefix_path, prefix_raw),
            "assetPointerArrayVirtualBase": asset_pointer_array_virtual_base,
        },
        "outputs": outputs,
        "validation": {
            "vertexAuditBadGroups": int(vertex_proof["badGroupCount"]),
            "observedWorldVertFormats": sorted(
                int(key)
                for key in vertex_proof.get("observedFormatGroupCounts", {})
            ),
            "allSurfaceMaterialsResolved": resolved_surfaces["materialResolution"][
                "allSurfacesResolved"
            ],
            "unresolvedSurfaceMaterials": resolved_surfaces["materialResolution"][
                "unresolvedSurfaceCount"
            ],
            "glbRegenerationByteIdentical": True,
            "gltfRegenerationByteIdentical": gltf_deterministic,
        },
        "stats": {
            "vertexAudit": {
                "surfaceCount": vertex_proof["surfaceCount"],
                "uniqueVertexGroups": vertex_proof["uniqueVertexGroups"],
                "vd0Bytes": vertex_proof["vd0Bytes"],
                "vd1Bytes": vertex_proof["vd1Bytes"],
                "observedFormatGroupCounts": vertex_proof[
                    "observedFormatGroupCounts"
                ],
            },
            "materialResolution": resolved_surfaces["materialResolution"],
            "normalizedWorld": normalized["stats"],
            "gltf": gltf["extras"]["T6"]["exportStats"],
        },
        "policies": {
            "materialResolution": "exact pointer join; no guessing/substitution",
            "coordinateConversion": "T6 Z-up inches -> glTF Y-up meters",
            "normalTransform": normalized["normalTransformPolicy"],
            "retailProof": (
                "a worldVertFormat is proven for this fixture only when its serialized "
                "vd0/vd1 group passes the byte audit with zero bad groups"
            ),
        },
    }

    manifest_bytes = _json_bytes(manifest)
    manifest_path = output_dir / f"{stem}.world_export_manifest.json"
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
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--write-gltf", action="store_true")
    parser.add_argument("--allow-unresolved-materials", action="store_true")
    args = parser.parse_args()

    manifest = run_pipeline(
        map_name=args.map_name,
        surfaces_path=args.surfaces,
        vd0_path=args.vd0,
        vd1_path=args.vd1,
        indices_path=args.indices,
        materials_path=args.materials,
        catalog_path=args.catalog,
        prefix_path=args.prefix,
        asset_pointer_array_virtual_base=args.asset_pointer_base,
        output_dir=args.out_dir,
        write_gltf=args.write_gltf,
        allow_unresolved_materials=args.allow_unresolved_materials,
    )
    print(
        json.dumps(
            {
                "map": manifest["map"],
                "manifest": manifest["manifest"],
                "validation": manifest["validation"],
                "gltfStats": manifest["stats"]["gltf"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
