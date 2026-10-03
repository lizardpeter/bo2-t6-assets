
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl R_SetSkyColorMatrix(GfxCmdBufInput *param_1,GfxViewInfo *param_2)

{
  code *pcVar1;
  bool bVar2;
  int unaff_ESI;
  float fVar3;
  vec4_t avStack_a0 [4];
  vec4_t vStack_60;
  undefined4 uStack_50;
  undefined4 uStack_4c;
  undefined4 uStack_48;
  undefined4 uStack_44;
  undefined4 uStack_40;
  undefined4 uStack_3c;
  undefined4 uStack_38;
  undefined4 uStack_34;
  uint uStack_14;
  
  uStack_14 = __security_cookie ^ (uint)&stack0xfffffff0;
  fVar3 = Dvar_GetFloat(r_skyColorTemp);
  colorTempMatrix(avStack_a0,fVar3);
  MatrixTranspose44(avStack_a0,&vStack_60);
  if ((_DAT_00d17848 != 2) && (_DAT_00d17848 != 3)) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  *(float *)(unaff_ESI + 0x220) = vStack_60.v[0];
  *(float *)(unaff_ESI + 0x224) = vStack_60.v[1];
  *(float *)(unaff_ESI + 0x228) = vStack_60.v[2];
  *(float *)(unaff_ESI + 0x22c) = vStack_60.v[3];
  if ((_DAT_00d1784c != 2) && (_DAT_00d1784c != 3)) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  *(undefined4 *)(unaff_ESI + 0x230) = uStack_50;
  *(undefined4 *)(unaff_ESI + 0x234) = uStack_4c;
  *(undefined4 *)(unaff_ESI + 0x238) = uStack_48;
  *(undefined4 *)(unaff_ESI + 0x23c) = uStack_44;
  if ((_DAT_00d17850 != 2) && (_DAT_00d17850 != 3)) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  *(undefined4 *)(unaff_ESI + 0x240) = uStack_40;
  *(undefined4 *)(unaff_ESI + 0x244) = uStack_3c;
  *(undefined4 *)(unaff_ESI + 0x248) = uStack_38;
  *(undefined4 *)(unaff_ESI + 0x24c) = uStack_34;
  return;
}

