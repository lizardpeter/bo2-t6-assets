
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl R_ResetModelLighting(void)

{
  ushort uVar1;
  code *pcVar2;
  undefined4 uVar3;
  vec3_t *pvVar4;
  bool bVar5;
  int iVar6;
  uint uVar7;
  uint uVar8;
  
  uVar7 = 0;
  uVar8 = 0;
  do {
    Com_Memset(*(void **)((int)modelLightGlob.pixelFreeBits + uVar8),0xff,
               modelLightGlob.pixelFreeBitsSize);
    uVar3 = ___real_7f7fffff;
    uVar8 = uVar8 + 4;
  } while (uVar8 < 0x10);
  uVar8 = 0;
  if (modelLightGlob.xmodelEntryLimit != 0) {
    iVar6 = 0;
    do {
      pvVar4 = modelLightGlob.lightingOrigins;
      *(undefined4 *)((int)modelLightGlob.lightingOrigins + iVar6) = uVar3;
      *(undefined4 *)((int)pvVar4 + iVar6 + 4) = uVar3;
      *(undefined4 *)((int)pvVar4 + iVar6 + 8) = uVar3;
      uVar8 = uVar8 + 1;
      iVar6 = iVar6 + 0xc;
    } while (uVar8 < modelLightGlob.xmodelEntryLimit);
  }
  if (smodelLightGlob.local.assignedCount != 0) {
    if ((rgp.world == (GfxWorld *)0x0) &&
       (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x49a,0,
                                 "(smodelLightGlob.local.assignedCount == 0 || rgp.world != 0)",""),
       !bVar5)) {
      pcVar2 = (code *)swi(3);
      (*pcVar2)();
      return;
    }
    if (smodelLightGlob.local.assignedCount != 0) {
      while( true ) {
        uVar8 = (uint)smodelLightGlob.local.smodelIndex[uVar7];
        if ((((rgp.world)->dpvs).smodelCount <= uVar8) &&
           (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x49e,0,
                                     "(unsigned)(smodelIndex) < (unsigned)(rgp.world->dpvs.smodelCount)"
                                     ,
                                     "smodelIndex doesn\'t index rgp.world->dpvs.smodelCount\n\t%i not in [0, %i)"
                                    ), !bVar5)) {
          pcVar2 = (code *)swi(3);
          (*pcVar2)();
          return;
        }
        uVar1 = ((rgp.world)->dpvs).smodelDrawInsts[uVar8].lightingHandle;
        if (((uVar1 == 0) || (modelLightGlob.totalEntryLimit < uVar1)) &&
           (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0xcc,0,
                                     "(1) <= (handle) && (handle) <= (modelLightGlob.totalEntryLimit)"
                                     ,
                                     "handle not in [1, modelLightGlob.totalEntryLimit]\n\t%i not in [%i, %i]"
                                    ), !bVar5)) break;
        if (uVar7 != uVar1 - 1) {
          uVar1 = ((rgp.world)->dpvs).smodelDrawInsts[uVar8].lightingHandle;
          if (((uVar1 == 0) || (modelLightGlob.totalEntryLimit < uVar1)) &&
             (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0xcc,0,
                                       "(1) <= (handle) && (handle) <= (modelLightGlob.totalEntryLimit)"
                                       ,
                                       "handle not in [1, modelLightGlob.totalEntryLimit]\n\t%i not in [%i, %i]"
                                      ), !bVar5)) {
            pcVar2 = (code *)swi(3);
            (*pcVar2)();
            return;
          }
          bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x49f,0,
                                   "(entryIndex) == (R_ModelLightingIndexFromHandle( rgp.world->dpvs.smodelDrawInsts[smodelIndex].lightingHandle ))"
                                   ,
                                   "entryIndex == R_ModelLightingIndexFromHandle( rgp.world->dpvs.smodelDrawInsts[smodelIndex].lightingHandle )\n\t%i, %i"
                                  );
          if (!bVar5) {
            pcVar2 = (code *)swi(3);
            (*pcVar2)();
            return;
          }
        }
        uVar7 = uVar7 + 1;
        ((rgp.world)->dpvs).smodelDrawInsts[uVar8].lightingHandle = 0;
        if (smodelLightGlob.local.assignedCount <= uVar7) {
          smodelLightGlob.local.assignedCount = 0;
          return;
        }
      }
      pcVar2 = (code *)swi(3);
      (*pcVar2)();
      return;
    }
  }
  smodelLightGlob.local.assignedCount = 0;
  return;
}

