
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

uint __cdecl
R_AllocModelLighting
          (vec3_t *param_1,float param_2,bool param_3,ushort *param_4,GfxLightingInfo *param_5)

{
  vec3_t *pvVar1;
  GfxLightingInfo GVar2;
  code *pcVar3;
  bool bVar4;
  uint uVar5;
  uint uVar6;
  uint uVar7;
  ushort uVar8;
  ushort unaff_DI;
  float fVar9;
  float fVar10;
  float fVar11;
  undefined3 in_stack_0000000d;
  GfxLightingSHAndVis *pGVar12;
  vec3_t vStack_20;
  vec3_t vStack_14;
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  bVar4 = Dvar_GetBool(r_showLightingOrigins);
  if (bVar4) {
    vStack_20._s_0.x = (param_1->_s_0).x - __real_3f800000;
    vStack_20._s_0.y = (param_1->_s_0).y - __real_3f800000;
    vStack_20._s_0.z = (param_1->_s_0).z - __real_3f800000;
    vStack_14._s_0.x = (param_1->_s_0).x + __real_3f800000;
    vStack_14._s_0.y = (param_1->_s_0).y + __real_3f800000;
    vStack_14._s_0.z = (param_1->_s_0).z + __real_3f800000;
    R_AddDebugBox(&frontEndDataOut->debugGlobals,&vStack_20,&vStack_14,&colorGreen);
  }
  if (param_4 == (ushort *)0x0) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x1cd,0,
                             "(cachedLightingHandle)","");
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      uVar5 = (*pcVar3)();
      return uVar5;
    }
  }
  if (param_5 == (GfxLightingInfo *)0x0) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x1ce,0,
                             "(lightingInfoOut)","");
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      uVar5 = (*pcVar3)();
      return uVar5;
    }
  }
  uVar8 = *param_4;
  if (uVar8 != 0) {
    bVar4 = Dvar_GetBool(r_cacheModelLighting);
    if (bVar4) {
      uVar5 = R_ModelLightingIndexFromHandle(unaff_DI);
      uVar5 = uVar5 - modelLightGlob.baseIndex;
      pvVar1 = modelLightGlob.lightingOrigins + uVar5;
      if (0.0 < param_2) {
        fVar10 = (pvVar1->_s_0).y - (param_1->_s_0).y;
        fVar9 = (pvVar1->_s_0).x - (param_1->_s_0).x;
        fVar11 = (pvVar1->_s_0).z - (param_1->_s_0).z;
        if (param_2 <= fVar10 * fVar10 + fVar9 * fVar9 + fVar11 * fVar11) goto LAB_00a7c398;
      }
      else if ((((param_1->_s_0).x != (pvVar1->_s_0).x) || ((param_1->_s_0).y != (pvVar1->_s_0).y))
              || ((param_1->_s_0).z != (pvVar1->_s_0).z)) goto LAB_00a7c398;
      GVar2 = modelLightGlob.lightingInfo[uVar5];
      if (GVar2.primaryLightIndex != 0xff) {
        LOCK();
        modelLightGlob.currPixelFreeBits[uVar5 >> 5] =
             modelLightGlob.currPixelFreeBits[uVar5 >> 5] & ~(0x80000000U >> ((byte)uVar5 & 0x1f));
        UNLOCK();
        *param_5 = GVar2;
        return (uint)uVar8;
      }
    }
  }
LAB_00a7c398:
  uVar5 = R_AllocModelLightingPixel(&modelLightGlob,&modelLightGlob);
  if (modelLightGlob.xmodelEntryLimit <= uVar5) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x200,0,
                             "(unsigned)(usedIndex) < (unsigned)(lightGlob->xmodelEntryLimit)",
                             "usedIndex doesn\'t index lightGlob->xmodelEntryLimit\n\t%i not in [0, %i)"
                            );
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      uVar5 = (*pcVar3)();
      return uVar5;
    }
  }
  if (modelLightGlob.allocModelFail != 0) {
    param_5->primaryLightIndex = 0xff;
    param_5->reflectionProbeIndex = '\0';
    param_5->lightingHandle = 0;
    return 0;
  }
  uVar6 = modelLightGlob.baseIndex + uVar5 + 1;
  pvVar1 = modelLightGlob.lightingOrigins + uVar5;
  (pvVar1->_s_0).x = (param_1->_s_0).x;
  (pvVar1->_s_0).y = (param_1->_s_0).y;
  (pvVar1->_s_0).z = (param_1->_s_0).z;
  uVar8 = (ushort)uVar6;
  *param_4 = uVar8;
  param_5->primaryLightIndex = 0xff;
  uVar7 = R_CalcReflectionProbeIndex(param_1);
  param_5->reflectionProbeIndex = (uchar)uVar7;
  param_5->lightingHandle = uVar8;
  modelLightGlob.lightingInfo[uVar5] = *param_5;
  pGVar12 = modelLightGlob.lightingSHAndVis + uVar5;
  memset((uchar *)pGVar12,'\0',0x34);
  R_CalcModelLighting((uint)param_1,(vec3_t *)&DAT_00000001,_param_3,SUB41(param_5,0),
                      &modelLightGlob.lightingInfo[uVar5].primaryLightIndex,(uchar *)pGVar12);
  if ((rgp.world)->primaryLightCount <= (uint)modelLightGlob.lightingInfo[uVar5].primaryLightIndex)
  {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x22e,0,
                             "(unsigned)(lightGlob->lightingInfo[usedIndex].primaryLightIndex) < (unsigned)(rgp.world->primaryLightCount)"
                             ,
                             "lightGlob->lightingInfo[usedIndex].primaryLightIndex doesn\'t index rgp.world->primaryLightCount\n\t%i not in [0, %i)"
                            );
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      uVar5 = (*pcVar3)();
      return uVar5;
    }
  }
  return uVar6 & 0xffff;
}

