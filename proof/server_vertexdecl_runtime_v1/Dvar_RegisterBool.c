
dvar_t * __cdecl _Dvar_RegisterBool(char *param_1,bool param_2,uint param_3,char *param_4)

{
  DvarValue DVar1;
  undefined1 auVar2 [16];
  dvar_t *pdVar3;
  undefined4 unaff_EDI;
  ulonglong uStack_c;
  
  DVar1._8_8_ = 0;
  DVar1.integer64 = uStack_c;
  auVar2._4_4_ = unaff_EDI;
  auVar2._0_4_ = param_4;
  auVar2._8_8_ = 0;
  pdVar3 = Dvar_RegisterVariant
                     (&DAT_00000001,param_3,(uint)param_2,DVar1,(DvarLimits)(auVar2 << 0x40),
                      (char *)(uint)param_2);
  return pdVar3;
}

