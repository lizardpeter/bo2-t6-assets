
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00758b20(void)

{
  float fVar1;
  float fVar2;
  float fVar3;
  uint *in_EAX;
  uint uVar4;
  float *unaff_ESI;
  uint *puVar5;
  int iVar6;
  float fVar7;
  float fVar8;
  double dVar9;
  float fVar10;
  
  fVar3 = _DAT_00c6982c;
  fVar2 = _DAT_00c0faec;
  fVar1 = _DAT_00bfa448;
  fVar8 = *unaff_ESI;
  if (_DAT_00bfa448 < *unaff_ESI) {
    fVar8 = _DAT_00bfa448;
  }
  fVar10 = unaff_ESI[1];
  if (_DAT_00bfa448 < unaff_ESI[1]) {
    fVar10 = _DAT_00bfa448;
  }
  fVar7 = unaff_ESI[2];
  if (_DAT_00bfa448 < unaff_ESI[2]) {
    fVar7 = _DAT_00bfa448;
  }
  *in_EAX = (((int)(SQRT(fVar7 * _DAT_00c6982c) * _DAT_00c0faec) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * _DAT_00c6982c) * _DAT_00c0faec) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * _DAT_00c6982c) * _DAT_00c0faec) & 0xffU;
  fVar8 = unaff_ESI[4];
  if (fVar1 < unaff_ESI[4]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[5];
  if (fVar1 < unaff_ESI[5]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[6];
  if (fVar1 < unaff_ESI[6]) {
    fVar7 = fVar1;
  }
  in_EAX[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[8];
  if (fVar1 < unaff_ESI[8]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[9];
  if (fVar1 < unaff_ESI[9]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[10];
  if (fVar1 < unaff_ESI[10]) {
    fVar7 = fVar1;
  }
  in_EAX[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  iVar6 = _DAT_036227fc;
  fVar8 = unaff_ESI[0xc];
  if (fVar1 < unaff_ESI[0xc]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xd];
  if (fVar1 < unaff_ESI[0xd]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xe];
  if (fVar1 < unaff_ESI[0xe]) {
    fVar7 = fVar1;
  }
  in_EAX[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)in_EAX + iVar6);
  fVar8 = unaff_ESI[0x10];
  if (fVar1 < unaff_ESI[0x10]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x11];
  if (fVar1 < unaff_ESI[0x11]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x12];
  if (fVar1 < unaff_ESI[0x12]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x14];
  if (fVar1 < unaff_ESI[0x14]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x15];
  if (fVar1 < unaff_ESI[0x15]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x16];
  if (fVar1 < unaff_ESI[0x16]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x18];
  if (fVar1 < unaff_ESI[0x18]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x19];
  if (fVar1 < unaff_ESI[0x19]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x1a];
  if (fVar1 < unaff_ESI[0x1a]) {
    fVar7 = fVar1;
  }
  puVar5[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x1c];
  if (fVar1 < unaff_ESI[0x1c]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x1d];
  if (fVar1 < unaff_ESI[0x1d]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x1e];
  if (fVar1 < unaff_ESI[0x1e]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0x20];
  if (fVar1 < unaff_ESI[0x20]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x21];
  if (fVar1 < unaff_ESI[0x21]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x22];
  if (fVar1 < unaff_ESI[0x22]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x24];
  if (fVar1 < unaff_ESI[0x24]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x25];
  if (fVar1 < unaff_ESI[0x25]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x26];
  if (fVar1 < unaff_ESI[0x26]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x28];
  if (fVar1 < unaff_ESI[0x28]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x29];
  if (fVar1 < unaff_ESI[0x29]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x2a];
  if (fVar1 < unaff_ESI[0x2a]) {
    fVar7 = fVar1;
  }
  puVar5[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x2c];
  if (fVar1 < unaff_ESI[0x2c]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x2d];
  if (fVar1 < unaff_ESI[0x2d]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x2e];
  if (fVar1 < unaff_ESI[0x2e]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0x30];
  if (fVar1 < unaff_ESI[0x30]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x31];
  if (fVar1 < unaff_ESI[0x31]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x32];
  if (fVar1 < unaff_ESI[0x32]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x34];
  if (fVar1 < unaff_ESI[0x34]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x35];
  if (fVar1 < unaff_ESI[0x35]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x36];
  if (fVar1 < unaff_ESI[0x36]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x38];
  if (fVar1 < unaff_ESI[0x38]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x39];
  if (fVar1 < unaff_ESI[0x39]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x3a];
  if (fVar1 < unaff_ESI[0x3a]) {
    fVar7 = fVar1;
  }
  puVar5[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x3c];
  if (fVar1 < unaff_ESI[0x3c]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x3d];
  if (fVar1 < unaff_ESI[0x3d]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x3e];
  if (fVar1 < unaff_ESI[0x3e]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + _DAT_035f13d4);
  fVar8 = unaff_ESI[0x40];
  if (fVar1 < unaff_ESI[0x40]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x41];
  if (fVar1 < unaff_ESI[0x41]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x42];
  if (fVar1 < unaff_ESI[0x42]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x44];
  if (fVar1 < unaff_ESI[0x44]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x45];
  if (fVar1 < unaff_ESI[0x45]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x46];
  if (fVar1 < unaff_ESI[0x46]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x48];
  if (fVar1 < unaff_ESI[0x48]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x49];
  if (fVar1 < unaff_ESI[0x49]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x4a];
  if (fVar1 < unaff_ESI[0x4a]) {
    fVar7 = fVar1;
  }
  puVar5[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x4c];
  if (fVar1 < unaff_ESI[0x4c]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x4d];
  if (fVar1 < unaff_ESI[0x4d]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x4e];
  if (fVar1 < unaff_ESI[0x4e]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0x50];
  if (fVar1 < unaff_ESI[0x50]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x51];
  if (fVar1 < unaff_ESI[0x51]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x52];
  if (fVar1 < unaff_ESI[0x52]) {
    fVar7 = fVar1;
  }
  dVar9 = SQRT(_DAT_00bd8a88);
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  uVar4 = (int)((float)dVar9 * fVar2) & 0xff;
  uVar4 = (uVar4 << 8 | uVar4) << 8 | uVar4;
  puVar5[1] = uVar4;
  puVar5[2] = uVar4;
  fVar8 = unaff_ESI[0x54];
  if (fVar1 < unaff_ESI[0x54]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x55];
  if (fVar1 < unaff_ESI[0x55]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x56];
  if (fVar1 < unaff_ESI[0x56]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0x58];
  if (fVar1 < unaff_ESI[0x58]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x59];
  if (fVar1 < unaff_ESI[0x59]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x5a];
  if (fVar1 < unaff_ESI[0x5a]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5[1] = uVar4;
  puVar5[2] = uVar4;
  fVar8 = unaff_ESI[0x5c];
  if (fVar1 < unaff_ESI[0x5c]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x5d];
  if (fVar1 < unaff_ESI[0x5d]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x5e];
  if (fVar1 < unaff_ESI[0x5e]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0x60];
  if (fVar1 < unaff_ESI[0x60]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x61];
  if (fVar1 < unaff_ESI[0x61]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x62];
  if (fVar1 < unaff_ESI[0x62]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[100];
  if (fVar1 < unaff_ESI[100]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x65];
  if (fVar1 < unaff_ESI[0x65]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x66];
  if (fVar1 < unaff_ESI[0x66]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x68];
  if (fVar1 < unaff_ESI[0x68]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x69];
  if (fVar1 < unaff_ESI[0x69]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x6a];
  if (fVar1 < unaff_ESI[0x6a]) {
    fVar7 = fVar1;
  }
  puVar5[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x6c];
  if (fVar1 < unaff_ESI[0x6c]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x6d];
  if (fVar1 < unaff_ESI[0x6d]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x6e];
  if (fVar1 < unaff_ESI[0x6e]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + _DAT_035f13d4);
  fVar8 = unaff_ESI[0x70];
  if (fVar1 < unaff_ESI[0x70]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x71];
  if (fVar1 < unaff_ESI[0x71]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x72];
  if (fVar1 < unaff_ESI[0x72]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x74];
  if (fVar1 < unaff_ESI[0x74]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x75];
  if (fVar1 < unaff_ESI[0x75]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x76];
  if (fVar1 < unaff_ESI[0x76]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x78];
  if (fVar1 < unaff_ESI[0x78]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x79];
  if (fVar1 < unaff_ESI[0x79]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x7a];
  if (fVar1 < unaff_ESI[0x7a]) {
    fVar7 = fVar1;
  }
  puVar5[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x7c];
  if (fVar1 < unaff_ESI[0x7c]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x7d];
  if (fVar1 < unaff_ESI[0x7d]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x7e];
  if (fVar1 < unaff_ESI[0x7e]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0x80];
  if (fVar1 < unaff_ESI[0x80]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x81];
  if (fVar1 < unaff_ESI[0x81]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x82];
  if (fVar1 < unaff_ESI[0x82]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5[1] = uVar4;
  puVar5[2] = uVar4;
  fVar8 = unaff_ESI[0x84];
  if (fVar1 < unaff_ESI[0x84]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x85];
  if (fVar1 < unaff_ESI[0x85]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x86];
  if (fVar1 < unaff_ESI[0x86]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0x88];
  if (fVar1 < unaff_ESI[0x88]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x89];
  if (fVar1 < unaff_ESI[0x89]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x8a];
  if (fVar1 < unaff_ESI[0x8a]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5[1] = uVar4;
  puVar5[2] = uVar4;
  fVar8 = unaff_ESI[0x8c];
  if (fVar1 < unaff_ESI[0x8c]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x8d];
  if (fVar1 < unaff_ESI[0x8d]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x8e];
  if (fVar1 < unaff_ESI[0x8e]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0x90];
  if (fVar1 < unaff_ESI[0x90]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x91];
  if (fVar1 < unaff_ESI[0x91]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x92];
  if (fVar1 < unaff_ESI[0x92]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x94];
  if (fVar1 < unaff_ESI[0x94]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x95];
  if (fVar1 < unaff_ESI[0x95]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x96];
  if (fVar1 < unaff_ESI[0x96]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x98];
  if (fVar1 < unaff_ESI[0x98]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x99];
  if (fVar1 < unaff_ESI[0x99]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x9a];
  if (fVar1 < unaff_ESI[0x9a]) {
    fVar7 = fVar1;
  }
  puVar5[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0x9c];
  if (fVar1 < unaff_ESI[0x9c]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0x9d];
  if (fVar1 < unaff_ESI[0x9d]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0x9e];
  if (fVar1 < unaff_ESI[0x9e]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + _DAT_035f13d4);
  fVar8 = unaff_ESI[0xa0];
  if (fVar1 < unaff_ESI[0xa0]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xa1];
  if (fVar1 < unaff_ESI[0xa1]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xa2];
  if (fVar1 < unaff_ESI[0xa2]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0xa4];
  if (fVar1 < unaff_ESI[0xa4]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xa5];
  if (fVar1 < unaff_ESI[0xa5]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xa6];
  if (fVar1 < unaff_ESI[0xa6]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0xa8];
  if (fVar1 < unaff_ESI[0xa8]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xa9];
  if (fVar1 < unaff_ESI[0xa9]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xaa];
  if (fVar1 < unaff_ESI[0xaa]) {
    fVar7 = fVar1;
  }
  puVar5[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0xac];
  if (fVar1 < unaff_ESI[0xac]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xad];
  if (fVar1 < unaff_ESI[0xad]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xae];
  if (fVar1 < unaff_ESI[0xae]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0xb0];
  if (fVar1 < unaff_ESI[0xb0]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xb1];
  if (fVar1 < unaff_ESI[0xb1]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xb2];
  if (fVar1 < unaff_ESI[0xb2]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0xb4];
  if (fVar1 < unaff_ESI[0xb4]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xb5];
  if (fVar1 < unaff_ESI[0xb5]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xb6];
  if (fVar1 < unaff_ESI[0xb6]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0xb8];
  if (fVar1 < unaff_ESI[0xb8]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xb9];
  if (fVar1 < unaff_ESI[0xb9]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xba];
  if (fVar1 < unaff_ESI[0xba]) {
    fVar7 = fVar1;
  }
  puVar5[2] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0xbc];
  if (fVar1 < unaff_ESI[0xbc]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xbd];
  if (fVar1 < unaff_ESI[0xbd]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xbe];
  if (fVar1 < unaff_ESI[0xbe]) {
    fVar7 = fVar1;
  }
  puVar5[3] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  puVar5 = (uint *)((int)puVar5 + iVar6);
  fVar8 = unaff_ESI[0xc0];
  if (fVar1 < unaff_ESI[0xc0]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xc1];
  if (fVar1 < unaff_ESI[0xc1]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xc2];
  if (fVar1 < unaff_ESI[0xc2]) {
    fVar7 = fVar1;
  }
  *puVar5 = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
            (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
            (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  fVar8 = unaff_ESI[0xc4];
  if (fVar1 < unaff_ESI[0xc4]) {
    fVar8 = fVar1;
  }
  fVar10 = unaff_ESI[0xc5];
  if (fVar1 < unaff_ESI[0xc5]) {
    fVar10 = fVar1;
  }
  fVar7 = unaff_ESI[0xc6];
  if (fVar1 < unaff_ESI[0xc6]) {
    fVar7 = fVar1;
  }
  puVar5[1] = (((int)(SQRT(fVar7 * fVar3) * fVar2) & 0xffU | 0xffffff00) << 8 |
              (int)(SQRT(fVar10 * fVar3) * fVar2) & 0xffU) << 8 |
              (int)(SQRT(fVar8 * fVar3) * fVar2) & 0xffU;
  FUN_007585e0(puVar5 + 2);
  FUN_007585e0(puVar5 + 3);
  iVar6 = (int)puVar5 + iVar6;
  FUN_007585e0(iVar6);
  FUN_007585e0(iVar6 + 4);
  FUN_007585e0(iVar6 + 8);
  FUN_007585e0(iVar6 + 0xc);
  return;
}

