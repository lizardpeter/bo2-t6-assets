#!/usr/bin/env python3
"""T6 OAT material manifest v5: exact shader-role preview promotion.

Builds on v4's exact image graph + decoded render-state archive. Ordinary materials
that are blocked from core-glTF preview because several dependencies share one broad
OAT semantic may be promoted only when one exact shader argument/role is unique.

Canonical portable preview roles:
  baseColorTexture <- unique `colorMap`, else unique `Diffuse_Map`/`DiffuseMap`
  normalTexture    <- unique `normalMap`/`Normal_Map`

Generated/layered materials remain unbound. No image filename classification and no
Treyarch layered compositor is invented.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from t6_oat_material_manifest_v4 import build_manifest as build_manifest_v4

PRODUCER = "t6_oat_material_manifest_v5.py"


def _norm_role(value: object) -> str:
    return str(value or "").replace("-", "_").lower()


def _binding(dep: dict) -> dict:
    return {
        "role": dep.get("role"),
        "semantic": dep.get("semantic"),
        "textureIndex": dep.get("textureIndex"),
        "imageAsset": dep.get("imageAsset"),
        "sourceTexture": dep.get("sourceTexture"),
        "sourceOatImagePath": dep.get("sourceOatImagePath"),
        "sourceOatImageAsset": dep.get("sourceOatImageAsset"),
        "samplerState": dep.get("samplerState"),
        "exactOatRolePromotion": True,
    }


def _choose(deps: list[dict], target: str) -> dict | None:
    if target == "baseColorTexture":
        exact = [d for d in deps if _norm_role(d.get("name")) == "colormap"]
        if len(exact) == 1:
            return exact[0]
        exact = [
            d
            for d in deps
            if _norm_role(d.get("name")) in ("diffuse_map", "diffusemap")
        ]
        return exact[0] if len(exact) == 1 else None
    exact = [
        d
        for d in deps
        if _norm_role(d.get("name")) in ("normalmap", "normal_map")
    ]
    return exact[0] if len(exact) == 1 else None


def _promote(doc: dict) -> dict:
    promoted: list[dict] = []
    for material in doc.get("materials", []):
        if material.get("layered") or material.get("compoundIdentity"):
            continue
        layers = material.get("layers") or []
        if len(layers) != 1:
            continue
        deps = layers[0].get("textures") or []
        preview = material.setdefault("standardPreview", {})
        blocked = material.setdefault("standardPreviewBlocked", [])
        for target in ("baseColorTexture", "normalTexture"):
            chosen = _choose(deps, target)
            if chosen is None:
                continue
            old = preview.get(target)
            if old and old.get("textureIndex") == chosen.get("textureIndex"):
                continue
            preview[target] = _binding(chosen)
            blocked[:] = [
                item
                for item in blocked
                if (item.get("texture") or {}).get("textureIndex")
                != chosen.get("textureIndex")
            ]
            promoted.append(
                {
                    "materialIndex": material.get("materialIndex"),
                    "material": material.get("material"),
                    "target": target,
                    "role": chosen.get("name"),
                    "semantic": chosen.get("semantic"),
                    "imageAsset": chosen.get("imageAsset"),
                    "replacedPreview": old,
                }
            )
    doc.setdefault("source", {})["producer"] = PRODUCER
    doc.setdefault("policy", {})["exactRolePreviewPromotion"] = (
        "ordinary materials only; exact OAT shader argument names; no filename inference; "
        "layered/generated materials remain unbound"
    )
    stats = doc.setdefault("stats", {})
    stats["exactRolePreviewPromotionCount"] = len(promoted)
    stats["standardPreviewBindingCountAfterExactRolePromotion"] = sum(
        len(m.get("standardPreview", {})) for m in doc.get("materials", [])
    )
    doc["exactRolePreviewPromotions"] = promoted
    return doc


def build_manifest(
    *,
    material_root: Path,
    catalog_doc: dict,
    source_texture_extension: str,
    allow_missing_materials: bool = False,
) -> dict:
    return _promote(
        build_manifest_v4(
            material_root=material_root,
            catalog_doc=catalog_doc,
            source_texture_extension=source_texture_extension,
            allow_missing_materials=allow_missing_materials,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_root", type=Path)
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--source-texture-extension", required=True)
    parser.add_argument("--allow-missing-materials", action="store_true")
    args = parser.parse_args()
    doc = build_manifest(
        material_root=args.material_root,
        catalog_doc=json.loads(args.catalog_json.read_text(encoding="utf-8")),
        source_texture_extension=args.source_texture_extension,
        allow_missing_materials=args.allow_missing_materials,
    )
    args.output_json.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.output_json), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
