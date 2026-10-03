
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

uint __cdecl R_AllocSceneModel(void)

{
  code *pcVar1;
  long lVar2;
  bool bVar3;
  uint uVar4;
  
  if (!rg.registered) {
    bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_scene.cpp",0xd3,0,"(rg.registered)","");
    if (!bVar3) {
      pcVar1 = (code *)swi(3);
      uVar4 = (*pcVar1)();
      return uVar4;
    }
  }
  if (rg.inFrame == false) {
    bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_scene.cpp",0xd5,0,"(rg.inFrame)","");
    if (!bVar3) {
      pcVar1 = (code *)swi(3);
      uVar4 = (*pcVar1)();
      return uVar4;
    }
  }
  lVar2 = scene.sceneModelCount;
  LOCK();
  scene.sceneModelCount = scene.sceneModelCount + 1;
  UNLOCK();
  uVar4 = Dvar_GetUnsignedInt(r_modelLimit);
  if (uVar4 <= (uint)lVar2) {
    scene.sceneModelCount = uVar4;
    R_WarnOncePerFrame(R_WARN_KNOWN_MODELS);
  }
  return lVar2;
}

