
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __fastcall FUN_007587f0(int param_1)

{
  byte bVar1;
  byte bVar2;
  float fVar3;
  float fVar4;
  int in_EAX;
  byte *pbVar5;
  float *pfVar6;
  int iVar7;
  float in_XMM0_Da;
  
  fVar4 = _DAT_00bfa448;
  fVar3 = _DAT_00bd70f8;
  pfVar6 = (float *)(param_1 + 8);
  pbVar5 = (byte *)(in_EAX + 2);
  iVar7 = 7;
  do {
    bVar1 = pbVar5[-1];
    bVar2 = *pbVar5;
    pfVar6[-2] = (float)pbVar5[-2] * fVar3 * (float)pbVar5[-2] * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[-1] = (float)bVar1 * fVar3 * (float)bVar1 * fVar3 * fVar4 * in_XMM0_Da;
    *pfVar6 = (float)bVar2 * fVar3 * (float)bVar2 * fVar3 * fVar4 * in_XMM0_Da;
    bVar1 = pbVar5[2];
    bVar2 = pbVar5[3];
    pfVar6[2] = (float)pbVar5[1] * fVar3 * (float)pbVar5[1] * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[3] = (float)bVar1 * fVar3 * (float)bVar1 * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[4] = (float)bVar2 * fVar3 * (float)bVar2 * fVar3 * fVar4 * in_XMM0_Da;
    bVar1 = pbVar5[5];
    bVar2 = pbVar5[6];
    pfVar6[6] = (float)pbVar5[4] * fVar3 * (float)pbVar5[4] * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[7] = (float)bVar1 * fVar3 * (float)bVar1 * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[8] = (float)bVar2 * fVar3 * (float)bVar2 * fVar3 * fVar4 * in_XMM0_Da;
    bVar1 = pbVar5[8];
    bVar2 = pbVar5[9];
    pfVar6[10] = (float)pbVar5[7] * fVar3 * (float)pbVar5[7] * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0xb] = (float)bVar1 * fVar3 * (float)bVar1 * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0xc] = (float)bVar2 * fVar3 * (float)bVar2 * fVar3 * fVar4 * in_XMM0_Da;
    bVar1 = pbVar5[0xb];
    bVar2 = pbVar5[0xc];
    pfVar6[0xe] = (float)pbVar5[10] * fVar3 * (float)pbVar5[10] * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0xf] = (float)bVar1 * fVar3 * (float)bVar1 * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0x10] = (float)bVar2 * fVar3 * (float)bVar2 * fVar3 * fVar4 * in_XMM0_Da;
    bVar1 = pbVar5[0xe];
    bVar2 = pbVar5[0xf];
    pfVar6[0x12] = (float)pbVar5[0xd] * fVar3 * (float)pbVar5[0xd] * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0x13] = (float)bVar1 * fVar3 * (float)bVar1 * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0x14] = (float)bVar2 * fVar3 * (float)bVar2 * fVar3 * fVar4 * in_XMM0_Da;
    bVar1 = pbVar5[0x11];
    bVar2 = pbVar5[0x12];
    pfVar6[0x16] = (float)pbVar5[0x10] * fVar3 * (float)pbVar5[0x10] * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0x17] = (float)bVar1 * fVar3 * (float)bVar1 * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0x18] = (float)bVar2 * fVar3 * (float)bVar2 * fVar3 * fVar4 * in_XMM0_Da;
    bVar1 = pbVar5[0x14];
    bVar2 = pbVar5[0x15];
    pfVar6[0x1a] = (float)pbVar5[0x13] * fVar3 * (float)pbVar5[0x13] * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0x1b] = (float)bVar1 * fVar3 * (float)bVar1 * fVar3 * fVar4 * in_XMM0_Da;
    pfVar6[0x1c] = (float)bVar2 * fVar3 * (float)bVar2 * fVar3 * fVar4 * in_XMM0_Da;
    pbVar5 = pbVar5 + 0x18;
    pfVar6 = pfVar6 + 0x20;
    iVar7 = iVar7 + -1;
  } while (iVar7 != 0);
  return;
}

