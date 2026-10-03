
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_0076ec70(int param_1)

{
  undefined4 uVar1;
  undefined4 uVar2;
  int iVar3;
  int unaff_ESI;
  float fVar4;
  float fVar5;
  float fVar6;
  float fVar7;
  double dVar8;
  uint uVar9;
  float fVar10;
  float fStack_28;
  float fStack_18;
  
  iVar3 = *(int *)(unaff_ESI + 0xe44);
  *(undefined4 *)(unaff_ESI + 0x340) = *(undefined4 *)(iVar3 + 0x4741dc);
  *(undefined4 *)(unaff_ESI + 0x344) = *(undefined4 *)(iVar3 + 0x4741e0);
  *(undefined4 *)(unaff_ESI + 0x348) = *(undefined4 *)(iVar3 + 0x4741e4);
  *(undefined4 *)(unaff_ESI + 0x34c) = *(undefined4 *)(iVar3 + 0x4741e8);
  uVar1 = *(undefined4 *)(iVar3 + 0x4741f0);
  uVar2 = *(undefined4 *)(iVar3 + 0x4741f4);
  *(undefined4 *)(unaff_ESI + 0x330) = *(undefined4 *)(iVar3 + 0x4741ec);
  *(undefined4 *)(unaff_ESI + 0x33c) = 0;
  fVar10 = _DAT_00d33b74;
  *(undefined4 *)(unaff_ESI + 0x334) = uVar1;
  *(undefined4 *)(unaff_ESI + 0x338) = uVar2;
  fVar4 = *(float *)(iVar3 + 0x4741f8) * _DAT_00c1a568;
  FUN_00a74623();
  fVar5 = *(float *)(iVar3 + 0x4741fc) * _DAT_00c1a568;
  FUN_00a74623();
  if (fVar4 - fVar5 != 0.0) {
    fVar10 = _DAT_00d2b3c8 / (fVar4 - fVar5);
  }
  *(uint *)(unaff_ESI + 800) = (uint)(fVar5 * fVar10) ^ _DAT_00c4c6f0;
  *(float *)(unaff_ESI + 0x324) = fVar10;
  *(undefined4 *)(unaff_ESI + 0x328) = 0;
  *(undefined4 *)(unaff_ESI + 0x32c) = 0;
  *(undefined4 *)(unaff_ESI + 0x310) = *(undefined4 *)(iVar3 + 0x4741bc);
  *(undefined4 *)(unaff_ESI + 0x314) = *(undefined4 *)(iVar3 + 0x4741c0);
  *(undefined4 *)(unaff_ESI + 0x318) = *(undefined4 *)(iVar3 + 0x4741c4);
  *(undefined4 *)(unaff_ESI + 0x31c) = *(undefined4 *)(iVar3 + 0x4741c8);
  fVar10 = *(float *)(param_1 + 8);
  fVar4 = *(float *)(iVar3 + 0x4741d8);
  fVar5 = *(float *)(iVar3 + 0x4741d0);
  if (fVar5 == 0.0) {
    *(undefined4 *)(unaff_ESI + 0x2f0) = 0;
    *(undefined4 *)(unaff_ESI + 0x2f4) = 0;
    *(undefined4 *)(unaff_ESI + 0x2f8) = 0;
    *(undefined4 *)(unaff_ESI + 0x2fc) = 0;
    *(undefined4 *)(unaff_ESI + 0x300) = 0;
    *(undefined4 *)(unaff_ESI + 0x304) = 0;
    *(undefined4 *)(unaff_ESI + 0x308) = 0;
    *(undefined4 *)(unaff_ESI + 0x30c) = 0;
    return;
  }
  fStack_28 = *(float *)(iVar3 + 0x474200);
  if (fVar5 * _DAT_00c498d4 < *(float *)(iVar3 + 0x474200)) {
    fStack_28 = fVar5 * _DAT_00c498d4;
  }
  if (fStack_28 < fVar5) {
    fStack_28 = fVar5;
  }
  dVar8 = _DAT_00bd71f0;
  FUN_00a7bf79();
  fVar6 = (float)dVar8;
  fVar7 = fVar5 / fStack_28;
  FUN_00a7a386();
  fVar7 = fVar7 - *(float *)(iVar3 + 0x4741d4) * (fVar10 - fVar4) * fVar6;
  if (0.0 <= fVar7) {
    fStack_18 = fVar7 + _DAT_00d2b3c8;
  }
  else {
    fStack_18 = fVar7;
    FUN_00a7be22();
  }
  fStack_28 = (float)((uint)fStack_28 ^ _DAT_00c4c6f0);
  fVar10 = *(float *)(iVar3 + 0x4741cc);
  uVar9 = (uint)(*(float *)(iVar3 + 0x4741d4) * fVar6) ^ _DAT_00c4c6f0;
  if (0.0 < *(float *)(iVar3 + 0x4741d4)) {
    fStack_28 = fStack_28 * fVar6;
  }
  *(float *)(unaff_ESI + 0x2f0) = fVar7;
  *(float *)(unaff_ESI + 0x2f4) = fStack_28;
  *(float *)(unaff_ESI + 0x2f8) = fVar10 * fVar5;
  *(uint *)(unaff_ESI + 0x2fc) = uVar9;
  *(float *)(unaff_ESI + 0x300) = fStack_18;
  *(undefined4 *)(unaff_ESI + 0x304) = 0;
  *(undefined4 *)(unaff_ESI + 0x308) = 0;
  *(undefined4 *)(unaff_ESI + 0x30c) = 0;
  return;
}

