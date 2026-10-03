
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

uint __cdecl R_FindProbeFromVolume(GfxWorldDraw *param_1,vec3_t *param_2)

{
  uint uVar1;
  code *pcVar2;
  bool bVar3;
  uint *in_EAX;
  uint uVar4;
  int iVar5;
  int *piVar6;
  uint uVar7;
  float *pfVar8;
  vec3_t *pvVar9;
  uint uVar10;
  float fVar11;
  uint uStack_c;
  uint uStack_8;
  
  if ((0xfe < *in_EAX) &&
     (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x4cf,0,
                               "(worldDraw->reflectionProbeCount < 0xff)",""), !bVar3)) {
    pcVar2 = (code *)swi(3);
    uVar4 = (*pcVar2)();
    return uVar4;
  }
  uVar4 = *in_EAX;
  uVar7 = 0;
  uStack_8 = 0;
  uStack_c = 1;
  if (uVar4 < 2) {
    return 0;
  }
  piVar6 = (int *)(in_EAX[1] + 0x8c);
  fVar11 = __real_3f800000;
  do {
    uVar1 = piVar6[1];
    if (uVar1 != 0) {
      pvVar9 = (vec3_t *)*piVar6;
      uVar10 = 0;
      if (uVar1 != 0) {
        do {
          uVar7 = 0;
          pfVar8 = pvVar9->v + 2;
          while (fVar11 <= pfVar8[-2] * (float)param_1->reflectionProbeCount +
                           pfVar8[-1] * (float)param_1->field1_0x4 +
                           *pfVar8 * (float)param_1->field2_0x8 + pfVar8[1]) {
            uVar7 = uVar7 + 1;
            pfVar8 = pfVar8 + 4;
            if (5 < uVar7) {
              iVar5 = Dvar_GetInt(r_showReflectionProbeSelection);
              if (iVar5 == 3) {
                iVar5 = 6;
                do {
                  R_AddDebugLine(&frontEndDataOut->debugGlobals,(vec3_t *)param_1,pvVar9,
                                 &colorYellow,0);
                  pvVar9 = (vec3_t *)((int)pvVar9 + 0x10);
                  iVar5 = iVar5 + -1;
                } while (iVar5 != 0);
              }
              uStack_8 = uStack_c;
              uVar7 = uStack_c;
              fVar11 = __real_3f800000;
              goto LAB_00a04a75;
            }
          }
          uVar10 = uVar10 + 1;
          pvVar9 = pvVar9 + 8;
          uVar7 = uStack_8;
        } while (uVar10 < uVar1);
      }
LAB_00a04a75:
      if (uVar7 != 0) {
        return uVar7;
      }
    }
    uStack_c = uStack_c + 1;
    piVar6 = piVar6 + 0x13;
    if (uVar4 <= uStack_c) {
      return uVar7;
    }
  } while( true );
}

