
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl
R_DrawStaticModelSurfLit(uint *param_1,GfxCmdBufContext param_2,GfxDrawSurfListInfo *param_3)

{
  ulong64 *puVar1;
  GfxTexture *pGVar2;
  code *pcVar3;
  GfxCmdBufContext GVar4;
  bool bVar5;
  uint uVar6;
  undefined4 unaff_EDI;
  
  PIXBeginNamedEvent(-1,"R_DrawStaticModelSurfLit");
  puVar1 = (param_2.field0_0x0._s_0.state)->vertexShaderConstState[3];
  *(undefined4 *)(puVar1 + 0x10) = 0;
  *(undefined4 *)((int)puVar1 + 0x84) = 0;
  puVar1 = (param_2.field0_0x0._s_0.state)->vertexShaderConstState[3];
  *(undefined4 *)puVar1 = 0;
  *(undefined4 *)((int)puVar1 + 4) = 0;
  puVar1 = (param_2.field0_0x0._s_0.state)->vertexShaderConstState[3];
  *(undefined4 *)(puVar1 + 4) = 0;
  *(undefined4 *)((int)puVar1 + 0x24) = 0;
  puVar1 = (param_2.field0_0x0._s_0.state)->vertexShaderConstState[3];
  *(undefined4 *)(puVar1 + 8) = 0;
  *(undefined4 *)((int)puVar1 + 0x44) = 0;
  puVar1 = (param_2.field0_0x0._s_0.state)->vertexShaderConstState[3];
  *(undefined4 *)(puVar1 + 0xc) = 0;
  *(undefined4 *)((int)puVar1 + 100) = 0;
  if (param_3 == (GfxDrawSurfListInfo *)0x0) {
    bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_draw_staticmodel.cpp",0x4da,0,"(info)",
                             "");
    if (!bVar5) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  uVar6 = (uint)(((param_2.field0_0x0._s_0.state)->field10_0x25ac).localPass)->precompiledIndex;
  pGVar2 = (param_2.field0_0x0._s_0.state)->samplerTexture[0xf];
  GVar4.field0_0x0._s_0.state = (GfxCmdBufState *)unaff_EDI;
  GVar4.field0_0x0._s_0.source = (GfxCmdBufSourceState *)param_2.field0_0x0._s_0.state;
  R_DrawStaticModelsLit((GfxStaticModelDrawStream *)param_2.field0_0x0._s_0.source,GVar4);
  (param_2.field0_0x0._s_0.state)->samplerTexture[0xf] = pGVar2;
  bVar5 = Sys_IsRenderThread();
  if (bVar5) {
    _D3DPERF_EndEvent_0(uVar6,param_1);
  }
  return;
}

