
void __cdecl R_SetAllStaticModelLighting(void)

{
  code *pcVar1;
  bool bVar2;
  uint uVar3;
  uint uVar4;
  uint unaff_EDI;
  uint uStack_c;
  uint uStack_8;
  
  PIXBeginNamedEvent(-1,"R_SetAllStaticModelLighting");
  if (smodelLightGlob.local.anyNewLighting == 0) {
    bVar2 = Sys_IsRenderThread();
  }
  else {
    smodelLightGlob.local.anyNewLighting = 0;
    uVar3 = ((rgp.world)->dpvs).smodelCount + 0x1f >> 5;
    if ((0x7ff < uVar3) &&
       (bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x3b6,0,
                                 "(wordCount < sizeof( smodelLightGlob.lightingBits ))",""), !bVar2)
       ) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
    uStack_c = 0;
    if (uVar3 != 0) {
      do {
        uStack_8 = smodelLightGlob.lightingBits[uStack_c];
        if (uStack_8 != 0) {
          while( true ) {
            uVar4 = 0x1f;
            if (uStack_8 != 0) {
              for (; uStack_8 >> uVar4 == 0; uVar4 = uVar4 - 1) {
              }
            }
            if (uStack_8 == 0) {
              uVar4 = `unsigned_int___cdecl_CountLeadingZeros(int)'::__l2::notFound;
            }
            if (0x1f < (uVar4 ^ 0x1f)) break;
            uVar4 = 0x80000000 >> ((byte)(uVar4 ^ 0x1f) & 0x1f);
            if (((uStack_8 & uVar4) == 0) &&
               (bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0x3c7,0,
                                         "(bits & bit)",""), !bVar2)) {
              pcVar1 = (code *)swi(3);
              (*pcVar1)();
              return;
            }
            uStack_8 = uStack_8 & ~uVar4;
            R_SetStaticModelLighting(unaff_EDI);
          }
        }
        uStack_c = uStack_c + 1;
      } while (uStack_c < uVar3);
    }
    bVar2 = Sys_IsRenderThread();
  }
  if (bVar2 != false) {
    _D3DPERF_EndEvent_0();
  }
  return;
}

