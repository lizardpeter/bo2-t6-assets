
void FUN_00760380(void)

{
  int *in_EAX;
  int iVar1;
  int iVar2;
  int *piVar3;
  int iStack_8;
  undefined4 uStack_4;
  
  iVar2 = *in_EAX;
  iVar1 = FUN_00763cf0(iVar2,&iStack_8,&uStack_4,0);
  if ((iVar1 != 0) && (*(uint *)(iStack_8 + 0x30) < 4)) {
    piVar3 = (int *)(iVar2 + 0x30);
    LOCK();
    iVar2 = *piVar3;
    if (iVar2 == 2) {
      *piVar3 = 3;
      iVar2 = 2;
    }
    UNLOCK();
    if (iVar2 == 2) {
      iVar2 = FUN_0075ff80(iStack_8,uStack_4,iVar1);
      *(int *)(iStack_8 + 0x30) = iVar2 + 4;
    }
  }
  return;
}

