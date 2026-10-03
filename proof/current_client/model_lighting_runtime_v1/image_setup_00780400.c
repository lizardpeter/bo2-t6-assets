
void FUN_00780400(int param_1,uint param_2,undefined4 param_3,int param_4)

{
  int iVar1;
  undefined4 uVar2;
  undefined4 *puVar3;
  int iVar4;
  int iVar5;
  
  iVar4 = 0;
  puVar3 = (undefined4 *)(param_1 + 0xc);
  do {
    iVar5 = param_4;
    if ((param_2 & 1) == 0) {
      iVar1 = param_4 >> (*(byte *)(iVar4 + 8 + param_1) & 0x1f);
      iVar5 = 1;
      if (1 < iVar1) {
        iVar5 = iVar1;
      }
    }
    uVar2 = FUN_00780590(param_2,param_3,iVar5);
    *puVar3 = uVar2;
    iVar4 = iVar4 + 1;
    puVar3 = puVar3 + 1;
  } while (iVar4 < 2);
  return;
}

