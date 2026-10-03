
void FUN_007619f0(void)

{
  undefined4 uVar1;
  int iVar2;
  undefined4 uStack_4;
  
  uVar1 = FUN_00593820("sun/%s.sun");
  iVar2 = FUN_00513030(uVar1,&uStack_4);
  if (-1 < iVar2) {
    iVar2 = FUN_00686bb0(&PTR_s_r_sunsprite_shader_01063be0,0x15,uStack_4,uVar1);
    if (iVar2 != 0) {
      FUN_00761700();
    }
    thunk_FUN_006129f0(uStack_4);
  }
  return;
}

