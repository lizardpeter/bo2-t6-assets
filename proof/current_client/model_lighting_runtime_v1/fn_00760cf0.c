
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00760cf0(void)

{
  int iVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  int iStack_4;
  
  iVar1 = _DAT_03a36af0;
  iVar2 = 0;
  iVar5 = 0;
  iStack_4 = 4;
  do {
    iVar3 = iVar5 + 8;
    iVar6 = 4;
    iVar4 = iVar5;
    do {
      *(int *)(&DAT_03a36984 + iVar2 * 4) = iVar3 + -4;
      *(int *)(&DAT_03a36980 + iVar2 * 4) = iVar4;
      *(int *)(&DAT_03a36988 + iVar2 * 4) = iVar3;
      *(int *)(&DAT_03a3698c + iVar2 * 4) = iVar3 + 4;
      iVar2 = iVar2 + 4;
      iVar4 = iVar4 + iVar1;
      iVar3 = iVar3 + iVar1;
      iVar6 = iVar6 + -1;
    } while (iVar6 != 0);
    iVar5 = iVar5 + _DAT_03a36af4;
    iStack_4 = iStack_4 + -1;
  } while (iStack_4 != 0);
  return;
}

