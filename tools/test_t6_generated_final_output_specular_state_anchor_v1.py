#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_generated_final_output_specular_state_anchor_v1 as anchor


def _add(nodes, kind, **kw):
    i=len(nodes);nodes.append({"id":i,"kind":kind,**kw});return i


def _sample(nodes,res,ch):
    return _add(nodes,"textureSample",resource=res,channel=ch,sampler=res+"_s",args=[])


def _lit(nodes,bits): return _add(nodes,"literal32",bits=bits)
def _op(nodes,op,*args): return _add(nodes,"op",op=op,args=list(args))


def fixture(*, explicit=False, threshold=False, bad_shared=False, dead=False):
    nodes=[]
    zero=_lit(nodes,"00000000");f02=_lit(nodes,anchor.F02_BITS)
    base_color_w=_sample(nodes,"colorMapSampler","w")
    prev={}
    if explicit:
        for ch in anchor.CHANNELS: prev[ch]=_sample(nodes,"specularMapSampler",ch)
        baseline={"mode":"explicit_specular"}
    else:
        prev={"x":f02,"y":f02,"z":f02,"w":base_color_w}
        baseline={"mode":"retail_fallback","rgb":[0.2,0.2,0.2],"alphaMode":"baseColorAlpha"}
    layer={ch:_sample(nodes,"specularMapSampler1",ch) for ch in anchor.CHANNELS}
    factor=_sample(nodes,"colorMapSampler1","w")
    factor2=_sample(nodes,"colorMapSampler1","x") if bad_shared else factor
    state={}
    for ch in anchor.CHANNELS:
        f=factor2 if (bad_shared and ch=="w") else factor
        if threshold:
            state[ch]=_op(nodes,"select",f,layer[ch],prev[ch])
        else:
            neg=_op(nodes,"neg",prev[ch]);diff=_op(nodes,"add",layer[ch],neg)
            term=_op(nodes,"mul",diff,f);state[ch]=_op(nodes,"add",prev[ch],term)
    # Make final state reachable from o0 unless dead=True.
    outputs=[]
    for ch in "xyz":
        root=_op(nodes,"add",state[ch],zero) if not dead else _sample(nodes,"lightmapSampler",ch)
        outputs.append({"channel":ch,"written":True,"node":root,"resources":[]})
    outputs.append({"channel":"w","written":True,"node":state["w"] if not dead else zero,"resources":[]})
    shader_sha="a"*64
    attachment={
        "format":"t6-generated-layered-specular-state-v1",
        "material":"*fixture",
        "techniqueSet":"lit_sm_r0c0x0_b1c1s1",
        "pixelShaderArchetype":"sha256:"+shader_sha,
        "baseline":baseline,
        "steps":[{
            "layerIndex":1,
            "operator":"t" if threshold else "b",
            "operation":"threshold" if threshold else "blend",
            "factorBinding":{"kind":"exactRgbThresholdCondition" if threshold else "exactRgbWeight"},
        }],
        "secondarySpecularLayerCount":1,
    }
    recipe={
        "material":"*fixture",
        "techniqueSet":"lit_sm_r0c0x0_b1c1s1",
        "pixelShaderArchetype":"sha256:"+shader_sha,
        "worldVertFormats":[1],
        "proof":{"fixture":True},
        anchor.SPEC_KEY:attachment,
    }
    recipes={"format":"t6-generated-world-shader-recipe-manifest-v1","materials":[recipe]}
    final={
        "format":anchor.FINAL_FORMAT,
        "materials":[{"material":"*fixture"}],
        "shaders":[{
            "sha256":shader_sha,
            "techniqueSets":[recipe["techniqueSet"]],
            "nodes":nodes,
            "outputs":[{"register":0,"lanes":outputs}],
        }],
    }
    return recipes,final


def main()->int:
    # The canonical validator can be replaced here because this regression is
    # focused on final-output recurrence mechanics, not recipe grammar (which has
    # dedicated tests). Preserve extension fields exactly as production expects.
    old=anchor.validate_manifest
    try:
        anchor.validate_manifest=lambda doc:{row["material"]:copy.deepcopy(row) for row in doc["materials"]}

        recipes,final=fixture(explicit=False)
        got=anchor.build(recipes,final)
        assert got["format"]==anchor.FORMAT
        assert got["summary"]=={
            "specularMaterialCount":1,
            "specularStepCount":1,
            "downstreamUsedMaterialCount":1,
            "uniqueSharedFactorDagCount":1,
            "allCompletedStatesDownstreamUsed":True,
            "strictDownstreamUse":True,
        }
        row=got["materials"][0]
        assert row["downstreamUsed"] is True
        assert set(row["steps"][0]["stateNodes"])==set(anchor.CHANNELS)
        assert row["steps"][0]["factorBindingKind"]=="exactRgbWeight"
        assert all(row["downstreamOutputLanes"][ch] for ch in anchor.CHANNELS)

        recipes,final=fixture(explicit=True)
        got=anchor.build(recipes,final)
        assert got["materials"][0]["baseline"]["mode"]=="explicit_specular"

        recipes,final=fixture(threshold=True)
        got=anchor.build(recipes,final)
        assert got["materials"][0]["steps"][0]["operator"]=="t"
        assert got["materials"][0]["steps"][0]["factorBindingKind"]=="exactRgbThresholdCondition"

        recipes,final=fixture(bad_shared=True)
        try:
            anchor.build(recipes,final)
        except anchor.SpecularFinalOutputAnchorError as exc:
            assert "shared b factor/condition hash count" in str(exc)
        else: raise AssertionError("per-channel specular factor disagreement was accepted")

        recipes,final=fixture(dead=True)
        try:
            anchor.build(recipes,final)
        except anchor.SpecularFinalOutputAnchorError as exc:
            assert "no exact o0 ancestry" in str(exc)
        else: raise AssertionError("dead completed specular state was promoted")
        relaxed=anchor.build(recipes,final,strict_downstream_use=False)
        assert relaxed["materials"][0]["downstreamUsed"] is False
        assert relaxed["summary"]["allCompletedStatesDownstreamUsed"] is False
    finally:
        anchor.validate_manifest=old

    print("PASS: exact generated specular XYZW final-output anchor v1")
    return 0

if __name__=="__main__": raise SystemExit(main())
