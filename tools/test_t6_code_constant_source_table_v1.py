#!/usr/bin/env python3
from __future__ import annotations
import t6_code_constant_source_table_v1 as table

ASSETS=r'''
namespace T6 {
enum MaterialConstantSource {
 CONST_SRC_CODE_LIGHT_POSITION = 0x0,
 CONST_SRC_CODE_FILTER_TAP_0 = 0x10,
 CONST_SRC_CODE_FILTER_TAP_1,
 CONST_SRC_CODE_FILTER_TAP_2,
 CONST_SRC_CODE_ALIAS = CONST_SRC_CODE_FILTER_TAP_0,
 CONST_SRC_CODE_WORLD_MATRIX = 0xD3,
 CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX,
 CONST_SRC_CODE_COUNT = CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX + 1,
};
}
'''
CONSTANTS=r'''
static inline techset::CommonCodeConstSourceInfo commonCodeConstSources[]{
 {
  .value = CONST_SRC_CODE_LIGHT_POSITION,
  .accessor = "lightPosition",
  .arrayCount = 0,
  .updateFrequency = techset::CommonCodeSourceUpdateFrequency::RARELY,
 },
 {
  .value = CONST_SRC_CODE_FILTER_TAP_0,
  .accessor = "filterTap",
  .arrayCount = 3,
  .updateFrequency = techset::CommonCodeSourceUpdateFrequency::CUSTOM,
  .techFlags = MTL_TECHFLAG_FIXTURE,
 },
 {
  .value = CONST_SRC_CODE_WORLD_MATRIX,
  .accessor = "worldMatrix",
  .arrayCount = 0,
  .updateFrequency = techset::CommonCodeSourceUpdateFrequency::PER_PRIM,
  .transposedMatrix = CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX,
 },
};
'''

def main()->int:
 enum=table.parse_material_constant_source_enum(ASSETS)
 assert enum['bySymbol']['CONST_SRC_CODE_LIGHT_POSITION']==0
 assert enum['bySymbol']['CONST_SRC_CODE_FILTER_TAP_0']==0x10
 assert enum['bySymbol']['CONST_SRC_CODE_FILTER_TAP_1']==0x11
 assert enum['bySymbol']['CONST_SRC_CODE_FILTER_TAP_2']==0x12
 assert enum['bySymbol']['CONST_SRC_CODE_ALIAS']==0x10
 assert enum['bySymbol']['CONST_SRC_CODE_WORLD_MATRIX']==0xD3
 assert enum['bySymbol']['CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX']==0xD4
 assert enum['bySymbol']['CONST_SRC_CODE_COUNT']==0xD5
 assert enum['aliasesByValue']['16']==['CONST_SRC_CODE_FILTER_TAP_0','CONST_SRC_CODE_ALIAS']
 rows=table.parse_common_code_const_sources(CONSTANTS,enum)
 by={row['accessor']:row for row in rows}
 assert by['lightPosition']['enumValue']==0 and by['lightPosition']['updateFrequency']=='RARELY'
 assert by['filterTap']['enumValue']==0x10 and by['filterTap']['arrayCount']==3
 assert by['filterTap']['techFlags']=='MTL_TECHFLAG_FIXTURE'
 assert by['filterTap']['enumAliases']==['CONST_SRC_CODE_FILTER_TAP_0','CONST_SRC_CODE_ALIAS']
 assert by['worldMatrix']['enumValue']==0xD3
 assert by['worldMatrix']['transposedMatrixEnumSymbol']=='CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX'
 assert by['worldMatrix']['transposedMatrixEnumValue']==0xD4
 doc=table.build_from_text(CONSTANTS,ASSETS,verify_pinned_blobs=False)
 assert doc['format']==table.FORMAT
 assert doc['summary']['codeConstantSourceCount']==3
 assert doc['summary']['arraySourceCount']==1
 assert doc['summary']['matrixPairSourceCount']==1
 assert doc['summary']['updateFrequencyCounts']=={'CUSTOM':1,'PER_PRIM':1,'RARELY':1}
 assert len(doc['summary']['rowsSha256'])==64
 assert doc['source']['techsetConstants']['gitBlobSha1']==table.git_blob_sha(CONSTANTS.encode())

 dup=CONSTANTS.replace('.accessor = "worldMatrix"','.accessor = "lightPosition"')
 try:table.parse_common_code_const_sources(dup,enum)
 except table.T6CodeConstantTableError as exc:assert 'duplicate code-constant accessor' in str(exc)
 else:raise AssertionError('duplicate accessor was accepted')

 bad=CONSTANTS.replace('CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX','CONST_SRC_CODE_NOT_REAL')
 try:table.parse_common_code_const_sources(bad,enum)
 except table.T6CodeConstantTableError as exc:assert 'unknown enum' in str(exc)
 else:raise AssertionError('unknown transpose enum was accepted')
 print('PASS: pinned T6 code constant source table parser v1');return 0
if __name__=='__main__':raise SystemExit(main())
