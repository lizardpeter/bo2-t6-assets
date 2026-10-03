
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl R_DrawStaticModelsLit(GfxStaticModelDrawStream *param_1,GfxCmdBufContext param_2)

{
  int *piVar1;
  int iVar2;
  int iVar3;
  GfxCmdBufContext GVar4;
  GfxCmdBufContext GVar5;
  GfxCmdBufContext GVar6;
  int *unaff_ESI;
  undefined4 unaff_EDI;
  
  while( true ) {
    piVar1 = (int *)unaff_ESI[1];
    iVar2 = *piVar1;
    unaff_ESI[2] = iVar2;
    unaff_ESI[1] = (int)(piVar1 + 1);
    if (iVar2 == 0) break;
    iVar3 = piVar1[1];
    unaff_ESI[3] = (int)(piVar1 + 2);
    unaff_ESI[1] = (int)(piVar1 + 2 + (iVar2 + 1U >> 1));
    unaff_ESI[0xd] = iVar3;
    RB_TrackDrawDynamic((GfxFrameStats *)unaff_ESI[10],(uint)*(ushort *)(iVar3 + 6) * iVar2 * 3,
                        (uint)*(ushort *)(iVar3 + 4) * iVar2);
    RB_TrackGeoIndex((GfxFrameStats *)unaff_ESI[10],(uint)*(ushort *)(iVar3 + 6) * unaff_ESI[2] * 3)
    ;
    R_SetVertexDeclTypeModelLit
              ((XSurface *)unaff_ESI[0xd],(GfxCmdBufState *)param_2.field0_0x0._s_0.source);
    R_SetStreamsForXModelSurface
              ((XSurface *)unaff_ESI[0xd],(GfxCmdBufState *)param_2.field0_0x0._s_0.source);
    iVar2 = *unaff_ESI;
    if (iVar2 == 2) {
      GVar4.field0_0x0._s_0.state = (GfxCmdBufState *)unaff_EDI;
      GVar4.field0_0x0._s_0.source = param_2.field0_0x0._s_0.source;
      R_DrawStaticModelLitLightmapVCNoPrepass(param_1,GVar4);
    }
    else if (iVar2 == 1) {
      GVar5.field0_0x0._s_0.state = (GfxCmdBufState *)unaff_EDI;
      GVar5.field0_0x0._s_0.source = param_2.field0_0x0._s_0.source;
      R_DrawStaticModelLitNoPrepass(param_1,GVar5);
    }
    else if (iVar2 == 3) {
      GVar6.field0_0x0._s_0.state = (GfxCmdBufState *)unaff_EDI;
      GVar6.field0_0x0._s_0.source = param_2.field0_0x0._s_0.source;
      R_DrawStaticModelUnlitNoPrepass(param_1,GVar6);
    }
    else {
      R_WarnOncePerFrame(R_WARN_UNKNOWN_STATICMODEL_SHADER);
    }
  }
  return;
}

