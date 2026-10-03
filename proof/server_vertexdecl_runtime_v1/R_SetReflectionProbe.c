
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl R_SetReflectionProbe(GfxCmdBufContext param_1,uint param_2)

{
  GfxTexture *pGVar1;
  ID3D11DeviceContext *pIVar2;
  code *pcVar3;
  bool bVar4;
  
  if (g_worldDraw == (GfxWorldDraw *)0x0) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.cpp",0x30c,0,"(g_worldDraw)","");
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  if (param_2 == 0xff) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.cpp",0x30d,0,
                             "(reflectionProbeIndex != (0xff))","");
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  if (g_worldDraw->reflectionProbeCount <= param_2) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.cpp",0x30e,0,
                             "(unsigned)(reflectionProbeIndex) < (unsigned)(g_worldDraw->reflectionProbeCount)"
                             ,
                             "reflectionProbeIndex doesn\'t index g_worldDraw->reflectionProbeCount\n\t%i not in [0, %i)"
                            );
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  if (((((param_1.field0_0x0._s_0.state)->field10_0x25ac).localPass)->customSamplerFlags & 1) != 0)
  {
    if ((param_1.field0_0x0._s_0.state)->samplerTexture[0xf] !=
        (g_worldDraw->field2_0x8).localReflectionProbeTextures + param_2) {
      (param_1.field0_0x0._s_0.state)->samplerTexture[0xf] =
           (g_worldDraw->field2_0x8).localReflectionProbeTextures + param_2;
      pGVar1 = (g_worldDraw->field2_0x8).localReflectionProbeTextures;
      pIVar2 = ((param_1.field0_0x0._s_0.state)->prim).field0_0x0.device;
      if (pGVar1 + param_2 == (GfxTexture *)0x0) {
        bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_setstate_d3d.h",0x122,0,"(texture)",
                                 "");
        if (!bVar4) {
          pcVar3 = (code *)swi(3);
          (*pcVar3)();
          return;
        }
      }
      (**(code **)((int)*pIVar2 + 0x20))(pIVar2,0xf,1,pGVar1 + param_2);
      if ((param_1.field0_0x0._s_0.state)->samplerState[0xf] != 0x72) {
        (param_1.field0_0x0._s_0.state)->samplerState[0xf] = 0x72;
        R_HW_ForceSamplerState(((param_1.field0_0x0._s_0.state)->prim).field0_0x0.device,0xf,0x72);
      }
      R_HW_SetVertexShaderConstant
                (param_1.field0_0x0._s_0.state,3,0x80,
                 (float *)&(g_worldDraw->field1_0x4).localReflectionProbes[param_2].lightingSH,0x30)
      ;
    }
  }
  return;
}

