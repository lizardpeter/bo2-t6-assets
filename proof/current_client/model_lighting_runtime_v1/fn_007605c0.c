
/* WARNING: Removing unreachable block (ram,0x007605dd) */
/* WARNING: Removing unreachable block (ram,0x0076061a) */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __fastcall FUN_007605c0(uint param_1,undefined4 *param_2,float *param_3)

{
  float fVar1;
  float fVar2;
  float fVar3;
  undefined4 *puVar4;
  uint uVar5;
  undefined4 *unaff_ESI;
  undefined4 *unaff_EDI;
  
  fVar3 = _DAT_00c519c8;
  uVar5 = (param_1 & 0xffff) - 1;
  fVar2 = ((float)(uVar5 >> 5 & 0x7fffffc) + _DAT_00d30a50) * _DAT_03a36a80;
  puVar4 = (undefined4 *)((uVar5 - _DAT_03a36a84) * 0x34 + _DAT_03a36aac);
  fVar1 = (float)puVar4[0xc];
  *param_3 = ((float)((uVar5 & 0x7f) * 4) + _DAT_00d30a50) * _DAT_00c38370;
  param_3[1] = fVar2;
  param_3[2] = fVar3;
  param_3[3] = fVar1;
  *unaff_EDI = *puVar4;
  unaff_EDI[1] = puVar4[1];
  unaff_EDI[2] = puVar4[2];
  unaff_EDI[3] = puVar4[3];
  *unaff_ESI = puVar4[4];
  unaff_ESI[1] = puVar4[5];
  unaff_ESI[2] = puVar4[6];
  unaff_ESI[3] = puVar4[7];
  *param_2 = puVar4[8];
  param_2[1] = puVar4[9];
  param_2[2] = puVar4[10];
  param_2[3] = puVar4[0xb];
  return;
}

