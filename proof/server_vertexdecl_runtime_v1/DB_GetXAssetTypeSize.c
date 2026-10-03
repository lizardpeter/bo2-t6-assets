
int __cdecl DB_GetXAssetTypeSize(int param_1)

{
  code *pcVar1;
  bool bVar2;
  int iVar3;
  
  if (DB_GetXAssetSizeHandler[param_1] == (_func___cdecl_int *)0x0) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\database\\db_assetnames.cpp",0x3d1,0,
                             "(DB_GetXAssetSizeHandler[type])","");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      iVar3 = (*pcVar1)();
      return iVar3;
    }
  }
                    /* WARNING: Could not recover jumptable at 0x005355cd. Too many branches */
                    /* WARNING: Treating indirect jump as call */
  iVar3 = (*DB_GetXAssetSizeHandler[param_1])();
  return iVar3;
}

