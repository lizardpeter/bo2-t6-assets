
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00760bf0(void)

{
  short sVar1;
  uint uVar2;
  uint uVar3;
  uint uVar4;
  uint uStack_3c;
  undefined1 auStack_34 [52];
  
  uVar4 = 0;
  if (_DAT_03a36910 != 0) {
    _DAT_03a36910 = 0;
    uVar3 = *(int *)(_DAT_035ae280 + 0x310) + 0x1fU >> 5;
    if (uVar3 != 0) {
      do {
        uStack_3c = *(uint *)(&DAT_03a2ad00 + uVar4 * 4);
        if (uStack_3c != 0) {
          while( true ) {
            uVar2 = 0x1f;
            if (uStack_3c != 0) {
              for (; uStack_3c >> uVar2 == 0; uVar2 = uVar2 - 1) {
              }
            }
            if (uStack_3c == 0) {
              uVar2 = _DAT_00c51864;
            }
            uVar2 = uVar2 ^ 0x1f;
            if (0x1f < uVar2) break;
            uStack_3c = uStack_3c & ~(0x80000000U >> ((byte)uVar2 & 0x1f));
            sVar1 = *(short *)((uVar2 + uVar4 * 0x20) * 0x98 + *(int *)(_DAT_035ae280 + 0x36c) +
                              0x44) + -1;
            if ((*(int *)(_DAT_035ae280 + 0x208) == 0) && (*(int *)(_DAT_035ae280 + 0x200) == 0)) {
              FUN_0075aee0(sVar1,0,auStack_34);
            }
            else {
              FUN_0075a3f0(0,sVar1,auStack_34);
            }
            FUN_007603f0();
          }
        }
        uVar4 = uVar4 + 1;
      } while (uVar4 < uVar3);
    }
  }
  return;
}

