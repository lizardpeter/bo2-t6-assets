
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_0072e880(undefined4 *param_1,undefined4 *param_2,int param_3,int param_4)

{
  int *piVar1;
  float fVar2;
  float fVar3;
  float fVar4;
  undefined4 uVar5;
  int *piVar6;
  bool bVar7;
  bool bVar8;
  int iVar9;
  undefined1 auVar10 [16];
  undefined1 auVar11 [12];
  char cVar12;
  char *pcVar13;
  int iVar14;
  int iVar15;
  undefined4 *puVar16;
  int iVar17;
  undefined4 *puVar18;
  undefined *puVar19;
  undefined4 *puVar20;
  undefined4 uVar21;
  float10 fVar22;
  float10 fVar23;
  float fVar24;
  float fVar25;
  float fVar26;
  undefined4 uVar27;
  undefined4 uVar28;
  undefined8 uVar29;
  int iStack_54;
  undefined1 auStack_40 [8];
  undefined4 uStack_38;
  bool bStack_34;
  undefined3 uStack_33;
  undefined4 uStack_30;
  undefined4 uStack_2c;
  float fStack_28;
  float fStack_24;
  undefined4 uStack_20;
  undefined4 uStack_1c;
  undefined4 uStack_18;
  float fStack_14;
  
  FUN_00593820("R_GenerateSortedDrawSurfs (cl=%d v=%d)",*param_1,_DAT_035ebe90);
  if ((param_4 == 0) || (bVar7 = true, *(int *)(param_4 + 4) == 0)) {
    bVar7 = false;
  }
  bVar8 = !bVar7;
  if (*(float *)(param_3 + 0x1700c) != _DAT_00d2bf88) {
    FUN_00561280(_DAT_03434824,*(float *)(param_3 + 0x1700c));
  }
  if (0 < _DAT_035a9128) {
    FUN_00684300(&PTR_PTR_01064170,&DAT_035a9128,0);
    _DAT_035a9128 = 0;
  }
  iVar17 = _DAT_035ebe90;
  iVar14 = _DAT_035ebe90 + 1;
  iVar15 = _DAT_035ebe90 * 0xc50;
  _DAT_035ebe90 = iVar14;
  *(int *)(_DAT_0341d400 + 0x47420c) = iVar14;
  *(int *)(_DAT_0341d400 + 0x474208) = iVar17;
  puVar16 = (undefined4 *)(iVar15 + *(int *)(_DAT_0341d400 + 0x474210));
  puVar16[0x67] = iVar17;
  stack0xffffffc4 = SUB1612((undefined1  [16])0x0,4);
  auVar11 = stack0xffffffc4;
  auStack_40._4_4_ = _DAT_0341d400 + 0x48b1f0;
  auStack_40._0_4_ = puVar16;
  auVar10 = _auStack_40;
  uStack_33 = auVar11._9_3_;
  _auStack_40 = auVar10._0_12_;
  bStack_34 = bVar8;
  uVar5 = *(undefined4 *)(_DAT_0341d400 + 0x474208);
  iVar17 = 0;
  do {
    _memset((void *)(puVar16[0x1e4] + iVar17),0,0x30);
    iVar17 = iVar17 + 0x30;
  } while (iVar17 < 0x570);
  if (((bVar7) || (cVar12 = FUN_006226f0(_DAT_02a7fc48), cVar12 == '\0')) ||
     (iStack_54 = 1, DAT_010648cc == '\0')) {
    iStack_54 = 0;
  }
  DAT_035ebeac = *(char *)(param_1 + 0x394) == '\0';
  if (_DAT_035ebe98 == 0.0) {
    FUN_0072e700();
  }
  _DAT_035ebea8 = 0;
  puVar18 = (undefined4 *)&DAT_03a3d8e0;
  puVar20 = (undefined4 *)puVar16[0x1e5];
  for (iVar17 = 0x394; iVar17 != 0; iVar17 = iVar17 + -1) {
    *puVar20 = *puVar18;
    puVar18 = puVar18 + 1;
    puVar20 = puVar20 + 1;
  }
  *(int *)(puVar16[0x1e5] + 0xe44) = _DAT_0341d400;
  *(undefined8 *)(puVar16 + 0x60) = _DAT_03553be8;
  *(undefined8 *)(puVar16 + 0x62) = _DAT_03553bf0;
  puVar16[100] = _DAT_03553bf8;
  puVar18 = param_2;
  puVar20 = puVar16;
  for (iVar17 = 0x54; iVar17 != 0; iVar17 = iVar17 + -1) {
    *puVar20 = *puVar18;
    puVar18 = puVar18 + 1;
    puVar20 = puVar20 + 1;
  }
  *(undefined8 *)(puVar16 + 0x54) = *(undefined8 *)(param_1 + 0x395);
  *(undefined8 *)(puVar16 + 0x56) = *(undefined8 *)(param_1 + 0x397);
  *(undefined8 *)(puVar16 + 0x58) = *(undefined8 *)(param_1 + 0x399);
  *(undefined8 *)(puVar16 + 0x5a) = *(undefined8 *)(param_1 + 0x39b);
  *(undefined8 *)(puVar16 + 0x5c) = *(undefined8 *)(param_1 + 0x39d);
  uVar29 = *(undefined8 *)(param_1 + 0x39f);
  puVar16[0x65] = iStack_54;
  *(undefined8 *)(puVar16 + 0x5e) = uVar29;
  puVar16[0x66] = *param_1;
  puVar16[0x68] = (uint)*(byte *)(param_1 + 0x394);
  puVar16[0x69] = (uint)*(byte *)((int)param_1 + 0xe51);
  *(undefined4 *)(puVar16[0x1df] + 0xdec) = param_1[1];
  puVar16[0x25b] = (uint)*(byte *)(param_3 + 0x16f18);
  *(undefined1 *)((int)puVar16 + 0xc33) = *(undefined1 *)(param_3 + 0x17010);
  *(undefined1 *)(puVar16 + 0x30d) = *(undefined1 *)(param_3 + 0x17011);
  puVar16[0x30e] = *(undefined4 *)(param_3 + 0x16d80);
  puVar16[0x25c] = *(undefined4 *)(param_3 + 0x16f1c);
  uVar21 = *(undefined4 *)(param_3 + 0x16f20);
  puVar18 = puVar16;
  puVar20 = puVar16 + 0x260;
  for (iVar17 = 0x54; iVar17 != 0; iVar17 = iVar17 + -1) {
    *puVar20 = *puVar18;
    puVar18 = puVar18 + 1;
    puVar20 = puVar20 + 1;
  }
  puVar16[0x25d] = uVar21;
  if (0.0 < *(float *)(param_3 + 0x16fe0)) {
    FUN_00696810(*(float *)(param_3 + 0x16fe0),*(undefined4 *)(param_3 + 0x16fe4),puVar16[0x2ae],
                 puVar16 + 0x270);
    puVar16[0x2ad] = _DAT_00d2b628;
    FUN_00727db0(1,1);
  }
  fVar24 = _DAT_00d2b3c8;
  *(undefined1 *)(puVar16 + 0x310) = *(undefined1 *)(param_3 + 0x17058);
  *(undefined1 *)(puVar16 + 0x2b4) = *(undefined1 *)(param_3 + 0x16fe8);
  puVar16[0x2b5] = *(undefined4 *)(param_3 + 0x17004);
  puVar18 = puVar16;
  puVar20 = puVar16 + 0x2b8;
  for (iVar17 = 0x54; iVar17 != 0; iVar17 = iVar17 + -1) {
    *puVar20 = *puVar18;
    puVar18 = puVar18 + 1;
    puVar20 = puVar20 + 1;
  }
  *(undefined1 *)(puVar16 + 0x30c) = *(undefined1 *)(param_3 + 0x16fe9);
  *(undefined1 *)((int)puVar16 + 0xc31) = *(undefined1 *)(param_3 + 0x16fea);
  if (*(float *)(param_3 + 0x16fec) <= 0.0) {
    if (0.0 < *(float *)(param_3 + 0x16ff4)) {
      fVar25 = *(float *)(param_3 + 0x16ff4);
      fVar2 = *(float *)(param_3 + 0x16ff8);
      fVar3 = *(float *)(param_3 + 0x16ffc);
      fVar4 = *(float *)(param_3 + 0x17000);
      puVar16[0x2c8] = fVar25 * (float)puVar16[0x2c8];
      puVar16[0x2cd] = (float)puVar16[0x2cd] * fVar2;
      fVar26 = fVar24 / fVar25 + fVar3;
      fVar24 = fVar24 / fVar2 + fVar4;
      puVar16[0x2d1] = (fVar24 + fVar4) / (fVar24 - fVar4);
      puVar16[0x2d0] = fVar25 + (fVar26 + fVar3) / (fVar3 - fVar26);
      puVar16[0x2d1] = (float)puVar16[0x2d1] - fVar2;
      FUN_00727db0(1,0);
      fVar24 = _DAT_00d2b3c8;
    }
  }
  else {
    FUN_00696810(*(float *)(param_3 + 0x16fec),*(undefined4 *)(param_3 + 0x16ff0),puVar16[0x306],
                 puVar16 + 0x2c8);
    puVar16[0x305] = _DAT_00d2b628;
    FUN_00727db0(1,1);
    fVar24 = _DAT_00d2b3c8;
  }
  *(undefined1 *)((int)puVar16 + 0xc32) = *(undefined1 *)(param_3 + 0x17008);
  if (bVar8) {
    *(undefined4 *)(_DAT_0341d400 + 0x48b660) = 0;
    FID_conflict__memcpy
              ((void *)(_DAT_0341d400 + 0x4751d0),(void *)param_1[0x3a1],
               *(int *)(_DAT_035ae280 + 0x108) * 0x160);
    fVar24 = _DAT_00d2b3c8;
    *(undefined4 *)(&DAT_0048b070 + _DAT_0341d400) = *(undefined4 *)(_DAT_035ae280 + 0x108);
  }
  iVar17 = puVar16[0x1e5];
  if (bVar7) {
    *(undefined1 *)(puVar16 + 0x25a) = 1;
    *(undefined4 *)(iVar17 + 0xd78) = _DAT_03a268b0;
    *(undefined4 *)(puVar16[0x1e5] + 0xd54) = _DAT_03a2689c;
    *(undefined4 *)(puVar16[0x1e5] + 0xd5c) = _DAT_035ae18c;
    iVar17 = puVar16[0x1e5];
    *(float *)(iVar17 + 0xcb0) = fVar24;
    *(float *)(iVar17 + 0xcb4) = fVar24;
    *(float *)(iVar17 + 0xcb8) = fVar24;
    *(float *)(iVar17 + 0xcbc) = fVar24;
  }
  else {
    *(undefined1 *)(puVar16 + 0x25a) = 0;
    *(undefined4 *)(iVar17 + 0xcb0) = 0;
    *(undefined4 *)(iVar17 + 0xcb4) = 0;
    *(undefined4 *)(iVar17 + 0xcb8) = 0;
    *(undefined4 *)(iVar17 + 0xcbc) = 0;
  }
  puVar16[0x1e2] = param_1[2];
  puVar16[0x1e1] = param_1[3];
  if (bVar8) {
    _memset(&DAT_03521e80,0,0xff);
  }
  FUN_005eae80(*param_1);
  FUN_00725b90();
  FUN_007227b0();
  FUN_00725e00();
  if (bVar8) {
    FUN_007672f0(2);
  }
  FUN_0072c180();
  FUN_0072c260();
  FUN_0072c4a0();
  FUN_0072da20(puVar16[0x1e5]);
  uVar21 = _DAT_00d33b80;
  iVar17 = puVar16[0x1e5];
  *(undefined4 *)(iVar17 + 0xd3c) = _DAT_03a36a9c;
  *(float *)(iVar17 + 0x2b4) = _DAT_03a36a80 * _DAT_00c41b58;
  *(undefined4 *)(iVar17 + 0x2b8) = _DAT_00d33b7c;
  *(undefined4 *)(iVar17 + 0x2b0) = uVar21;
  *(undefined4 *)(iVar17 + 700) = 0;
  iVar17 = puVar16[0x1e5];
  fVar22 = (float10)FUN_004645d0(_DAT_03434b24);
  iVar14 = FUN_0044dfc0(_DAT_03434ad4);
  iVar15 = FUN_0044dfc0(_DAT_03434778);
  fVar23 = (float10)FUN_004645d0(_DAT_03434b54);
  *(float *)(iVar17 + 0x3b0) = (float)fVar22;
  fVar24 = _DAT_00d2b3c8;
  *(float *)(iVar17 + 0x3b4) = (float)iVar14;
  *(float *)(iVar17 + 0x3bc) = (float)fVar23;
  *(float *)(iVar17 + 0x3b8) = (float)iVar15;
  iVar17 = puVar16[0x1e5];
  iVar14 = *(int *)(iVar17 + 0xe44);
  uVar21 = *(undefined4 *)(iVar14 + 0x475058);
  uVar27 = *(undefined4 *)(iVar14 + 0x47505c);
  *(undefined4 *)(iVar17 + 0x290) = *(undefined4 *)(iVar14 + 0x475054);
  *(undefined4 *)(iVar17 + 0x294) = uVar21;
  *(undefined4 *)(iVar17 + 0x298) = uVar27;
  *(float *)(iVar17 + 0x29c) = fVar24;
  uVar21 = *(undefined4 *)(iVar14 + 0x47509c);
  uVar27 = *(undefined4 *)(iVar14 + 0x4750a0);
  *(undefined4 *)(iVar17 + 0x2a0) = *(undefined4 *)(iVar14 + 0x475098);
  *(undefined4 *)(iVar17 + 0x2a4) = uVar21;
  *(undefined4 *)(iVar17 + 0x2a8) = uVar27;
  *(float *)(iVar17 + 0x2ac) = fVar24;
  FUN_0076ec70(puVar16 + 0x40);
  FUN_0074c5b0();
  iVar17 = puVar16[0x1e5];
  fVar24 = 0.0;
  *(undefined4 *)(iVar17 + 0x9d0) = puVar16[0x1e2];
  uVar21 = 0;
  *(undefined4 *)(iVar17 + 0x9d4) = 0;
  *(undefined4 *)(iVar17 + 0x9d8) = 0;
  *(undefined4 *)(iVar17 + 0x9dc) = 0;
  iVar17 = puVar16[0x1e5];
  uVar27 = uVar21;
  uVar28 = uVar21;
  if ((float)puVar16[0x43] != 0.0) {
    uVar21 = puVar16[0x40];
    uVar27 = puVar16[0x41];
    uVar28 = puVar16[0x42];
    fVar24 = (float)puVar16[0x43];
  }
  *(undefined4 *)(iVar17 + 0xc90) = uVar21;
  *(undefined4 *)(iVar17 + 0xc94) = uVar27;
  *(undefined4 *)(iVar17 + 0xc98) = uVar28;
  *(float *)(iVar17 + 0xc9c) = fVar24;
  iVar17 = puVar16[0x1e5];
  *(undefined4 *)(iVar17 + 0xbc0) = param_1[0x15];
  *(undefined4 *)(iVar17 + 0xbc4) = param_1[0x16];
  *(undefined4 *)(iVar17 + 0xbc8) = param_1[0x17];
  *(undefined4 *)(iVar17 + 0xbcc) = param_1[0x18];
  FUN_00729d90(puVar16);
  FUN_0072b7b0(puVar16,param_1,param_3);
  iVar17 = puVar16[0x1df];
  cVar12 = FUN_006226f0(_DAT_03434698);
  if (cVar12 == '\0') {
    puVar18 = param_1 + 0x68;
    puVar20 = (undefined4 *)(iVar17 + 0xd54);
    for (iVar14 = 0x24; iVar14 != 0; iVar14 = iVar14 + -1) {
      *puVar20 = *puVar18;
      puVar18 = puVar18 + 1;
      puVar20 = puVar20 + 1;
    }
  }
  else {
    FUN_0072bbe0();
  }
  FUN_0072bc80();
  fVar24 = *(float *)(param_3 + 0x30) * _DAT_00c5f1a4 * _DAT_00c50d24;
  FUN_00a7477a();
  iVar17 = puVar16[0x1e5];
  fVar25 = (float)param_2[0x4e] * _DAT_00d33aec;
  *(float *)(iVar17 + 0x284) = (float)param_2[0x4d] * _DAT_00c216b4;
  *(float *)(iVar17 + 0x280) = fVar25;
  *(undefined4 *)(iVar17 + 0x288) = 0;
  *(float *)(iVar17 + 0x28c) = fVar24;
  FUN_0072bd00();
  iVar17 = puVar16[0x1e5];
  uVar21 = param_1[4];
  *(undefined4 *)(iVar17 + 0xa84) = 0;
  *(undefined4 *)(iVar17 + 0xa80) = uVar21;
  *(undefined4 *)(iVar17 + 0xa88) = 0;
  *(undefined4 *)(iVar17 + 0xa8c) = 0;
  FUN_0072b3d0(puVar16);
  FUN_0072b0d0();
  FUN_0072b270();
  uVar21 = _DAT_034345f8;
  iVar17 = puVar16[0x1df];
  *(undefined8 *)(iVar17 + 0x134) = *(undefined8 *)(param_1 + 0x8c);
  *(undefined8 *)(iVar17 + 0x13c) = *(undefined8 *)(param_1 + 0x8e);
  *(undefined8 *)(iVar17 + 0x144) = *(undefined8 *)(param_1 + 0x90);
  *(undefined8 *)(iVar17 + 0x14c) = *(undefined8 *)(param_1 + 0x92);
  *(undefined8 *)(iVar17 + 0x154) = *(undefined8 *)(param_1 + 0x94);
  *(undefined4 *)(iVar17 + 0x15c) = param_1[0x96];
  iVar17 = puVar16[0x1df];
  cVar12 = FUN_006226f0(uVar21);
  if (cVar12 == '\0') {
    puVar18 = param_1 + 0x97;
    puVar20 = (undefined4 *)(iVar17 + 0x160);
    for (iVar14 = 0xe; iVar14 != 0; iVar14 = iVar14 + -1) {
      *puVar20 = *puVar18;
      puVar18 = puVar18 + 1;
      puVar20 = puVar20 + 1;
    }
  }
  else {
    FUN_0072b360();
  }
  FUN_0072b520();
  puVar18 = param_1 + 0xb7;
  puVar20 = (undefined4 *)(puVar16[0x1df] + 0x1e0);
  for (iVar17 = 0x2b0; iVar17 != 0; iVar17 = iVar17 + -1) {
    *puVar20 = *puVar18;
    puVar18 = puVar18 + 1;
    puVar20 = puVar20 + 1;
  }
  iVar17 = puVar16[0x1df];
  *(undefined8 *)(iVar17 + 0xca8) = *(undefined8 *)(param_1 + 0x369);
  *(undefined8 *)(iVar17 + 0xcb0) = *(undefined8 *)(param_1 + 0x36b);
  *(undefined8 *)(iVar17 + 0xcb8) = *(undefined8 *)(param_1 + 0x36d);
  *(undefined8 *)(iVar17 + 0xcc0) = *(undefined8 *)(param_1 + 0x36f);
  *(undefined8 *)(iVar17 + 0xcc8) = *(undefined8 *)(param_1 + 0x371);
  *(undefined4 *)(iVar17 + 0xcd0) = param_1[0x373];
  iVar17 = puVar16[0x1df];
  *(undefined8 *)(iVar17 + 0xcd4) = *(undefined8 *)(param_1 + 0x374);
  *(undefined8 *)(iVar17 + 0xcdc) = *(undefined8 *)(param_1 + 0x376);
  *(undefined8 *)(iVar17 + 0xce4) = *(undefined8 *)(param_1 + 0x378);
  *(undefined8 *)(iVar17 + 0xcec) = *(undefined8 *)(param_1 + 0x37a);
  *(undefined8 *)(iVar17 + 0xcf4) = *(undefined8 *)(param_1 + 0x37c);
  *(undefined4 *)(iVar17 + 0xcfc) = param_1[0x37e];
  FUN_00696b40(*param_1,uVar5);
  puVar18 = param_1 + 0x37f;
  puVar20 = (undefined4 *)(puVar16[0x1df] + 0xd00);
  for (iVar17 = 0x15; iVar17 != 0; iVar17 = iVar17 + -1) {
    *puVar20 = *puVar18;
    puVar18 = puVar18 + 1;
    puVar20 = puVar20 + 1;
  }
  FUN_00728ea0();
  FUN_00729aa0();
  FUN_0072c590(param_3);
  iVar17 = puVar16[0x1e5];
  iVar14 = puVar16[0x5a];
  *(float *)(iVar17 + 0x124) = (float)(int)puVar16[0x5b];
  *(float *)(iVar17 + 0x120) = (float)iVar14;
  *(undefined4 *)(iVar17 + 0x128) = 0;
  *(undefined4 *)(iVar17 + 300) = 0;
  FUN_006d5720(&PTR_PTR_010641d0);
  if (bVar7) {
    puVar16[0x1cc] = 0;
  }
  else {
    FUN_0072e530(puVar16);
    if (((0 < (int)puVar16[0x1cc]) && (*(char *)(puVar16 + 0x6c) == '\x02')) &&
       (iVar17 = 0, 0 < _DAT_03553bfc)) {
      pcVar13 = &DAT_03553c00;
LAB_0072f4b0:
      if (*pcVar13 != '\x02') goto code_r0x0072f4b5;
      puVar18 = (undefined4 *)(&DAT_03553c00 + iVar17 * 0x160);
      puVar20 = puVar16 + 0x6c;
      for (iVar14 = 0x58; iVar14 != 0; iVar14 = iVar14 + -1) {
        *puVar20 = *puVar18;
        puVar18 = puVar18 + 1;
        puVar20 = puVar20 + 1;
      }
    }
  }
LAB_0072f4e6:
  if (bVar8) {
    FUN_0072c0a0(puVar16,puVar16[0x1cc]);
  }
  if (_DAT_03a8e7d4 != 0) {
    fStack_14 = _DAT_00d2b3c8;
    uStack_20 = param_2[0x40];
    uStack_1c = param_2[0x41];
    uStack_18 = param_2[0x42];
    fVar22 = (float10)FUN_004645d0(_DAT_03434888);
    uStack_30 = 0;
    uStack_2c = 0;
    fVar25 = (float)fVar22 * _DAT_00c1a568;
    fVar24 = fVar25;
    FUN_00a742c4();
    fStack_28 = fVar24;
    FUN_00a74623();
    fStack_24 = fVar25;
    FUN_00722550(_DAT_03a8e7d4,&uStack_30,0,&DAT_043a670c,0);
  }
  if ((_DAT_03a3eab0 == 3) || (_DAT_03a3eab0 == 2)) {
    uStack_38 = 0;
    FUN_00684300(&PTR_PTR_01063e20,auStack_40,0);
    uStack_38 = 1;
    FUN_00684300(&PTR_PTR_01063e20,auStack_40,0);
    uStack_38 = 2;
    FUN_00684300(&PTR_PTR_01063e20,auStack_40,0);
    uStack_38 = 3;
    FUN_00684300(&PTR_PTR_01063e20,auStack_40,0);
    _memset(&DAT_03a2ad00,0,(*(int *)(_DAT_035ae280 + 0x310) + 0x1fU >> 5) * 4);
    FUN_00684300(&PTR_PTR_01063e60,auStack_40,0);
    FUN_006d5720(&PTR_PTR_01063e20);
    FUN_006d5720(&PTR_PTR_01063e60);
    FUN_0074dfa0();
    FUN_0072e480();
    puVar19 = &DAT_03521f80 + *(int *)(_DAT_0341d400 + 0x474208) * 0xff;
    if (*(int *)(_DAT_035ae280 + 0x104) != 0) {
      cVar12 = FUN_006226f0(_DAT_034345f4);
      if (cVar12 == '\0') {
        puVar19[*(int *)(_DAT_035ae280 + 0x104)] = 0;
      }
      else {
        cVar12 = FUN_006226f0(_DAT_03434798);
        if (cVar12 != '\0') {
          puVar19[*(int *)(_DAT_035ae280 + 0x104)] = 1;
        }
      }
    }
    if (bVar8) {
      _memset((void *)(_DAT_0341d400 + 0x462c70),0,0xff);
      cVar12 = FUN_006226f0(_DAT_02a7fc48);
      if ((cVar12 != '\0') && (DAT_010648cc != '\0')) {
        FUN_0073d220(puVar19,puVar16);
      }
    }
    if ((0 < (int)puVar16[0x1cc]) && (*(char *)(puVar16 + 0x6c) == '\x02')) {
      FUN_00684300(&PTR_PTR_01063ea0,auStack_40,0);
      FUN_00684300(&PTR_PTR_01063ed0,auStack_40,0);
    }
    FUN_00762b30();
    if ((iStack_54 == 1) &&
       (*(char *)(*(int *)(_DAT_035ae280 + 0x104) + 0x462c70 + _DAT_0341d400) != '\0')) {
      _DAT_035ebea8 = 1;
    }
  }
  else {
    FUN_006d5720(&PTR_PTR_01063fa0);
    FUN_0076e1e0(*(undefined4 *)(_DAT_035ae280 + 0x31c),0,0x1200);
    cVar12 = FUN_006226f0(_DAT_03434834);
    if (cVar12 != '\0') {
      FUN_00752770();
      FUN_00752770();
    }
    FUN_0076e1e0(*(undefined4 *)(_DAT_035ae280 + 0x324),7,0x200);
    FUN_00752770();
    FUN_0076e1e0(*(undefined4 *)(_DAT_035ae280 + 0x32c),0x10,0x400);
    cVar12 = FUN_006226f0(_DAT_03434834);
    if (cVar12 != '\0') {
      FUN_00752770();
    }
    FUN_0076e1e0(*(undefined4 *)(_DAT_035ae280 + 0x334),0x13,0x400);
    FUN_00752770();
    _memset(&DAT_03a2ad00,0,(*(int *)(_DAT_035ae280 + 0x310) + 0x1fU >> 5) * 4);
    FUN_0074dec0(puVar16[0x66],puVar16[0x67],puVar16 + 0x6c,puVar16[0x1cc],bVar8);
    FUN_0074dfa0();
  }
  FUN_006226f0(_DAT_03434644);
  if ((((_DAT_03a3eab0 == 3) || (_DAT_03a3eab0 == 2)) && (iStack_54 == 1)) &&
     (*(char *)(*(int *)(_DAT_035ae280 + 0x104) + 0x462c70 + _DAT_0341d400) != '\0')) {
    FUN_00684300(&PTR_PTR_01063e40,auStack_40,0);
    FUN_00684300(&PTR_PTR_01063e80,auStack_40,0);
  }
  FUN_004e5a90(puVar16[0x66]);
  FUN_006d5720(&PTR_PTR_01063fc0);
  FUN_006d5720(&PTR_PTR_01064010);
  FUN_00721bb0(puVar16);
  FUN_006d5720(&PTR_PTR_01064080);
  FUN_006d5720(&PTR_PTR_010640c0);
  FUN_006d5720(&PTR_PTR_010640a0);
  iVar17 = *(int *)(_DAT_0341d400 + 0x474208);
  uVar21 = 0;
  iVar14 = FUN_0044dfc0(_DAT_0343488c);
  if ((iVar14 != 0) && ((_DAT_03a3eab0 == 3 || (_DAT_03a3eab0 == 2)))) {
    FUN_00724ba0();
    uVar21 = FUN_0073e5e0(&DAT_03522380 + iVar17 * 0x580);
  }
  *(undefined4 *)(&DAT_03523980 + *(int *)(_DAT_0341d400 + 0x474208) * 4) = uVar21;
  FUN_006d5720(&PTR_PTR_01063ff0);
  FUN_006d5720(&PTR_PTR_01064150);
  FUN_006d5720(&PTR_PTR_01064130);
  FUN_006d5720(&PTR_PTR_01064170);
  FUN_00721340(puVar16);
  FUN_00720610();
  FUN_00720850();
  FUN_006d5720(&PTR_PTR_01064030);
  FUN_006d5720(&PTR_PTR_01064050);
  FUN_006d5720(&PTR_PTR_010640c0);
  FUN_006d5720(&PTR_PTR_010640e0);
  if (!bVar7) {
    FUN_0044c440(puVar16[0x66]);
    FUN_00443230(puVar16);
  }
  if (puVar16[0x1cc] == 0) {
    iVar17 = puVar16[0x1e5];
    *(undefined4 *)(iVar17 + 0xd70) = _DAT_035ae188;
    *(undefined1 *)(iVar17 + 0xe1c) = 0x61;
    *(undefined4 *)(iVar17 + 0xd4c) = _DAT_03a26860;
    *(undefined1 *)(iVar17 + 0xe13) = 0x65;
  }
  else {
    FUN_0072ccd0(puVar16[0x1e5],puVar16[0x1cc]);
  }
  iVar17 = 0x450;
  do {
    _memset((void *)(puVar16[0x1e4] + iVar17),0,0x30);
    iVar17 = iVar17 + 0x30;
  } while (iVar17 < 0x4b0);
  FUN_00720750();
  if (((_DAT_03a3eab0 == 3) || (_DAT_03a3eab0 == 2)) && ((iStack_54 == 1 && (bVar8)))) {
    if (*(char *)(*(int *)(_DAT_035ae280 + 0x104) + 0x462c70 + _DAT_0341d400) != '\0') {
      FUN_00720b00();
      FUN_006d5720(&PTR_PTR_01063e40);
      FUN_006d5720(&PTR_PTR_01063e80);
      FUN_007673e0(puVar16);
    }
    FUN_0076dc30(puVar16,uVar5);
    if ((0 < (int)puVar16[0x1cc]) && (*(char *)(puVar16 + 0x6c) == '\x02')) {
      FUN_0073ec90();
      if ((*(char *)(puVar16 + 0x6c) == '\x02') &&
         (*(int *)(*(int *)(&DAT_0048b070 + _DAT_0341d400) * 0x160 + 0x4750ac + _DAT_0341d400) != -1
         )) {
        FUN_00752770();
      }
      FUN_006d5720(&PTR_PTR_01063ea0);
      FUN_006d5720(&PTR_PTR_01063ed0);
      if ((*(char *)(puVar16 + 0x6c) == '\x02') &&
         (*(int *)(*(int *)(&DAT_0048b070 + _DAT_0341d400) * 0x160 + 0x4750ac + _DAT_0341d400) != -1
         )) {
        FUN_00752770();
      }
    }
    FUN_0076daf0(puVar16);
  }
  FUN_00760bf0();
  FUN_0072e0a0(&DAT_00d2e080,0x14,puVar16,param_2);
  iVar14 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  piVar6 = (int *)puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(1,_DAT_0341d400);
  *piVar6 = iVar14 + 0x9ec00 + iVar17 * 8;
  piVar6[1] = *piVar1 - iVar17;
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(1,_DAT_0341d400);
  *(int *)(iVar14 + 0x30) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 0x34) = *piVar1 - iVar17;
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(1,_DAT_0341d400);
  *(int *)(iVar14 + 0x60) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 100) = *piVar1 - iVar17;
  piVar1 = (int *)puVar16[0x1e4];
  for (iVar17 = piVar1[1]; iVar17 != 0; iVar17 = iVar17 + -1) {
    uVar29 = __aullshr();
    if (((int)((ulonglong)uVar29 >> 0x20) == 0) && ((uint)uVar29 < 0x10)) break;
  }
  piVar1[0x25] = piVar1[1] - iVar17;
  piVar1[0x24] = *piVar1 + iVar17 * 8;
  piVar1[1] = iVar17;
  iVar17 = puVar16[0x1e4];
  for (iVar14 = *(int *)(iVar17 + 0x34); iVar14 != 0; iVar14 = iVar14 + -1) {
    uVar29 = __aullshr();
    if (((int)((ulonglong)uVar29 >> 0x20) == 0) && ((uint)uVar29 < 0x10)) break;
  }
  *(int *)(iVar17 + 0xc4) = *(int *)(iVar17 + 0x34) - iVar14;
  *(int *)(iVar17 + 0xc0) = *(int *)(iVar17 + 0x30) + iVar14 * 8;
  *(int *)(iVar17 + 0x34) = iVar14;
  iVar17 = puVar16[0x1e4];
  for (iVar14 = *(int *)(iVar17 + 100); iVar14 != 0; iVar14 = iVar14 + -1) {
    uVar29 = __aullshr();
    if (((int)((ulonglong)uVar29 >> 0x20) == 0) && ((uint)uVar29 < 0x10)) break;
  }
  *(int *)(iVar17 + 0xf4) = *(int *)(iVar17 + 100) - iVar14;
  *(int *)(iVar17 + 0xf0) = *(int *)(iVar17 + 0x60) + iVar14 * 8;
  *(int *)(iVar17 + 100) = iVar14;
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(1,_DAT_0341d400);
  *(int *)(iVar14 + 0x120) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 0x124) = *piVar1 - iVar17;
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(3,_DAT_0341d400);
  *(int *)(iVar14 + 0x330) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 0x334) = *piVar1 - iVar17;
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(1,_DAT_0341d400);
  *(int *)(iVar14 + 0x150) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 0x154) = *piVar1 - iVar17;
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(1,_DAT_0341d400);
  *(int *)(iVar14 + 0x180) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 0x184) = *piVar1 - iVar17;
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(1,_DAT_0341d400);
  *(int *)(iVar14 + 0x1b0) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 0x1b4) = *piVar1 - iVar17;
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(1,_DAT_0341d400);
  *(int *)(iVar14 + 0x270) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 0x274) = *piVar1 - iVar17;
  FUN_0072e180(puVar16);
  FUN_0072e180(puVar16);
  iVar17 = puVar16[0x1e4];
  for (iVar14 = *(int *)(iVar17 + 0x154); iVar14 != 0; iVar14 = iVar14 + -1) {
    uVar29 = __aullshr();
    if (((int)((ulonglong)uVar29 >> 0x20) == 0) && ((uint)uVar29 < 0x10)) break;
  }
  *(int *)(iVar17 + 0x1e4) = *(int *)(iVar17 + 0x154) - iVar14;
  *(int *)(iVar17 + 0x1e0) = *(int *)(iVar17 + 0x150) + iVar14 * 8;
  *(int *)(iVar17 + 0x154) = iVar14;
  iVar17 = puVar16[0x1e4];
  for (iVar14 = *(int *)(iVar17 + 0x184); iVar14 != 0; iVar14 = iVar14 + -1) {
    uVar29 = __aullshr();
    if (((int)((ulonglong)uVar29 >> 0x20) == 0) && ((uint)uVar29 < 0x10)) break;
  }
  *(int *)(iVar17 + 0x214) = *(int *)(iVar17 + 0x184) - iVar14;
  *(int *)(iVar17 + 0x210) = *(int *)(iVar17 + 0x180) + iVar14 * 8;
  *(int *)(iVar17 + 0x184) = iVar14;
  iVar17 = puVar16[0x1e4];
  for (iVar14 = *(int *)(iVar17 + 0x1b4); iVar14 != 0; iVar14 = iVar14 + -1) {
    uVar29 = __aullshr();
    if (((int)((ulonglong)uVar29 >> 0x20) == 0) && ((uint)uVar29 < 0x10)) break;
  }
  *(int *)(iVar17 + 0x244) = *(int *)(iVar17 + 0x1b4) - iVar14;
  *(int *)(iVar17 + 0x240) = *(int *)(iVar17 + 0x1b0) + iVar14 * 8;
  *(int *)(iVar17 + 0x1b4) = iVar14;
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  FUN_007674e0(2,_DAT_0341d400);
  *(int *)(iVar14 + 0x300) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 0x304) = *piVar1 - iVar17;
  FUN_0072e180(puVar16);
  iVar15 = _DAT_0341d400;
  iVar17 = *(int *)(_DAT_0341d400 + 0x462d74);
  iVar14 = puVar16[0x1e4];
  FUN_007674e0(3,_DAT_0341d400);
  *(int *)(iVar14 + 0x2a0) = iVar15 + 0x9ec00 + iVar17 * 8;
  *(int *)(iVar14 + 0x2a4) = *(int *)(iVar15 + 0x462d74) - iVar17;
  iVar9 = _DAT_0341d400;
  iVar14 = puVar16[0x1e4];
  piVar1 = (int *)(_DAT_0341d400 + 0x462d74);
  iVar15 = *piVar1;
  FUN_007674e0(3,_DAT_0341d400);
  *(int *)(iVar14 + 0x2a0) = iVar9 + 0x9ec00 + iVar15 * 8;
  *(int *)(iVar14 + 0x2a4) = *piVar1 - iVar15;
  *(int *)(puVar16[0x1e4] + 0x2a0) = _DAT_0341d400 + 0x9ec00 + iVar17 * 8;
  *(int *)(puVar16[0x1e4] + 0x2a4) = *(int *)(_DAT_0341d400 + 0x462d74) - iVar17;
  FUN_00752770();
  iVar17 = puVar16[0x1e4];
  for (iVar14 = *(int *)(iVar17 + 0x2a4); iVar14 != 0; iVar14 = iVar14 + -1) {
    uVar29 = __aullshr();
    if (((int)((ulonglong)uVar29 >> 0x20) == 0) && ((uint)uVar29 < 0x3c)) break;
  }
  *(int *)(iVar17 + 0x424) = *(int *)(iVar17 + 0x2a4) - iVar14;
  *(int *)(iVar17 + 0x420) = *(int *)(iVar17 + 0x2a0) + iVar14 * 8;
  *(int *)(iVar17 + 0x2a4) = iVar14;
  iVar17 = puVar16[0x1e4];
  for (iVar14 = *(int *)(iVar17 + 0x2a4); iVar14 != 0; iVar14 = iVar14 + -1) {
    uVar29 = __aullshr();
    if (((int)((ulonglong)uVar29 >> 0x20) == 0) && ((uint)uVar29 < 0x38)) break;
  }
  *(int *)(iVar17 + 0x3f4) = *(int *)(iVar17 + 0x2a4) - iVar14;
  *(int *)(iVar17 + 0x3f0) = *(int *)(iVar17 + 0x2a0) + iVar14 * 8;
  *(int *)(iVar17 + 0x2a4) = iVar14;
  iVar17 = *(int *)(puVar16[0x1e4] + 0x2a4);
  for (iVar14 = iVar17; iVar14 != 0; iVar14 = iVar14 + -1) {
    uVar29 = __aullshr();
    if (((int)((ulonglong)uVar29 >> 0x20) == 0) && ((uint)uVar29 < 0x32)) break;
  }
  iVar15 = puVar16[0x1e4];
  *(int *)(iVar15 + 0x2d4) = iVar17 - iVar14;
  *(int *)(iVar15 + 0x2d0) = *(int *)(iVar15 + 0x2a0) + iVar14 * 8;
  *(int *)(iVar15 + 0x2a4) = iVar14;
  if (!bVar7) {
    FUN_004f7bc0();
  }
  FUN_0072e350(puVar16,param_2);
  FUN_0072e610(puVar16);
  iVar14 = _DAT_0341d400;
  iVar17 = _DAT_03441c70 * 0xc;
  *(undefined4 **)(&DAT_03441c40 + iVar17) = puVar16;
  *(int *)(&DAT_03441c44 + iVar17) = iVar14;
  *(undefined4 *)(&DAT_03441c48 + iVar17) = uVar5;
  _DAT_03441c70 = _DAT_03441c70 + 1;
  FUN_004ad0c0(*param_1,*(undefined4 *)(&DAT_0046f988 + iVar14));
  return;
code_r0x0072f4b5:
  iVar17 = iVar17 + 1;
  pcVar13 = pcVar13 + 0x160;
  if (_DAT_03553bfc <= iVar17) goto LAB_0072f4e6;
  goto LAB_0072f4b0;
}

