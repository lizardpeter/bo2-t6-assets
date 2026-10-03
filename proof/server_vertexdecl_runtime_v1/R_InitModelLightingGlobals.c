
/* WARNING: Removing unreachable block (ram,0x00a7b8a7) */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl R_InitModelLightingGlobals(void)

{
  code *pcVar1;
  byte bVar2;
  float fVar3;
  bool bVar4;
  void *pvVar5;
  int iVar6;
  uint uVar7;
  
  modelLightGlob.xmodelEntryLimit = 0x1000;
  for (uVar7 = 0x1f; 0x1000U >> uVar7 == 0; uVar7 = uVar7 - 1) {
  }
  iVar6 = 0x20 - (uVar7 ^ 0x1f);
  bVar2 = (byte)iVar6 & 0x1f;
  smodelLightGlob.local.entryLimit = (1 << ((byte)iVar6 & 0x1f)) - 0x1000;
  uVar7 = 1 << bVar2 | 1U >> 0x20 - bVar2;
  while (smodelLightGlob.local.entryLimit < 0x1000) {
    iVar6 = iVar6 + 1;
    smodelLightGlob.local.entryLimit = smodelLightGlob.local.entryLimit + uVar7;
    uVar7 = uVar7 << 1 | (uint)((int)uVar7 < 0);
  }
  if ((0x1e00 < smodelLightGlob.local.entryLimit) &&
     (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x45b,0,
                               "((smodelLightGlob.local.entryLimit <= 7680))",
                               "(smodelLightGlob.local.entryLimit) = %i"), !bVar4)) {
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  modelLightGlob.totalEntryLimit = 1 << ((byte)iVar6 & 0x1f);
  modelLightGlob.entryBitsY = iVar6 - 7;
  modelLightGlob.imageHeight = 1 << ((char)modelLightGlob.entryBitsY + 2U & 0x1f);
  fVar3 = (float)(int)modelLightGlob.imageHeight;
  if ((int)modelLightGlob.imageHeight < 0) {
    fVar3 = fVar3 + ___real_4f800000;
  }
  modelLightGlob.invImageHeight = 1.0 / fVar3;
  modelLightGlob.baseIndex = smodelLightGlob.local.entryLimit;
  if (((modelLightGlob.xmodelEntryLimit & 0x1f) != 0) &&
     (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x46c,0,
                               "((!(modelLightGlob.xmodelEntryLimit & 31)))",
                               "(modelLightGlob.xmodelEntryLimit) = %i"), !bVar4)) {
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  modelLightGlob.pixelFreeBitsSize = modelLightGlob.xmodelEntryLimit >> 3;
  modelLightGlob.pixelFreeBitsWordCount = modelLightGlob.xmodelEntryLimit >> 5;
  modelLightGlob.lightingOrigins =
       Z_VirtualAlloc(modelLightGlob.xmodelEntryLimit * 0xc,"R_AllocModelLightingGlobal",0x15);
  uVar7 = 0;
  do {
    pvVar5 = Z_VirtualAlloc(modelLightGlob.pixelFreeBitsSize,"R_AllocModelLightingGlobal",0x15);
    *(void **)((int)modelLightGlob.pixelFreeBits + uVar7) = pvVar5;
    uVar7 = uVar7 + 4;
  } while (uVar7 < 0x10);
  modelLightGlob.lightingInfo =
       Z_VirtualAlloc(modelLightGlob.xmodelEntryLimit * 4,"R_AllocModelLightingGlobal",0x15);
  modelLightGlob.lightingSHAndVis =
       Z_VirtualAlloc(modelLightGlob.xmodelEntryLimit * 0x34,"R_AllocModelLightingGlobal",0x15);
  return;
}

