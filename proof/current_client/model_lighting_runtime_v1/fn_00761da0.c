
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00761da0(int param_1)

{
  int iVar1;
  undefined4 uVar2;
  int *piVar3;
  undefined4 auStack_c [3];
  
  iVar1 = *(int *)(param_1 + 0x14);
  uVar2 = *(undefined4 *)(param_1 + 0x1c);
  FUN_0057a430(0x22);
  piVar3 = _DAT_035ae488;
  do {
    (**(code **)(*piVar3 + 0x38))(piVar3,uVar2,0,(iVar1 != 0) + '\x04',0,auStack_c);
  } while (_DAT_029e53c8 != 0);
  *(undefined4 *)(param_1 + 0x20) = auStack_c[0];
  FUN_005262b0();
  return;
}

