
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

uint __cdecl R_FindNearestReflectionProbe(GfxWorldDraw *param_1,vec3_t *param_2)

{
  code *pcVar1;
  bool bVar2;
  uint uVar3;
  uint uVar4;
  float *pfVar5;
  int iVar6;
  byte bVar7;
  uint *in_ECX;
  byte bVar8;
  float fVar9;
  float fVar10;
  float fVar11;
  float fVar12;
  
  if (in_ECX == (uint *)0x0) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x4a0,0,"(worldDraw)","");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      uVar3 = (*pcVar1)();
      return uVar3;
    }
  }
  if (0xfe < *in_ECX) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x4a1,0,
                             "(worldDraw->reflectionProbeCount < 0xff)","");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      uVar3 = (*pcVar1)();
      return uVar3;
    }
  }
  uVar3 = in_ECX[1];
  bVar8 = 0;
  bVar7 = 1;
  if (1 < *in_ECX) {
    uVar4 = 1;
    fVar12 = ___real_7f7fffff;
    do {
      pfVar5 = (float *)(uVar4 * 0x4c + uVar3);
      if (pfVar5[0x11] == 0.0) {
        fVar9 = (float)param_1->field1_0x4 - pfVar5[1];
        fVar10 = (float)param_1->reflectionProbeCount - *pfVar5;
        fVar11 = (float)param_1->field2_0x8 - pfVar5[2];
        fVar9 = fVar9 * fVar9 + fVar10 * fVar10 + fVar11 * fVar11;
        if (fVar9 < fVar12) {
          fVar12 = fVar9;
          bVar8 = bVar7;
        }
      }
      bVar7 = bVar7 + 1;
      uVar4 = (uint)bVar7;
    } while (uVar4 < *in_ECX);
    if (bVar8 == 0xff) goto LAB_00a0493a;
  }
  iVar6 = Dvar_GetInt(r_showReflectionProbeSelection);
  if (iVar6 == 3) {
    R_AddDebugLine(&frontEndDataOut->debugGlobals,(vec3_t *)param_1,
                   (vec3_t *)((uint)bVar8 * 0x4c + uVar3),&colorOrange,0);
  }
LAB_00a0493a:
  return (uint)bVar8;
}

