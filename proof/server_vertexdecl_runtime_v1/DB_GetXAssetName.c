
/* WARNING: Enum "XAssetType": Some values do not have unique names */
/* WARNING: Enum "nodeType": Some values do not have unique names */
/* WARNING: Enum "eAttachment": Some values do not have unique names */
/* WARNING: Enum "eAttachmentPoint": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

char * __cdecl DB_GetXAssetName(XAsset *param_1)

{
  code *pcVar1;
  bool bVar2;
  char *pcVar3;
  
  if (param_1 == (XAsset *)0x0) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\database\\db_assetnames.cpp",0x3c3,0,"(asset)","");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      pcVar3 = (char *)(*pcVar1)();
      return pcVar3;
    }
  }
  pcVar3 = DB_GetXAssetHeaderName(param_1->type,&param_1->header);
  return pcVar3;
}

