
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_0074efa0(ushort param_1,ushort param_2,undefined4 param_3,uint param_4,undefined4 param_5)

{
  byte bVar1;
  undefined1 auVar2 [12];
  int unaff_ESI;
  int unaff_EDI;
  int *piStack_64;
  int iStack_60;
  undefined1 auStack_5c [12];
  undefined8 uStack_50;
  uint uStack_3c;
  uint uStack_38;
  undefined4 uStack_34;
  undefined4 uStack_30;
  int iVar3;
  
  if (((param_4 & 0x40000) == 0) || (bVar1 = 1, _DAT_035e5f78 < 2)) {
    bVar1 = 0;
  }
  *(ushort *)(unaff_ESI + 0x14) = param_1;
  *(ushort *)(unaff_ESI + 0x16) = param_2;
  *(undefined2 *)(unaff_ESI + 0x18) = 1;
  *(undefined1 *)(unaff_ESI + 4) = 3;
  _memset(&uStack_3c,0,0x2c);
  uStack_3c = (uint)param_1;
  uStack_38 = (uint)param_2;
  uStack_34 = param_3;
  uStack_30 = 1;
  if (unaff_EDI == 0x28) {
    iVar3 = 0x27;
  }
  else if (unaff_EDI == 0x2d) {
    iVar3 = 0x2c;
  }
  else {
    iVar3 = 0x13;
    if (unaff_EDI != 0x14) {
      iVar3 = unaff_EDI;
    }
  }
  do {
    (**(code **)(*_DAT_035ae484 + 0x14))(_DAT_035ae484,&uStack_3c,param_5,&piStack_64);
  } while (_DAT_029e53c8 != 0);
  uStack_50 = 0;
  if (unaff_EDI == 0x28) {
    auStack_5c = SUB1612((undefined1  [16])0x0,4);
    iStack_60 = 0x29;
  }
  else {
    auStack_5c = SUB1612((undefined1  [16])0x0,4);
    if (unaff_EDI == 0x2d) {
      iStack_60 = 0x2e;
    }
    else if (unaff_EDI == 0x14) {
      iStack_60 = 0x15;
    }
    else if (unaff_EDI == 0x1b) {
      iStack_60 = 0x1c;
    }
    else {
      iStack_60 = iVar3;
    }
  }
  auVar2 = _iStack_60;
  auStack_5c._8_4_ = 0xffffffff;
  iStack_60 = auVar2._0_4_;
  auStack_5c._0_4_ = (uint)bVar1 * 2 + 4;
  do {
    (**(code **)(*_DAT_035ae484 + 0x1c))(_DAT_035ae484,piStack_64,&iStack_60);
  } while (_DAT_029e53c8 != 0);
  (**(code **)(*piStack_64 + 8))(piStack_64);
  return;
}

