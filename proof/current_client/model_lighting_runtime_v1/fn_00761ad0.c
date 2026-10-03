
/* WARNING: Function: __alloca_probe replaced with injection: alloca_probe */

void FUN_00761ad0(undefined4 param_1)

{
  char cVar1;
  int iVar2;
  char *pcVar3;
  undefined4 uVar4;
  char acStack_2000 [8188];
  undefined4 uStack_4;
  
  uStack_4 = 0x761ada;
  pcVar3 = acStack_2000;
  iVar2 = FUN_004ce700(&PTR_s_r_sunsprite_shader_01063be0,0x15,acStack_2000,0x2000);
  if (iVar2 != 0) {
    do {
      cVar1 = *pcVar3;
      pcVar3 = pcVar3 + 1;
    } while (cVar1 != '\0');
    uVar4 = FUN_00593820("sun/%s.sun",param_1,acStack_2000,(int)pcVar3 - (int)(acStack_2000 + 1));
    FUN_0043a130(uVar4);
  }
  return;
}

