
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_0075a6a0(undefined4 param_1,undefined4 param_2,uint param_3,undefined4 param_4,
                 undefined4 param_5,undefined2 param_6,float *param_7)

{
  float fVar1;
  float fVar2;
  int in_EAX;
  int iVar3;
  uint *puVar4;
  uint uVar5;
  float *pfVar6;
  float *_Dst;
  float fVar7;
  float fVar8;
  float fVar9;
  float fStack_7f0;
  float fStack_7ec;
  float fStack_7e8;
  float fStack_7e4;
  float fStack_7e0;
  float fStack_7dc;
  float fStack_7d8;
  float fStack_7d4;
  float fStack_7d0;
  float fStack_7cc;
  float fStack_7c8;
  float fStack_7c4;
  float fStack_7c0;
  float fStack_7bc;
  float fStack_7b8;
  float fStack_7b4;
  float fStack_7b0;
  float fStack_7ac;
  float fStack_7a8;
  float fStack_7a4;
  float fStack_7a0;
  float fStack_79c;
  float fStack_798;
  float fStack_794;
  float fStack_790;
  float fStack_78c;
  float fStack_788;
  float fStack_778;
  float fStack_774;
  float fStack_770;
  float fStack_76c;
  float fStack_768;
  float fStack_764;
  float fStack_760;
  float fStack_75c;
  float fStack_758;
  float fStack_754;
  float fStack_750;
  float fStack_74c;
  float fStack_748;
  float fStack_744;
  float fStack_740;
  float fStack_73c;
  float fStack_738;
  float fStack_734;
  float fStack_730;
  float fStack_72c;
  float fStack_728;
  float fStack_724;
  float fStack_720;
  float fStack_71c;
  float fStack_718;
  float fStack_714;
  float fStack_710;
  float afStack_708 [224];
  float afStack_388 [225];
  
  if (*(int *)(in_EAX + 0x38) == 0) {
    FUN_007587f0();
  }
  else {
    FUN_00758720(afStack_708);
  }
  uVar5 = 1;
  if (1 < param_3) {
    do {
      if (*(int *)(in_EAX + 0x38) == 0) {
        FUN_007587f0();
      }
      else {
        FUN_00758720(afStack_388);
        fStack_7f0 = fStack_778 + fStack_7f0;
        fStack_7ec = fStack_774 + fStack_7ec;
        fStack_7e8 = fStack_770 + fStack_7e8;
        fStack_7e4 = fStack_76c + fStack_7e4;
        fStack_7e0 = fStack_768 + fStack_7e0;
        fStack_7dc = fStack_764 + fStack_7dc;
        fStack_7d8 = fStack_760 + fStack_7d8;
        fStack_7d4 = fStack_75c + fStack_7d4;
        fStack_7d0 = fStack_758 + fStack_7d0;
        fStack_7cc = fStack_754 + fStack_7cc;
        fStack_7c8 = fStack_750 + fStack_7c8;
        fStack_7c4 = fStack_74c + fStack_7c4;
        fStack_7c0 = fStack_748 + fStack_7c0;
        fStack_7bc = fStack_744 + fStack_7bc;
        fStack_7b8 = fStack_740 + fStack_7b8;
        fStack_7b4 = fStack_73c + fStack_7b4;
        fStack_7b0 = fStack_738 + fStack_7b0;
        fStack_7ac = fStack_734 + fStack_7ac;
        fStack_7a8 = fStack_730 + fStack_7a8;
        fStack_7a4 = fStack_72c + fStack_7a4;
        fStack_7a0 = fStack_728 + fStack_7a0;
        fStack_79c = fStack_724 + fStack_79c;
        fStack_798 = fStack_720 + fStack_798;
        fStack_794 = fStack_71c + fStack_794;
        fStack_78c = fStack_78c + fStack_714;
        fStack_790 = fStack_718 + fStack_790;
        fStack_788 = fStack_710 + fStack_788;
      }
      iVar3 = 0;
      do {
        *(float *)((int)afStack_708 + iVar3) =
             *(float *)((int)afStack_388 + iVar3) + *(float *)((int)afStack_708 + iVar3);
        *(float *)((int)afStack_708 + iVar3 + 4) =
             *(float *)((int)afStack_388 + iVar3 + 4) + *(float *)((int)afStack_708 + iVar3 + 4);
        *(float *)((int)afStack_708 + iVar3 + 8) =
             *(float *)((int)afStack_388 + iVar3 + 8) + *(float *)((int)afStack_708 + iVar3 + 8);
        *(float *)((int)afStack_708 + iVar3 + 0x10) =
             *(float *)((int)afStack_388 + iVar3 + 0x10) +
             *(float *)((int)afStack_708 + iVar3 + 0x10);
        *(float *)((int)afStack_708 + iVar3 + 0x14) =
             *(float *)((int)afStack_388 + iVar3 + 0x14) +
             *(float *)((int)afStack_708 + iVar3 + 0x14);
        *(float *)((int)afStack_708 + iVar3 + 0x18) =
             *(float *)((int)afStack_388 + iVar3 + 0x18) +
             *(float *)((int)afStack_708 + iVar3 + 0x18);
        *(float *)((int)afStack_708 + iVar3 + 0x20) =
             *(float *)((int)afStack_388 + iVar3 + 0x20) +
             *(float *)((int)afStack_708 + iVar3 + 0x20);
        *(float *)((int)afStack_708 + iVar3 + 0x24) =
             *(float *)((int)afStack_388 + iVar3 + 0x24) +
             *(float *)((int)afStack_708 + iVar3 + 0x24);
        *(float *)((int)afStack_708 + iVar3 + 0x28) =
             *(float *)((int)afStack_388 + iVar3 + 0x28) +
             *(float *)((int)afStack_708 + iVar3 + 0x28);
        *(float *)((int)afStack_708 + iVar3 + 0x30) =
             *(float *)((int)afStack_388 + iVar3 + 0x30) +
             *(float *)((int)afStack_708 + iVar3 + 0x30);
        *(float *)((int)afStack_708 + iVar3 + 0x34) =
             *(float *)((int)afStack_388 + iVar3 + 0x34) +
             *(float *)((int)afStack_708 + iVar3 + 0x34);
        *(float *)((int)afStack_708 + iVar3 + 0x38) =
             *(float *)((int)afStack_388 + iVar3 + 0x38) +
             *(float *)((int)afStack_708 + iVar3 + 0x38);
        *(float *)((int)afStack_708 + iVar3 + 0x40) =
             *(float *)((int)afStack_388 + iVar3 + 0x40) +
             *(float *)((int)afStack_708 + iVar3 + 0x40);
        *(float *)((int)afStack_708 + iVar3 + 0x44) =
             *(float *)((int)afStack_388 + iVar3 + 0x44) +
             *(float *)((int)afStack_708 + iVar3 + 0x44);
        *(float *)((int)afStack_708 + iVar3 + 0x48) =
             *(float *)((int)afStack_388 + iVar3 + 0x48) +
             *(float *)((int)afStack_708 + iVar3 + 0x48);
        *(float *)((int)afStack_708 + iVar3 + 0x50) =
             *(float *)((int)afStack_388 + iVar3 + 0x50) +
             *(float *)((int)afStack_708 + iVar3 + 0x50);
        *(float *)((int)afStack_708 + iVar3 + 0x54) =
             *(float *)((int)afStack_388 + iVar3 + 0x54) +
             *(float *)((int)afStack_708 + iVar3 + 0x54);
        *(float *)((int)afStack_708 + iVar3 + 0x58) =
             *(float *)((int)afStack_388 + iVar3 + 0x58) +
             *(float *)((int)afStack_708 + iVar3 + 0x58);
        *(float *)((int)afStack_708 + iVar3 + 0x60) =
             *(float *)((int)afStack_388 + iVar3 + 0x60) +
             *(float *)((int)afStack_708 + iVar3 + 0x60);
        *(float *)((int)afStack_708 + iVar3 + 100) =
             *(float *)((int)afStack_388 + iVar3 + 100) + *(float *)((int)afStack_708 + iVar3 + 100)
        ;
        *(float *)((int)afStack_708 + iVar3 + 0x68) =
             *(float *)((int)afStack_388 + iVar3 + 0x68) +
             *(float *)((int)afStack_708 + iVar3 + 0x68);
        *(float *)((int)afStack_708 + iVar3 + 0x70) =
             *(float *)((int)afStack_388 + iVar3 + 0x70) +
             *(float *)((int)afStack_708 + iVar3 + 0x70);
        *(float *)((int)afStack_708 + iVar3 + 0x74) =
             *(float *)((int)afStack_388 + iVar3 + 0x74) +
             *(float *)((int)afStack_708 + iVar3 + 0x74);
        *(float *)((int)afStack_708 + iVar3 + 0x78) =
             *(float *)((int)afStack_388 + iVar3 + 0x78) +
             *(float *)((int)afStack_708 + iVar3 + 0x78);
        iVar3 = iVar3 + 0x80;
      } while (iVar3 < 0x380);
      uVar5 = uVar5 + 1;
    } while (uVar5 < param_3);
  }
  fVar2 = _DAT_00c519c8;
  fVar1 = _DAT_00bda7c8;
  if (*(int *)(in_EAX + 0x38) == 0) {
    _memset(param_7,0,0x30);
  }
  else {
    fVar7 = fStack_7ec * _DAT_00c519c8 + fStack_7f0 * _DAT_00bda7c8 + fStack_7e8 * _DAT_00bda7c8 +
            _DAT_00c5040c;
    fVar8 = fStack_798 * _DAT_00c519c8 + fStack_79c * _DAT_00bda7c8 + fStack_794 * _DAT_00bda7c8;
    fVar9 = _DAT_00d2b3c8 / fVar7;
    param_7[3] = fVar8 * _DAT_00c557d0;
    param_7[2] = fStack_7e8 * fVar9;
    *param_7 = fStack_7f0 * fVar9;
    param_7[1] = fStack_7ec * fVar9;
    param_7[4] = fStack_7e0 * fVar2 + fStack_7e4 * fVar1 + fStack_7dc * fVar1;
    param_7[5] = fStack_7d4 * fVar2 + fStack_7d8 * fVar1 + fStack_7d0 * fVar1;
    param_7[7] = fVar7 - fVar8;
    param_7[6] = fStack_7c8 * fVar2 + fStack_7cc * fVar1 + fStack_7c4 * fVar1;
    param_7[8] = fStack_7bc * fVar2 + fStack_7c0 * fVar1 + fStack_7b8 * fVar1;
    param_7[9] = fStack_7b0 * fVar2 + fStack_7b4 * fVar1 + fStack_7ac * fVar1;
    param_7[10] = fStack_7a4 * fVar2 + fStack_7a8 * fVar1 + fStack_7a0 * fVar1;
    param_7[0xb] = fStack_78c * fVar2 + fStack_790 * fVar1 + fStack_788 * fVar1;
  }
  FUN_00762770(afStack_708,param_4);
  iVar3 = _DAT_0341d400;
  puVar4 = (uint *)(_DAT_0341d400 + 0x462c68);
  LOCK();
  uVar5 = *puVar4;
  *puVar4 = *puVar4 + 1;
  UNLOCK();
  if (0xfff < uVar5) {
    FUN_0058fc30(0,"modelLightingPatchList ran out of elements.");
  }
  _Dst = (float *)(uVar5 * 900 + 0xdec68 + iVar3);
  _memset(_Dst,0,900);
  *(undefined2 *)_Dst = param_6;
  pfVar6 = afStack_708;
  for (iVar3 = 0xe0; _Dst = _Dst + 1, iVar3 != 0; iVar3 = iVar3 + -1) {
    *_Dst = *pfVar6;
    pfVar6 = pfVar6 + 1;
  }
  return;
}

