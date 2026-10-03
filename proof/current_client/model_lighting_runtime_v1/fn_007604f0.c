
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __fastcall FUN_007604f0(undefined8 *param_1)

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
  float *in_EAX;
  uint uVar13;
  uint uVar14;
  float fVar15;
  float fVar16;
  float fVar17;
  
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
  uVar13 = (uint)*param_1;
  uVar14 = (uint)((ulonglong)*param_1 >> 0x20);
  fVar15 = ((float)(int)(uVar13 & _UNK_00c31758 ^ _UNK_00c13fa8) * _UNK_00c19928 + _UNK_00c56ad8) *
           _UNK_00d2bc54 * _UNK_00d2bc64 + _UNK_00d2bc74;
  fVar16 = ((float)(int)(uVar14 & _UNK_00c31754 ^ _UNK_00c13fa4) * _UNK_00c19924 + _UNK_00c56ad4) *
           _UNK_00d2bc58 * _UNK_00d2bc68 + _UNK_00d2bc78;
  fVar17 = ((float)(int)(uVar14 & _UNK_00c3175c ^ _UNK_00c13fac) * _UNK_00c1992c + _UNK_00c56adc) *
           _UNK_00d2bc5c * _UNK_00d2bc6c + _UNK_00d2bc7c;
  *in_EAX = ((float)(int)(uVar13 & _DAT_00c31750 ^ _DAT_00c13fa0) * _DAT_00c19920 + _DAT_00c56ad0) *
            _DAT_00d2bc50 * _DAT_00d2bc60 + _DAT_00d2bc70;
  in_EAX[1] = fVar15;
  in_EAX[2] = fVar16;
  in_EAX[3] = fVar17;
  uVar13 = (uint)param_1[1];
  uVar14 = (uint)((ulonglong)param_1[1] >> 0x20);
  fVar15 = (float)(int)(uVar14 & _UNK_00c31754 ^ _UNK_00c13fa4) * _UNK_00c19924 + _UNK_00c56ad4;
  fVar16 = (float)(int)(uVar13 & _UNK_00c31758 ^ _UNK_00c13fa8) * _UNK_00c19928 + _UNK_00c56ad8;
  fVar17 = (float)(int)(uVar14 & _UNK_00c3175c ^ _UNK_00c13fac) * _UNK_00c1992c + _UNK_00c56adc;
  in_EAX[4] = ((float)(int)(uVar13 & _DAT_00c31750 ^ _DAT_00c13fa0) * _DAT_00c19920 + _DAT_00c56ad0)
              * fVar1 * fVar5 + fVar9;
  in_EAX[5] = fVar16 * fVar2 * fVar6 + fVar10;
  in_EAX[6] = fVar15 * fVar3 * fVar7 + fVar11;
  in_EAX[7] = fVar17 * fVar4 * fVar8 + fVar12;
  uVar13 = (uint)param_1[2];
  uVar14 = (uint)((ulonglong)param_1[2] >> 0x20);
  fVar15 = (float)(int)(uVar14 & _UNK_00c31754 ^ _UNK_00c13fa4) * _UNK_00c19924 + _UNK_00c56ad4;
  fVar16 = (float)(int)(uVar13 & _UNK_00c31758 ^ _UNK_00c13fa8) * _UNK_00c19928 + _UNK_00c56ad8;
  fVar17 = (float)(int)(uVar14 & _UNK_00c3175c ^ _UNK_00c13fac) * _UNK_00c1992c + _UNK_00c56adc;
  in_EAX[8] = ((float)(int)(uVar13 & _DAT_00c31750 ^ _DAT_00c13fa0) * _DAT_00c19920 + _DAT_00c56ad0)
              * fVar1 * fVar5 + fVar9;
  in_EAX[9] = fVar16 * fVar2 * fVar6 + fVar10;
  in_EAX[10] = fVar15 * fVar3 * fVar7 + fVar11;
  in_EAX[0xb] = fVar17 * fVar4 * fVar8 + fVar12;
  return;
}

