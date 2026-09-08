#!/usr/bin/env python3
from __future__ import annotations
import json
import tempfile
from pathlib import Path
import t6_seal6_native_shader_variant_probe_v1 as mod

MAT='mc/test_mat'

def write(root:Path, tag:str)->bytes:
    p=root/'materials'/f'{MAT}.json';p.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps({'_game':'t6','_type':'material','techniqueSet':'mc/test_ts','tag':tag,'textures':[]},sort_keys=True)+'\n').encode()
    p.write_bytes(raw);return raw

def main()->int:
    with tempfile.TemporaryDirectory() as td:
        base=Path(td);a=base/'a';b=base/'b';s=base/'shader'
        a.mkdir();b.mkdir();s.mkdir();ra=write(a,'a');rb=write(b,'b')
        real=mod.v4.build
        def fake(root,shader_roots):
            staged=root/'materials'/f'{MAT}.json'; raw=staged.read_bytes()
            owner=str(s.resolve())
            return {'summary':{'unresolvedMaterialCount':0,'divergentParentOwnedDependencyCount':0},'materials':[{'material':MAT,'materialJsonSha256':mod._sha(raw),'techniqueSet':'mc/test_ts','techniqueSetOwners':[owner],'declaredTechniqueTypes':['lit'],'hasLitBinding':True,'programs':[{'techniqueType':'lit','technique':'pimp_test','groupKey':'g','passStageIdentitySha256':'p','passCount':1,'techniqueOwner':owner,'parentTechniqueSetOwners':[owner]}]}]}
        mod.v4.build=fake
        try:
            r=mod.build([('shader',s)],[('a',a,MAT),('b',b,MAT)])
        finally:
            mod.v4.build=real
        assert r['summary']['variantCount']==2
        assert r['summary']['materialsWithDivergentPhysicalShaderSignatures']==0
        assert r['comparisons'][0]['shaderSignatureInvariantAcrossPhysicalVariants']
        assert r['variants'][0]['physicalMaterialSha256']!=r['variants'][1]['physicalMaterialSha256']
        assert r['variants'][0]['shaderSignatureSha256']==r['variants'][1]['shaderSignatureSha256']
    print('PASS t6_seal6_native_shader_variant_probe_v1')
    return 0
if __name__=='__main__': raise SystemExit(main())
