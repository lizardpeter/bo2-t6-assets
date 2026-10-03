
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

undefined4 FUN_00735630(void)

{
  int iVar1;
  undefined *puVar2;
  undefined4 *puVar3;
  undefined4 *puVar4;
  uint uVar5;
  undefined4 uStack_18;
  ulonglong auStack_14 [2];
  
  FUN_0075d9a0();
  FUN_007530c0();
  FUN_0075cc00();
  if (DAT_03a8e7a4 == '\0') {
    FUN_0070ff60();
    FUN_00761110();
  }
  FUN_0074cd50();
  if (DAT_03a8e7a4 == '\0') {
    FUN_0074cdb0();
  }
  _DAT_035e5f6c = 0;
  auStack_14[0] = 0;
  iVar1 = (**(code **)(*_DAT_035ae484 + 0x60))(_DAT_035ae484,auStack_14,&DAT_035e5fac);
  if (-1 < iVar1) {
    puVar2 = &DAT_035e5f4c;
    uVar5 = 0;
    while( true ) {
      iVar1 = (**(code **)(*_DAT_035ae484 + 0x60))(_DAT_035ae484,&stack0xffffffd8,puVar2);
      if (iVar1 < 0) break;
      uVar5 = uVar5 + 4;
      puVar2 = puVar2 + 4;
      if (0x1f < uVar5) {
        FUN_00753110();
        if (DAT_03a8e7a4 == '\0') {
          FUN_007714d0();
          FUN_0073adb0();
          puVar3 = (undefined4 *)&DAT_035a9310;
          do {
            uStack_18 = 1;
            auStack_14[0] = auStack_14[0] & 0xffffffff00000000;
            (**(code **)(*_DAT_035ae484 + 0x60))(_DAT_035ae484,&uStack_18,&stack0xffffffd8);
            puVar4 = puVar3 + 1;
            *puVar3 = 0;
            puVar3 = puVar4;
          } while ((int)puVar4 < 0x35a9320);
        }
        return 1;
      }
    }
  }
  return 0;
}

