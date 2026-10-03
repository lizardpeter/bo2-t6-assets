
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_0075bd10(float *param_1,float param_2,float *param_3)

{
  float *pfVar1;
  float *pfVar2;
  float *pfVar3;
  float *pfVar4;
  float *pfVar5;
  float *pfVar6;
  float *pfVar7;
  float *pfVar8;
  byte bVar9;
  short *psVar10;
  uint uVar11;
  int iVar12;
  float *pfVar13;
  char *pcVar14;
  int iVar15;
  uint uVar16;
  uint uVar17;
  float fVar18;
  float fVar19;
  float fVar20;
  float fVar21;
  float fVar22;
  byte bStack_7f5;
  float fStack_7f4;
  float fStack_7f0;
  float fStack_7ec;
  float fStack_7e8;
  float fStack_7e4;
  undefined1 auStack_7e0 [4];
  undefined4 uStack_7dc;
  float afStack_7d8 [8];
  float afStack_7b8 [8];
  undefined4 auStack_798 [8];
  float afStack_778 [224];
  float afStack_3f8 [253];
  
  uVar17 = 0;
  uStack_7dc = 0;
  fStack_7e4 = 0.0;
  bStack_7f5 = FUN_0075b860(_DAT_035ae280 + 0x1d0,auStack_798,auStack_7e0);
  iVar15 = _DAT_035ae280;
  if (bStack_7f5 == 0xff) {
    bStack_7f5 = 1;
  }
  uVar16 = 0;
  do {
    psVar10 = *(short **)((int)auStack_798 + uVar16);
    if (psVar10 != (short *)0x0) {
      bVar9 = *(byte *)(psVar10 + 1);
      if ((bVar9 != 0) && ((bVar9 == bStack_7f5 || ((bStack_7f5 == 1 && (bVar9 == 0xff)))))) {
        fStack_7e4 = (float)*(byte *)((int)psVar10 + 3) * _DAT_00bd70f8 *
                     *(float *)((int)afStack_7b8 + uVar16) + fStack_7e4;
      }
      fVar18 = *(float *)((int)afStack_7b8 + uVar16);
      uVar11 = 0;
      if (uVar17 != 0) {
        do {
          if (*(short *)((int)&fStack_7f4 + uVar11 * 2) == *psVar10) {
            afStack_7d8[uVar11] = afStack_7d8[uVar11] + fVar18;
            goto LAB_0075bdef;
          }
          uVar11 = uVar11 + 1;
        } while (uVar11 < uVar17);
      }
      *(short *)((int)&fStack_7f4 + uVar17 * 2) = *psVar10;
      afStack_7d8[uVar17] = fVar18;
      uVar17 = uVar17 + 1;
    }
LAB_0075bdef:
    uVar16 = uVar16 + 4;
    if (0x1f < uVar16) {
      if (uVar17 == 0) {
        bStack_7f5 = FUN_0075b270(&fStack_7f4);
        iVar15 = _DAT_035ae280;
      }
      else {
        if (*(int *)(_DAT_035ae280 + 0x208) == 0) {
          FUN_007587f0();
        }
        else {
          FUN_00758720(afStack_778);
          iVar15 = _DAT_035ae280;
        }
        uVar16 = 1;
        if (1 < uVar17) {
          do {
            if (*(int *)(iVar15 + 0x208) == 0) {
              FUN_007587f0();
            }
            else {
              FUN_00758720(afStack_3f8);
              iVar15 = _DAT_035ae280;
            }
            iVar12 = 0;
            do {
              *(float *)((int)afStack_778 + iVar12) =
                   *(float *)((int)afStack_3f8 + iVar12) + *(float *)((int)afStack_778 + iVar12);
              *(float *)((int)afStack_778 + iVar12 + 4) =
                   *(float *)((int)afStack_3f8 + iVar12 + 4) +
                   *(float *)((int)afStack_778 + iVar12 + 4);
              *(float *)((int)afStack_778 + iVar12 + 8) =
                   *(float *)((int)afStack_3f8 + iVar12 + 8) +
                   *(float *)((int)afStack_778 + iVar12 + 8);
              *(float *)((int)afStack_778 + iVar12 + 0x10) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x10) +
                   *(float *)((int)afStack_778 + iVar12 + 0x10);
              *(float *)((int)afStack_778 + iVar12 + 0x14) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x14) +
                   *(float *)((int)afStack_778 + iVar12 + 0x14);
              *(float *)((int)afStack_778 + iVar12 + 0x18) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x18) +
                   *(float *)((int)afStack_778 + iVar12 + 0x18);
              *(float *)((int)afStack_778 + iVar12 + 0x20) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x20) +
                   *(float *)((int)afStack_778 + iVar12 + 0x20);
              *(float *)((int)afStack_778 + iVar12 + 0x24) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x24) +
                   *(float *)((int)afStack_778 + iVar12 + 0x24);
              *(float *)((int)afStack_778 + iVar12 + 0x28) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x28) +
                   *(float *)((int)afStack_778 + iVar12 + 0x28);
              *(float *)((int)afStack_778 + iVar12 + 0x30) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x30) +
                   *(float *)((int)afStack_778 + iVar12 + 0x30);
              *(float *)((int)afStack_778 + iVar12 + 0x34) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x34) +
                   *(float *)((int)afStack_778 + iVar12 + 0x34);
              *(float *)((int)afStack_778 + iVar12 + 0x38) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x38) +
                   *(float *)((int)afStack_778 + iVar12 + 0x38);
              *(float *)((int)afStack_778 + iVar12 + 0x40) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x40) +
                   *(float *)((int)afStack_778 + iVar12 + 0x40);
              *(float *)((int)afStack_778 + iVar12 + 0x44) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x44) +
                   *(float *)((int)afStack_778 + iVar12 + 0x44);
              *(float *)((int)afStack_778 + iVar12 + 0x48) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x48) +
                   *(float *)((int)afStack_778 + iVar12 + 0x48);
              *(float *)((int)afStack_778 + iVar12 + 0x50) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x50) +
                   *(float *)((int)afStack_778 + iVar12 + 0x50);
              *(float *)((int)afStack_778 + iVar12 + 0x54) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x54) +
                   *(float *)((int)afStack_778 + iVar12 + 0x54);
              *(float *)((int)afStack_778 + iVar12 + 0x58) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x58) +
                   *(float *)((int)afStack_778 + iVar12 + 0x58);
              *(float *)((int)afStack_778 + iVar12 + 0x60) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x60) +
                   *(float *)((int)afStack_778 + iVar12 + 0x60);
              *(float *)((int)afStack_778 + iVar12 + 100) =
                   *(float *)((int)afStack_3f8 + iVar12 + 100) +
                   *(float *)((int)afStack_778 + iVar12 + 100);
              *(float *)((int)afStack_778 + iVar12 + 0x68) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x68) +
                   *(float *)((int)afStack_778 + iVar12 + 0x68);
              *(float *)((int)afStack_778 + iVar12 + 0x70) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x70) +
                   *(float *)((int)afStack_778 + iVar12 + 0x70);
              *(float *)((int)afStack_778 + iVar12 + 0x74) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x74) +
                   *(float *)((int)afStack_778 + iVar12 + 0x74);
              *(float *)((int)afStack_778 + iVar12 + 0x78) =
                   *(float *)((int)afStack_3f8 + iVar12 + 0x78) +
                   *(float *)((int)afStack_778 + iVar12 + 0x78);
              iVar12 = iVar12 + 0x80;
            } while (iVar12 < 0x380);
            uVar16 = uVar16 + 1;
          } while (uVar16 < uVar17);
        }
        fStack_7f4 = 0.0;
        fStack_7f0 = 0.0;
        fStack_7ec = 0.0;
        pfVar13 = afStack_778 + 1;
        iVar12 = 7;
        do {
          pfVar1 = pfVar13 + 1;
          pfVar2 = pfVar13 + 5;
          pfVar3 = pfVar13 + 9;
          pfVar4 = pfVar13 + 0xd;
          pfVar5 = pfVar13 + 0x11;
          pfVar6 = pfVar13 + 0x15;
          pfVar7 = pfVar13 + 0x19;
          fStack_7f4 = pfVar13[0x1b] +
                       pfVar13[0x17] +
                       pfVar13[0x13] +
                       pfVar13[0xf] +
                       pfVar13[0xb] + pfVar13[7] + pfVar13[3] + pfVar13[-1] + fStack_7f4;
          fStack_7f0 = pfVar13[0x1c] +
                       pfVar13[0x18] +
                       pfVar13[0x14] +
                       pfVar13[0x10] +
                       pfVar13[0xc] + pfVar13[8] + pfVar13[4] + *pfVar13 + fStack_7f0;
          pfVar8 = pfVar13 + 0x1d;
          pfVar13 = pfVar13 + 0x20;
          iVar12 = iVar12 + -1;
          fStack_7ec = *pfVar8 + *pfVar7 + *pfVar6 + *pfVar5 + *pfVar4 + *pfVar3 + *pfVar2 + *pfVar1
                                                                                             + 
                                                  fStack_7ec;
        } while (iVar12 != 0);
        fStack_7f0 = fStack_7f0 * _DAT_00d33bb4;
        fStack_7f4 = fStack_7f4 * _DAT_00d33bb4;
        fStack_7ec = fStack_7ec * _DAT_00d33bb4;
        fStack_7e8 = fStack_7e4;
      }
      if (bStack_7f5 != 0) {
        if (bStack_7f5 != 1) {
          pcVar14 = (char *)((uint)bStack_7f5 * 0xc4 + _DAT_02560790);
          fVar20 = *(float *)(pcVar14 + 0x20) - *param_1;
          fVar21 = *(float *)(pcVar14 + 0x24) - param_1[1];
          fVar22 = *(float *)(pcVar14 + 0x28) - param_1[2];
          fVar18 = SQRT(fVar21 * fVar21 + fVar20 * fVar20 + fVar22 * fVar22) /
                   *(float *)(pcVar14 + 0x2c);
          if (0.0 <= fVar18 - _DAT_00d2b3c8) {
            fVar18 = _DAT_00d2b3c8;
          }
          fVar18 = (_DAT_00d2b3c8 - fVar18) * (_DAT_00d2b3c8 - fVar18);
          if (*pcVar14 == '\x02') {
            fVar19 = SQRT(fVar21 * fVar21 + fVar20 * fVar20 + fVar22 * fVar22);
            if (0.0 <= (float)((uint)fVar19 ^ _DAT_00c4c6f0)) {
              fVar19 = _DAT_00d2b3c8;
            }
            fVar19 = _DAT_00d2b3c8 / fVar19;
            fVar20 = *(float *)(pcVar14 + 0x18) * fVar21 * fVar19 +
                     *(float *)(pcVar14 + 0x14) * fVar20 * fVar19 +
                     *(float *)(pcVar14 + 0x1c) * fVar22 * fVar19;
            if (0.0 <= (float)((uint)fVar20 ^ _DAT_00c4c6f0)) {
              fVar20 = 0.0;
            }
            fVar21 = _DAT_00d2b3c8 / (*(float *)(pcVar14 + 0x34) - *(float *)(pcVar14 + 0x30));
            fVar20 = (float)((uint)(*(float *)(pcVar14 + 0x30) * fVar21) ^ _DAT_00c4c6f0) +
                     fVar21 * fVar20;
            if (0.0 <= (float)((uint)fVar20 ^ _DAT_00c4c6f0)) {
              fVar20 = 0.0;
            }
            if (0.0 <= fVar20 - _DAT_00d2b3c8) {
              fVar20 = _DAT_00d2b3c8;
            }
            fVar18 = fVar20 * fVar18;
          }
          param_2 = fVar18 * fStack_7e8 * param_2;
          *param_3 = *(float *)(pcVar14 + 0x50) * param_2 + fStack_7f4;
          param_3[1] = *(float *)(pcVar14 + 0x54) * param_2 + fStack_7f0;
          param_3[2] = *(float *)(pcVar14 + 0x58) * param_2 + fStack_7ec;
          return;
        }
        param_2 = *(float *)(iVar15 + 0x94) * fStack_7e8 * param_2;
        *param_3 = *(float *)(iVar15 + 0x88) * param_2 + fStack_7f4;
        param_3[1] = *(float *)(_DAT_035ae280 + 0x8c) * param_2 + fStack_7f0;
        param_3[2] = *(float *)(_DAT_035ae280 + 0x90) * param_2 + fStack_7ec;
        return;
      }
      *param_3 = fStack_7f4;
      param_3[1] = fStack_7f0;
      param_3[2] = fStack_7ec;
      return;
    }
  } while( true );
}

