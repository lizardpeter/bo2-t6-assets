
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl R_SetStreamsForXModelSurface(XSurface *param_1,GfxCmdBufState *param_2)

{
  R_SetStreamSource(&param_2->prim,param_1->vb0,0,0x20,(uint)param_1->vertCount);
  return;
}

