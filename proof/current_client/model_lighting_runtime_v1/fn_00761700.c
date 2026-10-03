
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00761700(void)

{
  undefined4 uVar1;
  char *pcVar2;
  undefined4 uVar3;
  undefined1 *unaff_ESI;
  float10 fVar4;
  undefined1 auStack_14 [16];
  
  pcVar2 = (char *)FUN_00614d20(_DAT_03a24a84);
  uVar3 = _DAT_035ae1e8;
  if (*pcVar2 != '\0') {
    uVar3 = FUN_00734c90(pcVar2,6,1,0xffffffff);
  }
  uVar1 = _DAT_03a270fc;
  *(undefined4 *)(unaff_ESI + 4) = uVar3;
  fVar4 = (float10)FUN_004645d0(uVar1);
  *(float *)(unaff_ESI + 0xc) = (float)fVar4;
  pcVar2 = (char *)FUN_00614d20(_DAT_03a270f8);
  uVar3 = _DAT_035ae1e8;
  if (*pcVar2 != '\0') {
    uVar3 = FUN_00734c90(pcVar2,6,1,0xffffffff);
  }
  *(undefined4 *)(unaff_ESI + 8) = uVar3;
  fVar4 = (float10)FUN_004645d0(_DAT_03a248fc);
  uVar3 = _DAT_03a270f0;
  *(float *)(unaff_ESI + 0x10) = (float)(fVar4 * (float10)_DAT_00c519c8);
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a270f4;
  fVar4 = (float10)fcos(fVar4 * (float10)_DAT_00c1a568);
  *(float *)(unaff_ESI + 0x14) = (float)fVar4;
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a270e0;
  *(float *)(unaff_ESI + 0x18) = (float)(fVar4 * (float10)_DAT_00c519c8);
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a270d8;
  fVar4 = (float10)fcos(fVar4 * (float10)_DAT_00c1a568);
  *(float *)(unaff_ESI + 0x1c) = (float)fVar4;
  fVar4 = (float10)FUN_004645d0(uVar3);
  *(float *)(unaff_ESI + 0x20) = (float)fVar4;
  fVar4 = (float10)FUN_004645d0(_DAT_03a270cc);
  uVar3 = _DAT_03a270d4;
  *(int *)(unaff_ESI + 0x24) =
       (int)ROUND((float)(fVar4 * (float10)_DAT_00c4d158) + (float)_DAT_00c57bf0);
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a26ef0;
  *(int *)(unaff_ESI + 0x28) =
       (int)ROUND((float)(fVar4 * (float10)_DAT_00c4d158) + (float)_DAT_00c57bf0);
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a270e4;
  fVar4 = (float10)fcos(fVar4 * (float10)_DAT_00c1a568);
  *(float *)(unaff_ESI + 0x2c) = (float)fVar4;
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a270dc;
  fVar4 = (float10)fcos(fVar4 * (float10)_DAT_00c1a568);
  *(float *)(unaff_ESI + 0x30) = (float)fVar4;
  fVar4 = (float10)FUN_004645d0(uVar3);
  *(float *)(unaff_ESI + 0x34) = (float)fVar4;
  fVar4 = (float10)FUN_004645d0(_DAT_03a270d0);
  uVar3 = _DAT_03a26ef4;
  *(int *)(unaff_ESI + 0x38) =
       (int)ROUND((float)(fVar4 * (float10)_DAT_00c4d158) + (float)_DAT_00c57bf0);
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a270ec;
  *(int *)(unaff_ESI + 0x3c) =
       (int)ROUND((float)(fVar4 * (float10)_DAT_00c4d158) + (float)_DAT_00c57bf0);
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a270e8;
  fVar4 = (float10)fcos(fVar4 * (float10)_DAT_00c1a568);
  *(float *)(unaff_ESI + 0x40) = (float)fVar4;
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a36af8;
  fVar4 = (float10)fcos(fVar4 * (float10)_DAT_00c1a568);
  *(float *)(unaff_ESI + 0x44) = (float)fVar4;
  fVar4 = (float10)FUN_004645d0(uVar3);
  *(float *)(unaff_ESI + 0x48) = (float)fVar4;
  fVar4 = (float10)FUN_004645d0(_DAT_03a26efc);
  uVar3 = _DAT_03a270c8;
  *(int *)(unaff_ESI + 0x4c) =
       (int)ROUND((float)(fVar4 * (float10)_DAT_00c4d158) + (float)_DAT_00c57bf0);
  fVar4 = (float10)FUN_004645d0(uVar3);
  uVar3 = _DAT_03a26ef8;
  *(int *)(unaff_ESI + 0x50) =
       (int)ROUND((float)(fVar4 * (float10)_DAT_00c4d158) + (float)_DAT_00c57bf0);
  FUN_0053e5d0(uVar3,auStack_14);
  FUN_0045dc40(auStack_14,unaff_ESI + 0x54,0,0);
  *unaff_ESI = 1;
  return;
}

