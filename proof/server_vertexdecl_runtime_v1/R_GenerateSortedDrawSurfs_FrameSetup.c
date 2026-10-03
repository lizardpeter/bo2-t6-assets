
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl R_SetupVisibility(GfxViewParms *param_1,GfxViewInfo *param_2,bool param_3)

{
  bool bVar1;
  GfxViewInfo *in_EAX;
  GfxSunShadowProjection *unaff_ESI;
  GfxCmdBufInput *unaff_EDI;
  
  PIXBeginNamedEvent(-1,"R_SetupVisibility");
  R_SetViewFrustumPlanes(in_EAX);
  PIXBeginNamedEvent(-1,"R_InitialEntityCulling");
  R_InitialEntityCulling();
  bVar1 = Sys_IsRenderThread();
  if (bVar1) {
    _D3DPERF_EndEvent_0();
  }
  PIXBeginNamedEvent(-1,"R_AddWorldSurfacesDpvs");
  R_AddWorldSurfacesDpvs(param_1->bspCellIndex,false);
  bVar1 = Sys_IsRenderThread();
  if (bVar1) {
    _D3DPERF_EndEvent_0();
  }
  if ((char)param_2 != '\0') {
    R_FinishSunShadowMaps(2);
  }
  R_SetSunShadowConstants(unaff_EDI,unaff_ESI);
  bVar1 = Sys_IsRenderThread();
  if (bVar1) {
    _D3DPERF_EndEvent_0();
    return;
  }
  return;
}

