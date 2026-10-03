
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __fastcall
FUN_0075a3f0(undefined4 param_1,int param_2,undefined4 param_3,undefined2 param_4,float *param_5)

{
  uint *puVar1;
  uint uVar2;
  float fVar3;
  float fVar4;
  int iVar5;
  undefined4 *puVar6;
  undefined4 *_Dst;
  float fVar7;
  float fVar8;
  float fVar9;
  float fStack_3f8;
  float fStack_3f4;
  float fStack_3f0;
  float fStack_3ec;
  float fStack_3e8;
  float fStack_3e4;
  float fStack_3e0;
  float fStack_3dc;
  float fStack_3d8;
  float fStack_3d4;
  float fStack_3d0;
  float fStack_3cc;
  float fStack_3c8;
  float fStack_3c4;
  float fStack_3c0;
  float fStack_3bc;
  float fStack_3b8;
  float fStack_3b4;
  float fStack_3b0;
  float fStack_3ac;
  float fStack_3a8;
  float fStack_3a4;
  float fStack_3a0;
  float fStack_39c;
  float fStack_398;
  float fStack_394;
  float fStack_390;
  undefined4 auStack_388 [225];
  
  if (*(int *)(param_2 + 0x38) == 0) {
    FUN_007587f0();
    _memset(param_5,0,0x30);
  }
  else {
    fVar9 = _DAT_00d2b3c8;
    FUN_00758720(auStack_388);
    fVar4 = _DAT_00c519c8;
    fVar3 = _DAT_00bda7c8;
    fVar7 = fStack_3f4 * _DAT_00c519c8 + fStack_3f8 * _DAT_00bda7c8 + fStack_3f0 * _DAT_00bda7c8 +
            _DAT_00c5040c;
    fVar8 = fStack_3a0 * _DAT_00c519c8 + fStack_3a4 * _DAT_00bda7c8 + fStack_39c * _DAT_00bda7c8;
    fVar9 = fVar9 / fVar7;
    param_5[2] = fVar9 * fStack_3f0;
    param_5[3] = fVar8 * _DAT_00c557d0;
    *param_5 = fVar9 * fStack_3f8;
    param_5[1] = fVar9 * fStack_3f4;
    param_5[4] = fStack_3e8 * fVar4 + fStack_3ec * fVar3 + fStack_3e4 * fVar3;
    param_5[7] = fVar7 - fVar8;
    param_5[5] = fStack_3dc * fVar4 + fStack_3e0 * fVar3 + fStack_3d8 * fVar3;
    param_5[6] = fStack_3d0 * fVar4 + fStack_3d4 * fVar3 + fStack_3cc * fVar3;
    param_5[8] = fStack_3c4 * fVar4 + fStack_3c8 * fVar3 + fStack_3c0 * fVar3;
    param_5[9] = fStack_3b8 * fVar4 + fStack_3bc * fVar3 + fStack_3b4 * fVar3;
    param_5[10] = fStack_3ac * fVar4 + fStack_3b0 * fVar3 + fStack_3a8 * fVar3;
    param_5[0xb] = fStack_394 * fVar4 + fStack_398 * fVar3 + fStack_390 * fVar3;
  }
  FUN_00762770(auStack_388,param_3);
  iVar5 = _DAT_0341d400;
  puVar1 = (uint *)(_DAT_0341d400 + 0x462c68);
  LOCK();
  uVar2 = *puVar1;
  *puVar1 = *puVar1 + 1;
  UNLOCK();
  if (0xfff < uVar2) {
    FUN_0058fc30(0,"modelLightingPatchList ran out of elements.");
  }
  _Dst = (undefined4 *)(uVar2 * 900 + 0xdec68 + iVar5);
  _memset(_Dst,0,900);
  *(undefined2 *)_Dst = param_4;
  puVar6 = auStack_388;
  for (iVar5 = 0xe0; _Dst = _Dst + 1, iVar5 != 0; iVar5 = iVar5 + -1) {
    *_Dst = *puVar6;
    puVar6 = puVar6 + 1;
  }
  return;
}

