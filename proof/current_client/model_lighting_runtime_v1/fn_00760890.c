
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

int FUN_00760890(int param_1)

{
  uint *puVar1;
  uint uVar2;
  uint uVar3;
  uint uVar4;
  uint uVar5;
  int unaff_EDI;
  
  do {
    uVar5 = *(uint *)(param_1 + 0x58);
    while( true ) {
      uVar2 = *(uint *)(*(int *)(unaff_EDI + 0x4c) + uVar5 * 4);
      uVar4 = *(uint *)(*(int *)(unaff_EDI + 0x48) + uVar5 * 4) &
              *(uint *)(*(int *)(unaff_EDI + 0x44) + uVar5 * 4) & uVar2;
      uVar3 = 0x1f;
      if (uVar4 != 0) {
        for (; uVar4 >> uVar3 == 0; uVar3 = uVar3 - 1) {
        }
      }
      if (uVar4 == 0) {
        uVar3 = _DAT_00c51864;
      }
      uVar3 = uVar3 ^ 0x1f;
      if (uVar3 < 0x20) break;
      uVar5 = (uVar5 + 1) % *(uint *)(unaff_EDI + 0x54);
      if (uVar5 == *(uint *)(param_1 + 0x58)) {
        *(undefined4 *)(param_1 + 0x30) = 1;
        return 0;
      }
    }
    *(uint *)(param_1 + 0x58) = uVar5;
    puVar1 = (uint *)(*(int *)(unaff_EDI + 0x4c) + uVar5 * 4);
    LOCK();
    uVar4 = *puVar1;
    if (uVar2 == uVar4) {
      *puVar1 = ~(0x80000000U >> ((byte)uVar3 & 0x1f)) & uVar2;
      uVar4 = uVar2;
    }
    UNLOCK();
  } while (uVar4 != uVar2);
  return uVar5 * 0x20 + uVar3;
}

