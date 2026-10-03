
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

undefined4 __fastcall FUN_00762410(float *param_1,float *param_2,char *param_3)

{
  float fVar1;
  float *unaff_ESI;
  float fVar2;
  float fVar3;
  float fVar4;
  float fVar5;
  float fVar6;
  float fVar7;
  float fVar8;
  
  fVar1 = _DAT_00d2b3c8;
  fVar5 = *(float *)(param_3 + 0x1c) - *param_1;
  fVar6 = *(float *)(param_3 + 0x20) - param_1[1];
  fVar7 = *(float *)(param_3 + 0x24) - param_1[2];
  fVar8 = *(float *)(param_3 + 0x28);
  fVar2 = fVar6 * fVar6 + fVar5 * fVar5 + fVar7 * fVar7;
  if ((*param_3 != '\x05') && (_DAT_00c49fe8 < (double)*(float *)(param_3 + 0x2c))) {
    fVar8 = fVar8 / *(float *)(param_3 + 0x2c);
  }
  if ((fVar2 <= fVar8 * fVar8) && (fVar2 = SQRT(fVar2), _DAT_00c44e34 <= fVar2)) {
    fVar3 = _DAT_00d2b3c8 / fVar2;
    *param_2 = fVar5 * fVar3;
    param_2[1] = fVar6 * fVar3;
    param_2[2] = fVar7 * fVar3;
    fVar4 = fVar1;
    if (*param_3 != '\x05') {
      fVar5 = *(float *)(param_3 + 0x14) * fVar6 * fVar3 +
              *(float *)(param_3 + 0x10) * fVar5 * fVar3 +
              *(float *)(param_3 + 0x18) * fVar7 * fVar3;
      if (fVar5 <= *(float *)(param_3 + 0x2c)) {
        return 0;
      }
      if (fVar5 < *(float *)(param_3 + 0x30)) {
        fVar4 = (fVar5 - *(float *)(param_3 + 0x2c)) /
                (*(float *)(param_3 + 0x30) - *(float *)(param_3 + 0x2c));
      }
    }
    fVar2 = fVar2 / fVar8;
    fVar8 = fVar2;
    if (0.0 <= fVar2 - fVar1) {
      fVar8 = fVar1;
    }
    fVar5 = 0.0;
    if ((float)((uint)fVar2 ^ _DAT_00c4c6f0) < 0.0) {
      fVar5 = fVar8;
    }
    fVar4 = (fVar1 - fVar5) * (fVar1 - fVar5) * fVar4;
    *unaff_ESI = *(float *)(param_3 + 4) * fVar4;
    unaff_ESI[1] = *(float *)(param_3 + 8) * fVar4;
    unaff_ESI[2] = *(float *)(param_3 + 0xc) * fVar4;
    return 1;
  }
  return 0;
}

