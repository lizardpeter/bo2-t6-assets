
uint __cdecl R_AllocModelLightingPixel(GfxModelLightGlob *param_1,GfxModelLightGlob *param_2)

{
  uint uVar1;
  uint uVar2;
  uint uVar3;
  uint uVar4;
  
  do {
    uVar4 = param_1->pixelFreeRover;
    while( true ) {
      uVar1 = param_2->currPixelFreeBits[uVar4];
      uVar2 = param_2->prevPixelFreeBits[uVar4] & param_2->prevPrevPixelFreeBits[uVar4] & uVar1;
      uVar3 = 0x1f;
      if (uVar2 != 0) {
        for (; uVar2 >> uVar3 == 0; uVar3 = uVar3 - 1) {
        }
      }
      if (uVar2 == 0) {
        uVar3 = `unsigned_int___cdecl_CountLeadingZeros(int)'::__l2::notFound;
      }
      uVar3 = uVar3 ^ 0x1f;
      if (uVar3 < 0x20) break;
      uVar4 = (uVar4 + 1) % param_2->pixelFreeBitsWordCount;
      if (uVar4 == param_1->pixelFreeRover) {
        param_1->allocModelFail = 1;
        R_WarnOncePerFrame(R_WARN_MODEL_LIGHT_CACHE);
        return 0;
      }
    }
    param_1->pixelFreeRover = uVar4;
    LOCK();
    uVar2 = param_2->currPixelFreeBits[uVar4];
    if (uVar1 == uVar2) {
      param_2->currPixelFreeBits[uVar4] = ~(0x80000000U >> ((byte)uVar3 & 0x1f)) & uVar1;
      uVar2 = uVar1;
    }
    UNLOCK();
  } while (uVar2 != uVar1);
  return uVar4 * 0x20 + uVar3;
}

