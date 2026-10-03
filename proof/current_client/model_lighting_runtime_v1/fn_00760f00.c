
/* WARNING: Removing unreachable block (ram,0x00760f13) */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00760f00(void)

{
  byte bVar1;
  undefined4 uVar2;
  int iVar3;
  uint uVar4;
  
  _DAT_03a36aa0 = 0x1000;
  for (uVar4 = 0x1f; 0x1000U >> uVar4 == 0; uVar4 = uVar4 - 1) {
  }
  iVar3 = 0x20 - (uVar4 ^ 0x1f);
  bVar1 = (byte)iVar3 & 0x1f;
  _DAT_03a36900 = (1 << ((byte)iVar3 & 0x1f)) - 0x1000;
  uVar4 = 1 << bVar1 | 1U >> 0x20 - bVar1;
  while (_DAT_03a36900 < 0x1000) {
    iVar3 = iVar3 + 1;
    _DAT_03a36900 = _DAT_03a36900 + uVar4;
    uVar4 = uVar4 << 1 | (uint)((int)uVar4 < 0);
  }
  _DAT_03a36a88 = 1 << ((byte)iVar3 & 0x1f);
  _DAT_03a36a8c = iVar3 + -7;
  _DAT_03a36a90 = 1 << ((byte)iVar3 - 5 & 0x1f);
  _DAT_03a36a80 = (float)_DAT_03a36a90;
  if (_DAT_03a36a90 < 0) {
    _DAT_03a36a80 = _DAT_03a36a80 + _DAT_00bfd8fc;
  }
  _DAT_03a36a80 = 1.0 / _DAT_03a36a80;
  _DAT_03a36ad0 = 0x200;
  _DAT_03a36ad4 = 0x80;
  _DAT_03a36a84 = _DAT_03a36900;
  _DAT_03a36aa8 = FUN_005f6970(0xc000);
  uVar4 = 0;
  do {
    uVar2 = FUN_005f6970(_DAT_03a36ad0);
    *(undefined4 *)(&DAT_03a36ab4 + uVar4) = uVar2;
    uVar4 = uVar4 + 4;
  } while (uVar4 < 0x10);
  _DAT_03a36aa4 = FUN_005f6970(_DAT_03a36aa0 * 4);
  _DAT_03a36aac = FUN_005f6970(_DAT_03a36aa0 * 0x34);
  return;
}

