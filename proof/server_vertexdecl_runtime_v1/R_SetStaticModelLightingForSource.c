
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl
R_SetStaticModelLightingForSource(GfxStaticModelDrawInst *param_1,GfxCmdBufSourceState *param_2)

{
  R_SetStaticModelLightingConsts
            (param_1->lightingHandle,param_1->visibility,&param_1->lightingSH,
             (param_2->input).consts + 0x45,(param_2->input).consts + 0x46,
             (param_2->input).consts + 0x47,(param_2->input).consts + 0x48);
  param_2->constVersions[0x45] = param_2->constVersions[0x45] + 1;
  param_2->constVersions[0x46] = param_2->constVersions[0x46] + 1;
  param_2->constVersions[0x47] = param_2->constVersions[0x47] + 1;
  param_2->constVersions[0x48] = param_2->constVersions[0x48] + 1;
  return;
}

