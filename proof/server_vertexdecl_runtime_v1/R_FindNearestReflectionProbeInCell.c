
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

uint __cdecl R_FindNearestReflectionProbeInCell(int param_1,vec3_t *param_2)

{
  byte bVar1;
  byte bVar2;
  GfxReflectionProbe *pGVar3;
  code *pcVar4;
  GfxWorldDraw *pGVar5;
  bool bVar6;
  uint uVar7;
  int iVar8;
  vec3_t *pvVar9;
  float fVar10;
  float fVar11;
  float fVar12;
  float fStack_20;
  uint uStack_1c;
  byte bStack_15;
  vec3_t vStack_14;
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  if (((uint)((rgp.world)->dpvsPlanes).cellCount <= (uint)param_1) &&
     (bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x462,0,
                               "(unsigned)(cellIndex) < (unsigned)(rgp.world->dpvsPlanes.cellCount)"
                               ,
                               "cellIndex doesn\'t index rgp.world->dpvsPlanes.cellCount\n\t%i not in [0, %i)"
                              ), !bVar6)) {
    pcVar4 = (code *)swi(3);
    uVar7 = (*pcVar4)();
    return uVar7;
  }
  pGVar5 = g_worldDraw;
  pvVar9 = &(rgp.world)->cells[param_1].mins;
  if ((g_worldDraw == (GfxWorldDraw *)0x0) &&
     (bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x468,0,"(worldDraw)",""),
     !bVar6)) {
    pcVar4 = (code *)swi(3);
    uVar7 = (*pcVar4)();
    return uVar7;
  }
  if ((0xfe < pGVar5->reflectionProbeCount) &&
     (bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x469,0,
                               "(worldDraw->reflectionProbeCount < 0xff)",""), !bVar6)) {
    pcVar4 = (code *)swi(3);
    uVar7 = (*pcVar4)();
    return uVar7;
  }
  pGVar3 = (pGVar5->field1_0x4).localReflectionProbes;
  iVar8 = *(int *)((int)pvVar9 + 0x2c);
  bVar1 = *(byte *)((int)pvVar9 + 0x28);
  bStack_15 = 0;
  fStack_20 = ___real_7f7fffff;
  uStack_1c = 0;
  if (bVar1 != 0) {
    do {
      bVar2 = *(byte *)(uStack_1c + iVar8);
      if (((bVar2 == 0) || (bVar2 == 0xff)) &&
         (bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x478,0,
                                   "(probeIndex != (0) && probeIndex != (0xff))",""), !bVar6)) {
        pcVar4 = (code *)swi(3);
        uVar7 = (*pcVar4)();
        return uVar7;
      }
      uVar7 = (uint)bVar2;
      if (((pGVar5->field1_0x4).localReflectionProbes[uVar7].probeVolumeCount != 0) &&
         (bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x47b,0,
                                   "(worldDraw->reflectionProbes[probeIndex].probeVolumeCount == 0)"
                                   ,""), !bVar6)) {
        pcVar4 = (code *)swi(3);
        uVar7 = (*pcVar4)();
        return uVar7;
      }
      if ((pGVar5->reflectionProbeCount <= uVar7) &&
         (bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x47c,0,
                                   "(unsigned)(probeIndex) < (unsigned)(worldDraw->reflectionProbeCount)"
                                   ,
                                   "probeIndex doesn\'t index worldDraw->reflectionProbeCount\n\t%i not in [0, %i)"
                                  ), !bVar6)) {
        pcVar4 = (code *)swi(3);
        uVar7 = (*pcVar4)();
        return uVar7;
      }
      fVar11 = (param_2->_s_0).x - pGVar3[uVar7].origin._s_0.x;
      fVar10 = (param_2->_s_0).y - pGVar3[uVar7].origin._s_0.y;
      fVar12 = (param_2->_s_0).z - pGVar3[uVar7].origin._s_0.z;
      fVar10 = fVar10 * fVar10 + fVar11 * fVar11 + fVar12 * fVar12;
      if (fVar10 < fStack_20) {
        fStack_20 = fVar10;
        bStack_15 = bVar2;
      }
      uStack_1c = uStack_1c + 1;
    } while (uStack_1c < bVar1);
    if (bStack_15 == 0xff) {
      return 0xff;
    }
  }
  iVar8 = Dvar_GetInt(r_showReflectionProbeSelection);
  if (iVar8 == 3) {
    vStack_14._s_0.x = ((pvVar9->_s_0).x + pvVar9[1]._s_0.x) * __real_3f000000;
    vStack_14._s_0.y = (*(float *)((int)pvVar9 + 0x10) + (pvVar9->_s_0).y) * __real_3f000000;
    vStack_14._s_0.z = (*(float *)((int)pvVar9 + 0x14) + (pvVar9->_s_0).z) * __real_3f000000;
    R_AddDebugLine(&frontEndDataOut->debugGlobals,param_2,&vStack_14,&colorMagenta,0);
    R_AddDebugBox(&frontEndDataOut->debugGlobals,pvVar9,pvVar9 + 1,&colorMagenta);
  }
  return (uint)bStack_15;
}

