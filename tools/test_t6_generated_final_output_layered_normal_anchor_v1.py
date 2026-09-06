#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_generated_final_output_layered_normal_anchor_v1 as anchor
import t6_generated_final_output_directional_lightmap_anchor_v2 as directional
import t6_generated_final_output_io_signature_v1 as io_signature
import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3


def fixture(*, target=True):
    nodes=[]
    def add(kind,**kw):i=len(nodes);nodes.append({'id':i,'kind':kind,**kw});return i
    base={ch:add('symbol',name=f'v1.{ch}') for ch in 'xyz'}
    ybasis={ch:add('symbol',name=f'v2.{ch}') for ch in 'xyz'}
    xbasis={ch:add('symbol',name=f'v3.{ch}') for ch in 'xyz'}
    lx=add('symbol',name='cb1[10].x');ly=add('symbol',name='cb1[10].y')
    raw={};sq={}
    for ch in 'xyz':
        xt=add('op',op='mul',args=[lx,xbasis[ch]])
        yt=add('op',op='mul',args=[ybasis[ch],ly])
        a=add('op',op='add',args=[base[ch],xt])
        raw[ch]=add('op',op='add',args=[yt,a])
        sq[ch]=add('op',op='mul',args=[raw[ch],raw[ch]])
    dxy=add('op',op='add',args=[sq['x'],sq['y']]);dot=add('op',op='add',args=[dxy,sq['z']]);rsq=add('op',op='rsq',args=[dot])
    normal={ch:add('op',op='mul',args=[rsq,raw[ch]]) for ch in 'xyz'}
    other={ch:add('symbol',name=f'cb2[3].{ch}') for ch in 'xyz'}
    sha='a'*64
    technique='lit_sm_r0c0n0_b1c1n1' if target else 'lit_sm_r0c0_b1c1'
    final={'format':symbolic_v3.FORMAT,'shaders':[{'sha256':sha,'techniqueSets':[technique],'nodes':nodes}]}
    sig_entries=[]
    for reg,sem in ((1,'TEXCOORD1'),(2,'TEXCOORD2'),(3,'TEXCOORD3')):
        sig_entries.append({'register':reg,'semantic':sem})
    io={'format':io_signature.FORMAT,'shaders':[{'sha256':sha,'inputSignature':{'registerMap':{'1':'TEXCOORD1','2':'TEXCOORD2','3':'TEXCOORD3'},'entries':sig_entries}}]}
    direc={'format':directional.FORMAT,'shaders':[{'sha256':sha,'equations':[{'normalNodes':other},{'normalNodes':normal}]}]}
    return final,io,direc,{'normal':normal,'raw':raw,'lx':lx,'ly':ly,'nodes':nodes}


def expect_fail(final,io,direc,phrase):
    try:anchor.build(final,io,direc,strict=True)
    except anchor.GeneratedFinalOutputLayeredNormalAnchorError as exc:assert phrase in str(exc),str(exc)
    else:raise AssertionError(f'expected failure containing {phrase!r}')


def main():
    final,io,direc,state=fixture()
    result=anchor.build(final,io,direc,strict=True)
    assert result['format']==anchor.FORMAT
    assert result['summary']['shaderCount']==1
    assert result['summary']['layeredNormalTargetShaderCount']==1
    assert result['summary']['anchoredLayeredNormalShaderCount']==1
    assert result['summary']['matchedDirectionalEquationCount']==1
    assert result['summary']['missingTargetShaderCount']==0 and result['summary']['ambiguousTargetShaderCount']==0
    row=result['shaders'][0];assert row['anchored'] is True and row['matchCount']==1
    match=row['matches'][0];assert match['directionalEquationIndex']==1
    assert match['layeredNormalXNode']==state['lx'] and match['layeredNormalYNode']==state['ly']
    assert match['normalNodes']==state['normal'] and match['rawNormalNodes']==state['raw']
    assert match['basis']=={'baseNormal':'TEXCOORD1.xyz','layeredXBasis':'TEXCOORD3.xyz','layeredYBasis':'TEXCOORD2.xyz'}

    f,i,d,s=fixture();d['shaders'][0]['equations']=[d['shaders'][0]['equations'][0]]
    expect_fail(f,i,d,'has 0 matching directional equations')

    f,i,d,s=fixture();d['shaders'][0]['equations'].append({'normalNodes':dict(s['normal'])})
    expect_fail(f,i,d,'has 2 matching directional equations')

    f,i,d,s=fixture();i['shaders'][0]['inputSignature']['registerMap']['3']='TEXCOORD4'
    expect_fail(f,i,d,'lacks required ISGN semantics')

    f,i,d,s=fixture();
    # Break the shared layered-X root in z only while keeping the outer normalize shape.
    new_scalar=len(s['nodes']);s['nodes'].append({'id':new_scalar,'kind':'symbol','name':'cb1[11].x'})
    rawz=s['raw']['z'];terms=anchor._flatten_add(s['nodes'],rawz)
    xterm=next(t for t in terms if anchor._mul_scalar_basis(s['nodes'],t,{1:'TEXCOORD1',2:'TEXCOORD2',3:'TEXCOORD3'},'TEXCOORD3','z') is not None)
    pair=s['nodes'][xterm]['args'];s['nodes'][xterm]['args']=[new_scalar,pair[1]] if pair[0]==s['lx'] else [pair[0],new_scalar]
    expect_fail(f,i,d,'has 0 matching directional equations')

    f,i,d,s=fixture(target=False)
    # Keep only unrelated directional N; non-target paths are not forced into layered-normal semantics.
    d['shaders'][0]['equations']=[d['shaders'][0]['equations'][0]]
    relaxed=anchor.build(f,i,d,strict=True)
    assert relaxed['summary']['layeredNormalTargetShaderCount']==0
    assert relaxed['summary']['anchoredLayeredNormalShaderCount']==0
    assert relaxed['summary']['missingTargetShaderCount']==0

    bad=copy.deepcopy(io);bad['shaders'][0]['sha256']='b'*64
    expect_fail(final,bad,direc,'shader sets disagree')

    print('PASS: generated final-output layered-normal semantic anchor v1')
    return 0
if __name__=='__main__':raise SystemExit(main())
