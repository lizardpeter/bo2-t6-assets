
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __thiscall
FUN_0074f170(undefined2 param_1,ushort param_2,undefined4 param_3,undefined4 param_4)

{
  undefined2 in_AX;
  int unaff_ESI;
  undefined4 unaff_EDI;
  int *piStack_64;
  undefined4 uStack_60;
  undefined4 uStack_5c;
  undefined1 auStack_40 [12];
  
  *(ushort *)(unaff_ESI + 0x14) = param_2;
  auStack_40._2_2_ = 0;
  auStack_40._0_2_ = param_2;
  *(undefined2 *)(unaff_ESI + 0x16) = param_1;
  *(undefined2 *)(unaff_ESI + 0x18) = in_AX;
  *(undefined1 *)(unaff_ESI + 4) = 4;
  auStack_40._4_2_ = param_1;
  auStack_40._6_2_ = 0;
  auStack_40._8_2_ = in_AX;
  auStack_40._10_2_ = 0;
  stack0xffffffcc = unaff_EDI;
  do {
    (**(code **)(*_DAT_035ae484 + 0x18))(_DAT_035ae484,auStack_40,param_4,&piStack_64);
  } while (_DAT_029e53c8 != 0);
  _uStack_5c = SUB1612((undefined1  [16])0x0,4);
  uStack_5c = 8;
  uStack_60 = param_3;
  stack0xffffffac = unaff_EDI;
  do {
    (**(code **)(*_DAT_035ae484 + 0x1c))(_DAT_035ae484,piStack_64,&uStack_60);
  } while (_DAT_029e53c8 != 0);
  (**(code **)(*piStack_64 + 8))(piStack_64);
  return;
}

