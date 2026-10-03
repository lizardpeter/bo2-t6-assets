
void __fastcall FUN_00762060(int param_1,float *param_2)

{
  float *pfVar1;
  float *pfVar2;
  float *unaff_EDI;
  float fVar3;
  
  pfVar2 = (float *)&DAT_03a3e818;
  pfVar1 = (float *)(param_1 + 0x14);
  do {
    fVar3 = pfVar2[-1] * param_2[1] + pfVar2[-2] * *param_2 + param_2[2] * *pfVar2;
    if (0.0 < fVar3) {
      pfVar1[-5] = *unaff_EDI * fVar3 + pfVar1[-5];
      pfVar1[-4] = unaff_EDI[1] * fVar3 + pfVar1[-4];
      pfVar1[-3] = unaff_EDI[2] * fVar3 + pfVar1[-3];
    }
    fVar3 = pfVar2[2] * param_2[1] + pfVar2[1] * *param_2 +
            *(float *)((int)pfVar1 + ((int)&DAT_03a3e810 - param_1)) * param_2[2];
    if (0.0 < fVar3) {
      pfVar1[-2] = *unaff_EDI * fVar3 + pfVar1[-2];
      pfVar1[-1] = unaff_EDI[1] * fVar3 + pfVar1[-1];
      *pfVar1 = unaff_EDI[2] * fVar3 + *pfVar1;
    }
    fVar3 = *(float *)((int)pfVar1 + ((int)&DAT_03a3e818 - param_1)) * param_2[1] +
            *(float *)((int)pfVar1 + ((int)&DAT_03a3e814 - param_1)) * *param_2 +
            *(float *)((int)pfVar1 + ((int)&DAT_03a3e81c - param_1)) * param_2[2];
    if (0.0 < fVar3) {
      pfVar1[1] = *unaff_EDI * fVar3 + pfVar1[1];
      pfVar1[2] = unaff_EDI[1] * fVar3 + pfVar1[2];
      pfVar1[3] = unaff_EDI[2] * fVar3 + pfVar1[3];
    }
    fVar3 = *(float *)((int)pfVar1 + ((int)&DAT_03a3e824 - param_1)) * param_2[1] +
            *(float *)((int)pfVar1 + ((int)&DAT_03a3e820 - param_1)) * *param_2 +
            *(float *)((int)pfVar1 + ((int)&DAT_03a3e828 - param_1)) * param_2[2];
    if (0.0 < fVar3) {
      pfVar1[4] = *unaff_EDI * fVar3 + pfVar1[4];
      pfVar1[5] = unaff_EDI[1] * fVar3 + pfVar1[5];
      pfVar1[6] = unaff_EDI[2] * fVar3 + pfVar1[6];
    }
    pfVar2 = pfVar2 + 0xc;
    pfVar1 = pfVar1 + 0xc;
  } while ((int)pfVar2 < 0x3a3eab8);
  return;
}

