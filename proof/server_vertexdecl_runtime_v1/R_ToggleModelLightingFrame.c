
void __cdecl R_ToggleModelLightingFrame(void)

{
  uint uVar1;
  
  smodelLightGlob.local.frameCount = smodelLightGlob.local.frameCount + 1;
  modelLightGlob.modFrameCount = modelLightGlob.modFrameCount + 1 & 3;
  modelLightGlob.allocModelFail = 0;
  modelLightGlob.prevPrevPixelFreeBits =
       modelLightGlob.pixelFreeBits[modelLightGlob.modFrameCount - 2 & 3];
  modelLightGlob.prevPixelFreeBits =
       modelLightGlob.pixelFreeBits[modelLightGlob.modFrameCount - 1 & 3];
  modelLightGlob.currPixelFreeBits = modelLightGlob.pixelFreeBits[modelLightGlob.modFrameCount];
  Com_Memset(modelLightGlob.currPixelFreeBits,0xff,modelLightGlob.pixelFreeBitsSize);
  uVar1 = 0;
  smodelLightGlob.local.freeableCount = 0;
  if (smodelLightGlob.local.assignedCount != 0) {
    do {
      if (3 < smodelLightGlob.local.frameCount - smodelLightGlob.local.usedFrameCount[uVar1]) {
        smodelLightGlob.freeableHandles[smodelLightGlob.local.freeableCount] = (short)uVar1 + 1;
        smodelLightGlob.local.freeableCount = smodelLightGlob.local.freeableCount + 1;
      }
      uVar1 = uVar1 + 1;
    } while (uVar1 < smodelLightGlob.local.assignedCount);
  }
  return;
}

