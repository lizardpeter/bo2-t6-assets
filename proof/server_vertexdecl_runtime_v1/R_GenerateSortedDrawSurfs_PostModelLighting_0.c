
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl R_SetSkyConstants(GfxCmdBufInput *param_1,GfxViewInfo *param_2)

{
  code *pcVar1;
  bool bVar2;
  int iVar3;
  int iVar4;
  int unaff_ESI;
  float fVar5;
  float fVar6;
  
  fVar5 = Dvar_GetFloat(r_skyTransition);
  iVar3 = Dvar_GetInt(r_shaderDebugA);
  iVar4 = Dvar_GetInt(r_shaderDebugB);
  fVar6 = Dvar_GetFloat(r_shaderDebugC);
  if ((_DAT_00d178ac != 2) && (_DAT_00d178ac != 3)) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x687,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  *(float *)(unaff_ESI + 0x3b0) = fVar5;
  *(float *)(unaff_ESI + 0x3b4) = (float)iVar3;
  *(float *)(unaff_ESI + 0x3b8) = (float)iVar4;
  *(float *)(unaff_ESI + 0x3bc) = fVar6;
  return;
}

