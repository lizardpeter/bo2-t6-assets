
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00780ad0(undefined2 param_1,undefined2 param_2,undefined2 param_3,uint param_4,
                 undefined4 param_5,undefined4 param_6)

{
  undefined4 uVar1;
  char cVar2;
  int in_EAX;
  uint uVar3;
  
  *(undefined2 *)(in_EAX + 0x14) = param_1;
  uVar1 = _DAT_0343486c;
  *(undefined2 *)(in_EAX + 0x16) = param_2;
  *(undefined2 *)(in_EAX + 0x18) = param_3;
  uVar3 = param_4 >> 1 & 1;
  cVar2 = FUN_006226f0(uVar1);
  if (cVar2 != '\0') {
    if ((param_4 & 4) == 0) {
      if ((param_4 & 8) == 0) {
        FUN_0074efa0(*(undefined2 *)(in_EAX + 0x14),*(undefined2 *)(in_EAX + 0x16),uVar3,param_4,
                     param_6);
      }
      else {
        FUN_0074f170(*(undefined2 *)(in_EAX + 0x14),param_5,param_6);
      }
    }
    else {
      FUN_0074f260(uVar3,param_5,param_6);
    }
    FUN_00780400();
  }
  return;
}

