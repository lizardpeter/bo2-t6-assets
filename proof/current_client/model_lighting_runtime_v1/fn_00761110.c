
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00761110(void)

{
  int iVar1;
  undefined *puVar2;
  undefined4 uStack_40;
  undefined4 uStack_3c;
  undefined4 uStack_38;
  undefined4 uStack_34;
  undefined1 auStack_30 [12];
  undefined4 uStack_24;
  undefined4 uStack_20;
  
  _DAT_03a252a0 = PTR_s__model_lighting_010642d4;
  _DAT_03a2525d = 0x401;
  DAT_03a25263 = 0;
  iVar1 = FUN_0074ef50();
  *(undefined **)(&DAT_03a22850 + iVar1 * 4) = &DAT_03a25258;
  _DAT_03a36a9c = &DAT_03a25258;
  FUN_00780ad0(0x200,_DAT_03a36a90,4,10,0x1c,0);
  uStack_20 = 0;
  uStack_3c = _DAT_03a36a90;
  uStack_40 = 0x200;
  uStack_38 = 4;
  uStack_34 = 1;
  stack0xffffffd4 = SUB1612((undefined1  [16])0x0,4);
  auStack_30._0_8_ = 0x30000001c;
  uStack_24 = 0x10000;
  puVar2 = &DAT_03a36ae4;
  do {
    do {
      (**(code **)(*_DAT_035ae484 + 0x18))(_DAT_035ae484,&uStack_40,0,puVar2);
    } while (_DAT_029e53c8 != 0);
    puVar2 = puVar2 + 4;
  } while ((int)puVar2 < 0x3a36aec);
  _DAT_03a36ae0 = 0;
  return;
}

