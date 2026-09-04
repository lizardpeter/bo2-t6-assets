#!/usr/bin/env python3
"""Retained T6 reflection vertex-matrix chain proof.

For the 16 physically retained vertex shaders to which all 5,676 mapped
surface-normal reflection passes resolve, this verifier proves a single exact
SM4 dataflow chain:

    worldPos4 = dlights.worldMatrix * float4(POSITION.xyz, 1)
    TEXCOORD5.xyz = worldPos4.xyz
    SV_Position = PerSceneConsts.viewProjectionMatrix * worldPos4

The pass-level matrix-binding proof independently establishes that those RDEF
destinations receive T6 code constants TRANSPOSE_WORLD_MATRIX (0xD5) and
TRANSPOSE_VIEW_PROJECTION_MATRIX (0xE5). The packed-VS alias proof supplies the
5,676 occurrence counts for the 16 direct payload identities.

No CPU-side camera-relative meaning is assigned to worldPos4/TEXCOORD5 here.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path

EXPECTED_VS=16
EXPECTED_OCC=5676
ALIAS_SHA='5f396e952843514832649c0f6d8bac3ed1c5c2719806fd483d5b6bf2b21e2f40'
MATRIX_SHA='95352fe874098ef2ebf70dc6d775dcff201897ae88f5486997777985e2378e17'
TYPE_TEMP=0; TYPE_OUTPUT=2; TYPE_CB=8
OP_DP4=17

def load(p,n):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def prove_vs(prod,coord,sem,blob):
    base=prod.prove_vs(coord,sem,blob)
    if base is None:raise ValueError('TEXCOORD5 producer baseline failed')
    isgn=prod.signature(blob,b'ISGN');osgn=prod.signature(blob,b'OSGN')
    w=coord.get_program_words(blob);inst=list(coord.walk(w));tab=prod.writer_table(coord,w,inst)
    t5reg=base['osgnRegister']
    t5=[prod.latest(tab,TYPE_OUTPUT,t5reg,ch,len(inst)) for ch in 'xyz']
    if any(x is None for x in t5) or len({x[0] for x in t5})!=1:raise ValueError('TEXCOORD5 output split')
    t5i=t5[0][0];T=t5[0][4]
    if len(T)!=2:raise ValueError('TEXCOORD5 MOV operand count')
    src=T[1]
    if src['type']!=TYPE_TEMP or len(src['idx'])!=1:raise ValueError('TEXCOORD5 source is not TEMP')
    worldreg=src['idx'][0]
    if coord.effective_for_dest(src,T[0]['comps'])!='xyz':raise ValueError('TEXCOORD5 source swizzle')

    posregs=[r for r,s in osgn.items() if s==('SV_Position',0)]
    if len(posregs)!=1:raise ValueError(f'SV_Position output register count {len(posregs)}')
    preg=posregs[0];clip=[prod.latest(tab,TYPE_OUTPUT,preg,ch,len(inst)) for ch in 'xyzw']
    if any(x is None for x in clip) or len({x[0] for x in clip})!=4 or any(x[2]!=OP_DP4 for x in clip):
        raise ValueError('SV_Position is not four distinct DP4 writers')
    vp=[]
    for ch,q in zip('xyzw',clip):
        ii,p,op,d,O=q
        if d['comps']!=ch or len(O)!=3:raise ValueError('clip DP4 shape')
        a,b=O[1],O[2];cb=a if a['type']==TYPE_CB else b if b['type']==TYPE_CB else None
        vv=b if cb is a else a if cb is b else None
        if cb is None or vv is None or len(cb['idx'])!=2:raise ValueError('clip DP4 operands')
        if vv['type']!=TYPE_TEMP or vv['idx']!=[worldreg] or vv['comps'][:4]!='xyzw':
            raise ValueError('clip DP4 does not consume exact world temp')
        cbn,bo,var=sem.cb_var_at(blob,cb['idx'][0],cb['idx'][1],cb['comps'][0])
        vp.append((cb['idx'][0],cb['idx'][1],bo,cbn,var))
    expvp=[(0,36,576,'PerSceneConsts','viewProjectionMatrix'),(0,37,592,'PerSceneConsts','viewProjectionMatrix'),
           (0,38,608,'PerSceneConsts','viewProjectionMatrix'),(0,39,624,'PerSceneConsts','viewProjectionMatrix')]
    if vp!=expvp:raise ValueError(f'viewProjection rows {vp}')

    before=min(x[0] for x in clip)
    world=[prod.latest(tab,TYPE_TEMP,worldreg,ch,before) for ch in 'xyzw']
    if any(x is None for x in world) or len({x[0] for x in world})!=4 or any(x[2]!=OP_DP4 for x in world):
        raise ValueError('world temp is not four distinct DP4 writers')
    wr=[]
    for ch,q in zip('xyzw',world):
        ii,p,op,d,O=q
        if d['comps']!=ch or len(O)!=3:raise ValueError('world DP4 shape')
        a,b=O[1],O[2];cb=a if a['type']==TYPE_CB else b if b['type']==TYPE_CB else None
        vv=b if cb is a else a if cb is b else None
        if cb is None or vv is None:raise ValueError('world DP4 operands')
        if prod.homogeneous_position(coord,w,inst,tab,ii,vv,isgn)!=('POSITION',0):
            raise ValueError('world DP4 does not consume homogeneous POSITION.xyz,1')
        cbn,bo,var=sem.cb_var_at(blob,cb['idx'][0],cb['idx'][1],cb['comps'][0])
        wr.append((cb['idx'][0],cb['idx'][1],bo,cbn,var))
    expwr=[(3,0,0,'dlights','worldMatrix'),(3,1,16,'dlights','worldMatrix'),
           (3,2,32,'dlights','worldMatrix'),(3,3,48,'dlights','worldMatrix')]
    if wr!=expwr:raise ValueError(f'world rows {wr}')

    for ch,q in zip('xyz',world[:3]):
        z=prod.latest(tab,TYPE_TEMP,worldreg,ch,t5i)
        if z is None or z[0]!=q[0]:raise ValueError('TEXCOORD5 does not reuse exact world temp writer')
    return {'vertexShaderSha256':hashlib.sha256(blob).hexdigest(),'worldTempRegister':worldreg,
            'worldDp4InstructionIndices':[x[0] for x in world],
            'texcoord5OutputRegister':t5reg,'texcoord5MovInstructionIndex':t5i,
            'svPositionOutputRegister':preg,'clipDp4InstructionIndices':[x[0] for x in clip]}

def build(root,producer_verifier,alias_verifier,coordinate_verifier,semantic_verifier,alias_manifest,matrix_manifest):
    prod=load(producer_verifier,'prod');alias=load(alias_verifier,'alias');coord=load(coordinate_verifier,'coord');sem=load(semantic_verifier,'sem')
    araw=alias_manifest.read_bytes();mraw=matrix_manifest.read_bytes()
    if hashlib.sha256(araw).hexdigest()!=ALIAS_SHA:raise ValueError('packed-VS alias manifest SHA mismatch')
    if hashlib.sha256(mraw).hexdigest()!=MATRIX_SHA:raise ValueError('matrix-binding manifest SHA mismatch')
    ad=json.loads(araw);md=json.loads(mraw)
    if ad['summary']['resolvedTargetProducerOccurrenceCount']!=EXPECTED_OCC or ad['summary']['resolvedTargetVertexShaderCount']!=EXPECTED_VS:
        raise ValueError('alias summary mismatch')
    if md['summary']['targetPassOccurrenceCount']!=EXPECTED_OCC or md['summary']['worldMatrixBindingCheckCount']!=EXPECTED_OCC:
        raise ValueError('matrix summary mismatch')
    if md['worldMatrixBinding']['codeIndex']!=0xD5 or md['matrixBindingCensus'][1]['codeIndex']!=0xE5:
        raise ValueError('matrix source identities mismatch')

    events,blobs=alias.collect_events(root,prod)
    table=ad['encoding']['vertexShaderTable']
    counts={table[i]:n for i,n in ad['resolvedVertexShaderCounts']}
    if len(counts)!=EXPECTED_VS or sum(counts.values())!=EXPECTED_OCC:raise ValueError('resolved count table mismatch')
    rows=[]
    for h in sorted(counts):
        blob=blobs.get(h)
        if blob is None:raise ValueError(f'direct VS bytes missing {h}')
        q=prove_vs(prod,coord,sem,blob);q['resolvedPassOccurrenceCount']=counts[h];rows.append(q)
    if len(rows)!=EXPECTED_VS:raise ValueError('chain proof count')
    summary={'resolvedVertexShaderCount':len(rows),'resolvedPassOccurrenceCount':sum(x['resolvedPassOccurrenceCount'] for x in rows),
             'worldPositionDp4CheckCount':len(rows)*4,'worldPositionDp4FailureCount':0,
             'texcoord5ExactWorldValueReuseCheckCount':len(rows)*3,'texcoord5ExactWorldValueReuseFailureCount':0,
             'viewProjectionDp4CheckCount':len(rows)*4,'viewProjectionDp4FailureCount':0,
             'worldMatrixRdefRowCheckCount':len(rows)*4,'viewProjectionRdefRowCheckCount':len(rows)*4,
             'vertexShaderRowsSha256':jhash(rows)}
    return {'format':'t6-retail-reflection-probe-vertex-matrix-chain-v1',
            'producer':'tools/t6_retail_reflection_probe_vertex_matrix_chain_v1.py',
            'sources':{'texcoord5ProducerProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD5_PRODUCER_V1.json',
                       'packedVsAliasProof':alias_manifest.name,'matrixBindingProof':matrix_manifest.name},
            'equations':{'worldPosition':'worldPos4 = dlights.worldMatrix * float4(POSITION.xyz,1)',
                         'texcoord5':'TEXCOORD5.xyz = worldPos4.xyz',
                         'clipPosition':'SV_Position = PerSceneConsts.viewProjectionMatrix * worldPos4',
                         'engineWorldSource':'CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX (0xD5)',
                         'engineViewProjectionSource':'CONST_SRC_CODE_TRANSPOSE_VIEW_PROJECTION_MATRIX (0xE5)'},
            'vertexShaderRows':rows,'summary':summary,
            'proofBoundary':'Direct retained-SM4/RDEF chain proof over all 16 physically retained vertex-shader payloads to which the packed-VS alias proof resolves the 5,676 mapped surface-normal reflection pass occurrences. Each shader forms one homogeneous POSITION-derived four-vector with dlights.worldMatrix rows cb3[0..3], copies the exact x/y/z writer values to TEXCOORD5, and feeds the exact same xyzw value to four DP4s against PerSceneConsts.viewProjectionMatrix rows cb0[36..39] to emit SV_Position. The independent retained MaterialShaderArgument proof binds those destinations to T6 code sources TRANSPOSE_WORLD_MATRIX (0xD5) and TRANSPOSE_VIEW_PROJECTION_MATRIX (0xE5). This proves the vertex transform chain and occurrence inheritance, but not CPU-side camera-relative semantics of WORLD_MATRIX.'}

def main():
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True)
    a.add_argument('--producer-verifier',type=Path,required=True);a.add_argument('--alias-verifier',type=Path,required=True)
    a.add_argument('--coordinate-verifier',type=Path,required=True);a.add_argument('--semantic-verifier',type=Path,required=True)
    a.add_argument('--alias-manifest',type=Path,required=True);a.add_argument('--matrix-manifest',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True);q=a.parse_args()
    d=build(q.root,q.producer_verifier,q.alias_verifier,q.coordinate_verifier,q.semantic_verifier,q.alias_manifest,q.matrix_manifest)
    q.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
