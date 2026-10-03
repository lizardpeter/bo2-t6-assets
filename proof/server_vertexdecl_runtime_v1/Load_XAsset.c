
/* WARNING: Enum "XAssetType": Some values do not have unique names */
/* WARNING: Enum "nodeType": Some values do not have unique names */
/* WARNING: Enum "eAttachment": Some values do not have unique names */
/* WARNING: Enum "eAttachmentPoint": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl Load_XAsset(bool param_1)

{
  bool bVar1;
  
  bVar1 = Load_Stream(param_1,varXAsset,8);
  if (bVar1) {
    varXAssetHeader = &varXAsset->header;
    Load_XAssetHeader(false);
  }
  return;
}

