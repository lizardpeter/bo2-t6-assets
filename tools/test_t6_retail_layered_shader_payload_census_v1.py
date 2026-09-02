#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_PS='9268c99b27fc0cc8148ff96cb980db477b3c3918b7870621d1a8ac177aa7a773'
EXPECTED_VS='9aabac50fa9cd0a5647e3653bc2fd9c0857de6086a924aadbf33d574e598d6a5'
EXPECTED_SLOT4='f3065ec05f2992048ceb7e3fae845f13e6e8b57f1eb717e644b26cb45774f799'
EXPECTED={'directPixelShaderPayloadOccurrences':6016,'directVertexShaderPayloadOccurrences':112,'distinctLayeredTechniqueSetNames':165,'formatDirectPixelShaderCoverage':{'1':78,'2':54,'3':46,'4':52,'5':26,'6':9,'7':8},'formatTechniqueSetOccurrenceCounts':{'0':138,'1':78,'2':54,'3':46,'4':52,'5':26,'6':9,'7':8},'layeredTechniqueSetOccurrences':273,'layeredTechniqueSetOccurrencesWithDirectPixelShader':273,'layeredTechniqueSetOccurrencesWithoutDirectPixelShader':0,'slot4DirectPixelShaderOccurrences':273,'slot4TechniqueSetOccurrencesWithDirectPixelShader':273,'slot4UniqueDirectPixelShaderBytes':1585072,'slot4UniqueDirectPixelShaderCount':173,'slot4UniquePixelShaderByFormat':{'1':36,'2':25,'3':30,'4':45,'5':21,'6':8,'7':8},'slotDirectPixelShaderOccurrences':{'2':10,**{str(i):273 for i in range(4,26)}},'uniqueDirectPixelShaderBytes':51218700,'uniqueDirectPixelShaderCount':3808,'uniqueDirectVertexShaderBytes':305192,'uniqueDirectVertexShaderCount':36,'uniquePixelShaderFormatAssociations':{'1':792,'1/2':2,'2':550,'3':660,'4':990,'5':462,'6':176,'7':176}}

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def validate(d):
 assert d['format']=='t6-retail-layered-shader-payload-census-v1' and d['summary']==EXPECTED
 assert d['uniqueDirectPixelShaderSetSha256']==EXPECTED_PS and d['uniqueDirectVertexShaderSetSha256']==EXPECTED_VS and d['slot4UniquePixelShaderSetSha256']==EXPECTED_SLOT4
 assert len(d['mapCoverage'])==5 and sum(x['layeredTechniqueSetOccurrences'] for x in d['mapCoverage'])==273
 assert sum(x['slot4DirectPixelShaderOccurrences'] for x in d['mapCoverage'])==273
 assert len(d['pixelShaderExamples'])==4 and len(d['slot4PixelShaderExamples'])==4

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LAYERED_SHADER_PAYLOAD_CENSUS_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_layered_shader_payload_census_v1.py'));ap.add_argument('--root',type=Path);ap.add_argument('--parser',type=Path,default=Path('tools/t6_retail_special_shader_payload_census_v1.py'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));a=ap.parse_args();doc=json.loads(a.manifest.read_text());validate(doc)
 if a.root:
  m=load(a.verifier,'layeredpayload');got=m.build(a.root,a.parser,a.helper);validate(got);assert got==doc,'retail rerun differs from committed layered shader payload manifest'
 print('PASS: T6 retail layered shader payload census regression')
if __name__=='__main__':main()
