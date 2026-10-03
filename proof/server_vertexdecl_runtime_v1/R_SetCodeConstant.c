
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl
R_SetCodeConstant(GfxCmdBufSourceState *param_1,uint param_2,float param_3,float param_4,
                 float param_5,float param_6)

{
  code *pcVar1;
  bool bVar2;
  vec4_t *pvVar3;
  
  if (0xd2 < param_2) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x69b,0,
                             "(unsigned)(constant) < (unsigned)(CONST_SRC_CODE_COUNT_FLOAT4)",
                             "constant doesn\'t index CONST_SRC_CODE_COUNT_FLOAT4\n\t%i not in [0, %i)"
                            );
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  pvVar3 = (param_1->input).consts + param_2;
  pvVar3->v[0] = param_3;
  pvVar3->v[1] = param_4;
  pvVar3->v[2] = param_5;
  pvVar3->v[3] = param_6;
  if (0xf2 < param_2) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x624,0,
                             "(unsigned)(constant) < (unsigned)((sizeof( source->constVersions ) / (sizeof( source->constVersions[0] ) * (sizeof( source->constVersions ) != 4 || sizeof( source->constVersions[0] ) <= 4))))"
                             ,
                             "constant doesn\'t index ARRAY_COUNT( source->constVersions )\n\t%i not in [0, %i)"
                            );
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  param_1->constVersions[param_2] = param_1->constVersions[param_2] + 1;
  return;
}

