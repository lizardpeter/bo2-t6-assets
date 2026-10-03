
bool __cdecl R_AllocStaticModelLighting(GfxStaticModelDrawInst *param_1,uint param_2)

{
  code *pcVar1;
  bool bVar2;
  undefined1 uVar3;
  uint uVar4;
  ushort unaff_DI;
  ushort uVar5;
  uint uVar6;
  
  if (rgp.world == (GfxWorld *)0x0) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x143,0,
                             "(rgp.world)","");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      uVar3 = (*pcVar1)();
      return (bool)uVar3;
    }
  }
  if (param_1->lightingHandle != 0) {
    uVar4 = R_ModelLightingIndexFromHandle(unaff_DI);
    smodelLightGlob.local.usedFrameCount[uVar4] = smodelLightGlob.local.frameCount;
    return true;
  }
  if (smodelLightGlob.local.assignedCount < smodelLightGlob.local.entryLimit) {
    uVar5 = (short)smodelLightGlob.local.assignedCount + 1;
    uVar4 = smodelLightGlob.local.assignedCount;
    smodelLightGlob.local.assignedCount = smodelLightGlob.local.assignedCount + 1;
  }
  else {
    do {
      if (smodelLightGlob.local.freeableCount == 0) {
        return false;
      }
      uVar4 = smodelLightGlob.local.freeableCount - 1;
      uVar5 = smodelLightGlob.freeableHandles[smodelLightGlob.local.freeableCount - 1];
      uVar6 = (uint)uVar5;
      smodelLightGlob.local.freeableCount = uVar4;
      if ((uVar5 == 0) || (modelLightGlob.totalEntryLimit < uVar6)) {
        bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0xcc,0,
                                 "(1) <= (handle) && (handle) <= (modelLightGlob.totalEntryLimit)",
                                 "handle not in [1, modelLightGlob.totalEntryLimit]\n\t%i not in [%i, %i]"
                                );
        if (!bVar2) {
          pcVar1 = (code *)swi(3);
          uVar3 = (*pcVar1)();
          return (bool)uVar3;
        }
      }
      uVar4 = uVar6 - 1;
    } while (smodelLightGlob.local.frameCount == smodelLightGlob.local.usedFrameCount[uVar6 - 1]);
    ((rgp.world)->dpvs).smodelDrawInsts[smodelLightGlob.local.smodelIndex[uVar6 - 1]].lightingHandle
         = 0;
  }
  if (uVar5 == 0) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x171,0,"(handle)",
                             "");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      uVar3 = (*pcVar1)();
      return (bool)uVar3;
    }
  }
  param_1->lightingHandle = uVar5;
  if (param_2 != (param_2 & 0xffff)) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\qcommon\\../universal/assertive.h",0x15f,0,
                             "(i) == (static_cast< Type >( i ))",
                             "i == static_cast< Type >( i )\n\t%i, %i");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      uVar3 = (*pcVar1)();
      return (bool)uVar3;
    }
  }
  smodelLightGlob.local.smodelIndex[uVar4] = (ushort)param_2;
  if (0x1ff < param_2 >> 5) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x17a,0,
                             "(unsigned)(smodelIndex >> 5) < (unsigned)((sizeof( smodelLightGlob.lightingBits ) / (sizeof( smodelLightGlob.lightingBits[0] ) * (sizeof( smodelLightGlob.lightingBits ) != 4 || sizeof( smodelLightGlob.lightingBits[0] ) <= 4))))"
                             ,
                             "smodelIndex >> 5 doesn\'t index ARRAY_COUNT( smodelLightGlob.lightingBits )\n\t%i not in [0, %i)"
                            );
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      uVar3 = (*pcVar1)();
      return (bool)uVar3;
    }
  }
  smodelLightGlob.lightingBits[param_2 >> 5] =
       smodelLightGlob.lightingBits[param_2 >> 5] | 0x80000000U >> ((byte)param_2 & 0x1f);
  smodelLightGlob.local.anyNewLighting = 1;
  smodelLightGlob.local.usedFrameCount[uVar4] = smodelLightGlob.local.frameCount;
  return true;
}

