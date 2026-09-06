#!/usr/bin/env python3
from __future__ import annotations
import t6_code_sampler_source_table_v1 as table

def main()->int:
 assets='''
enum MaterialTextureSource {
 TEXTURE_SRC_CODE_BLACK = 0x0,
 TEXTURE_SRC_CODE_LIGHTMAP_PRIMARY = 0x4,
 TEXTURE_SRC_CODE_REFLECTION_PROBE = 0x1A,
 TEXTURE_SRC_CODE_ALIAS = TEXTURE_SRC_CODE_REFLECTION_PROBE,
 TEXTURE_SRC_CODE_COUNT
};
'''
 constants='''
static inline techset::CommonCodeSamplerSourceInfo commonCodeSamplerSources[]{
 { .value = TEXTURE_SRC_CODE_LIGHTMAP_PRIMARY, .accessor = "lightmapSamplerPrimary", .updateFrequency = techset::CommonCodeSourceUpdateFrequency::CUSTOM, },
 { .value = TEXTURE_SRC_CODE_REFLECTION_PROBE, .accessor = "reflectionProbeSampler", .updateFrequency = techset::CommonCodeSourceUpdateFrequency::CUSTOM, .customSamplerIndex = CUSTOM_SAMPLER_REFLECTION_PROBE, .techFlags = MTL_TECHFLAG_REFLECTION_PROBE, },
};
'''
 doc=table.build_from_text(constants,assets)
 assert doc['format']==table.FORMAT
 assert doc['summary']['codeSamplerSourceCount']==2
 assert doc['summary']['customSamplerSourceCount']==1
 assert doc['summary']['techFlaggedSourceCount']==1
 by={r['accessor']:r for r in doc['rows']}
 assert by['lightmapSamplerPrimary']['enumValue']==4
 probe=by['reflectionProbeSampler']
 assert probe['enumSymbol']=='TEXTURE_SRC_CODE_REFLECTION_PROBE'
 assert probe['enumValue']==0x1A
 assert probe['enumAliases']==['TEXTURE_SRC_CODE_REFLECTION_PROBE','TEXTURE_SRC_CODE_ALIAS']
 assert probe['customSamplerIndex']=='CUSTOM_SAMPLER_REFLECTION_PROBE'
 assert probe['updateFrequency']=='CUSTOM'
 try:table.build_from_text(constants,assets,verify_pinned_blobs=True)
 except table.T6CodeSamplerTableError as exc:assert 'Git blob' in str(exc)
 else:raise AssertionError('synthetic source incorrectly passed pinned OAT blob verification')
 bad=constants.replace('.accessor = "reflectionProbeSampler"','.accessor = "lightmapSamplerPrimary"')
 try:table.build_from_text(bad,assets)
 except table.T6CodeSamplerTableError as exc:assert 'duplicate code-sampler accessor' in str(exc)
 else:raise AssertionError('duplicate sampler accessor accepted')
 print('PASS: pinned T6 code sampler source table v1');return 0
if __name__=='__main__':raise SystemExit(main())
