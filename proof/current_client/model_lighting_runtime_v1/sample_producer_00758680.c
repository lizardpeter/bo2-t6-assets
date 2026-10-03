
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __thiscall FUN_00758680(float *param_1,undefined1 (*param_2) [16])

{
  float fVar1;
  float fVar2;
  float fVar3;
  float *in_EAX;
  undefined1 auVar4 [16];
  
  fVar1 = *param_1;
  fVar2 = param_1[1];
  fVar3 = param_1[2];
  auVar4._0_4_ = in_EAX[4] * fVar1 + *in_EAX + in_EAX[8] * fVar2 + in_EAX[0xc] * fVar3 +
                 fVar3 * fVar1 * in_EAX[0x10] + fVar3 * fVar2 * in_EAX[0x14] +
                 fVar2 * fVar1 * in_EAX[0x18] +
                 (fVar3 * fVar3 * _DAT_00d2bc30 - _DAT_00c82c30) * in_EAX[0x1c] +
                 (fVar1 * fVar1 - fVar2 * fVar2) * in_EAX[0x20];
  auVar4._4_4_ = in_EAX[5] * fVar1 + in_EAX[1] + in_EAX[9] * fVar2 + in_EAX[0xd] * fVar3 +
                 fVar3 * fVar1 * in_EAX[0x11] + fVar3 * fVar2 * in_EAX[0x15] +
                 fVar2 * fVar1 * in_EAX[0x19] +
                 (fVar3 * fVar3 * _UNK_00d2bc34 - _UNK_00c82c34) * in_EAX[0x1d] +
                 (fVar1 * fVar1 - fVar2 * fVar2) * in_EAX[0x21];
  auVar4._8_4_ = in_EAX[6] * fVar1 + in_EAX[2] + in_EAX[10] * fVar2 + in_EAX[0xe] * fVar3 +
                 fVar3 * fVar1 * in_EAX[0x12] + fVar3 * fVar2 * in_EAX[0x16] +
                 fVar2 * fVar1 * in_EAX[0x1a] +
                 (fVar3 * fVar3 * _UNK_00d2bc38 - _UNK_00c82c38) * in_EAX[0x1e] +
                 (fVar1 * fVar1 - fVar2 * fVar2) * in_EAX[0x22];
  auVar4._12_4_ =
       in_EAX[7] * fVar1 + in_EAX[3] + in_EAX[0xb] * fVar2 + in_EAX[0xf] * fVar3 +
       fVar3 * fVar1 * in_EAX[0x13] + fVar3 * fVar2 * in_EAX[0x17] + fVar2 * fVar1 * in_EAX[0x1b] +
       (fVar3 * fVar3 * _UNK_00d2bc3c - _UNK_00c82c3c) * in_EAX[0x1f] +
       (fVar1 * fVar1 - fVar2 * fVar2) * in_EAX[0x23];
  auVar4 = maxps(auVar4,_DAT_00c82c10);
  *param_2 = auVar4;
  return;
}

