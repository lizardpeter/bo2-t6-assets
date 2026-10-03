
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl R_SetHeroLighting(GfxCmdBufInput *param_1,GfxViewInfo *param_2,refdef_t *param_3)

{
  undefined4 uVar1;
  undefined4 uVar2;
  code *pcVar3;
  undefined4 uVar4;
  undefined4 uVar5;
  undefined4 uVar6;
  undefined4 uVar7;
  bool bVar8;
  int unaff_ESI;
  int unaff_EDI;
  float fVar9;
  vec4_t avStack_170 [4];
  vec4_t avStack_130 [4];
  vec4_t vStack_f0;
  undefined4 uStack_e0;
  undefined4 uStack_dc;
  undefined4 uStack_d8;
  undefined4 uStack_d0;
  undefined4 uStack_cc;
  undefined4 uStack_c8;
  vec4_t vStack_b0;
  undefined4 uStack_a0;
  float fStack_9c;
  undefined4 uStack_98;
  undefined4 uStack_94;
  undefined4 uStack_90;
  undefined4 uStack_8c;
  float fStack_88;
  undefined4 uStack_84;
  undefined4 uStack_80;
  undefined4 uStack_7c;
  undefined4 uStack_78;
  undefined4 uStack_74;
  vec4_t vStack_70;
  float fStack_60;
  float fStack_5c;
  float fStack_58;
  undefined4 uStack_54;
  float fStack_50;
  float fStack_4c;
  float fStack_48;
  undefined4 uStack_44;
  undefined4 uStack_40;
  undefined4 uStack_3c;
  undefined4 uStack_38;
  undefined4 uStack_34;
  vec3_t vStack_24;
  uint uStack_14;
  
  uStack_14 = __security_cookie ^ (uint)&stack0xfffffff0;
  fStack_48 = Dvar_GetFloat(r_heroLightSaturation);
  uVar7 = _UNK_00d0647c;
  uVar6 = _UNK_00d06478;
  uVar5 = _UNK_00d06474;
  uVar4 = _DAT_00d06470;
  vStack_70.v[1] = (__real_3f800000 - fStack_48) * ___real_3e800000;
  fStack_60 = (__real_3f800000 - fStack_48) * __real_3f000000;
  vStack_70.v[0] = fStack_48 + vStack_70.v[1];
  fStack_5c = fStack_48 + fStack_60;
  fStack_48 = fStack_48 + vStack_70.v[1];
  vStack_70.v[3] = 0.0;
  uStack_54 = 0;
  uStack_44 = 0;
  uStack_40 = _DAT_00d06470;
  uStack_3c = _UNK_00d06474;
  uStack_38 = _UNK_00d06478;
  uStack_34 = _UNK_00d0647c;
  vStack_70.v[2] = vStack_70.v[1];
  fStack_58 = fStack_60;
  fStack_50 = vStack_70.v[1];
  fStack_4c = vStack_70.v[1];
  fVar9 = Dvar_GetFloat(r_heroLightColorTemp);
  colorTempMatrix(avStack_170,fVar9);
  MatrixMultiply44(avStack_170,&vStack_70,avStack_130);
  Dvar_GetVec3(r_heroLightScale,&vStack_24);
  uVar1 = *(undefined4 *)(unaff_EDI + 0x774);
  uVar2 = *(undefined4 *)(unaff_EDI + 0x778);
  if ((_DAT_00d17a28 != 2) && (_DAT_00d17a28 != 3)) {
    bVar8 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x687,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar8) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  *(undefined4 *)(unaff_ESI + 0x9a0) = uVar1;
  *(undefined4 *)(unaff_ESI + 0x9a4) = uVar2;
  fVar9 = __real_3f800000;
  *(float *)(unaff_ESI + 0x9a8) = __real_3f800000;
  *(float *)(unaff_ESI + 0x9ac) = fVar9;
  vStack_b0.v[0] = vStack_24._s_0.x;
  vStack_b0.v[1] = 0.0;
  vStack_b0.v[2] = 0.0;
  vStack_b0.v[3] = 0.0;
  uStack_a0 = 0;
  fStack_9c = vStack_24._s_0.y;
  uStack_98 = 0;
  uStack_94 = 0;
  uStack_90 = 0;
  uStack_8c = 0;
  uStack_84 = 0;
  fStack_88 = vStack_24._s_0.z;
  uStack_80 = uVar4;
  uStack_7c = uVar5;
  uStack_78 = uVar6;
  uStack_74 = uVar7;
  MatrixMultiply44(avStack_130,&vStack_b0,&vStack_f0);
  if ((_DAT_00d17a1c != 2) && (_DAT_00d17a1c != 3)) {
    bVar8 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x687,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar8) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  *(float *)(unaff_ESI + 0x970) = vStack_f0.v[0];
  *(undefined4 *)(unaff_ESI + 0x974) = uStack_e0;
  *(undefined4 *)(unaff_ESI + 0x978) = uStack_d0;
  *(undefined4 *)(unaff_ESI + 0x97c) = 0;
  if ((_DAT_00d17a20 != 2) && (_DAT_00d17a20 != 3)) {
    bVar8 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x687,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar8) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  *(float *)(unaff_ESI + 0x980) = vStack_f0.v[1];
  *(undefined4 *)(unaff_ESI + 0x984) = uStack_dc;
  *(undefined4 *)(unaff_ESI + 0x988) = uStack_cc;
  *(undefined4 *)(unaff_ESI + 0x98c) = 0;
  if ((_DAT_00d17a24 != 2) && (_DAT_00d17a24 != 3)) {
    bVar8 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x687,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar8) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  *(float *)(unaff_ESI + 0x990) = vStack_f0.v[2];
  *(undefined4 *)(unaff_ESI + 0x994) = uStack_d8;
  *(undefined4 *)(unaff_ESI + 0x998) = uStack_c8;
  *(undefined4 *)(unaff_ESI + 0x99c) = 0;
  return;
}

