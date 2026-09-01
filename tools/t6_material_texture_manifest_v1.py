#!/usr/bin/env python3
"""Normalize exact T6 material/texture-role mappings without inventing shader semantics.

The primary input is the flat material texture mapping emitted by the retained
BO2 Blender/Frost workflow:

  material_index,material,layer_index,layer,role,
  texture_index,source_texture,compositors

Some derivative tables may prepend an optional `index` column; it is ignored.
The semantic contract begins at `material_index`.

That table is already semantic rather than positional: roles such as colorMap,
normalMap, specularMap, colorGloss, colorOpacity are explicit, and layered
materials carry compositor identities such as BlendTextures/MultiplyTextures.

This normalizer deliberately distinguishes:
- standardPreview bindings that are safe to express in core glTF today
  (single/base-layer colorMap and normalMap only),
- source-closed T6 semantic dependencies that are retained but not silently
  translated (specularMap and other roles),
- packed/composited/layered dependencies that require a Treyarch-aware shader
  or an independently proven bake.

No texture is selected by filename suffix or row position.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


class TextureManifestError(RuntimeError):
    pass


CORE_PREVIEW_ROLES = {
    "colorMap": "baseColorTexture",
    "normalMap": "normalTexture",
}

# These are exact source semantic labels, but mapping them to a standard PBR
# channel would require an additional conversion policy.
SOURCE_CLOSED_NONCORE_ROLES = {
    "specularMap",
    "detailMap",
    "waterMap",
    "function",
    "2d",
}

# These names describe packed/compositor products recovered by the prior BO2
# material pipeline. Their channel interpretation is intentionally not guessed.
PACKED_OR_COMPOSITE_ROLES = {
    "colorGloss",
    "colorOpacity",
}


def _int(value: str, field: str, row_number: int) -> int:
    try:
        return int(value)
    except Exception as exc:
        raise TextureManifestError(
            f"row {row_number}: invalid integer {field}={value!r}"
        ) from exc


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _resolve_texture(source_texture: str, texture_root: Path | None) -> dict | None:
    if texture_root is None:
        return None
    # The mapping records exact source basenames. Preserve that contract: do
    # not fuzzy-match shortened/hash-suffixed names or extensions.
    candidate = texture_root / source_texture
    if not candidate.is_file():
        return {
            "found": False,
            "path": str(candidate),
        }
    return {
        "found": True,
        "path": str(candidate),
        "bytes": candidate.stat().st_size,
        "sha256": _sha256(candidate),
    }


def _compositor_identities(text: str) -> list[str]:
    """Preserve recovered compositor expressions without guessing grammar.

    The retained Frost mapping contains pipe-delimited expressions such as
    `ao_decal_ramp|BlendTextures` and longer chains. The meaning/order of every
    pipe token is not yet source-closed, so a pipe expression remains one
    opaque identity. Comma/semicolon are accepted only as outer separators for
    derivative tables that store more than one recovered expression per cell.
    """
    value = text.strip()
    if not value:
        return []
    values: list[str] = []
    for comma_part in value.split(","):
        for semicolon_part in comma_part.split(";"):
            identity = semicolon_part.strip()
            if identity:
                values.append(identity)
    return values


def normalize_mapping_csv(
    csv_path: Path,
    *,
    texture_root: Path | None = None,
) -> dict:
    raw = csv_path.read_bytes()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    required = {
        "material_index",
        "material",
        "layer_index",
        "layer",
        "role",
        "texture_index",
        "source_texture",
        "compositors",
    }
    fields = set(reader.fieldnames or [])
    missing = sorted(required - fields)
    if missing:
        raise TextureManifestError(f"mapping CSV missing columns {missing}")

    materials: dict[tuple[int, str], dict] = {}
    seen_rows: set[tuple] = set()
    role_counts = Counter()
    compositor_counts = Counter()
    duplicate_identical_rows = 0
    exact_texture_files_found = 0
    exact_texture_files_missing = 0

    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        material_index = _int(row["material_index"], "material_index", row_number)
        material_name = (row["material"] or "").strip()
        layer_index = _int(row["layer_index"], "layer_index", row_number)
        layer_name = (row["layer"] or "").strip()
        role = (row["role"] or "").strip()
        texture_index = _int(row["texture_index"], "texture_index", row_number)
        source_texture = (row["source_texture"] or "").strip()
        compositor_text = (row["compositors"] or "").strip()
        compositors = _compositor_identities(compositor_text)

        if not material_name:
            raise TextureManifestError(f"row {row_number}: empty material name")
        if layer_index < 0:
            raise TextureManifestError(f"row {row_number}: negative layer_index")
        if not layer_name:
            raise TextureManifestError(f"row {row_number}: empty layer name")
        if not role:
            raise TextureManifestError(f"row {row_number}: empty role")
        if not source_texture:
            raise TextureManifestError(f"row {row_number}: empty source_texture")

        identity = (
            material_index,
            material_name,
            layer_index,
            layer_name,
            role,
            texture_index,
            source_texture,
            tuple(compositors),
        )
        if identity in seen_rows:
            duplicate_identical_rows += 1
            continue
        seen_rows.add(identity)

        key = (material_index, material_name)
        material = materials.setdefault(
            key,
            {
                "materialIndex": material_index,
                "material": material_name,
                "layers": {},
                "compositors": [],
            },
        )
        layer = material["layers"].setdefault(
            layer_index,
            {
                "layerIndex": layer_index,
                "layer": layer_name,
                "textures": [],
            },
        )
        if layer["layer"] != layer_name:
            raise TextureManifestError(
                f"material {material_name!r} layer {layer_index} has conflicting names "
                f"{layer['layer']!r} and {layer_name!r}"
            )

        for compositor in compositors:
            if compositor not in material["compositors"]:
                material["compositors"].append(compositor)
            compositor_counts[compositor] += 1

        resolved_file = _resolve_texture(source_texture, texture_root)
        if resolved_file is not None:
            if resolved_file["found"]:
                exact_texture_files_found += 1
            else:
                exact_texture_files_missing += 1

        dependency = {
            "role": role,
            "textureIndex": texture_index,
            "sourceTexture": source_texture,
            "compositors": compositors,
        }
        if resolved_file is not None:
            dependency["file"] = resolved_file
        layer["textures"].append(dependency)
        role_counts[role] += 1

    normalized_materials: list[dict] = []
    standard_preview_binding_count = 0
    layered_material_count = 0
    compositor_material_count = 0
    unresolved_standard_semantics = 0

    for _, material in sorted(materials.items(), key=lambda item: item[0]):
        layers = [material["layers"][i] for i in sorted(material["layers"])]
        for layer in layers:
            layer["textures"].sort(
                key=lambda tex: (tex["role"], tex["textureIndex"], tex["sourceTexture"])
            )
        material["layers"] = layers
        material["compositors"].sort()
        is_layered = len(layers) > 1
        has_compositor = bool(material["compositors"])
        if is_layered:
            layered_material_count += 1
        if has_compositor:
            compositor_material_count += 1

        preview: dict[str, dict] = {}
        blocked: list[dict] = []
        base_layer = next((layer for layer in layers if layer["layerIndex"] == 0), None)
        if base_layer is not None:
            for texture in base_layer["textures"]:
                role = texture["role"]
                if not is_layered and not has_compositor and role in CORE_PREVIEW_ROLES:
                    target = CORE_PREVIEW_ROLES[role]
                    if target in preview:
                        blocked.append(
                            {
                                "role": role,
                                "reason": "multiple exact candidates for one standard binding",
                                "texture": texture,
                            }
                        )
                        preview.pop(target, None)
                        unresolved_standard_semantics += 1
                    else:
                        preview[target] = {
                            "role": role,
                            "textureIndex": texture["textureIndex"],
                            "sourceTexture": texture["sourceTexture"],
                        }
                elif role in CORE_PREVIEW_ROLES:
                    blocked.append(
                        {
                            "role": role,
                            "reason": "layered/composited material requires explicit bake/shader policy",
                            "texture": texture,
                        }
                    )
                else:
                    blocked.append(
                        {
                            "role": role,
                            "reason": (
                                "source semantic retained; no core-glTF conversion policy"
                                if role in SOURCE_CLOSED_NONCORE_ROLES
                                else "packed/composite or unknown semantic retained"
                            ),
                            "texture": texture,
                        }
                    )
        standard_preview_binding_count += len(preview)

        normalized_materials.append(
            {
                "materialIndex": material["materialIndex"],
                "material": material["material"],
                "layered": is_layered,
                "compositors": material["compositors"],
                "layers": layers,
                "standardPreview": preview,
                "standardPreviewBlocked": blocked,
            }
        )

    return {
        "format": "t6-material-texture-manifest-v1",
        "source": {
            "file": csv_path.name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "textureRoot": str(texture_root) if texture_root is not None else None,
            "columns": reader.fieldnames or [],
            "optionalIndexColumnPresent": "index" in fields,
        },
        "policy": {
            "roleSelection": "exact role column only; never filename/position heuristics",
            "corePreviewRoles": CORE_PREVIEW_ROLES,
            "specularPolicy": "preserve exact TS_SPECULAR_MAP dependency; no implicit PBR remap",
            "packedRolePolicy": "preserve colorGloss/colorOpacity and other packed roles until channel semantics are proven",
            "layeredPolicy": "preserve all layers/compositor identities; no implicit bake",
            "compositorGrammar": "pipe-delimited expressions are opaque exact identities until grammar is source-closed",
            "textureFileResolution": "exact source_texture basename under textureRoot only",
        },
        "stats": {
            "materialCount": len(normalized_materials),
            "layeredMaterialCount": layered_material_count,
            "compositorMaterialCount": compositor_material_count,
            "textureDependencyCount": sum(role_counts.values()),
            "roleCounts": dict(sorted(role_counts.items())),
            "compositorUseCounts": dict(sorted(compositor_counts.items())),
            "standardPreviewBindingCount": standard_preview_binding_count,
            "ambiguousStandardPreviewBindings": unresolved_standard_semantics,
            "duplicateIdenticalRows": duplicate_identical_rows,
            "exactTextureFilesFound": exact_texture_files_found,
            "exactTextureFilesMissing": exact_texture_files_missing,
        },
        "materials": normalized_materials,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mapping_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--texture-root", type=Path)
    args = parser.parse_args()

    document = normalize_mapping_csv(
        args.mapping_csv,
        texture_root=args.texture_root,
    )
    args.output_json.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": str(args.output_json), **document["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
