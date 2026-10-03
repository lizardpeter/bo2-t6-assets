
void __fastcall FUN_00762280(int param_1)

{
  int in_EAX;
  float *pfVar1;
  float *pfVar2;
  int iVar3;
  
  pfVar1 = (float *)(in_EAX + 0x18);
  pfVar2 = (float *)(param_1 + 0x14);
  iVar3 = 7;
  do {
    pfVar1[-6] = pfVar2[-5] + pfVar1[-6];
    pfVar1[-5] = pfVar2[-4] + pfVar1[-5];
    pfVar1[-4] = pfVar2[-3] + pfVar1[-4];
    pfVar1[-2] = pfVar2[-2] + pfVar1[-2];
    pfVar1[-1] = pfVar2[-1] + pfVar1[-1];
    *pfVar1 = *pfVar2 + *pfVar1;
    pfVar1[2] = pfVar2[1] + pfVar1[2];
    pfVar1[3] = pfVar2[2] + pfVar1[3];
    pfVar1[4] = pfVar2[3] + pfVar1[4];
    pfVar1[6] = pfVar2[4] + pfVar1[6];
    pfVar1[7] = pfVar2[5] + pfVar1[7];
    pfVar1[8] = pfVar2[6] + pfVar1[8];
    pfVar1[10] = pfVar2[7] + pfVar1[10];
    pfVar1[0xb] = pfVar2[8] + pfVar1[0xb];
    pfVar1[0xc] = pfVar2[9] + pfVar1[0xc];
    pfVar1[0xe] = pfVar2[10] + pfVar1[0xe];
    pfVar1[0xf] = pfVar2[0xb] + pfVar1[0xf];
    pfVar1[0x10] = pfVar2[0xc] + pfVar1[0x10];
    pfVar1[0x12] = pfVar2[0xd] + pfVar1[0x12];
    pfVar1[0x13] = pfVar2[0xe] + pfVar1[0x13];
    pfVar1[0x14] = pfVar2[0xf] + pfVar1[0x14];
    pfVar1[0x16] = pfVar2[0x10] + pfVar1[0x16];
    pfVar1[0x17] = pfVar2[0x11] + pfVar1[0x17];
    pfVar1[0x18] = pfVar2[0x12] + pfVar1[0x18];
    pfVar2 = pfVar2 + 0x18;
    pfVar1 = pfVar1 + 0x20;
    iVar3 = iVar3 + -1;
  } while (iVar3 != 0);
  return;
}

