
/* WARNING: Enum "XAssetType": Some values do not have unique names */
/* WARNING: Enum "nodeType": Some values do not have unique names */
/* WARNING: Enum "eAttachment": Some values do not have unique names */
/* WARNING: Enum "eAttachmentPoint": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl DB_SetXAssetName(XAsset *param_1,char *param_2)

{
  code *pcVar1;
  bool bVar2;
  
  if (DB_XAssetSetNameHandler[param_1->type] == (_func___cdecl_void_XAssetHeader_ptr_char_ptr *)0x0)
  {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\database\\db_assetnames.cpp",0x3ca,0,
                             "(DB_XAssetSetNameHandler[asset->type])","");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  (*DB_XAssetSetNameHandler[param_1->type])(&param_1->header,param_2);
  return;
}

