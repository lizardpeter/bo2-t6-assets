
/* WARNING: Removing unreachable block (ram,0x007606b1) */
/* WARNING: Removing unreachable block (ram,0x007606d8) */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __thiscall FUN_00760690(float *param_1,byte param_2,undefined4 param_3,undefined4 *param_4)

{
  float fVar1;
  float fVar2;
  uint in_EAX;
  uint uVar3;
  undefined4 *unaff_ESI;
  undefined4 *unaff_EDI;
  undefined4 uStack_30;
  undefined4 uStack_2c;
  undefined4 uStack_28;
  undefined4 uStack_24;
  undefined4 uStack_20;
  undefined4 uStack_1c;
  undefined4 uStack_18;
  undefined4 uStack_14;
  undefined4 uStack_10;
  undefined4 uStack_c;
  undefined4 uStack_8;
  undefined4 uStack_4;
  
  fVar2 = _DAT_00c519c8;
  uVar3 = (in_EAX & 0xffff) - 1;
  fVar1 = ((float)(uVar3 >> 5 & 0x7fffffc) + _DAT_00d30a50) * _DAT_03a36a80;
  *param_1 = ((float)((uVar3 & 0x7f) * 4) + _DAT_00d30a50) * _DAT_00c38370;
  param_1[1] = fVar1;
  param_1[2] = fVar2;
  param_1[3] = (float)param_2 * _DAT_00bd70f8;
  FUN_007604f0();
  *param_4 = uStack_30;
  param_4[1] = uStack_2c;
  param_4[2] = uStack_28;
  param_4[3] = uStack_24;
  *unaff_EDI = uStack_20;
  unaff_EDI[1] = uStack_1c;
  unaff_EDI[2] = uStack_18;
  unaff_EDI[3] = uStack_14;
  *unaff_ESI = uStack_10;
  unaff_ESI[1] = uStack_c;
  unaff_ESI[2] = uStack_8;
  unaff_ESI[3] = uStack_4;
  return;
}

