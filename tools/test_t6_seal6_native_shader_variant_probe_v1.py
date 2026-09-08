#!/usr/bin/env python3
from __future__ import annotations
import json
import tempfile
from pathlib import Path
import t6_seal6_native_shader_variant_probe_v1 as mod

MAT='mc/test_mat'
TS='mc/test_ts'

def write(root:Path, tag:str)->bytes:
    p=root/'materials'/f'{MAT}.json';p.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps({'_game':'t6','_type':'material','techniqueSet':TS,'tag':tag,'textures':[]},sort_keys=True)+'\n').encode()
    p.write_bytes(raw);return raw

def parent(root:Path):
    p=root/'techsets'/f'{TS}.techset';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture\n')

def main()->int:
    with tempfile.TemporaryDirectory() as td:
        base=Path(td);a=base/'a';b=base/'b';p=base/'parent'
        a.mkdir();b.mkdir();p.mkdir();write(a,'a');write(b,'b');parent(p)
        real=mod.v4.build
        def fake(root,shader_roots):
            assert len(shader_roots)==1
            staged=root/'materials'/f'{MAT}.json'; raw=staged.read_bytes()
            owner=str(Path(shader_roots[0]).resolve())
            return {'summary':{'unresolvedMaterialCount':0,'divergentParentOwnedDependencyCount':0},'materials':[{'material':MAT,'materialJsonSha256':mod._sha(raw),'techniqueSet':TS,'techniqueSetOwners':[owner],'declaredTechniqueTypes':['lit'],'hasLitBinding':True,'programs':[{'techniqueType':'lit','technique':'pimp_test','groupKey':'g','passStageIdentitySha256':'p','passCount':1,'techniqueOwner':owner,'parentTechniqueSetOwners':[owner]}]}]}
        mod.v4.build=fake
        try:
            r=mod.build([('a',a),('b',b),('parent',p)],[('va',a,p,MAT),('vb',b,p,MAT)])
        finally:
            mod.v4.build=real
        assert r['summary']['variantCount']==2
        assert r['summary']['materialsWithDivergentPhysicalShaderSignatures']==0
        assert r['comparisons'][0]['shaderSignatureInvariantAcrossPhysicalVariants']
        assert r['variants'][0]['physicalMaterialRootLabel']=='a'
        assert r['variants'][1]['physicalMaterialRootLabel']=='b'
        assert r['variants'][0]['physicalParentRootLabel']=='parent'
        assert r['variants'][1]['physicalParentRootLabel']=='parent'
        assert r['variants'][0]['physicalMaterialSha256']!=r['variants'][1]['physicalMaterialSha256']
        assert r['variants'][0]['shaderSignatureSha256']==r['variants'][1]['shaderSignatureSha256']
    print('PASS t6_seal6_native_shader_variant_probe_v1')
    return 0
if __name__=='__main__': raise SystemExit(main())
