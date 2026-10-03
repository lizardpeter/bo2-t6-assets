
dvar_t * __cdecl
Dvar_RegisterVariant
          (char *param_1,dvarType_t param_2,uint param_3,DvarValue param_4,DvarLimits param_5,
          char *param_6)

{
  code *pcVar1;
  DvarValue DVar2;
  DvarValue DVar3;
  DvarLimits DVar4;
  DvarLimits DVar5;
  bool bVar6;
  int iVar7;
  dvar_t *pdVar8;
  undefined4 unaff_EBX;
  char *unaff_EBP;
  char *unaff_ESI;
  dvar_t *unaff_EDI;
  uint in_stack_00000010;
  
  if ((param_2 & 0x4000) == DVAR_TYPE_INVALID) {
    iVar7 = CanKeepStringPointer((char *)unaff_EDI);
    if (iVar7 == 0) {
      bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\universal\\dvar.cpp",0xae6,0,
                               "(((flags & (1 << 14)) || CanKeepStringPointer( dvarName )))",
                               "(dvarName) = %s");
      if (!bVar6) {
        pcVar1 = (code *)swi(3);
        pdVar8 = (dvar_t *)(*pcVar1)();
        return pdVar8;
      }
    }
  }
  pdVar8 = Dvar_FindMalleableVar(unaff_ESI);
  if (pdVar8 != (dvar_t *)0x0) {
    DVar2.integer64._4_4_ = param_4.integer;
    DVar2.unsignedInt = in_stack_00000010;
    DVar2._8_4_ = param_4._4_4_;
    DVar2._12_4_ = param_4._8_4_;
    DVar4.integer.max = (int)param_5.integer64.min;
    DVar4.enumeration.stringCount = param_4._12_4_;
    DVar4.integer64.max._0_4_ = param_5.integer64.min._4_4_;
    DVar4.integer64.max._4_4_ = param_5.integer64.max._0_4_;
    Dvar_Reregister(unaff_EDI,param_1,param_2,param_3,DVar2,DVar4,unaff_ESI);
    return pdVar8;
  }
  DVar3._12_4_ = (int)param_5.integer64.min;
  DVar3._0_12_ = param_4._4_12_;
  DVar5.integer64.max._0_4_ = unaff_ESI;
  DVar5.integer64.min = param_5._4_8_;
  DVar5.integer64.max._4_4_ = unaff_EBX;
  pdVar8 = Dvar_RegisterNew((char *)param_2,param_3,in_stack_00000010,DVar3,DVar5,unaff_EBP);
  return pdVar8;
}

