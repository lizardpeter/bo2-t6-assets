
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __thiscall FUN_006bab90(int *param_1,int param_2,char param_3)

{
  float fVar1;
  float fVar2;
  float fVar3;
  float fVar4;
  float fVar5;
  ulonglong uVar6;
  undefined8 uVar7;
  undefined8 uVar8;
  undefined8 uVar9;
  undefined4 *puVar10;
  int iVar11;
  float *pfVar12;
  int iVar13;
  byte bVar14;
  int iVar15;
  float10 fVar16;
  float fVar17;
  uint uVar18;
  float fVar19;
  uint uVar20;
  float fVar21;
  undefined8 uStack_110;
  undefined8 uStack_108;
  int *piStack_f8;
  float fStack_f4;
  undefined8 uStack_f0;
  undefined8 uStack_e8;
  float *pfStack_e0;
  undefined4 *puStack_dc;
  float fStack_d8;
  float fStack_d4;
  undefined8 uStack_d0;
  undefined8 uStack_c8;
  float fStack_c0;
  float fStack_bc;
  float fStack_b8;
  float fStack_a8;
  float fStack_a4;
  float fStack_a0;
  float fStack_9c;
  float fStack_98;
  undefined1 auStack_90 [64];
  undefined1 auStack_50 [76];
  
  if (param_2 != 0) {
    param_1[0x88] = param_2;
  }
  if ((*(byte *)(param_1 + 0x9b) & 1) != 0) {
    FUN_0046e7e0();
    return;
  }
  iVar15 = param_1[0x88];
  if (*(float *)(iVar15 + 0x78) == _DAT_00d2bf88) {
    FUN_004aafa0(&uStack_110,&uStack_d0);
    uStack_f0 = CONCAT44(uStack_110._4_4_,(float)uStack_f0);
    fVar21 = (float)uStack_d0;
    fVar17 = uStack_d0._4_4_;
    fVar19 = (float)uStack_c8;
    fVar1 = (float)uStack_108;
  }
  else {
    uStack_110._0_4_ = *(float *)(iVar15 + 0x78);
    fVar21 = *(float *)(iVar15 + 0x84);
    fVar17 = *(float *)(iVar15 + 0x88);
    fVar19 = *(float *)(iVar15 + 0x8c);
    uStack_f0 = CONCAT44(*(undefined4 *)(iVar15 + 0x7c),(float)uStack_f0);
    fVar1 = *(float *)(iVar15 + 0x80);
  }
  uStack_e8 = CONCAT44(uStack_e8._4_4_,fVar1);
  fStack_9c = fVar17 - uStack_f0._4_4_;
  fStack_98 = fVar19 - fVar1;
  uStack_110._4_4_ = (fVar17 + uStack_f0._4_4_) * _DAT_00c519c8;
  fStack_a0 = fVar21 - (float)uStack_110;
  uStack_110._0_4_ = (fVar21 + (float)uStack_110) * _DAT_00c519c8;
  uStack_108._0_4_ = (fVar19 + fVar1) * _DAT_00c519c8;
  FUN_00a0b9d0(&fStack_a0,&fStack_c0,&fStack_a8);
  iVar15 = param_1[0x88];
  fStack_a8 = *(float *)(iVar15 + 0x40) / fStack_a8;
  fStack_c0 = fStack_a8 * fStack_c0;
  fStack_bc = fStack_bc * fStack_a8;
  fStack_b8 = fStack_b8 * fStack_a8;
  uStack_110 = CONCAT44(*(float *)(iVar15 + 0x94) + uStack_110._4_4_,
                        (float)uStack_110 + *(float *)(iVar15 + 0x90));
  puVar10 = *(undefined4 **)*param_1;
  uStack_108 = CONCAT44(uStack_108._4_4_,*(float *)(iVar15 + 0x98) + (float)uStack_108);
  puStack_dc = puVar10;
  FUN_006c4a30(auStack_50,puVar10 + 0xc,(undefined4 *)*param_1 + 8);
  iVar15 = *param_1;
  uVar18 = (uint)uStack_110._4_4_ ^ _DAT_00c4c6f0;
  uVar20 = (uint)(float)uStack_108 ^ _DAT_00c4c6f0;
  *(uint *)(iVar15 + 0x50) = (uint)(float)uStack_110 ^ _DAT_00c4c6f0;
  *(uint *)(iVar15 + 0x54) = uVar18;
  *(uint *)(iVar15 + 0x58) = uVar20;
  FUN_0063ac40(auStack_90,*param_1 + 0x20);
  FUN_006c4a30(puVar10 + 0xc,auStack_50,auStack_90);
  *puVar10 = puVar10[0x18];
  puVar10[1] = puVar10[0x19];
  puVar10[2] = puVar10[0x1a];
  iVar15 = param_1[0x97];
  fVar21 = _DAT_00d6774c;
  if ((*(short *)(iVar15 + 0x24) != 6) &&
     (((*(short *)(iVar15 + 4) == 2 || (*(short *)(iVar15 + 0x24) == 4)) ||
      (fVar21 = _DAT_00c6c564, *(int *)(iVar15 + 0x4b4) != 0)))) {
    fVar21 = *(float *)(iVar15 + 0x124) * _DAT_00c1a568;
  }
  puVar10[0x3d] = fVar21;
  FUN_00a0a780(*(undefined4 *)(param_1[0x88] + 0x40));
  FUN_00a0a730(&fStack_c0);
  piStack_f8 = param_1 + 0x101;
  pfStack_e0 = (float *)(param_1 + 0x22);
  fStack_a4 = SQRT(((float)param_1[0x20] - (float)param_1[0x40]) *
                   ((float)param_1[0x20] - (float)param_1[0x40]) +
                   ((float)param_1[0x21] - (float)param_1[0x41]) *
                   ((float)param_1[0x21] - (float)param_1[0x41]) +
                   ((float)param_1[0x22] - (float)param_1[0x42]) *
                   ((float)param_1[0x22] - (float)param_1[0x42]));
  iVar15 = 0;
  do {
    if (pfStack_e0[-1] == _DAT_00d2bf88) {
      *piStack_f8 = 0;
    }
    else {
      if (param_3 == '\0') {
        iVar13 = *piStack_f8;
      }
      else {
        iVar13 = FUN_00a06140(puStack_dc,0,1);
        *piStack_f8 = iVar13;
      }
      uVar6 = *(ulonglong *)(*param_1 + 0x50);
      uStack_e8 = *(ulonglong *)(*param_1 + 0x58);
      uStack_f0._0_4_ = (float)uVar6;
      uStack_f0._4_4_ = (float)(uVar6 >> 0x20);
      iVar11 = param_1[0x88];
      fVar17 = (float)((uint)(pfStack_e0[-2] + (float)uStack_f0) & _DAT_00c1b5a0) / fStack_a4;
      uStack_110 = CONCAT44(uStack_f0._4_4_ + pfStack_e0[-1],pfStack_e0[-2] + (float)uStack_f0);
      uStack_108 = CONCAT44((int)((ulonglong)uStack_108 >> 0x20),
                            (((float)uStack_e8 + *pfStack_e0) - *(float *)(iVar11 + 0x24)) +
                            *(float *)(iVar11 + 0x18));
      fVar21 = fVar17;
      if (0.0 <= fVar17 - _DAT_00c25a04) {
        fVar21 = _DAT_00c25a04;
      }
      if (0.0 <= (float)((uint)fVar17 ^ _DAT_00c4c6f0)) {
        fVar21 = 0.0;
      }
      fStack_d4 = (_DAT_00c25a04 - fVar21) * _DAT_00d30a50;
      fStack_f4 = *(float *)(iVar11 + 0x40);
      uStack_f0 = uVar6;
      fVar16 = (float10)FUN_004645d0(_DAT_02be2dfc);
      fStack_d8 = (float)fVar16;
      iVar11 = param_1[0x88];
      uStack_d0 = 0;
      uStack_c8 = CONCAT44(uStack_c8._4_4_,_DAT_00be7bf4);
      fVar21 = *(float *)(iVar11 + 0xec);
      if (*(float *)(iVar11 + 0xec) == 0.0) {
        fVar21 = _DAT_00c331a0;
      }
      fVar17 = *(float *)(iVar11 + 0x48);
      if (fVar17 <= 0.0) {
        fVar17 = *(float *)(iVar11 + 0x44);
      }
      FUN_00a09780(&uStack_110,&uStack_d0,&DAT_00d67700,*(undefined4 *)(iVar11 + 0x18),
                   *(float *)(iVar11 + 0x30) * (_DAT_00c25a04 / fStack_d8),
                   *(float *)(iVar11 + 0x34) * (_DAT_00c25a04 / fStack_d8),
                   *(float *)(iVar11 + 0x1c) * fStack_d8 * fStack_d4 * fStack_f4,
                   *(float *)(iVar11 + 0x20) * fStack_d8 * fStack_d4 * fStack_f4,
                   *(undefined4 *)(iVar11 + 0x28),*(undefined4 *)(iVar11 + 0x44),fVar17,fVar21);
      if ((((*(short *)(param_1[0x97] + 4) == 2) || (*(int *)(param_1[0x97] + 0x4b4) != 0)) ||
          ((iVar15 == 0 || ((iVar15 == 1 || (iVar15 == 4)))))) || (iVar15 == 5)) {
        *(uint *)(iVar13 + 0xb0) = *(uint *)(iVar13 + 0xb0) | 8;
      }
      else {
        *(uint *)(iVar13 + 0xb0) = *(uint *)(iVar13 + 0xb0) & 0xfffffff7;
      }
      if (*(short *)(param_1[0x97] + 0x24) == 6) {
        *(uint *)(iVar13 + 0xb0) = *(uint *)(iVar13 + 0xb0) | 0x80;
      }
      if ((iVar15 == 2) || (iVar15 == 3)) {
        *(uint *)(iVar13 + 0xb0) = *(uint *)(iVar13 + 0xb0) | 0x20;
      }
      else {
        *(uint *)(iVar13 + 0xb0) = *(uint *)(iVar13 + 0xb0) & 0xffffffdf;
      }
      *(uint *)(iVar13 + 0xb0) = *(uint *)(iVar13 + 0xb0) | 0x40;
      iVar11 = *(int *)(param_1[0x88] + 0x70);
      uVar18 = *(uint *)(iVar13 + 0xb0);
      if (iVar11 == 0) {
        if ((iVar15 == 0) || (iVar15 == 1)) {
          uVar18 = uVar18 | 0x10;
        }
        else {
LAB_006bb182:
          uVar18 = uVar18 & 0xffffffef;
        }
      }
      else if (iVar11 == 1) {
        if ((iVar15 != 2) && (iVar15 != 3)) goto LAB_006bb182;
        uVar18 = uVar18 | 0x10;
      }
      else {
        if (iVar11 != 2) goto LAB_006bb18b;
        uVar18 = uVar18 | 0x10;
      }
      *(uint *)(iVar13 + 0xb0) = uVar18;
    }
LAB_006bb18b:
    fVar21 = _DAT_00c519c8;
    pfStack_e0 = pfStack_e0 + 0x10;
    iVar15 = iVar15 + 1;
    piStack_f8 = piStack_f8 + 1;
    if (5 < iVar15) {
      iVar15 = param_1[0x97];
      if ((*(short *)(iVar15 + 4) == 4) && (param_1[0x101] == 0)) {
        uStack_f0 = uStack_f0 & 0xffffffff;
        uStack_e8 = uStack_e8 & 0xffffffff00000000;
        fVar17 = _DAT_00bcd654;
        fStack_f4 = _DAT_00c498d4;
      }
      else {
        uVar7 = *(undefined8 *)(param_1[0x102] + 0x30);
        uVar8 = *(undefined8 *)(param_1[0x101] + 0x30);
        uVar9 = *(undefined8 *)(param_1[0x101] + 0x38);
        uStack_f0._4_4_ = (float)((ulonglong)uVar8 >> 0x20);
        uStack_110._4_4_ = (float)((ulonglong)uVar7 >> 0x20);
        uStack_f0._4_4_ = uStack_f0._4_4_ + uStack_110._4_4_;
        uStack_110._0_4_ = (float)uVar7;
        uStack_f0._0_4_ = (float)uVar8;
        uStack_e8._0_4_ = (float)uVar9;
        uStack_108._0_4_ = (float)*(undefined8 *)(param_1[0x102] + 0x38);
        uStack_e8._0_4_ = (float)uStack_e8 + (float)uStack_108;
        fVar17 = ((float)uStack_110 + (float)uStack_f0) * _DAT_00c519c8;
        uStack_d0 = *(undefined8 *)(param_1[0x104] + 0x30);
        uStack_c8 = *(undefined8 *)(param_1[0x104] + 0x38);
        uStack_110 = *(undefined8 *)(param_1[0x103] + 0x30);
        uStack_108 = *(undefined8 *)(param_1[0x103] + 0x38);
        uStack_f0 = CONCAT44(uStack_f0._4_4_ * _DAT_00c519c8,(float)uStack_f0);
        uStack_e8._4_4_ = (undefined4)((ulonglong)uVar9 >> 0x20);
        uStack_e8 = CONCAT44(uStack_e8._4_4_,(float)uStack_e8 * _DAT_00c519c8);
        fStack_f4 = fVar17 - ((float)uStack_d0 + (float)uStack_110) * _DAT_00c519c8;
      }
      bVar14 = *(byte *)((int)param_1 + 0x26e) & 1;
      pfVar12 = (float *)param_1[0x88];
      fVar19 = pfVar12[1];
      if (bVar14 != 0) {
        fVar19 = (float)*(int *)(iVar15 + 0x43c) * fVar19;
      }
      piStack_f8 = (int *)*pfVar12;
      if (bVar14 != 0) {
        piStack_f8 = (int *)(*(float *)(iVar15 + 0x444) * (float)piStack_f8);
      }
      fVar1 = pfVar12[0x10];
      fVar2 = pfVar12[6];
      fVar3 = pfVar12[0x19];
      fStack_d4 = pfVar12[3];
      fStack_d8 = pfVar12[5];
      fVar4 = pfVar12[0x18];
      fVar5 = pfVar12[0x1a];
      param_1[0x107] = (int)piStack_f8;
      param_1[0x10c] = (int)fVar2;
      param_1[0x10e] = (int)fStack_d4;
      param_1[0x10f] = (int)fStack_d8;
      param_1[0x109] = (int)(fVar5 * fVar1);
      param_1[0x10a] = (int)(fVar3 * fVar1);
      param_1[0x108] = (int)(fVar1 * fVar19);
      param_1[0x10b] = (int)(fVar4 * fVar1);
      param_1[0x111] = (int)uStack_f0._4_4_;
      param_1[0x112] = (int)(float)uStack_e8;
      param_1[0x110] = (int)fVar17;
      param_1[0x114] = (int)fStack_f4;
      fStack_f4 = fStack_f4 * fVar21;
      fVar21 = (float)param_1[0x10e];
      param_1[0x116] = 0;
      param_1[0x8f] = 0;
      FUN_00a7477a();
      fVar17 = 0.0;
      param_1[0x115] = (int)(fStack_f4 / fVar21);
      if (fStack_f4 / fVar21 < 0.0) {
        param_1[0x115] = 0;
      }
      if (param_1[0x99] != 0) {
        *(float *)(param_1[0x99] + 0x24) =
             *(float *)(param_1[0x88] + 0x4c) * *(float *)(param_1[0x88] + 0x40);
        *(float *)(param_1[0x99] + 0x28) =
             *(float *)(param_1[0x88] + 0x50) * *(float *)(param_1[0x88] + 0x40);
        *(float *)(param_1[0x99] + 0x30) =
             *(float *)(param_1[0x88] + 0x54) * *(float *)(param_1[0x88] + 0x40);
        fVar17 = 0.0;
        FUN_00554810();
      }
      if (fVar17 < *(float *)(param_1[0x88] + 0xf4)) {
        puStack_dc[0x47] = *(float *)(param_1[0x88] + 0xf4) * _DAT_00c85390;
      }
      if (fVar17 < *(float *)(param_1[0x88] + 0xf8)) {
        puStack_dc[0x48] = *(float *)(param_1[0x88] + 0xf8) * _DAT_00c519c8;
      }
      return;
    }
  } while( true );
}

