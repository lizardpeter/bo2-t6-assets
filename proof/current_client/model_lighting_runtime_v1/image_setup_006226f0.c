
bool FUN_006226f0(int param_1)

{
  int iVar1;
  
  if (param_1 == 0) {
    return false;
  }
  if (*(int *)(param_1 + 0x10) == 1) {
    return (bool)*(undefined1 *)(param_1 + 0x18);
  }
  iVar1 = FUN_00a7301a(*(undefined4 *)(param_1 + 0x18));
  return iVar1 != 0;
}

