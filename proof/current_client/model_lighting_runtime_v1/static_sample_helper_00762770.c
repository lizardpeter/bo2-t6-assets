
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00762770(undefined4 param_1,float *param_2)

{
  float fVar1;
  float fVar2;
  float fVar3;
  int iVar4;
  bool bVar5;
  char cVar6;
  float *pfVar7;
  int iVar8;
  int iVar9;
  int iStack_328;
  float afStack_324 [32];
  undefined1 auStack_2a4 [676];
  
  cVar6 = FUN_006226f0(_DAT_034348d0);
  if ((cVar6 != '\0') && (param_2 != (float *)0x0)) {
    cVar6 = FUN_006226f0(_DAT_03434a1c);
    if (cVar6 != '\0') {
      FUN_00762580();
    }
    _DAT_03a8e7c4 = *(int *)(_DAT_035ae280 + 0x3ec);
    _DAT_03a8e7c8 = *(int *)(_DAT_035ae280 + 0x3f0);
    _DAT_03a8e7cc = *(int *)(_DAT_035ae280 + 0x3f4);
    _DAT_03a8e7d0 = *(int *)(_DAT_035ae280 + 0x3f8);
    if (_DAT_03a8e7c4 != 0) {
      afStack_324[0] = 0.0;
      if (_DAT_03a8e7c8 == 0) {
        afStack_324[0] = -NAN;
      }
      bVar5 = false;
      iVar8 = 1;
      do {
        iVar4 = (&iStack_328)[iVar8];
        iVar9 = iVar8 + -1;
        if (iVar4 < 0) {
          cVar6 = FUN_00762410(_DAT_03a8e7cc + (iVar4 + 1) * -0x38);
          if (cVar6 != '\0') {
            if (!bVar5) {
              bVar5 = true;
              _memset(auStack_2a4,0,0x2a0);
            }
            FUN_00762060();
          }
        }
        else {
          fVar1 = *param_2;
          pfVar7 = (float *)(iVar4 * 0x20 + _DAT_03a8e7d0);
          if ((((*pfVar7 <= fVar1) && (fVar2 = param_2[1], pfVar7[1] <= fVar2)) &&
              (fVar3 = param_2[2], pfVar7[2] <= fVar3)) &&
             (((fVar1 < pfVar7[3] || fVar1 == pfVar7[3] && (fVar2 < pfVar7[4] || fVar2 == pfVar7[4])
               ) && (fVar3 < pfVar7[5] || fVar3 == pfVar7[5])))) {
            if (pfVar7[6] != 0.0) {
              afStack_324[iVar9] = pfVar7[6];
              iVar9 = iVar8;
            }
            if (pfVar7[7] != 0.0) {
              afStack_324[iVar9] = pfVar7[7];
              iVar9 = iVar9 + 1;
            }
          }
        }
        iVar8 = iVar9;
      } while (iVar9 != 0);
      if (bVar5) {
        FUN_00762280();
      }
    }
  }
  return;
}

