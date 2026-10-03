
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

uint FUN_0075b270(float *param_1)

{
  float *pfVar1;
  float *pfVar2;
  float *pfVar3;
  float *pfVar4;
  float *pfVar5;
  float *pfVar6;
  float *pfVar7;
  float *pfVar8;
  char cVar9;
  undefined1 *in_EAX;
  uint uVar10;
  float *pfVar11;
  int iVar12;
  uint unaff_ESI;
  float fVar13;
  float fVar14;
  float fVar15;
  undefined1 uStack_3f9;
  uint uStack_3f8;
  float afStack_3f4 [29];
  undefined1 auStack_380 [4];
  float afStack_37c [223];
  
  if ((*(uint *)(in_EAX + 0x30) <= unaff_ESI) && (*(uint *)(in_EAX + 0x38) <= unaff_ESI)) {
    *param_1 = 0.0;
    param_1[1] = 0.0;
    param_1[2] = 0.0;
    param_1[3] = 0.0;
    return (uint)in_EAX & 0xffffff00;
  }
  uStack_3f9 = *in_EAX;
  uStack_3f8 = unaff_ESI & 0xffff;
  afStack_3f4[0] = _DAT_00d2b3c8;
  cVar9 = FUN_0075b120(&uStack_3f8,afStack_3f4,&uStack_3f9);
  if (((cVar9 == '\0') && (unaff_ESI == 0)) &&
     (uVar10 = FUN_006226f0(_DAT_03434964), fVar13 = _DAT_00c77ff4, (char)uVar10 != '\0')) {
    *param_1 = 0.0;
    param_1[2] = fVar13;
    param_1[1] = fVar13;
    param_1[3] = 0.0;
    return uVar10 & 0xffffff00;
  }
  if (*(int *)(_DAT_035ae280 + 0x208) == 0) {
    FUN_007587f0();
  }
  else {
    FUN_00758720(auStack_380);
  }
  fVar13 = 0.0;
  fVar14 = 0.0;
  fVar15 = 0.0;
  pfVar11 = afStack_37c;
  iVar12 = 7;
  do {
    pfVar1 = pfVar11 + 1;
    pfVar2 = pfVar11 + 5;
    pfVar3 = pfVar11 + 9;
    pfVar4 = pfVar11 + 0xd;
    pfVar5 = pfVar11 + 0x11;
    pfVar6 = pfVar11 + 0x15;
    fVar14 = pfVar11[0x17] +
             pfVar11[0x13] +
             pfVar11[0xf] + pfVar11[0xb] + pfVar11[7] + pfVar11[3] + pfVar11[-1] + fVar14 +
             pfVar11[0x1b];
    pfVar7 = pfVar11 + 0x19;
    fVar13 = pfVar11[0x1c] +
             pfVar11[0x18] +
             pfVar11[0x14] +
             pfVar11[0x10] + pfVar11[0xc] + pfVar11[8] + pfVar11[4] + fVar13 + *pfVar11;
    pfVar8 = pfVar11 + 0x1d;
    pfVar11 = pfVar11 + 0x20;
    iVar12 = iVar12 + -1;
    fVar15 = *pfVar8 + *pfVar7 + *pfVar6 + *pfVar5 + *pfVar4 + *pfVar3 + *pfVar2 + *pfVar1 + fVar15;
  } while (iVar12 != 0);
  fVar13 = fVar13 * _DAT_00d33bb4;
  fVar15 = fVar15 * _DAT_00d33bb4;
  *param_1 = fVar14 * _DAT_00d33bb4;
  param_1[2] = fVar15;
  param_1[1] = fVar13;
  param_1[3] = afStack_3f4[0];
  return CONCAT31((int3)((uint)pfVar11 >> 8),uStack_3f9);
}

