
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_0075aee0(undefined2 param_1,undefined4 *param_2,undefined4 *param_3)

{
  uint *puVar1;
  uint uVar2;
  undefined4 uVar3;
  undefined4 *puVar4;
  int iVar5;
  int iVar6;
  undefined4 *puVar7;
  undefined4 auStack_380 [224];
  
  _memset(auStack_380,0,0x380);
  iVar6 = _DAT_0341d400;
  puVar4 = auStack_380 + 1;
  iVar5 = 0x38;
  do {
    puVar4[-1] = 0;
    *puVar4 = 0;
    puVar4[1] = 0;
    puVar4 = puVar4 + 4;
    iVar5 = iVar5 + -1;
  } while (iVar5 != 0);
  puVar1 = (uint *)(_DAT_0341d400 + 0x462c68);
  LOCK();
  uVar2 = *puVar1;
  *puVar1 = *puVar1 + 1;
  UNLOCK();
  if (0xfff < uVar2) {
    FUN_0058fc30(0,"modelLightingPatchList ran out of elements.");
  }
  puVar4 = (undefined4 *)(uVar2 * 900 + 0xdec68 + iVar6);
  _memset(puVar4,0,900);
  *(undefined2 *)puVar4 = param_1;
  puVar7 = auStack_380;
  for (iVar6 = 0xe0; puVar4 = puVar4 + 1, iVar6 != 0; iVar6 = iVar6 + -1) {
    *puVar4 = *puVar7;
    puVar7 = puVar7 + 1;
  }
  if (param_2 != (undefined4 *)0x0) {
    *param_2 = 0;
  }
  uVar3 = _DAT_00d2b3c8;
  if (param_3 != (undefined4 *)0x0) {
    *param_3 = _DAT_00d2b3c8;
    param_3[1] = uVar3;
    param_3[2] = uVar3;
    param_3[3] = 0;
    param_3[4] = 0;
    param_3[5] = 0;
    param_3[6] = 0;
    param_3[7] = uVar3;
    param_3[8] = 0;
    param_3[9] = 0;
    param_3[10] = 0;
    param_3[0xb] = 0;
  }
  return;
}

