
/* WARNING: Removing unreachable block (ram,0x00a7b2cc) */
/* WARNING: Removing unreachable block (ram,0x00a7b2f7) */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl
R_SetModelLightingConsts
          (ushort param_1,vec4_t *param_2,vec4_t *param_3,vec4_t *param_4,vec4_t *param_5)

{
  float fVar1;
  code *pcVar2;
  float fVar3;
  float fVar4;
  bool bVar5;
  uint uVar6;
  uint uVar7;
  GfxLightingSHAndVis *pGVar8;
  
  if (((param_1 == 0) || (modelLightGlob.totalEntryLimit < param_1)) &&
     (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0xcc,0,
                               "(1) <= (handle) && (handle) <= (modelLightGlob.totalEntryLimit)",
                               "handle not in [1, modelLightGlob.totalEntryLimit]\n\t%i not in [%i, %i]"
                              ), !bVar5)) {
    pcVar2 = (code *)swi(3);
    (*pcVar2)();
    return;
  }
  uVar6 = param_1 - 1;
  fVar4 = ((float)((uVar6 & 0x7f) * 4) + ___real_40000000) * ___real_3b000000;
  uVar7 = uVar6 - modelLightGlob.baseIndex;
  fVar3 = ((float)(uVar6 >> 5 & 0x7fffffc) + ___real_40000000) * modelLightGlob.invImageHeight;
  if ((modelLightGlob.xmodelEntryLimit <= uVar7) &&
     (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x115,0,
                               "(unsigned)(usedIndex) < (unsigned)(modelLightGlob.xmodelEntryLimit)"
                               ,
                               "usedIndex doesn\'t index modelLightGlob.xmodelEntryLimit\n\t%i not in [0, %i)"
                              ), !bVar5)) {
    pcVar2 = (code *)swi(3);
    (*pcVar2)();
    return;
  }
  pGVar8 = modelLightGlob.lightingSHAndVis + uVar7;
  fVar1 = pGVar8->vis;
  param_2->v[0] = fVar4;
  param_2->v[1] = fVar3;
  param_2->v[2] = __real_3f000000;
  param_2->v[3] = fVar1;
  param_3->v[0] = (pGVar8->sh).V0.v[0];
  param_3->v[1] = (pGVar8->sh).V0.v[1];
  param_3->v[2] = (pGVar8->sh).V0.v[2];
  param_3->v[3] = (pGVar8->sh).V0.v[3];
  param_4->v[0] = (pGVar8->sh).V1.v[0];
  param_4->v[1] = (pGVar8->sh).V1.v[1];
  param_4->v[2] = (pGVar8->sh).V1.v[2];
  param_4->v[3] = (pGVar8->sh).V1.v[3];
  param_5->v[0] = (pGVar8->sh).V2.v[0];
  param_5->v[1] = (pGVar8->sh).V2.v[1];
  param_5->v[2] = (pGVar8->sh).V2.v[2];
  param_5->v[3] = (pGVar8->sh).V2.v[3];
  return;
}

