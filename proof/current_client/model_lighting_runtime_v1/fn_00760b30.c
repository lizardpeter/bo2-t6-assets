
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00760b30(void)

{
  uint uVar1;
  
  _DAT_03a3690c = _DAT_03a3690c + 1;
  _DAT_03a36a98 = _DAT_03a36a98 + 1 & 3;
  _DAT_03a36ab0 = 0;
  _DAT_03a36ac4 = *(undefined4 *)(&DAT_03a36ab4 + (_DAT_03a36a98 - 2 & 3) * 4);
  _DAT_03a36ac8 = *(undefined4 *)(&DAT_03a36ab4 + (_DAT_03a36a98 - 1 & 3) * 4);
  _DAT_03a36acc = *(void **)(&DAT_03a36ab4 + _DAT_03a36a98 * 4);
  _memset(_DAT_03a36acc,0xff,_DAT_03a36ad0);
  uVar1 = 0;
  _DAT_03a36908 = 0;
  if (_DAT_03a36904 != 0) {
    do {
      if (3 < (uint)(_DAT_03a3690c - *(int *)(&DAT_03a2f100 + uVar1 * 4))) {
        *(short *)(&DAT_03a27100 + _DAT_03a36908 * 2) = (short)uVar1 + 1;
        _DAT_03a36908 = _DAT_03a36908 + 1;
      }
      uVar1 = uVar1 + 1;
    } while (uVar1 < _DAT_03a36904);
  }
  return;
}

