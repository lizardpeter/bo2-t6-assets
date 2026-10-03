
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl R_SetFrameFog(GfxCmdBufInput *param_1,vec4_t *param_2)

{
  GfxBackEndData *pGVar1;
  code *pcVar2;
  bool bVar3;
  float unaff_ESI;
  undefined4 unaff_EDI;
  float fVar4;
  float fVar5;
  float fVar6;
  float fVar7;
  double dVar8;
  uint uVar9;
  float fVar10;
  float fStack_2c;
  float fStack_28;
  float fStack_14;
  
  bVar3 = Dvar_GetBool(r_fog);
  if (!bVar3) {
    if (((_DAT_00d1787c != 2) && (_DAT_00d1787c != 3)) &&
       (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x687,0,
                                 "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                                 ,"(constant) = %i"), !bVar3)) {
      pcVar2 = (code *)swi(3);
      (*pcVar2)();
      return;
    }
    param_1->consts[0x2f].v[0] = 0.0;
    *(undefined4 *)((int)param_1->consts + 0x2f4) = 0;
    *(undefined4 *)((int)param_1->consts + 0x2f8) = 0;
    *(undefined4 *)((int)param_1->consts + 0x2fc) = 0;
    if (((_DAT_00d17880 != 2) && (_DAT_00d17880 != 3)) &&
       (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x687,0,
                                 "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                                 ,"(constant) = %i"), !bVar3)) {
      pcVar2 = (code *)swi(3);
      (*pcVar2)();
      return;
    }
    param_1->consts[0x30].v[0] = 0.0;
    *(undefined4 *)((int)param_1->consts + 0x304) = 0;
    *(undefined4 *)((int)param_1->consts + 0x308) = 0;
    *(undefined4 *)((int)param_1->consts + 0x30c) = 0;
    return;
  }
  pGVar1 = param_1->data;
  if (((_DAT_00d17890 != 2) && (_DAT_00d17890 != 3)) &&
     (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                               "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                               ,"(constant) = %i"), !bVar3)) {
    pcVar2 = (code *)swi(3);
    (*pcVar2)();
    return;
  }
  param_1->consts[0x34].v[0] = (pGVar1->fogSettings).sunFogColor.v[0];
  *(float *)((int)param_1->consts + 0x344) = (pGVar1->fogSettings).sunFogColor.v[1];
  *(float *)((int)param_1->consts + 0x348) = (pGVar1->fogSettings).sunFogColor.v[2];
  *(float *)((int)param_1->consts + 0x34c) = (pGVar1->fogSettings).sunFogColor.v[3];
  fVar10 = (pGVar1->fogSettings).sunFogDir._s_0.x;
  fVar4 = (pGVar1->fogSettings).sunFogDir._s_0.y;
  fVar5 = (pGVar1->fogSettings).sunFogDir._s_0.z;
  if (((_DAT_00d1788c != 2) && (_DAT_00d1788c != 3)) &&
     (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                               "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                               ,"(constant) = %i"), !bVar3)) {
    pcVar2 = (code *)swi(3);
    (*pcVar2)();
    return;
  }
  param_1->consts[0x33].v[0] = fVar10;
  *(float *)((int)param_1->consts + 0x334) = fVar4;
  *(float *)((int)param_1->consts + 0x338) = fVar5;
  *(undefined4 *)((int)param_1->consts + 0x33c) = 0;
  fVar10 = ___real_4b189680;
  fVar4 = (pGVar1->fogSettings).sunFogStartAng * ___real_3c8efa35;
  __libm_sse2_cosf(unaff_ESI);
  fVar5 = (pGVar1->fogSettings).sunFogEndAng * ___real_3c8efa35;
  __libm_sse2_cosf(unaff_ESI);
  if (fVar4 - fVar5 != 0.0) {
    fVar10 = __real_3f800000 / (fVar4 - fVar5);
  }
  fVar4 = (float)((uint)(fVar5 * fVar10) ^ ___mask__NegFloat_);
  if (((_DAT_00d17888 != 2) && (_DAT_00d17888 != 3)) &&
     (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                               "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                               ,"(constant) = %i"), !bVar3)) {
    pcVar2 = (code *)swi(3);
    (*pcVar2)();
    return;
  }
  param_1->consts[0x32].v[0] = fVar4;
  *(float *)((int)param_1->consts + 0x324) = fVar10;
  *(undefined4 *)((int)param_1->consts + 0x328) = 0;
  *(undefined4 *)((int)param_1->consts + 0x32c) = 0;
  if (((_DAT_00d17884 != 2) && (_DAT_00d17884 != 3)) &&
     (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                               "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                               ,"(constant) = %i"), !bVar3)) {
    pcVar2 = (code *)swi(3);
    (*pcVar2)();
    return;
  }
  param_1->consts[0x31].v[0] = (pGVar1->fogSettings).color.v[0];
  *(float *)((int)param_1->consts + 0x314) = (pGVar1->fogSettings).color.v[1];
  *(float *)((int)param_1->consts + 0x318) = (pGVar1->fogSettings).color.v[2];
  *(float *)((int)param_1->consts + 0x31c) = (pGVar1->fogSettings).color.v[3];
  fVar10 = (pGVar1->fogSettings).density;
  fVar4 = param_2->v[2];
  fVar5 = (pGVar1->fogSettings).baseHeight;
  fStack_2c = (pGVar1->fogSettings).maxDensity;
  if (fVar10 == 0.0) {
    if (((_DAT_00d1787c != 2) && (_DAT_00d1787c != 3)) &&
       (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x687,0,
                                 "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                                 ,"(constant) = %i"), !bVar3)) {
      pcVar2 = (code *)swi(3);
      (*pcVar2)();
      return;
    }
    param_1->consts[0x2f].v[0] = 0.0;
    *(undefined4 *)((int)param_1->consts + 0x2f4) = 0;
    *(undefined4 *)((int)param_1->consts + 0x2f8) = 0;
    *(undefined4 *)((int)param_1->consts + 0x2fc) = 0;
    if (((_DAT_00d17880 != 2) && (_DAT_00d17880 != 3)) &&
       (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x687,0,
                                 "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                                 ,"(constant) = %i"), !bVar3)) {
      pcVar2 = (code *)swi(3);
      (*pcVar2)();
      return;
    }
    param_1->consts[0x30].v[0] = 0.0;
    *(undefined4 *)((int)param_1->consts + 0x304) = 0;
    *(undefined4 *)((int)param_1->consts + 0x308) = 0;
    *(undefined4 *)((int)param_1->consts + 0x30c) = 0;
    return;
  }
  if (fVar10 * ___real_42c80000 < fStack_2c) {
    fStack_2c = fVar10 * ___real_42c80000;
  }
  if (fStack_2c < fVar10) {
    fStack_2c = fVar10;
  }
  dVar8 = ___real_4000000000000000;
  __libm_sse2_log((double)CONCAT44(unaff_EDI,unaff_ESI));
  fVar6 = (float)dVar8;
  fVar7 = fVar10 / fStack_2c;
  __libm_sse2_logf(unaff_ESI);
  fVar7 = fVar7 - (pGVar1->fogSettings).heightDensity * (fVar4 - fVar5) * fVar6;
  if (0.0 <= fVar7) {
    fStack_28 = fVar7 + __real_3f800000;
  }
  else {
    fStack_28 = fVar7;
    __libm_sse2_expf(unaff_ESI);
  }
  fStack_14 = (float)((uint)fStack_2c ^ ___mask__NegFloat_);
  fVar4 = (pGVar1->fogSettings).heightDensity;
  fVar5 = (pGVar1->fogSettings).fogStart;
  uVar9 = (uint)(fVar4 * fVar6) ^ ___mask__NegFloat_;
  if (___real_00000000 < fVar4) {
    fStack_14 = fVar6 * fStack_14;
  }
  if (((_DAT_00d1787c != 2) && (_DAT_00d1787c != 3)) &&
     (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                               "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                               ,"(constant) = %i"), !bVar3)) {
    pcVar2 = (code *)swi(3);
    (*pcVar2)();
    return;
  }
  param_1->consts[0x2f].v[0] = fVar7;
  *(float *)((int)param_1->consts + 0x2f4) = fStack_14;
  *(float *)((int)param_1->consts + 0x2f8) = fVar5 * fVar10;
  *(uint *)((int)param_1->consts + 0x2fc) = uVar9;
  if (((_DAT_00d17880 != 2) && (_DAT_00d17880 != 3)) &&
     (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                               "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                               ,"(constant) = %i"), !bVar3)) {
    pcVar2 = (code *)swi(3);
    (*pcVar2)();
    return;
  }
  param_1->consts[0x30].v[0] = fStack_28;
  *(undefined4 *)((int)param_1->consts + 0x304) = 0;
  *(undefined4 *)((int)param_1->consts + 0x308) = 0;
  *(undefined4 *)((int)param_1->consts + 0x30c) = 0;
  return;
}

