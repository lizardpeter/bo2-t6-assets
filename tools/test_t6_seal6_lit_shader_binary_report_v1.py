#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import tempfile
from pathlib import Path
import t6_seal6_lit_shader_binary_report_v1 as mod


def stage(kind, rel, raw, asset):
    return {'kind':kind,'asset':asset,'relativeFile':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'shaderModel':'4.0','arguments':[{'sourceClass':'material','materialProperty':'Diffuse_Map'}] if kind=='pixelShader' else []}

def binding(tech, pass_sha, vs, ps):
    return {'technique':tech,'types':['lit'],'parsedPassStageIdentitySha256':pass_sha,'passes':[{'index':0,'stateMap':'passthrough','vertexRouting':[],'stages':[vs,ps]}]}

def owner(label, tech, pass_sha, vs, ps):
    return {'rootLabel':label,'bytes':10,'sha256':'a'*64,'fullParentChildSignatureSha256':'b'*64,'bindings':[binding(tech,pass_sha,vs,ps)]}

def main()->int:
    with tempfile.TemporaryDirectory() as td:
        base=Path(td); roots=[]
        raw_vs=b'VS-A';raw_ps_h=b'PS-H';raw_ps_s=b'PS-S';raw_vs_c=b'VS-C';raw_ps_c=b'PS-C'
        for label in ['faction','patch','common']:
            root=base/label;root.mkdir();roots.append((label,root))
        files={
          'faction': [('shader_bin/vs_a.cso',raw_vs),('shader_bin/ps_h.cso',raw_ps_h)],
          'patch': [('shader_bin/vs_alias.cso',raw_vs),('shader_bin/ps_h.cso',raw_ps_h)],
          'common': [('shader_bin/vs_a.cso',raw_vs),('shader_bin/ps_s.cso',raw_ps_s),('shader_bin/vs_c.cso',raw_vs_c),('shader_bin/ps_c.cso',raw_ps_c)],
        }
        for label,rows in files.items():
            root=dict(roots)[label]
            for rel,raw in rows:
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        hero_f=owner('faction','hero','p1',stage('vertexShader','shader_bin/vs_a.cso',raw_vs,'vs_a'),stage('pixelShader','shader_bin/ps_h.cso',raw_ps_h,'ps_h'))
        hero_p=owner('patch','hero','p2',stage('vertexShader','shader_bin/vs_alias.cso',raw_vs,'vs_alias'),stage('pixelShader','shader_bin/ps_h.cso',raw_ps_h,'ps_h'))
        std=owner('common','skin','p3',stage('vertexShader','shader_bin/vs_a.cso',raw_vs,'vs_a'),stage('pixelShader','shader_bin/ps_s.cso',raw_ps_s,'ps_s'))
        cor=owner('common','cornea','p4',stage('vertexShader','shader_bin/vs_c.cso',raw_vs_c,'vs_c'),stage('pixelShader','shader_bin/ps_c.cso',raw_ps_c,'ps_c'))
        report={'format':mod.OWNER_FORMAT,'techniqueSets':[
          {'techniqueSet':mod.TARGET_TECHSETS[0],'owners':[hero_f,hero_p]},
          {'techniqueSet':mod.TARGET_TECHSETS[1],'owners':[std]},
          {'techniqueSet':mod.TARGET_TECHSETS[2],'owners':[cor]},
        ]}
        real=mod.inspect_dxbc
        def fake(raw,*,name=None):
            is_vs=raw in (raw_vs,raw_vs_c)
            return {'format':'t6-dxbc-inspection-v1','chunkCount':2,'program':{'programType':'vertex' if is_vs else 'pixel','shaderModel':'4.0'},'reflection':{'creator':'fixture','constantBufferCount':0,'boundResourceCount':0,'boundResources':[]},'chunks':[{'tag':'RDEF','payloadBytes':1,'payloadSha256':'1'*64},{'tag':'SHDR','payloadBytes':1,'payloadSha256':'2'*64}]}
        mod.inspect_dxbc=fake
        semantics={'format':'t6-retail-lprobe-lit-semantics-v1','families':[{'id':'fixture-solved','vertexShader':{'dxbcSha256':hashlib.sha256(raw_vs_c).hexdigest()},'pixelShader':{'dxbcSha256':hashlib.sha256(raw_ps_c).hexdigest()}}]}
        try:
            out=mod.build(report,roots,solved_semantics=semantics,archive_dir=base/'archive')
        finally: mod.inspect_dxbc=real
        assert out['summary']['techniqueSetFamilies']==3
        assert out['summary']['physicalLitVariants']==4
        assert out['summary']['uniqueVertexDxbcPrograms']==2
        assert out['summary']['uniquePixelDxbcPrograms']==3
        assert out['summary']['heroSerializedLitPassIdentityInvariant'] is False
        assert out['summary']['heroExecutableVsPsPairInvariant'] is True
        hero=out['families'][0]
        assert hero['serializedLitPassIdentityInvariantAcrossOwners'] is False
        assert hero['executableVsPsPairInvariantAcrossOwners'] is True
        cornea=out['families'][2]
        assert cornea['variants'][0]['existingBlenderSolvedFamilyIds']==['fixture-solved']
        assert len(list((base/'archive').glob('*.cso')))==5
    print('PASS t6_seal6_lit_shader_binary_report_v1')
    return 0
if __name__=='__main__': raise SystemExit(main())
