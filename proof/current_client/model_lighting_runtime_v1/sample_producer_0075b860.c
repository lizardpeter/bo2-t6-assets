
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

char __thiscall FUN_0075b860(float *param_1,int param_2,void *param_3,undefined4 *param_4)

{
  undefined4 *puVar1;
  undefined4 uVar2;
  bool bVar3;
  float *in_EAX;
  int iVar4;
  char cVar5;
  uint uVar6;
  float fVar7;
  float fVar8;
  float fVar9;
  float fVar10;
  float fVar11;
  float fVar12;
  float fVar13;
  float fVar14;
  float fVar15;
  char cStack_2a;
  float fStack_20;
  float fStack_1c;
  float fStack_18;
  int aiStack_14 [4];
  
  fVar7 = *in_EAX;
  fVar8 = (float)(_DAT_00c59da4 & (uint)fVar7);
  fVar9 = (float)((uint)_DAT_00bd1200 & -(uint)((float)((uint)fVar7 ^ (uint)fVar8) < _DAT_00bd1200)
                 | (uint)fVar8);
  fVar9 = (fVar7 + fVar9) - fVar9;
  fVar14 = in_EAX[1];
  fVar10 = (float)(_DAT_00c59da4 & (uint)fVar14);
  fVar11 = (float)((uint)_DAT_00bd1200 &
                   -(uint)((float)((uint)fVar14 ^ (uint)fVar10) < _DAT_00bd1200) | (uint)fVar10);
  fVar11 = (fVar14 + fVar11) - fVar11;
  fVar15 = in_EAX[2];
  fVar12 = (float)(_DAT_00c59da4 & (uint)fVar15);
  fVar13 = (float)((uint)_DAT_00bd1200 &
                   -(uint)((float)((uint)fVar15 ^ (uint)fVar12) < _DAT_00bd1200) | (uint)fVar12);
  fVar13 = (fVar15 + fVar13) - fVar13;
  aiStack_14[0] =
       (int)(fVar9 - (float)(-(uint)(fVar8 < fVar9 - fVar7) & (uint)_DAT_00d2b3c8)) + 0x20000 >> 5;
  aiStack_14[1] =
       (int)(fVar11 - (float)(-(uint)(fVar10 < fVar11 - fVar14) & (uint)_DAT_00d2b3c8)) + 0x20000 >>
       5;
  aiStack_14[2] =
       (int)(fVar13 - (float)(-(uint)(fVar12 < fVar13 - fVar15) & (uint)_DAT_00d2b3c8)) + 0x20000 >>
       6;
  fStack_20 = (float)aiStack_14[*(int *)(param_2 + 0x14)];
  if (aiStack_14[*(int *)(param_2 + 0x14)] < 0) {
    fStack_20 = fStack_20 + _DAT_00bfd8fc;
  }
  iVar4 = *(int *)(param_2 + 0x18);
  fStack_20 = (in_EAX[*(int *)(param_2 + 0x14)] - _DAT_00c58510) * _DAT_00c6982c - fStack_20;
  fStack_1c = (float)aiStack_14[iVar4];
  if (aiStack_14[iVar4] < 0) {
    fStack_1c = fStack_1c + _DAT_00bfd8fc;
  }
  fStack_1c = (in_EAX[iVar4] - _DAT_00c58510) * _DAT_00c6982c - fStack_1c;
  fStack_18 = (float)aiStack_14[2];
  if (aiStack_14[2] < 0) {
    fStack_18 = fStack_18 + _DAT_00bfd8fc;
  }
  fStack_18 = (fVar15 - _DAT_00c58510) * _DAT_00c216b4 - fStack_18;
  fVar14 = _DAT_00d2b3c8 - fStack_18;
  fVar11 = (_DAT_00d2b3c8 - fStack_1c) * fVar14;
  fVar7 = _DAT_00d2b3c8 - fStack_20;
  fVar15 = (_DAT_00d2b3c8 - fStack_1c) * fStack_18;
  param_1[4] = fVar11 * fStack_20;
  param_1[5] = fVar15 * fStack_20;
  fVar14 = fVar14 * fStack_1c;
  *param_1 = fVar7 * fVar11;
  param_1[1] = fVar7 * fVar15;
  param_1[2] = fVar7 * fVar14;
  param_1[6] = fVar14 * fStack_20;
  param_1[3] = fVar7 * fStack_18 * fStack_1c;
  param_1[7] = fStack_18 * fStack_1c * fStack_20;
  *param_4 = 1;
  FUN_0075b4b0(param_2,aiStack_14,param_3,param_4);
  aiStack_14[*(int *)(param_2 + 0x14)] = aiStack_14[*(int *)(param_2 + 0x14)] + 1;
  FUN_0075b4b0(param_2,aiStack_14,(int)param_3 + 0x10,param_4);
  aiStack_14[*(int *)(param_2 + 0x14)] = aiStack_14[*(int *)(param_2 + 0x14)] + -1;
  fVar7 = 0.0;
  cVar5 = '\0';
  bVar3 = false;
  uVar6 = 0;
  iVar4 = (int)param_3 - (int)param_1;
  do {
    puVar1 = *(undefined4 **)(iVar4 + (int)param_1);
    if (puVar1 != (undefined4 *)0x0) {
      fVar14 = *param_1;
      if (_DAT_00c44e34 <= fVar14) {
        uVar2 = *puVar1;
        *(undefined1 *)((int)&fStack_20 + uVar6) = 0;
        cStack_2a = (char)((uint)uVar2 >> 0x10);
        if (bVar3) {
          if ((cVar5 == '\0') ||
             ((cStack_2a != '\0' && ((cVar5 == -1 || ((cStack_2a != -1 && (fVar7 < fVar14)))))))) {
            fVar7 = fVar14;
            cVar5 = cStack_2a;
          }
        }
        else {
          _memset(param_3,0,uVar6 * 4);
          bVar3 = true;
          fVar7 = fVar14;
          cVar5 = cStack_2a;
        }
      }
      else {
        *(undefined4 *)(iVar4 + (int)param_1) = 0;
      }
    }
    uVar6 = uVar6 + 1;
    param_1 = param_1 + 1;
  } while (uVar6 < 8);
  return cVar5;
}

