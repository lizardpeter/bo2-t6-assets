
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl
R_DrawStaticModelSkinnedSurfLit(uint *param_1,GfxCmdBufContext param_2,GfxDrawSurfListInfo *param_3)

{
  uint uVar1;
  XSurface *pXVar2;
  code *pcVar3;
  bool bVar4;
  GfxStaticModelDrawStream GStack_40;
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  R_SetupPassPerObjectArgs(param_2);
  if (param_3 == (GfxDrawSurfListInfo *)0x0) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_draw_staticmodel.cpp",0x4da,0,"(info)",
                             "");
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  GStack_40.precompiledIndex =
       (uint)(((param_2.field0_0x0._s_0.state)->field10_0x25ac).localPass)->precompiledIndex;
  GStack_40.customSamplerFlags =
       (uint)(((param_2.field0_0x0._s_0.state)->field10_0x25ac).localPass)->customSamplerFlags;
  GStack_40.reflectionProbeTexture = (param_2.field0_0x0._s_0.state)->samplerTexture[0xf];
  GStack_40.viewOrigin.v[0] = (param_3->viewOrigin).v[0];
  GStack_40.viewOrigin.v[1] = (param_3->viewOrigin).v[1];
  GStack_40.frameStats = &((param_2.field0_0x0._s_0.state)->prim).frameStats;
  GStack_40.viewOrigin.v[2] = (param_3->viewOrigin).v[2];
  GStack_40.viewInfoIndex = param_3->viewInfo->viewInfoIndex;
  GStack_40.viewOrigin.v[3] = (param_3->viewOrigin).v[3];
  while( true ) {
    uVar1 = *param_1;
    if (uVar1 == 0) break;
    pXVar2 = (XSurface *)param_1[1];
    GStack_40.smodelList = (ushort *)(param_1 + 2);
    GStack_40.primDrawSurfPos = (uint *)((int)GStack_40.smodelList + (uVar1 + 1 >> 1) * 4);
    GStack_40.smodelCount = uVar1;
    GStack_40.localSurf = pXVar2;
    RB_TrackDrawDynamic(GStack_40.frameStats,pXVar2->triCount * uVar1 * 3,pXVar2->vertCount * uVar1)
    ;
    RB_TrackGeoIndex(GStack_40.frameStats,pXVar2->triCount * uVar1 * 3);
    R_DrawStaticModelsSkinnedDrawSurfLighting(&GStack_40,param_2);
    param_1 = GStack_40.primDrawSurfPos;
  }
  (param_2.field0_0x0._s_0.state)->samplerTexture[0xf] = GStack_40.reflectionProbeTexture;
  return;
}

