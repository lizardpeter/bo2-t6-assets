
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00762580(void)

{
  float fVar1;
  int in_EAX;
  float *pfVar2;
  int iVar3;
  undefined4 *puVar4;
  float10 fVar5;
  undefined4 uVar6;
  
  fVar5 = (float10)FUN_004645d0(_DAT_034347ac);
  fVar1 = (float)fVar5;
  pfVar2 = (float *)(in_EAX + 0x18);
  iVar3 = 7;
  do {
    pfVar2[-6] = pfVar2[-6] * fVar1;
    pfVar2[-5] = fVar1 * pfVar2[-5];
    pfVar2[-4] = pfVar2[-4] * fVar1;
    pfVar2[-2] = pfVar2[-2] * fVar1;
    pfVar2[-1] = pfVar2[-1] * fVar1;
    *pfVar2 = *pfVar2 * fVar1;
    pfVar2[2] = pfVar2[2] * fVar1;
    pfVar2[3] = fVar1 * pfVar2[3];
    pfVar2[4] = pfVar2[4] * fVar1;
    pfVar2[6] = fVar1 * pfVar2[6];
    pfVar2[7] = pfVar2[7] * fVar1;
    pfVar2[8] = pfVar2[8] * fVar1;
    pfVar2[10] = pfVar2[10] * fVar1;
    pfVar2[0xb] = fVar1 * pfVar2[0xb];
    pfVar2[0xc] = pfVar2[0xc] * fVar1;
    pfVar2[0xe] = pfVar2[0xe] * fVar1;
    pfVar2[0xf] = pfVar2[0xf] * fVar1;
    pfVar2[0x10] = pfVar2[0x10] * fVar1;
    pfVar2[0x12] = pfVar2[0x12] * fVar1;
    pfVar2[0x13] = fVar1 * pfVar2[0x13];
    pfVar2[0x14] = pfVar2[0x14] * fVar1;
    pfVar2[0x16] = fVar1 * pfVar2[0x16];
    pfVar2[0x17] = pfVar2[0x17] * fVar1;
    pfVar2[0x18] = pfVar2[0x18] * fVar1;
    pfVar2 = pfVar2 + 0x20;
    iVar3 = iVar3 + -1;
  } while (iVar3 != 0);
  FUN_004645d0(_DAT_034348a0);
  puVar4 = (undefined4 *)(in_EAX + 8);
  iVar3 = 0x38;
  do {
    uVar6 = puVar4[-2];
    FUN_00a7c19f();
    puVar4[-2] = uVar6;
    uVar6 = puVar4[-1];
    FUN_00a7c19f();
    puVar4[-1] = uVar6;
    uVar6 = *puVar4;
    FUN_00a7c19f();
    *puVar4 = uVar6;
    puVar4 = puVar4 + 4;
    iVar3 = iVar3 + -1;
  } while (iVar3 != 0);
  return;
}

