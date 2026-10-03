
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __thiscall FUN_00758720(undefined8 *param_1,int param_2)

{
  float fVar1;
  float fVar2;
  float fVar3;
  float fVar4;
  float fVar5;
  float fVar6;
  float fVar7;
  float fVar8;
  float fVar9;
  float fVar10;
  float fVar11;
  float fVar12;
  uint uVar13;
  uint uVar14;
  uint uVar15;
  uint uVar16;
  int in_EAX;
  float *pfVar17;
  int extraout_ECX;
  float *pfVar18;
  int extraout_EDX;
  int iVar19;
  uint uVar20;
  float fVar21;
  uint uVar22;
  float fVar23;
  float fVar24;
  float fVar25;
  float in_XMM2_Da;
  float afStack_a0 [39];
  
  uVar16 = uRam02a0fe2c;
  uVar15 = uRam02a0fe28;
  uVar14 = uRam02a0fe24;
  uVar13 = _DAT_02a0fe20;
  fVar12 = _UNK_00d2bc7c;
  fVar11 = _UNK_00d2bc78;
  fVar10 = _UNK_00d2bc74;
  fVar9 = _DAT_00d2bc70;
  fVar8 = _UNK_00d2bc6c;
  fVar7 = _UNK_00d2bc68;
  fVar6 = _UNK_00d2bc64;
  fVar5 = _DAT_00d2bc60;
  fVar4 = _UNK_00d2bc5c;
  fVar3 = _UNK_00d2bc58;
  fVar2 = _UNK_00d2bc54;
  fVar1 = _DAT_00d2bc50;
  pfVar18 = afStack_a0;
  pfVar17 = (float *)(in_EAX + 8);
  iVar19 = 9;
  do {
    uVar20 = (uint)*param_1;
    uVar22 = (uint)((ulonglong)*param_1 >> 0x20);
    fVar25 = (float)(int)(uVar22 & _UNK_00c3175c ^ _UNK_00c13fac) * _UNK_00c1992c + _UNK_00c56adc;
    fVar21 = (float)((uint)((float)((uint)((float)(int)(uVar20 & _DAT_00c31750 ^ _DAT_00c13fa0) *
                                           _DAT_00c19920 + _DAT_00c56ad0) & uVar13) * fVar1 * fVar5
                           + fVar9) & uVar13) * in_XMM2_Da;
    fVar23 = (float)((uint)((float)((uint)((float)(int)(uVar20 & _UNK_00c31758 ^ _UNK_00c13fa8) *
                                           _UNK_00c19928 + _UNK_00c56ad8) & uVar14) * fVar2 * fVar6
                           + fVar10) & uVar14) * in_XMM2_Da;
    fVar24 = (float)((uint)((float)((uint)((float)(int)(uVar22 & _UNK_00c31754 ^ _UNK_00c13fa4) *
                                           _UNK_00c19924 + _UNK_00c56ad4) & uVar15) * fVar3 * fVar7
                           + fVar11) & uVar15) * in_XMM2_Da;
    pfVar17[-2] = fVar21;
    *pfVar18 = fVar21;
    pfVar18[1] = fVar23;
    pfVar18[2] = fVar24;
    pfVar18[3] = (float)((uint)((float)((uint)fVar25 & uVar16) * fVar4 * fVar8 + fVar12) & uVar16) *
                 in_XMM2_Da;
    pfVar17[-1] = fVar23;
    *pfVar17 = fVar24;
    param_1 = (undefined8 *)((int)param_1 + 6);
    pfVar18 = pfVar18 + 4;
    pfVar17 = pfVar17 + 3;
    iVar19 = iVar19 + -1;
  } while (iVar19 != 0);
  do {
    FUN_00758680(param_2);
    param_2 = extraout_EDX + 0x10;
  } while (extraout_ECX + 0xc < 0x3a3eab0);
  return;
}

