
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00600c10(undefined4 param_1,float *param_2,undefined4 param_3,undefined4 param_4,
                 int param_5,undefined4 param_6,undefined4 param_7,int param_8,int param_9,
                 char param_10)

{
  float fVar1;
  float fVar2;
  int iVar3;
  int iVar4;
  int iVar5;
  undefined4 uVar6;
  int iVar7;
  float10 fVar8;
  float fVar9;
  float fVar10;
  float fVar11;
  float fVar12;
  float fVar13;
  float fVar14;
  float fVar15;
  
  uVar6 = FUN_006f6af0(param_1);
  iVar5 = _DAT_0113f18c;
  fVar1 = *(float *)(param_8 + 0x98);
  if ((param_9 != 0) && (*(float *)(param_5 + 0xc) != 0.0)) {
    iVar3 = *(int *)(_DAT_0113f18c + 0x81e5c);
    iVar4 = *(int *)(_DAT_0113f18c + 0x4808c);
    if (iVar3 == 0) {
      if (param_10 == '\x01') {
        return;
      }
    }
    else if ((float)iVar3 + _DAT_00c651dc < (float)iVar4) {
      *(undefined4 *)(_DAT_0113f18c + 0x81e60) = 0;
      *(undefined4 *)(iVar5 + 0x81e64) = 0;
    }
    fVar8 = (float10)FUN_00733f80(param_3,param_4);
    fVar2 = (float)fVar8;
    if (param_10 != '\0') {
      fVar12 = *(float *)(iVar5 + 0x81e60);
      fVar9 = (((float)iVar3 + _DAT_00c651dc) - (float)iVar4) * _DAT_00c4e018;
      fVar9 = fVar9 * fVar9;
      fVar10 = fVar9 * _DAT_00c2a108;
      if (fVar10 < fVar12) {
        *(float *)(iVar5 + 0x81e64) = fVar9 * _DAT_00bf8810;
      }
      if (fVar12 < (float)((uint)fVar10 ^ _DAT_00c4c6f0)) {
        *(float *)(iVar5 + 0x81e64) = fVar9 * _DAT_00c519c8;
      }
      *(float *)(iVar5 + 0x81e60) = *(float *)(iVar5 + 0x81e64) + fVar12;
    }
    iVar7 = FUN_00734020(param_1,param_9,0,param_3);
    fVar12 = *param_2;
    fVar9 = param_2[1];
    fVar10 = fVar9 + _DAT_00c498d4;
    if (((param_10 == '\0') || (iVar3 == 0)) || ((float)iVar3 + _DAT_00c651dc <= (float)iVar4)) {
      fVar15 = 0.0;
    }
    else {
      fVar15 = *(float *)(iVar5 + 0x81e60);
      fVar11 = fVar15 * _DAT_00c1a568;
      fVar13 = (float)((uint)fVar15 ^ _DAT_00c4c6f0) * _DAT_00c1a568;
      fVar9 = fVar11;
      FUN_00a74623();
      fVar14 = (_DAT_00c25a04 - fVar9) * (float)iVar7 * fVar2 * _DAT_00c519c8;
      fVar9 = fVar13;
      FUN_00a742c4();
      fVar12 = fVar14 + fVar12 + fVar9 * fVar10;
      FUN_00a742c4();
      fVar11 = fVar11 * (float)iVar7 * fVar2 * _DAT_00c519c8;
      fVar9 = param_2[1];
      FUN_00a74623();
      fVar9 = (fVar9 - fVar11) + (fVar13 * fVar10 - fVar10);
    }
    if (fVar1 != _DAT_00d2bf88) {
      FUN_0063a0e0(uVar6,param_9,0x100,param_3,fVar12,fVar9,fVar15,param_2[4],param_2[5],fVar2,fVar2
                   ,param_5,*(undefined1 *)(param_8 + 0x38),param_8 + 0x8c,0,0,0,0,0,0);
      return;
    }
    FUN_00633c10(uVar6,param_9,0x100,param_3,fVar12,fVar9,fVar15,param_2[4],param_2[5],fVar2,fVar2,
                 param_5,param_7);
  }
  return;
}

