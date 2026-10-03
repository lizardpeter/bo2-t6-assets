
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00761d10(void)

{
  int iVar1;
  uint uVar2;
  int iVar3;
  
  iVar3 = 0;
  uVar2 = 0x10;
  iVar1 = _DAT_035ae188;
  do {
    if (*(int *)(&DAT_03a385c0 + uVar2) != iVar1) {
      *(int *)(&DAT_03a385c0 + uVar2) = iVar1;
      (**(code **)(*_DAT_03a38610 + 0x20))(_DAT_03a38610,iVar3,1,iVar1);
      iVar1 = _DAT_035ae188;
    }
    if (((&DAT_03a38580)[iVar3] != '\x01') &&
       ((&DAT_03a38580)[iVar3] = 1, *(int *)(&DAT_03a38580 + uVar2) != 1)) {
      FUN_00740500(_DAT_03a38610,iVar3);
      iVar1 = _DAT_035ae188;
      *(undefined4 *)(&DAT_03a38580 + uVar2) = 1;
    }
    uVar2 = uVar2 + 4;
    iVar3 = iVar3 + 1;
  } while (uVar2 < 0x50);
  return;
}

