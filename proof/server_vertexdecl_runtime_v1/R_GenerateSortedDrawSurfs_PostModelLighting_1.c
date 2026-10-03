
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl R_SetSunConstants(GfxCmdBufInput *param_1,float param_2)

{
  undefined4 uVar1;
  undefined4 uVar2;
  undefined4 uVar3;
  int iVar4;
  code *pcVar5;
  bool bVar6;
  int unaff_EDI;
  
  iVar4 = *(int *)(unaff_EDI + 0xe44);
  if (*(char *)(iVar4 + 0x60960) != '\x01') {
    bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_scene.cpp",0x1600,0,
                             "(sun->type == GFX_LIGHT_TYPE_DIR)","");
    if (!bVar6) {
      pcVar5 = (code *)swi(3);
      (*pcVar5)();
      return;
    }
  }
  uVar1 = *(undefined4 *)(iVar4 + 0x60974);
  uVar2 = *(undefined4 *)(iVar4 + 0x60978);
  uVar3 = *(undefined4 *)(iVar4 + 0x6097c);
  if ((_DAT_00d17864 != 2) && (_DAT_00d17864 != 3)) {
    bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar6) {
      pcVar5 = (code *)swi(3);
      (*pcVar5)();
      return;
    }
  }
  *(undefined4 *)(unaff_EDI + 0x290) = uVar1;
  *(undefined4 *)(unaff_EDI + 0x294) = uVar2;
  *(undefined4 *)(unaff_EDI + 0x298) = uVar3;
  *(float *)(unaff_EDI + 0x29c) = __real_3f800000;
  uVar1 = *(undefined4 *)(iVar4 + 0x609b8);
  uVar2 = *(undefined4 *)(iVar4 + 0x609bc);
  uVar3 = *(undefined4 *)(iVar4 + 0x609c0);
  if ((_DAT_00d17868 != 2) && (_DAT_00d17868 != 3)) {
    bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x692,0,
                             "((g_codeConstUpdateFreq[constant] == MTL_UPDATE_RARELY || g_codeConstUpdateFreq[constant] == MTL_UPDATE_CUSTOM))"
                             ,"(constant) = %i");
    if (!bVar6) {
      pcVar5 = (code *)swi(3);
      (*pcVar5)();
      return;
    }
  }
  *(undefined4 *)(unaff_EDI + 0x2a0) = uVar1;
  *(undefined4 *)(unaff_EDI + 0x2a4) = uVar2;
  *(undefined4 *)(unaff_EDI + 0x2a8) = uVar3;
  *(float *)(unaff_EDI + 0x2ac) = __real_3f800000;
  return;
}

