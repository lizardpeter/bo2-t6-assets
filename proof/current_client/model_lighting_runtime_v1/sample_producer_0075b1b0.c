
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

undefined1
FUN_0075b1b0(undefined4 param_1,undefined4 param_2,undefined4 *param_3,undefined4 param_4,
            uint param_5)

{
  char cVar1;
  undefined1 *unaff_ESI;
  undefined1 uStack_d;
  uint auStack_c [2];
  
  if ((*(uint *)(unaff_ESI + 0x30) <= param_5) && (*(uint *)(unaff_ESI + 0x38) <= param_5)) {
    FUN_0075aee0(param_2,param_3,param_4);
    return 0;
  }
  uStack_d = *unaff_ESI;
  *param_3 = _DAT_00d2b3c8;
  auStack_c[0] = param_5 & 0xffff;
  cVar1 = FUN_0075b120(auStack_c,param_3,&uStack_d);
  if ((cVar1 == '\0') && (param_5 == 0)) {
    cVar1 = FUN_006226f0(_DAT_03434964);
    if (cVar1 != '\0') {
      FUN_0075b000(param_2,param_3,param_4);
      return 0;
    }
  }
  FUN_0075a3f0(param_1,param_2,param_4);
  return uStack_d;
}

