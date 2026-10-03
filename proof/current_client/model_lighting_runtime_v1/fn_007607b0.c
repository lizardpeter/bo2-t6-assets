
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

uint __thiscall FUN_007607b0(uint param_1,int param_2)

{
  int iVar1;
  uint uVar2;
  ushort uVar3;
  
  if (*(ushort *)(param_2 + 0x44) != 0) {
    iVar1 = *(ushort *)(param_2 + 0x44) - 1;
    *(int *)(&DAT_03a2f100 + iVar1 * 4) = _DAT_03a3690c;
    return CONCAT31((int3)((uint)iVar1 >> 8),1);
  }
  if (_DAT_03a36904 < _DAT_03a36900) {
    uVar3 = (short)_DAT_03a36904 + 1;
    uVar2 = _DAT_03a36904;
    _DAT_03a36904 = _DAT_03a36904 + 1;
  }
  else {
    uVar2 = 0;
    do {
      if (_DAT_03a36908 == 0) {
        return uVar2 & 0xffffff00;
      }
      _DAT_03a36908 = _DAT_03a36908 + -1;
      uVar3 = *(ushort *)(&DAT_03a27100 + _DAT_03a36908 * 2);
      uVar2 = uVar3 - 1;
    } while (_DAT_03a3690c == *(int *)(&DAT_03a2f100 + uVar2 * 4));
    *(undefined2 *)
     ((uint)*(ushort *)(&DAT_03a2b500 + uVar2 * 2) * 0x98 + 0x44 + *(int *)(_DAT_035ae280 + 0x36c))
         = 0;
  }
  *(ushort *)(param_2 + 0x44) = uVar3;
  *(short *)(&DAT_03a2b500 + uVar2 * 2) = (short)param_1;
  *(uint *)(&DAT_03a2ad00 + (param_1 >> 5) * 4) =
       *(uint *)(&DAT_03a2ad00 + (param_1 >> 5) * 4) | 0x80000000U >> ((byte)param_1 & 0x1f);
  _DAT_03a36910 = 1;
  *(int *)(&DAT_03a2f100 + uVar2 * 4) = _DAT_03a3690c;
  return CONCAT31((int3)(uVar2 >> 8),1);
}

