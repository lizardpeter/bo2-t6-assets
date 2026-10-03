
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_007585e0(uint *param_1)

{
  float *in_EAX;
  float fVar1;
  float fVar2;
  float fVar3;
  
  fVar1 = *in_EAX;
  if (_DAT_00bfa448 < *in_EAX) {
    fVar1 = _DAT_00bfa448;
  }
  fVar3 = in_EAX[1];
  if (_DAT_00bfa448 < in_EAX[1]) {
    fVar3 = _DAT_00bfa448;
  }
  fVar2 = in_EAX[2];
  if (_DAT_00bfa448 < in_EAX[2]) {
    fVar2 = _DAT_00bfa448;
  }
  *param_1 = (((int)(SQRT(fVar2 * _DAT_00c6982c) * _DAT_00c0faec) & 0xffU | 0xffffff00) << 8 |
             (int)(SQRT(fVar3 * _DAT_00c6982c) * _DAT_00c0faec) & 0xffU) << 8 |
             (int)(SQRT(fVar1 * _DAT_00c6982c) * _DAT_00c0faec) & 0xffU;
  return;
}

