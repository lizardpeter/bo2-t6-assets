#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

EXPECTED_SUMMARY={
 'retainedMapCount':5,
 'uniqueReflectionProbeShaderCount':5868,
 'sharedParameterFetchCount':4236,
 'squaredMaterialColorFetchCount':4216,
 'immediateMaterialColorFetchCount':20,
 'materialColorSquareFailureCount':0,
 'immediateMaterialColorBits':'3d23d70a',
 'sFirstWriterCount':4216,
 'directSampleSCount':1914,
 'shaderRowsSha256':'4c0301cdeec58ce83e83f0e89e8d44d8f5a95e75d195e8c263f6cb45f26a2f42',
 'sFirstWriterRowsSha256':'dba9b35ea1092680fa3d1b84a13fd594286e72e547d6855f08947c4bfd3faad5',
 'directSRowsSha256':'52c3b534c400d09afc773c5efcb6458ccd5f9dccc6c1dd5dd22af3a9b51e4a1e'
}
EXPECTED_WRITERS={'CB':40,'MAD':1750,'MOVC':132,'MUL':380,'SAMPLE':1914}
EXPECTED_DIRECT={
 ('SpecularAndGloss',2,'xyz','SAMPLE'):140,
 ('SpecularAndGloss',3,'xyz','SAMPLE'):40,
 ('SpecularAndGloss',4,'xyz','SAMPLE'):40,
 ('SpecularAndGloss',6,'xyz','SAMPLE'):20,
 ('SpecularAndGloss2',2,'xyz','SAMPLE'):60,
 ('SpecularGlossMap',1,'xyz','SAMPLE'):20,
 ('Specular_Color_Map',3,'xyz','SAMPLE'):20,
 ('specularMapSampler',1,'xyz','SAMPLE'):440,
 ('specularMapSampler',2,'xyz','SAMPLE'):1008,
 ('specularMapSampler',3,'xyz','SAMPLE'):86,
 ('specular_map',1,'xyz','SAMPLE'):20,
 ('specular_map',4,'xyz','SAMPLE'):20,
}

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def validate(d):
 assert d['format']=='t6-retail-reflection-probe-material-color-v1'
 assert d['summary']==EXPECTED_SUMMARY
 assert d['equation']['squaredFamily']=='P.rgb = S.rgb * S.rgb'
 assert d['equation']['immediateFamilyBits']=='3d23d70a'
 assert {x['firstWriter']:x['count'] for x in d['sFirstWriterCounts']}==EXPECTED_WRITERS
 assert {(x['resourceName'],x['resourceRegister'],x['channels'],x['opcode']):x['count'] for x in d['directSampleSSources']}==EXPECTED_DIRECT

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_MATERIAL_COLOR_V1.json'))
 ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_color_v1.py'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'))
 ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'))
 ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'))
 ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'))
 ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'))
 ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
 ap.add_argument('--root',type=Path)
 a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'material').build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.shared_verifier,a.guard)
  validate(got);assert got==d,'retail rerun differs from committed material-color manifest'
 print('PASS: T6 retained reflectionProbeSampler material-color square regression')
if __name__=='__main__':main()
