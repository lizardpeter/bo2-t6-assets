
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_0072da20(int param_1)

{
  char cVar1;
  int in_EAX;
  undefined4 uVar2;
  undefined4 uVar3;
  char *pcVar4;
  size_t sVar5;
  uint uVar6;
  uint uVar7;
  byte bVar8;
  uint uVar9;
  undefined2 *puVar10;
  float10 fVar11;
  float10 fVar12;
  float10 fVar13;
  float10 fVar14;
  float fVar15;
  float fVar16;
  float fVar17;
  char acStack_80 [124];
  
  fVar17 = *(float *)(in_EAX + 8);
  fVar11 = (float10)FUN_004645d0();
  fVar12 = (float10)FUN_004645d0();
  fVar13 = (float10)FUN_004645d0();
  fVar14 = (float10)FUN_004645d0();
  fVar15 = (_DAT_00c12844 - (float)fVar11) * _DAT_00c1a568;
  FUN_00a74623();
  fVar16 = (_DAT_00c12844 - (float)fVar12) * _DAT_00c1a568;
  FUN_00a74623();
  if ((float)((uint)(fVar16 - fVar15) & _DAT_00c1b5a0) <= _DAT_00c5040c) {
    fVar17 = 0.0;
  }
  else {
    fVar17 = (fVar17 - fVar15) / (fVar16 - fVar15);
    if (0.0 <= fVar17) {
      if (_DAT_00d2b3c8 < fVar17) {
        fVar17 = _DAT_00d2b3c8;
      }
      fVar17 = fVar17 * fVar17;
    }
    else {
      fVar17 = 0.0;
    }
  }
  fVar15 = (_DAT_00d2b3c8 - fVar17) * (float)fVar13 + fVar17 * (float)fVar14;
  cVar1 = FUN_006226f0();
  if (cVar1 != '\0') {
    FUN_0044dfc0(_DAT_03434754,"consoleFont");
    uVar2 = FUN_00593820();
    uVar3 = FUN_00733f50(uVar2,1);
    __snprintf(acStack_80,0x40,"intensity0 angle=%.2f factor=%.2f",(double)(float)fVar11,
               (double)(float)fVar13);
    _DAT_0341d404[6] = _DAT_0341d404[6] + 0x400;
    uVar2 = _DAT_00c498d4;
    if (acStack_80[0] != '\0') {
      pcVar4 = acStack_80;
      do {
        cVar1 = *pcVar4;
        pcVar4 = pcVar4 + 1;
      } while (cVar1 != '\0');
      sVar5 = (int)pcVar4 - (int)(acStack_80 + 1);
      uVar7 = sVar5 + 0x68 & 0xfffffffc;
      if (_DAT_0341d404[6] == 0) {
        LOCK();
        _DAT_02b6c698 = _DAT_02b6c698 + 1;
        UNLOCK();
      }
      if (((_DAT_0341d404[4] + _DAT_0341d404[2]) - _DAT_0341d404[1]) + -0x2000 < (int)uVar7) {
        _DAT_0341d404[3] = 0;
      }
      else {
        puVar10 = (undefined2 *)(*_DAT_0341d404 + _DAT_0341d404[1]);
        _DAT_0341d404[1] = _DAT_0341d404[1] + uVar7;
        _DAT_0341d404[3] = (int)puVar10;
        *(undefined1 *)(puVar10 + 1) = 0x11;
        if (_DAT_035ebed8 == 0) {
          uVar6 = 0xffffffff;
          bVar8 = 0;
        }
        else {
          uVar6 = *(uint *)(&DAT_035ebecc + _DAT_035ebed8 * 4);
          if ((int)uVar6 < 0) {
            bVar8 = 0;
          }
          else {
            bVar8 = (byte)uVar6 | 0x80;
          }
        }
        *(byte *)((int)puVar10 + 3) = bVar8;
        if (uVar6 < 6) {
          uVar9 = (uint)(byte)PTR_DAT_01064c31;
          *(int *)(&DAT_035e60c4 + uVar6 * 0xa4) = *(int *)(&DAT_035e60c4 + uVar6 * 0xa4) + 1;
          *(uint *)(&DAT_035e60c8 + uVar6 * 0xa4) = *(int *)(&DAT_035e60c8 + uVar6 * 0xa4) + uVar9;
        }
        *puVar10 = (short)uVar7;
        *(undefined4 *)(puVar10 + 4) = uVar2;
        *(undefined4 *)(puVar10 + 6) = uVar2;
        *(float *)(puVar10 + 8) = _DAT_00d2b3c8;
        *(undefined4 *)(puVar10 + 0xc) = 0;
        *(undefined4 *)(puVar10 + 0x10) = _DAT_00c41b58;
        uVar2 = _DAT_00d30a50;
        *(undefined4 *)(puVar10 + 2) = 0;
        *(undefined4 *)(puVar10 + 0xe) = uVar3;
        *(undefined4 *)(puVar10 + 0x12) = uVar2;
        cVar1 = FUN_006226f0();
        if (cVar1 != '\0') {
          *(float *)(puVar10 + 0x12) = *(float *)(puVar10 + 0x12) * _DAT_00c519c8;
        }
        FUN_00698a80(&DAT_00c83274,puVar10 + 0x14);
        *(undefined4 *)(puVar10 + 0x16) = 0x40;
        *(undefined4 *)(puVar10 + 0x18) = 0;
        FID_conflict__memcpy(puVar10 + 0x32,acStack_80,sVar5);
        *(undefined1 *)((int)puVar10 + sVar5 + 100) = 0;
      }
    }
    _DAT_0341d404[6] = _DAT_0341d404[6] + -0x400;
    __snprintf(acStack_80,0x40,"intensity1 angle=%.2f factor=%.2f",(double)(float)fVar12,
               (double)(float)fVar14);
    _DAT_0341d404[6] = _DAT_0341d404[6] + 0x400;
    if (acStack_80[0] != '\0') {
      pcVar4 = acStack_80;
      do {
        cVar1 = *pcVar4;
        pcVar4 = pcVar4 + 1;
      } while (cVar1 != '\0');
      sVar5 = (int)pcVar4 - (int)(acStack_80 + 1);
      uVar7 = sVar5 + 0x68 & 0xfffffffc;
      if (_DAT_0341d404[6] == 0) {
        LOCK();
        _DAT_02b6c698 = _DAT_02b6c698 + 1;
        UNLOCK();
      }
      if (((_DAT_0341d404[4] + _DAT_0341d404[2]) - _DAT_0341d404[1]) + -0x2000 < (int)uVar7) {
        _DAT_0341d404[3] = 0;
      }
      else {
        puVar10 = (undefined2 *)(*_DAT_0341d404 + _DAT_0341d404[1]);
        _DAT_0341d404[1] = _DAT_0341d404[1] + uVar7;
        _DAT_0341d404[3] = (int)puVar10;
        *(undefined1 *)(puVar10 + 1) = 0x11;
        if (_DAT_035ebed8 == 0) {
          uVar6 = 0xffffffff;
          bVar8 = 0;
        }
        else {
          uVar6 = *(uint *)(&DAT_035ebecc + _DAT_035ebed8 * 4);
          if ((int)uVar6 < 0) {
            bVar8 = 0;
          }
          else {
            bVar8 = (byte)uVar6 | 0x80;
          }
        }
        *(byte *)((int)puVar10 + 3) = bVar8;
        if (uVar6 < 6) {
          uVar9 = (uint)(byte)PTR_DAT_01064c31;
          *(int *)(&DAT_035e60c4 + uVar6 * 0xa4) = *(int *)(&DAT_035e60c4 + uVar6 * 0xa4) + 1;
          *(uint *)(&DAT_035e60c8 + uVar6 * 0xa4) = *(int *)(&DAT_035e60c8 + uVar6 * 0xa4) + uVar9;
        }
        uVar2 = _DAT_00c498d4;
        *puVar10 = (short)uVar7;
        *(undefined4 *)(puVar10 + 4) = uVar2;
        *(undefined4 *)(puVar10 + 6) = _DAT_00c2ad2c;
        *(float *)(puVar10 + 8) = _DAT_00d2b3c8;
        *(undefined4 *)(puVar10 + 0xc) = 0;
        *(undefined4 *)(puVar10 + 0x10) = _DAT_00c41b58;
        uVar2 = _DAT_00d30a50;
        *(undefined4 *)(puVar10 + 2) = 0;
        *(undefined4 *)(puVar10 + 0xe) = uVar3;
        *(undefined4 *)(puVar10 + 0x12) = uVar2;
        cVar1 = FUN_006226f0();
        if (cVar1 != '\0') {
          *(float *)(puVar10 + 0x12) = *(float *)(puVar10 + 0x12) * _DAT_00c519c8;
        }
        FUN_00698a80(&DAT_00c83274,puVar10 + 0x14);
        *(undefined4 *)(puVar10 + 0x16) = 0x40;
        *(undefined4 *)(puVar10 + 0x18) = 0;
        FID_conflict__memcpy(puVar10 + 0x32,acStack_80,sVar5);
        *(undefined1 *)((int)puVar10 + sVar5 + 100) = 0;
      }
    }
    _DAT_0341d404[6] = _DAT_0341d404[6] + -0x400;
    __snprintf(acStack_80,0x40,"intensity=%.2f interp=%.2f",(double)fVar15,(double)fVar17);
    _DAT_0341d404[6] = _DAT_0341d404[6] + 0x400;
    if (acStack_80[0] != '\0') {
      pcVar4 = acStack_80;
      do {
        cVar1 = *pcVar4;
        pcVar4 = pcVar4 + 1;
      } while (cVar1 != '\0');
      sVar5 = (int)pcVar4 - (int)(acStack_80 + 1);
      uVar7 = sVar5 + 0x68 & 0xfffffffc;
      if (_DAT_0341d404[6] == 0) {
        LOCK();
        _DAT_02b6c698 = _DAT_02b6c698 + 1;
        UNLOCK();
      }
      if (((_DAT_0341d404[4] + _DAT_0341d404[2]) - _DAT_0341d404[1]) + -0x2000 < (int)uVar7) {
        _DAT_0341d404[3] = 0;
      }
      else {
        puVar10 = (undefined2 *)(*_DAT_0341d404 + _DAT_0341d404[1]);
        _DAT_0341d404[1] = _DAT_0341d404[1] + uVar7;
        _DAT_0341d404[3] = (int)puVar10;
        *(undefined1 *)(puVar10 + 1) = 0x11;
        if (_DAT_035ebed8 == 0) {
          uVar6 = 0xffffffff;
          bVar8 = 0;
        }
        else {
          uVar6 = *(uint *)(&DAT_035ebecc + _DAT_035ebed8 * 4);
          if ((int)uVar6 < 0) {
            bVar8 = 0;
          }
          else {
            bVar8 = (byte)uVar6 | 0x80;
          }
        }
        *(byte *)((int)puVar10 + 3) = bVar8;
        if (uVar6 < 6) {
          uVar9 = (uint)(byte)PTR_DAT_01064c31;
          *(int *)(&DAT_035e60c4 + uVar6 * 0xa4) = *(int *)(&DAT_035e60c4 + uVar6 * 0xa4) + 1;
          *(uint *)(&DAT_035e60c8 + uVar6 * 0xa4) = *(int *)(&DAT_035e60c8 + uVar6 * 0xa4) + uVar9;
        }
        uVar2 = _DAT_00c498d4;
        *puVar10 = (short)uVar7;
        *(undefined4 *)(puVar10 + 4) = uVar2;
        *(undefined4 *)(puVar10 + 6) = _DAT_00c08508;
        *(float *)(puVar10 + 8) = _DAT_00d2b3c8;
        *(undefined4 *)(puVar10 + 0xc) = 0;
        *(undefined4 *)(puVar10 + 0x10) = _DAT_00c41b58;
        uVar2 = _DAT_00d30a50;
        *(undefined4 *)(puVar10 + 2) = 0;
        *(undefined4 *)(puVar10 + 0xe) = uVar3;
        *(undefined4 *)(puVar10 + 0x12) = uVar2;
        cVar1 = FUN_006226f0();
        if (cVar1 != '\0') {
          *(float *)(puVar10 + 0x12) = *(float *)(puVar10 + 0x12) * _DAT_00c519c8;
        }
        FUN_00698a80(&DAT_00c83274,puVar10 + 0x14);
        *(undefined4 *)(puVar10 + 0x16) = 0x40;
        *(undefined4 *)(puVar10 + 0x18) = 0;
        FID_conflict__memcpy(puVar10 + 0x32,acStack_80,sVar5);
        *(undefined1 *)((int)puVar10 + sVar5 + 100) = 0;
      }
    }
    _DAT_0341d404[6] = _DAT_0341d404[6] + -0x400;
  }
  *(float *)(param_1 + 0xca0) = fVar15;
  *(float *)(param_1 + 0xca4) = fVar15;
  *(float *)(param_1 + 0xca8) = fVar15;
  *(float *)(param_1 + 0xcac) = fVar15;
  return;
}

