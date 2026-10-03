
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

uint FUN_00760930(float *param_1,float param_2,undefined4 param_3,ushort *param_4,
                 undefined4 *param_5)

{
  float *pfVar1;
  uint *puVar2;
  undefined1 *puVar3;
  undefined4 uVar4;
  undefined1 uVar5;
  int iVar6;
  int iVar7;
  ushort uVar8;
  uint uVar9;
  int iVar10;
  
  uVar8 = *param_4;
  if (uVar8 != 0) {
    uVar9 = ((uint)uVar8 - _DAT_03a36a84) - 1;
    pfVar1 = (float *)(_DAT_03a36aa8 + uVar9 * 0xc);
    if (0.0 < param_2) {
      if (param_2 <=
          (pfVar1[1] - param_1[1]) * (pfVar1[1] - param_1[1]) +
          (*pfVar1 - *param_1) * (*pfVar1 - *param_1) +
          (pfVar1[2] - param_1[2]) * (pfVar1[2] - param_1[2])) goto LAB_00760999;
    }
    else if (((*param_1 != *pfVar1) || (param_1[1] != pfVar1[1])) || (param_1[2] != pfVar1[2]))
    goto LAB_00760999;
    uVar4 = *(undefined4 *)(_DAT_03a36aa4 + uVar9 * 4);
    if ((char)uVar4 != -1) {
      puVar2 = (uint *)(_DAT_03a36acc + (uVar9 >> 5) * 4);
      LOCK();
      *puVar2 = *puVar2 & ~(0x80000000U >> ((byte)uVar9 & 0x1f));
      UNLOCK();
      *param_5 = uVar4;
      return (uint)uVar8;
    }
  }
LAB_00760999:
  iVar6 = FUN_00760890(&DAT_03a36a80);
  if (_DAT_03a36ab0 == 0) {
    iVar10 = _DAT_03a36a84 + iVar6;
    pfVar1 = (float *)(_DAT_03a36aa8 + iVar6 * 0xc);
    *pfVar1 = *param_1;
    pfVar1[1] = param_1[1];
    pfVar1[2] = param_1[2];
    uVar8 = (ushort)(iVar10 + 1U);
    *param_4 = uVar8;
    *(undefined1 *)param_5 = 0xff;
    iVar7 = FUN_0071f960(param_1);
    if (iVar7 == 0) {
      iVar7 = FUN_0071f3c0();
      if (iVar7 == -1) {
        iVar7 = FUN_0071f8e0();
      }
      else {
        iVar7 = FUN_0071f700(param_1);
      }
    }
    *(ushort *)((int)param_5 + 2) = uVar8;
    *(char *)((int)param_5 + 1) = (char)iVar7;
    *(undefined4 *)(_DAT_03a36aa4 + iVar6 * 4) = *param_5;
    _memset((void *)(iVar6 * 0x34 + _DAT_03a36aac),0,0x34);
    iVar7 = (iVar10 - _DAT_03a36a84) * 0x34 + _DAT_03a36aac;
    puVar3 = (undefined1 *)(_DAT_03a36aa4 + iVar6 * 4);
    uVar5 = FUN_0075bb80(_DAT_035ae280 + 0x1d0,param_1,iVar10,iVar7 + 0x30,iVar7,param_3);
    *(undefined1 *)param_5 = uVar5;
    if (puVar3 != (undefined1 *)0x0) {
      *puVar3 = uVar5;
    }
    return iVar10 + 1U & 0xffff;
  }
  *param_5 = 0xff;
  return 0;
}

