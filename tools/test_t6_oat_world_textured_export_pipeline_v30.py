#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v30 as v30
from t6_world_gltf_export_v1 import glb_bytes


def recipe(material="*fixture"):
    return {
        "material":material,
        "techniqueSet":"lit_sm_r0c0x0_b1c1s1",
        "pixelShaderArchetype":"sha256:"+"a"*64,
        "worldVertFormats":[1],
        "proof":{"fixture":True},
        "generatedSpecularStateV1":{
            "format":"t6-generated-layered-specular-state-v1",
            "material":material,
            "techniqueSet":"lit_sm_r0c0x0_b1c1s1",
            "pixelShaderArchetype":"sha256:"+"a"*64,
            "baseline":{"mode":"retail_fallback","rgb":[0.2,0.2,0.2],"alphaMode":"constantZero","alphaValue":0.0},
            "steps":[{"layerIndex":1,"operator":"b","factorBinding":{"kind":"exactRgbWeight"}}],
            "secondarySpecularLayerCount":1,
        },
    }


def fixture_glb(conflict=False):
    r=recipe();r2=copy.deepcopy(r)
    if conflict:r2["generatedSpecularStateV1"]["secondarySpecularLayerCount"]=2
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":0}],
        "materials":[
            {"name":"*fixture","extras":{"T6":{"generatedShaderRecipeV1":r}}},
            {"name":"*fixture__lm3","extras":{"T6":{"generatedShaderRecipeV1":r2}}},
        ],
    }
    return glb_bytes(doc,b"")


def main()->int:
    m=v30._embedded_recipe_manifest(fixture_glb(False))
    assert m["format"]==v30.RECIPE_FORMAT
    assert len(m["materials"])==1
    assert m["materials"][0]["material"]=="*fixture"
    assert m["extraction"]["canonicalRecipeCount"]==1
    assert m["extraction"]["materialShellCount"]==2
    assert m["extraction"]["previewShellDuplicateCount"]==1
    try:v30._embedded_recipe_manifest(fixture_glb(True))
    except v30.OatTexturedPipelineV30Error as exc:assert "disagree on canonical recipe" in str(exc)
    else:raise AssertionError("conflicting preview-shell recipes were accepted")

    with tempfile.TemporaryDirectory(prefix="t6_v30_") as td:
        root=Path(td);old=root/"mp_nuketown_2020.world_oat_portable_textured_v29.glb";old.write_bytes(fixture_glb(False))
        final=root/"mp_nuketown_2020.generated_slot4_final_output_symbolic_v3.json";final.write_text(json.dumps({"format":"t6-generated-slot4-final-output-symbolic-v3","shaders":[]}),encoding="utf-8")
        old_manifest=root/"old_v29.json";old_manifest.write_text("{}",encoding="utf-8")
        base={
            "format":v30.v29.FORMAT,
            "outputs":{
                "oatPortableTexturedGlb":{"path":str(old),"file":old.name,"bytes":old.stat().st_size,"sha256":"x"},
                "generatedSlot4FinalOutputSymbolic":{"path":str(final),"file":final.name,"bytes":final.stat().st_size,"sha256":"y"},
            },
            "stats":{},"validation":{},"policies":{},
            "manifest":{"path":str(old_manifest)},
        }
        old_run=v30.v29.run_oat_textured_pipeline;old_build=v30.spec_anchor.build
        calls=[]
        try:
            v30.v29.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
            def fake_build(recipes,final_doc,strict_downstream_use=True):
                calls.append((copy.deepcopy(recipes),strict_downstream_use))
                return {
                    "format":v30.spec_anchor.FORMAT,
                    "materials":[{"material":"*fixture"}],
                    "summary":{
                        "specularMaterialCount":1,
                        "specularStepCount":1,
                        "downstreamUsedMaterialCount":1,
                        "uniqueSharedFactorDagCount":1,
                        "allCompletedStatesDownstreamUsed":True,
                        "strictDownstreamUse":True,
                    },
                    "rowsSha256":"a"*64,
                }
            v30.spec_anchor.build=fake_build
            result=v30.run_oat_textured_pipeline(output_dir=root,map_name="mp_nuketown_2020")
        finally:
            v30.v29.run_oat_textured_pipeline=old_run;v30.spec_anchor.build=old_build
        assert len(calls)==2 and all(strict for _,strict in calls)
        assert calls[0][0]==calls[1][0]
        assert calls[0][0]["extraction"]["previewShellDuplicateCount"]==1
        assert result["format"]==v30.FORMAT
        assert result["validation"]["v30SpecularStateAnchorGenerated"] is True
        assert result["validation"]["v30AllCompletedSpecularStatesDownstreamUsed"] is True
        assert result["validation"]["v30CanonicalEmbeddedRecipeCount"]==1
        assert result["validation"]["v30PreviewShellDuplicateCount"]==1
        new=Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        assert new.name.endswith("_v30.glb") and new.read_bytes()==fixture_glb(False)
        side=Path(result["outputs"]["generatedFinalOutputSpecularStateAnchor"]["path"])
        assert json.loads(side.read_text())["summary"]["specularMaterialCount"]==1
        assert not old_manifest.exists()

    print("PASS: production v30 generated specular final-output sidecar")
    return 0

if __name__=="__main__":raise SystemExit(main())
