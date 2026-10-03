
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00761f50(void)

{
  float fVar1;
  float fVar2;
  float *pfVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  int iVar7;
  float fVar8;
  float fVar9;
  float fVar10;
  float fVar11;
  
  fVar2 = _DAT_00d2b3c8;
  fVar1 = _DAT_00bdbb58;
  iVar5 = 0;
  iVar7 = 0;
  do {
    fVar11 = (float)iVar7 * fVar1 - fVar2;
    iVar6 = 0;
    do {
      fVar10 = (float)iVar6 * fVar1 - fVar2;
      iVar4 = 0;
      pfVar3 = (float *)(&DAT_03a3e818 + iVar5 * 0xc);
      do {
        if ((((1 < iVar4 - 1U) || (1 < iVar6 - 1U)) || (iVar7 < 1)) || (2 < iVar7)) {
          fVar8 = (float)iVar4 * fVar1 - fVar2;
          fVar9 = SQRT(fVar8 * fVar8 + fVar10 * fVar10 + fVar11 * fVar11);
          if (_DAT_00d2bf88 <= (float)((uint)fVar9 ^ _DAT_00c4c6f0)) {
            fVar9 = fVar2;
          }
          fVar9 = fVar2 / fVar9;
          pfVar3[-2] = fVar8 * fVar9;
          pfVar3[-1] = fVar10 * fVar9;
          *pfVar3 = fVar11 * fVar9;
          iVar5 = iVar5 + 1;
          pfVar3 = pfVar3 + 3;
        }
        iVar4 = iVar4 + 1;
      } while (iVar4 < 4);
      iVar6 = iVar6 + 1;
    } while (iVar6 < 4);
    iVar7 = iVar7 + 1;
  } while (iVar7 < 4);
  return;
}

