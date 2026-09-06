#!/usr/bin/env python3
"""Production T6 world export pipeline v30: exact specular-state downstream join.

v30 preserves v29 visual bytes.  When the exact final-output DAG exists, it
reconstructs a canonical generated recipe manifest from recipes already embedded
in the v29 GLB (deduplicating preview material shells by canonical retail
material identity), then requires every v21 specular-bearing recipe to match its
exact XYZW recurrence inside the complete o0 DAG and to be downstream-used.

No physical interpretation of specular X/Y/Z/W is introduced.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import t6_generated_final_output_specular_state_anchor_v1 as spec_anchor
import t6_oat_world_textured_export_pipeline_v29 as v29
from t6_generated_shader_recipe_contract_v1 import EXTRA_KEY, FORMAT as RECIPE_FORMAT
from t6_glb_parse_v1 import parse_glb
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS, DEFAULT_SHADOWMAP_SCALE

FORMAT = "t6-oat-world-textured-export-pipeline-manifest-v30"


class OatTexturedPipelineV30Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _jb(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _rec(path: Path, data: bytes | None = None) -> dict:
    payload = path.read_bytes() if data is None else data
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _path(record, label: str) -> Path:
    if not isinstance(record, dict):
        raise OatTexturedPipelineV30Error(f"missing {label} record")
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise OatTexturedPipelineV30Error(f"{label} does not exist: {path}")
    return path


def _embedded_recipe_manifest(glb_bytes: bytes) -> dict:
    doc, _raw = parse_glb(glb_bytes)
    by_retail: dict[str, dict] = {}
    shell_names: dict[str, list[str]] = {}
    for material in doc.get("materials", []):
        shell = str(material.get("name") or "")
        recipe = material.get("extras", {}).get("T6", {}).get(EXTRA_KEY)
        if not isinstance(recipe, dict):
            continue
        retail = str(recipe.get("material") or "")
        if not retail.startswith("*"):
            raise OatTexturedPipelineV30Error(
                f"material shell {shell!r} embeds invalid canonical recipe material {retail!r}"
            )
        old = by_retail.get(retail)
        if old is not None and old != recipe:
            raise OatTexturedPipelineV30Error(
                f"preview shells disagree on canonical recipe for {retail!r}"
            )
        by_retail[retail] = copy.deepcopy(recipe)
        shell_names.setdefault(retail, []).append(shell)
    if not by_retail:
        raise OatTexturedPipelineV30Error("v29 GLB contains no embedded generated recipes")
    return {
        "format": RECIPE_FORMAT,
        "materials": [by_retail[name] for name in sorted(by_retail)],
        "extraction": {
            "source": "v29 GLB material.extras.T6.generatedShaderRecipeV1",
            "canonicalRecipeCount": len(by_retail),
            "materialShellCount": sum(len(rows) for rows in shell_names.values()),
            "previewShellDuplicateCount": sum(max(0, len(rows)-1) for rows in shell_names.values()),
            "joinPolicy": "canonical embedded recipe.material identity; duplicate shells must carry byte-equivalent JSON recipes",
        },
    }


def run_oat_textured_pipeline(**kwargs) -> dict:
    result = v29.run_oat_textured_pipeline(**kwargs)
    if result.get("format") != v29.FORMAT:
        raise OatTexturedPipelineV30Error(
            f"unexpected v29 base manifest {result.get('format')!r}"
        )
    output_dir = Path(kwargs["output_dir"])
    map_name = str(kwargs["map_name"])
    outputs = result.get("outputs", {})

    old_glb = _path(outputs.get("oatPortableTexturedGlb"), "v29 portable GLB")
    glb_bytes = old_glb.read_bytes()
    new_glb = output_dir / f"{map_name}.world_oat_portable_textured_v30.glb"
    new_glb.write_bytes(glb_bytes)
    if old_glb != new_glb and old_glb.is_file():
        old_glb.unlink()
    outputs["oatPortableTexturedGlb"] = _rec(new_glb, glb_bytes)

    gltf_record = outputs.get("oatPortableTexturedGltf")
    had_gltf = isinstance(gltf_record, dict)
    if had_gltf:
        old_gltf = _path(gltf_record, "v29 portable glTF")
        gltf_bytes = old_gltf.read_bytes()
        new_gltf = output_dir / f"{map_name}.world_oat_portable_textured_v30.gltf"
        new_gltf.write_bytes(gltf_bytes)
        if old_gltf != new_gltf and old_gltf.is_file():
            old_gltf.unlink()
        outputs["oatPortableTexturedGltf"] = _rec(new_gltf, gltf_bytes)

    final_record = outputs.get("generatedSlot4FinalOutputSymbolic")
    spec_doc = recipe_doc = None
    if isinstance(final_record, dict):
        final_doc = json.loads(_path(final_record, "final-output symbolic sidecar").read_text(encoding="utf-8"))
        recipe_doc = _embedded_recipe_manifest(glb_bytes)
        try:
            s1 = spec_anchor.build(recipe_doc, final_doc, strict_downstream_use=True)
            s2 = spec_anchor.build(recipe_doc, final_doc, strict_downstream_use=True)
        except Exception as exc:
            raise OatTexturedPipelineV30Error(
                f"generated specular final-output anchoring failed: {exc}"
            ) from exc
        b1 = _jb(s1); b2 = _jb(s2)
        if s1 != s2 or b1 != b2:
            raise OatTexturedPipelineV30Error(
                "generated specular final-output anchor regeneration was not byte-identical"
            )
        if map_name == "mp_nuketown_2020" and int(s1["summary"]["specularMaterialCount"]) <= 0:
            raise OatTexturedPipelineV30Error(
                "strict Nuketown final-output proof found no v21 specular-bearing recipes"
            )
        spec_doc = s1
        path = output_dir / f"{map_name}.generated_final_output_specular_state_anchor_v1.json"
        path.write_bytes(b1)
        outputs["generatedFinalOutputSpecularStateAnchor"] = _rec(path, b1)

    summary = None if spec_doc is None else spec_doc["summary"]
    extraction = None if recipe_doc is None else recipe_doc["extraction"]
    result.setdefault("stats", {})["generatedFinalOutputSpecularStateAnchor"] = summary
    result["stats"]["v30EmbeddedRecipeExtraction"] = extraction
    result.setdefault("validation", {}).update({
        "v30SpecularStateAnchorGenerated": spec_doc is not None,
        "v30SpecularStateAnchorDeterministic": None if spec_doc is None else True,
        "v30SpecularMaterialCount": None if summary is None else int(summary["specularMaterialCount"]),
        "v30SpecularStepCount": None if summary is None else int(summary["specularStepCount"]),
        "v30SpecularDownstreamUsedMaterialCount": None if summary is None else int(summary["downstreamUsedMaterialCount"]),
        "v30AllCompletedSpecularStatesDownstreamUsed": None if summary is None else bool(summary["allCompletedStatesDownstreamUsed"]),
        "v30CanonicalEmbeddedRecipeCount": None if extraction is None else int(extraction["canonicalRecipeCount"]),
        "v30PreviewShellDuplicateCount": None if extraction is None else int(extraction["previewShellDuplicateCount"]),
        "v30VisualGlbByteIdenticalToV29": True,
        "v30VisualGltfByteIdenticalToV29": True if had_gltf else None,
    })
    result.setdefault("policies", {})["v30SpecularFinalOutputJoin"] = (
        "extract canonical recipes from the production GLB by embedded retail recipe identity; "
        "require exact v21 specular XYZW recurrence with one shared factor/condition across all four "
        "channels per layer and exact completed-state ancestry to o0; do not assign metallic, roughness, "
        "F0, gloss, or other physical channel meanings"
    )

    old_manifest = result.pop("manifest", None)
    if isinstance(old_manifest, dict):
        path = Path(str(old_manifest.get("path") or ""))
        if path.is_file():
            path.unlink()
    result["format"] = FORMAT
    payload = _jb(result)
    manifest_path = output_dir / f"{map_name}.world_oat_textured_export_manifest_v30.json"
    manifest_path.write_bytes(payload)
    result["manifest"] = _rec(manifest_path, payload)
    return result


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
    for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
    a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'specularAnchor':r['outputs'].get('generatedFinalOutputSpecularStateAnchor'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())
