
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl R_SetupDynamicModelLighting(GfxCmdBufInput *param_1)

{
  code *pcVar1;
  float fVar2;
  GfxImage *pGVar3;
  bool bVar4;
  float fVar5;
  
  pGVar3 = modelLightGlob.image;
  if ((param_1 == (GfxCmdBufInput *)0x0) &&
     (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x6f6,0,"(input)",""), !bVar4
     )) {
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  param_1->codeImages[3] = pGVar3;
  fVar5 = modelLightGlob.invImageHeight * ___real_3fc00000;
  if (((_DAT_00d1786c != 2) && (_DAT_00d1786c != 3)) &&
     (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                               "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                               ,"(constant) = %i"), !bVar4)) {
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  fVar2 = ___real_3b400000;
  *(float *)((int)param_1->consts + 0x2b4) = fVar5;
  *(undefined4 *)((int)param_1->consts + 0x2b8) = ___real_3ec00000;
  param_1->consts[0x2b].v[0] = fVar2;
  *(undefined4 *)((int)param_1->consts + 700) = 0;
  return;
}

