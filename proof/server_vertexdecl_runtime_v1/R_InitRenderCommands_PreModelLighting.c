
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl GenerateLightGridBasisDirs(void)

{
  code *pcVar1;
  float fVar2;
  float fVar3;
  bool bVar4;
  float *pfVar5;
  int iVar6;
  int iVar7;
  int iVar8;
  int iVar9;
  float fVar10;
  float fVar11;
  float fVar12;
  float fVar13;
  
  fVar3 = ___real_3f2aaaab;
  fVar2 = __real_3f800000;
  iVar7 = 0;
  iVar9 = 0;
  do {
    fVar13 = (float)iVar9 * fVar3 - fVar2;
    iVar8 = 0;
    do {
      fVar12 = (float)iVar8 * fVar3 - fVar2;
      iVar6 = 0;
      pfVar5 = (float *)((int)gridBasisDirs + iVar7 * 0xc + 8);
      do {
        if ((((1 < iVar6 - 1U) || (1 < iVar8 - 1U)) || (iVar9 < 1)) || (2 < iVar9)) {
          fVar10 = (float)iVar6 * fVar3 - fVar2;
          fVar11 = SQRT(fVar10 * fVar10 + fVar12 * fVar12 + fVar13 * fVar13);
          if (___real_00000000 <= (float)((uint)fVar11 ^ ___mask__NegFloat_)) {
            fVar11 = fVar2;
          }
          fVar11 = fVar2 / fVar11;
          pfVar5[-2] = fVar10 * fVar11;
          pfVar5[-1] = fVar12 * fVar11;
          *pfVar5 = fVar13 * fVar11;
          iVar7 = iVar7 + 1;
          pfVar5 = pfVar5 + 3;
        }
        iVar6 = iVar6 + 1;
      } while (iVar6 < 4);
      iVar8 = iVar8 + 1;
    } while (iVar8 < 4);
    iVar9 = iVar9 + 1;
  } while (iVar9 < 4);
  if ((iVar7 != 0x38) &&
     (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_pointlights.cpp",0x2d,1,
                               "(basisIndex == (6 * 4 * 4 - (6 * 2) * 4 + 8))",""), !bVar4)) {
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  return;
}

