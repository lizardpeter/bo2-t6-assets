#!/usr/bin/env python3
from __future__ import annotations
import hashlib,tempfile
from pathlib import Path
import t6_generated_final_output_cbuffer_signature_v1 as c


def rdef(blob):
    return {
        'format':'t6-dxbc-rdef-cbuffers-v1','dxbcSha256':hashlib.sha256(blob).hexdigest(),'shaderModel':'4.0','constantBufferCount':2,
        'constantBuffers':[
            {'name':'PerMaterial','bindPoint':1,'size':960,'type':0,'flags':0,'variables':[{'name':'alphaRevealParms1','startOffset':944,'size':16,'endOffset':960,'flags':0,'typeOffset':123}]},
            {'name':'PerFrame','bindPoint':3,'size':16,'type':0,'flags':0,'variables':[{'name':'worldSomething','startOffset':0,'size':16,'endOffset':16,'flags':0,'typeOffset':456}]},
        ]}
    }

def main()->int:
    assigns=c.parse_tech_assignments('''
alphaRevealParms1 = material.alphaRevealParms1;
worldSomething = code.worldSomething;
otherVar = float4(1, 2, 3, 4);
vertex.texcoord[5] = code.normalTransform[0];
''')
    assert assigns=={'alphaRevealParms1':'material.alphaRevealParms1','worldSomething':'code.worldSomething','otherVar':'float4(1, 2, 3, 4)'}
    assert c._source_identity(assigns['alphaRevealParms1'])=={'sourceClass':'material','sourceExpression':'material.alphaRevealParms1','sourceName':'alphaRevealParms1'}
    assert c._source_identity(assigns['worldSomething'])['sourceClass']=='code'
    assert c._source_identity(assigns['otherVar'])['sourceClass']=='other'
    try:c.parse_tech_assignments('x = material.a;\nx = material.b;')
    except c.FinalOutputCbufferSignatureError as exc:assert 'conflicting assignments' in str(exc)
    else:raise AssertionError('conflicting .tech assignment accepted')

    blob=b'DXBC-cbuffer-signature-fixture';sha=hashlib.sha256(blob).hexdigest()
    mapping={'lit_sm_fixture':assigns}
    x=c.map_symbol('cb1[59].x',rdef(blob),mapping);y=c.map_symbol('cb1[59].y',rdef(blob),mapping);z=c.map_symbol('cb3[0].z',rdef(blob),mapping)
    assert x['byteOffset']==944 and x['buffer']['name']=='PerMaterial' and x['variable']['name']=='alphaRevealParms1' and x['variable']['relativeScalarIndex']==0
    assert y['byteOffset']==948 and y['variable']['relativeByteOffset']==4 and y['variable']['relativeScalarIndex']==1
    assert x['techniqueAssignments'][0]['sourceClass']=='material'
    assert z['byteOffset']==8 and z['buffer']['name']=='PerFrame' and z['variable']['name']=='worldSomething' and z['variable']['relativeScalarIndex']==2 and z['techniqueAssignments'][0]['sourceClass']=='code'
    try:c.map_symbol('cb2[0].x',rdef(blob),mapping)
    except c.FinalOutputCbufferSignatureError as exc:assert 'RDEF b2 buffer count 0' in str(exc)
    else:raise AssertionError('missing RDEF cbuffer was accepted')

    with tempfile.TemporaryDirectory(prefix='t6_cb_sig_') as td:
        root=Path(td);(root/'shader_bin').mkdir();(root/'techniques').mkdir();(root/'shader_bin'/'ps_fixture.cso').write_bytes(blob);(root/'techniques'/'fixture.tech').write_text('alphaRevealParms1 = material.alphaRevealParms1;\nworldSomething = code.worldSomething;\n')
        final={'format':c.FINAL_FORMAT,'shaders':[{'sha256':sha,'techniqueSets':['lit_sm_fixture'],'nodes':[{'id':0,'kind':'symbol','name':'cb1[59].x'},{'id':1,'kind':'symbol','name':'cb1[59].y'},{'id':2,'kind':'symbol','name':'cb3[0].z'},{'id':3,'kind':'symbol','name':'v0.x'}]}]}
        old_resolve=c.resolve_slot_shader;old_parse=c.parse_rdef_constant_buffers
        try:
            c.resolve_slot_shader=lambda oat_root,technique,slot_index:{'techniqueAsset':'fixture','techniqueFile':'techniques/fixture.tech','pixelShaders':[{'asset':'fixture','relativeFile':'shader_bin/ps_fixture.cso','sha256':sha}]}
            c.parse_rdef_constant_buffers=lambda data:rdef(data)
            got=c.build(final,root)
        finally:c.resolve_slot_shader=old_resolve;c.parse_rdef_constant_buffers=old_parse
        assert got['summary']['shaderCount']==1
        assert got['summary']['usedCbufferSymbolCount']==3 and got['summary']['usedCbufferNodeCount']==3
        assert got['summary']['uniqueReflectedVariableCount']==2
        assert got['summary']['techniqueAssignmentSourceClassCounts']=={'code':1,'material':2}
        rows={r['symbol']:r for r in got['shaders'][0]['usedCbufferSymbols']}
        assert rows['cb1[59].x']['nodeIds']==[0] and rows['cb3[0].z']['techniqueAssignments'][0]['sourceName']=='worldSomething'
    print('PASS: exact generated final-output cbuffer RDEF signature v1');return 0
if __name__=='__main__':raise SystemExit(main())
