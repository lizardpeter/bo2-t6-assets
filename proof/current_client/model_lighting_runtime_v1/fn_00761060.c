
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00761060(void)

{
  undefined4 uVar1;
  int iVar2;
  int iVar3;
  uint uVar4;
  
  uVar4 = 0;
  do {
    _memset(*(void **)(&DAT_03a36ab4 + uVar4),0xff,_DAT_03a36ad0);
    uVar1 = _DAT_00c331a0;
    uVar4 = uVar4 + 4;
  } while (uVar4 < 0x10);
  uVar4 = 0;
  if (_DAT_03a36aa0 != 0) {
    iVar3 = 0;
    do {
      iVar2 = _DAT_03a36aa8;
      *(undefined4 *)(_DAT_03a36aa8 + iVar3) = uVar1;
      *(undefined4 *)(iVar2 + 4 + iVar3) = uVar1;
      *(undefined4 *)(iVar2 + 8 + iVar3) = uVar1;
      uVar4 = uVar4 + 1;
      iVar3 = iVar3 + 0xc;
    } while (uVar4 < _DAT_03a36aa0);
  }
  uVar4 = 0;
  if (_DAT_03a36904 == 0) {
    _DAT_03a36904 = 0;
    return;
  }
  do {
    iVar3 = uVar4 * 2;
    uVar4 = uVar4 + 1;
    *(undefined2 *)
     ((uint)*(ushort *)(&DAT_03a2b500 + iVar3) * 0x98 + 0x44 + *(int *)(_DAT_035ae280 + 0x36c)) = 0;
  } while (uVar4 < _DAT_03a36904);
  _DAT_03a36904 = 0;
  return;
}

