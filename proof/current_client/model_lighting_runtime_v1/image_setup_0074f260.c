
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_0074f260(undefined4 param_1,undefined4 param_2,undefined4 param_3)

{
  int unaff_ESI;
  ushort unaff_DI;
  int *piStack_64;
  undefined4 uStack_60;
  undefined1 auStack_5c [12];
  undefined8 uStack_50;
  uint uStack_3c;
  uint uStack_38;
  undefined4 uStack_34;
  undefined4 uStack_30;
  undefined4 uStack_2c;
  undefined4 uStack_28;
  undefined4 uStack_24;
  undefined4 uStack_20;
  undefined4 uStack_1c;
  undefined4 uStack_14;
  
  *(ushort *)(unaff_ESI + 0x14) = unaff_DI;
  *(ushort *)(unaff_ESI + 0x16) = unaff_DI;
  *(undefined2 *)(unaff_ESI + 0x18) = 1;
  *(undefined1 *)(unaff_ESI + 4) = 5;
  _memset(&uStack_3c,0,0x2c);
  uStack_3c = (uint)unaff_DI;
  uStack_34 = param_1;
  uStack_30 = 6;
  uStack_2c = param_2;
  uStack_28 = 1;
  uStack_24 = 0;
  uStack_20 = 0;
  uStack_1c = 8;
  uStack_14 = 4;
  uStack_38 = uStack_3c;
  do {
    (**(code **)(*_DAT_035ae484 + 0x14))(_DAT_035ae484,&uStack_3c,param_3,&piStack_64);
  } while (_DAT_029e53c8 != 0);
  uStack_50 = 0;
  auStack_5c = SUB1612((undefined1  [16])0x0,4);
  auStack_5c._0_4_ = 9;
  uStack_60 = uStack_2c;
  auStack_5c._8_4_ = 0xffffffff;
  do {
    (**(code **)(*_DAT_035ae484 + 0x1c))(_DAT_035ae484,piStack_64,&uStack_60);
  } while (_DAT_029e53c8 != 0);
  (**(code **)(*piStack_64 + 8))(piStack_64);
  return;
}

