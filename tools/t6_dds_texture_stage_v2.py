#!/usr/bin/env python3
"""Deterministically stage T6/OAT DDS dependencies with semantic-aware BC5 v2.

v1 reconstructed BC5 Z only for textures bound to core-glTF `normalTexture`.
That is insufficient for source-closed layered materials, whose normalMap
textures are deliberately not standard-preview-bound. v2 instead derives BC5
interpretation from the exact material dependency role:

- every use role == normalMap -> BC5 R/G are normal X/Y and positive Z is rebuilt;
- no use role == normalMap -> BC5 remains raw two-channel data represented R/G/B=0;
- mixed normalMap + non-normal roles for one BC5 source fail closed.

All non-BC5 decode behavior remains the proven v1 implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_dds_texture_stage_v1 import DdsStageError, _decode_dds, _sha256
from t6_texture_stage_v1 import _collect_dependencies, _encode_png_rgba


def stage_dds(
    material_manifest: dict,
    *,
    texture_root: Path,
    output_dir: Path,
    material_manifest_name: str | None = None,
    material_manifest_sha256: str | None = None,
    allow_missing: bool = False,
) -> dict:
    dependencies = _collect_dependencies(material_manifest)
    output_dir.mkdir(parents=True, exist_ok=True)

    staged: list[dict] = []
    missing: list[dict] = []
    unsupported: list[dict] = []

    for source_texture in sorted(dependencies):
        uses = dependencies[source_texture]
        source_path = texture_root / source_texture
        if not source_path.is_file():
            record = {"sourceTexture": source_texture, "uses": uses}
            missing.append(record)
            if not allow_missing:
                raise DdsStageError(f"missing exact source texture {source_path}")
            continue

        roles = {str(use.get("role") or "") for use in uses}
        semantic_normal = roles == {"normalMap"}
        mixed_normal_semantics = "normalMap" in roles and roles != {"normalMap"}

        source_bytes = source_path.read_bytes()
        source_sha = _sha256(source_bytes)
        try:
            width, height, rgba, dds_meta = _decode_dds(
                source_bytes,
                reconstruct_bc5_normal_z=semantic_normal,
            )
        except DdsStageError as exc:
            record = {
                "sourceTexture": source_texture,
                "sourcePath": str(source_path),
                "sourceBytes": len(source_bytes),
                "sourceSha256": source_sha,
                "reason": str(exc),
                "uses": uses,
            }
            unsupported.append(record)
            if not allow_missing:
                raise
            continue

        is_bc5 = "BC5" in str(dds_meta.get("format") or "")
        if is_bc5 and mixed_normal_semantics:
            record = {
                "sourceTexture": source_texture,
                "sourcePath": str(source_path),
                "sourceBytes": len(source_bytes),
                "sourceSha256": source_sha,
                "reason": (
                    "BC5 source has mixed normalMap and non-normal material semantics"
                ),
                "roles": sorted(roles),
                "uses": uses,
            }
            unsupported.append(record)
            if not allow_missing:
                raise DdsStageError(record["reason"] + f": {source_texture}")
            continue

        png = _encode_png_rgba(width, height, rgba)
        output_name = hashlib.sha256(source_texture.encode("utf-8")).hexdigest() + ".png"
        output_path = output_dir / output_name
        output_path.write_bytes(png)
        staged.append(
            {
                "sourceTexture": source_texture,
                "sourcePath": str(source_path),
                "sourceBytes": len(source_bytes),
                "sourceSha256": source_sha,
                "dds": {
                    **dds_meta,
                    "materialRoles": sorted(roles),
                    "normalInterpretationSource": (
                        "all exact material dependency roles are normalMap"
                        if semantic_normal
                        else "no exact material dependency role is normalMap"
                    ),
                },
                "png": {
                    "file": output_name,
                    "path": str(output_path),
                    "bytes": len(png),
                    "sha256": _sha256(png),
                    "width": width,
                    "height": height,
                    "format": "RGBA8",
                },
                "uses": uses,
            }
        )

    return {
        "format": "t6-texture-stage-manifest-v1",
        "source": {
            "kind": "DDS",
            "materialManifest": material_manifest_name,
            "materialManifestSha256": material_manifest_sha256,
            "textureRoot": str(texture_root),
            "stageVersion": 2,
        },
        "policy": {
            "resolution": "exact sourceTexture basename under textureRoot only",
            "decode": (
                "first mip only; BC1/BC3/BC5_UNORM/RGBA8/BGRA8 source-closed subset"
            ),
            "bc5Normal": (
                "reconstruct positive Z when every exact material dependency role is "
                "normalMap, including unbound layered dependencies; no Y inversion"
            ),
            "bc5MixedSemantic": (
                "fail closed when one BC5 DDS has both normalMap and non-normal roles"
            ),
            "png": "RGBA8, filter 0, zlib level 9, no metadata chunks",
            "outputNaming": "sha256(sourceTexture UTF-8) + .png",
            "deduplication": "one staged PNG per exact sourceTexture",
        },
        "stats": {
            "referencedTextureCount": len(dependencies),
            "stagedTextureCount": len(staged),
            "missingTextureCount": len(missing),
            "unsupportedTextureCount": len(unsupported),
            "standardPreviewSourceCount": len(
                {
                    source
                    for source, uses in dependencies.items()
                    if any(use.get("standardPreviewTarget") for use in uses)
                }
            ),
            "semanticNormalSourceCount": len(
                {
                    source
                    for source, uses in dependencies.items()
                    if {str(use.get("role") or "") for use in uses} == {"normalMap"}
                }
            ),
            "bc5NormalReconstructionCount": sum(
                1
                for entry in staged
                if entry["dds"].get("bc5NormalZReconstructed")
            ),
        },
        "textures": staged,
        "missing": missing,
        "unsupported": unsupported,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_manifest", type=Path)
    parser.add_argument("--texture-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    raw = args.material_manifest.read_bytes()
    material_manifest = json.loads(raw.decode("utf-8"))
    doc = stage_dds(
        material_manifest,
        texture_root=args.texture_root,
        output_dir=args.out_dir,
        material_manifest_name=args.material_manifest.name,
        material_manifest_sha256=_sha256(raw),
        allow_missing=args.allow_missing,
    )
    manifest_out = args.manifest_out or (
        args.out_dir / "t6_texture_stage_manifest_v2.json"
    )
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_out.write_bytes(payload)
    print(
        json.dumps(
            {"out": str(manifest_out), "sha256": _sha256(payload), **doc["stats"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
