
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl
R_AddDObjToScene(DObj *param_1,cpose_t *param_2,uint param_3,uint param_4,vec3_t *param_5,
                float *param_6,float *param_7,int param_8,int param_9,ShaderConstantSet *param_10,
                float param_11,float param_12,bool param_13)

{
  vec3_t *pvVar1;
  GfxEntity *pGVar2;
  code *pcVar3;
  dvar_t *pdVar4;
  bool bVar5;
  int iVar6;
  XModel *pXVar7;
  uint uVar8;
  XAnimTree_s *pXVar9;
  sval_u sVar10;
  long *plVar11;
  int iVar12;
  float fVar13;
  float fVar14;
  ushort uStack_58;
  uint uStack_54;
  uchar uStack_48;
  vec3_t vStack_44;
  vec3_t vStack_38;
  vec3_t vStack_2c;
  vec3_t vStack_20;
  vec3_t vStack_14;
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  PIXBeginNamedEvent(-1,"R_AddDObjToScene");
  bVar5 = Sys_IsMainThread();
  if ((!bVar5) &&
     (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_scene.cpp",0x22d,0,
                               "(Sys_IsMainThread())",""), !bVar5)) {
    pcVar3 = (code *)swi(3);
    (*pcVar3)();
    return;
  }
  if ((param_1 == (DObj *)0x0) &&
     (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_scene.cpp",0x22e,0,"(obj)",""), !bVar5
     )) {
    pcVar3 = (code *)swi(3);
    (*pcVar3)();
    return;
  }
  if ((param_2 == (cpose_t *)0x0) &&
     (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_scene.cpp",0x22f,0,"(pose)",""),
     !bVar5)) {
    pcVar3 = (code *)swi(3);
    (*pcVar3)();
    return;
  }
  if ((gfxCfg.entCount <= param_3) &&
     (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_scene.cpp",0x230,0,
                               "(unsigned)(entnum) < (unsigned)(gfxCfg.entCount)",
                               "entnum doesn\'t index gfxCfg.entCount\n\t%i not in [0, %i)"), !bVar5
     )) {
    pcVar3 = (code *)swi(3);
    (*pcVar3)();
    return;
  }
  if (scene.dpvs.sceneDObjIndex[param_3] == 0xffff) {
    bVar5 = Dvar_GetBool(r_showBounds);
    if (bVar5) {
      CG_GetPoseOrigin(param_2,&vStack_14);
      fVar14 = param_1->radius * param_12;
      fVar13 = (float)((uint)fVar14 ^ ___mask__NegFloat_);
      vStack_2c._s_0.x = vStack_14._s_0.x + fVar13;
      vStack_2c._s_0.y = vStack_14._s_0.y + fVar13;
      vStack_2c._s_0.z = vStack_14._s_0.z + fVar13;
      vStack_20._s_0.x = vStack_14._s_0.x + fVar14;
      vStack_20._s_0.y = vStack_14._s_0.y + fVar14;
      vStack_20._s_0.z = vStack_14._s_0.z + fVar14;
      CG_GetPoseAbsMinMax(param_2,&vStack_38,&vStack_44);
      R_AddDebugBox(&frontEndDataOut->debugGlobals,&vStack_2c,&vStack_20,&colorGreen);
      R_AddDebugBox(&frontEndDataOut->debugGlobals,&vStack_38,&vStack_44,&colorPink);
    }
    iVar6 = DObjGetNumModels(param_1);
    iVar12 = 0;
    if (0 < iVar6) {
      do {
        pXVar7 = DObjGetModel(param_1,iVar12);
        if ((pXVar7->flags & 0x100000U) != 0) {
          param_4 = param_4 | 0x400000;
          break;
        }
        iVar12 = iVar12 + 1;
      } while (iVar12 < iVar6);
    }
    uStack_54 = 0;
    if (((((param_4 & 0xffbfffff) != 0) || (*param_6 != 0.0)) || (*param_7 != 0.0)) ||
       (-1 < param_9)) {
      bVar5 = Dvar_GetBool(r_swrk_override_enable);
      if (bVar5) {
        fVar13 = Dvar_GetFloat(r_swrk_override_characterCharredAmount);
      }
      else {
        fVar13 = *param_7;
      }
      fVar14 = *param_6;
      plVar11 = &frontEndDataOut->gfxEntCount;
      LOCK();
      uStack_54 = *plVar11;
      *plVar11 = *plVar11 + 1;
      UNLOCK();
      if (uStack_54 < 0x100) {
        pGVar2 = frontEndDataOut->gfxEnts + uStack_54;
        pGVar2->renderFxFlags = param_4;
        pGVar2->materialTime = fVar14;
        pGVar2->destructibleBurnAmount = fVar13;
        pGVar2->textureOverrideIndex = param_9;
      }
      else {
        frontEndDataOut->gfxEntCount = 0x100;
        R_WarnOncePerFrame(R_WARN_KNOWN_SPECIAL_MODELS);
        uStack_54 = 0;
      }
    }
    uStack_48 = '\0';
    bVar5 = Dvar_GetBool(r_shader_constant_set_enable);
    if (bVar5) {
      if ((param_10 == (ShaderConstantSet *)0x0) ||
         (bVar5 = R_ShaderConstantSetIsUsed(param_10), !bVar5)) {
        uStack_48 = '\0';
      }
      else {
        uVar8 = R_ShaderConstantSet_CopyToFrontEndDataOut(param_10);
        uStack_48 = (uchar)uVar8;
      }
    }
    uStack_58 = (ushort)param_3;
    if ((((param_4 & 0x20004) == 0) && (iVar6 == 1)) &&
       ((pXVar9 = DObjGetTree(param_1), pXVar9 == (XAnimTree_s *)0x0 ||
        (pXVar7 = DObjGetModel(param_1,0), (pXVar7->flags & 0x200000U) != 0)))) {
      uVar8 = R_AllocSceneModel();
      if (uVar8 < 0x400) {
        scene.dpvs.sceneXModelIndex[param_3] = (ushort)uVar8;
        pXVar7 = DObjGetModel(param_1,0);
        scene.sceneModel[uVar8].info.packed = 0xff00;
        scene.sceneModel[uVar8].model = pXVar7;
        scene.sceneModel[uVar8].obj = param_1;
        scene.sceneModel[uVar8].pose = param_2;
        scene.sceneModel[uVar8].entnum = uStack_58;
        sVar10 = node_pos((uint)param_2);
        scene.sceneModel[uVar8].cachedLightingHandle = (ushort *)sVar10;
        scene.sceneModel[uVar8].lightingOriginToleranceSq = param_11;
        scene.sceneModel[uVar8].useHeroLighting = (byte)(param_4 >> 0x16) & 1;
        CG_GetPoseOrigin(param_2,&scene.sceneModel[uVar8].placement.base.origin);
        CG_GetPoseQuat(param_2,(vec4_t *)&scene.sceneModel[uVar8].placement);
        fVar13 = __real_3f800000 / param_12;
        scene.sceneModel[uVar8].placement.scale = param_12;
        scene.sceneModel[uVar8].invScaleSq = fVar13 * fVar13;
        fVar13 = XModelGetRadius(pXVar7);
        scene.sceneModel[uVar8].radius = fVar13 * param_12;
        scene.sceneModel[uVar8].lightingOrigin._s_0.x = (param_5->_s_0).x;
        scene.sceneModel[uVar8].lightingOrigin._s_0.y = (param_5->_s_0).y;
        pdVar4 = r_modelSkelWorker;
        scene.sceneModel[uVar8].lightingOrigin._s_0.z = (param_5->_s_0).z;
        scene.sceneModel[uVar8].gfxEntIndex = (ushort)uStack_54;
        scene.sceneModel[uVar8].modelShaderConstantSetIndex = uStack_48;
        scene.sceneModel[uVar8].primaryLightIndex = 0xff;
        scene.sceneModel[uVar8].reflectionProbeIndex = '\0';
        bVar5 = Dvar_GetBool(pdVar4);
        if (bVar5) {
          CG_PredictiveSkelModel(scene.sceneModel + uVar8);
        }
      }
    }
    else {
      uVar8 = R_AllocSceneDObj();
      if (uVar8 < 0x400) {
        scene.sceneDObj[uVar8].obj = param_1;
        scene.sceneDObj[uVar8].entnum = uStack_58;
        scene.dpvs.sceneDObjIndex[param_3] = (ushort)uVar8;
        scene.sceneDObj[uVar8].info.pose = param_2;
        scene.sceneDObj[uVar8].cull.state = 0;
        fVar13 = DObjGetRadius(param_1);
        pvVar1 = &scene.sceneDObj[uVar8].placement.base.origin;
        fVar13 = fVar13 * param_12;
        CG_GetPoseOrigin(param_2,pvVar1);
        CG_GetPoseQuat(param_2,(vec4_t *)&scene.sceneDObj[uVar8].placement);
        scene.sceneDObj[uVar8].radius = fVar13;
        fVar14 = __real_3f800000;
        scene.sceneDObj[uVar8].placement.scale = param_12;
        scene.sceneDObj[uVar8].invScaleSq = (fVar14 / param_12) * (fVar14 / param_12);
        fVar14 = (float)((uint)fVar13 ^ ___mask__NegFloat_);
        scene.sceneDObj[uVar8].cull.mins._s_0.x = (pvVar1->_s_0).x + fVar14;
        scene.sceneDObj[uVar8].cull.mins._s_0.y =
             scene.sceneDObj[uVar8].placement.base.origin._s_0.y + fVar14;
        scene.sceneDObj[uVar8].cull.mins._s_0.z =
             scene.sceneDObj[uVar8].placement.base.origin._s_0.z + fVar14;
        scene.sceneDObj[uVar8].cull.maxs._s_0.x = (pvVar1->_s_0).x + fVar13;
        scene.sceneDObj[uVar8].cull.maxs._s_0.y =
             fVar13 + scene.sceneDObj[uVar8].placement.base.origin._s_0.y;
        scene.sceneDObj[uVar8].cull.maxs._s_0.z =
             scene.sceneDObj[uVar8].placement.base.origin._s_0.z + fVar13;
        scene.sceneDObj[uVar8].lightingOrigin._s_0.x = (param_5->_s_0).x;
        scene.sceneDObj[uVar8].lightingOrigin._s_0.y = (param_5->_s_0).y;
        scene.sceneDObj[uVar8].lightingOrigin._s_0.z = (param_5->_s_0).z;
        scene.sceneDObj[uVar8].useHeroLighting = (byte)(param_4 >> 0x16) & 1;
        scene.sceneDObj[uVar8].gfxEntIndex = (ushort)uStack_54;
        scene.sceneDObj[uVar8].gfxEntIndex2 = 0;
        scene.sceneDObj[uVar8].altXModelIndex = (char)param_8 + '\x01';
        scene.sceneDObj[uVar8].entShaderConstantSetIndex = uStack_48;
        scene.sceneDObj[uVar8].lightingOriginToleranceSq = param_11;
        scene.sceneDObj[uVar8].primaryLightIndex = 0xff;
        scene.sceneDObj[uVar8].reflectionProbeIndex = '\0';
        if (param_13) {
          scene.sceneDObjViewmodelIndex = uVar8;
        }
        CG_PredictiveSkinCEntity(scene.sceneDObj + uVar8);
      }
    }
  }
  bVar5 = Sys_IsRenderThread();
  if (bVar5) {
    _D3DPERF_EndEvent_0();
  }
  return;
}

