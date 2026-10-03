
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00761e10(float param_1,float param_2,float param_3,float param_4)

{
  undefined4 *puVar1;
  float *pfVar2;
  float fVar3;
  int unaff_ESI;
  
  FUN_00761da0();
  fVar3 = _DAT_00d2b3c8;
  puVar1 = *(undefined4 **)(unaff_ESI + 0x10);
  *puVar1 = 3;
  puVar1[1] = 0x20002;
  puVar1[2] = 0x10000;
  pfVar2 = *(float **)(unaff_ESI + 0x20);
  pfVar2[1] = param_2;
  *pfVar2 = param_1;
  pfVar2[2] = 0.0;
  pfVar2[3] = fVar3;
  pfVar2[4] = -NAN;
  pfVar2[7] = 1.9882659;
  pfVar2[5] = 0.0;
  pfVar2[6] = 0.0;
  pfVar2[9] = param_2;
  pfVar2[10] = 0.0;
  pfVar2[0xb] = fVar3;
  pfVar2[0xf] = 1.9882659;
  pfVar2[0xc] = -NAN;
  pfVar2[8] = param_1 + param_3;
  pfVar2[0xd] = fVar3;
  pfVar2[0xe] = 0.0;
  pfVar2[0x10] = param_1 + param_3;
  pfVar2[0x11] = param_2 + param_4;
  pfVar2[0x12] = 0.0;
  pfVar2[0x13] = fVar3;
  pfVar2[0x17] = 1.9882659;
  pfVar2[0x14] = -NAN;
  pfVar2[0x15] = fVar3;
  pfVar2[0x16] = fVar3;
  pfVar2[0x18] = param_1;
  pfVar2[0x19] = param_2 + param_4;
  pfVar2[0x1a] = 0.0;
  pfVar2[0x1b] = fVar3;
  pfVar2[0x1f] = 1.9882659;
  pfVar2[0x1c] = -NAN;
  pfVar2[0x1d] = 0.0;
  pfVar2[0x1e] = fVar3;
  if (*(int *)(unaff_ESI + 0x20) != 0) {
    FUN_0057a430(0x22);
    (**(code **)(*_DAT_035ae488 + 0x3c))(_DAT_035ae488,*(undefined4 *)(unaff_ESI + 0x1c),0);
    FUN_005262b0(0x22);
    *(undefined4 *)(unaff_ESI + 0x20) = 0;
  }
  *(undefined4 *)(unaff_ESI + 4) = 6;
  *(undefined4 *)(unaff_ESI + 0x14) = 0x80;
  return;
}

