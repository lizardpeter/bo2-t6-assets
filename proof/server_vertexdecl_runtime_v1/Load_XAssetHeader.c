
/* WARNING: Enum "XAssetType": Some values do not have unique names */
/* WARNING: Enum "nodeType": Some values do not have unique names */
/* WARNING: Enum "eAttachment": Some values do not have unique names */
/* WARNING: Enum "eAttachmentPoint": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl Load_XAssetHeader(bool param_1)

{
  XAssetType XVar1;
  
  XVar1 = varXAsset->type;
  if (XVar1 == ASSET_TYPE_PHYSPRESET) {
    varPhysPresetPtr = &varXAssetHeader->physPreset;
    Load_PhysPresetPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_PHYSCONSTRAINTS) {
    varPhysConstraintsPtr = &varXAssetHeader->physConstraints;
    Load_PhysConstraintsPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_DESTRUCTIBLEDEF) {
    varDestructibleDefPtr = &varXAssetHeader->destructibleDef;
    Load_DestructibleDefPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_XANIMPARTS) {
    varXAnimPartsPtr = &varXAssetHeader->parts;
    Load_XAnimPartsPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_XMODEL) {
    varXModelPtr = &varXAssetHeader->model;
    Load_XModelPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_MATERIAL) {
    varMaterialHandle = &varXAssetHeader->material;
    Load_MaterialHandle(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_TECHNIQUE_SET) {
    varMaterialTechniqueSetPtr = &varXAssetHeader->techniqueSet;
    Load_MaterialTechniqueSetPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_IMAGE) {
    varGfxImagePtr = &varXAssetHeader->image;
    Load_GfxImagePtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_SOUND) {
    varSndBankPtr = &varXAssetHeader->sound;
    Load_SndBankPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_SOUND_PATCH) {
    varSndPatchPtr = &varXAssetHeader->soundPatch;
    Load_SndPatchPtr(param_1);
    return;
  }
  if ((XVar1 == ASSET_TYPE_CLIPMAP) || (XVar1 == ASSET_TYPE_CLIPMAP_PVS)) {
    varclipMap_ptr = &varXAssetHeader->clipMap;
    Load_clipMap_ptr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_COMWORLD) {
    varComWorldPtr = &varXAssetHeader->comWorld;
    Load_ComWorldPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_GAMEWORLD_SP) {
    varGameWorldSpPtr = &varXAssetHeader->gameWorldSp;
    Load_GameWorldSpPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_GAMEWORLD_MP) {
    varGameWorldMpPtr = &varXAssetHeader->gameWorldMp;
    Load_GameWorldMpPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_MAP_ENTS) {
    varMapEntsPtr = &varXAssetHeader->mapEnts;
    Load_MapEntsPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_GFXWORLD) {
    varGfxWorldPtr = &varXAssetHeader->gfxWorld;
    Load_GfxWorldPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_LIGHT_DEF) {
    varGfxLightDefPtr = &varXAssetHeader->lightDef;
    Load_GfxLightDefPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_FONT) {
    varFontHandle = &varXAssetHeader->font;
    Load_FontHandle(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_FONTICON) {
    varFontIconHandle = &varXAssetHeader->fontIcon;
    Load_FontIconHandle(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_MENULIST) {
    varMenuListPtr = &varXAssetHeader->menuList;
    Load_MenuListPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_MENU) {
    varmenuDef_ptr = &varXAssetHeader->menu;
    Load_menuDef_ptr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_LOCALIZE_ENTRY) {
    varLocalizeEntryPtr = &varXAssetHeader->localize;
    Load_LocalizeEntryPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_WEAPON) {
    varWeaponVariantDefPtr = &varXAssetHeader->weapon;
    Load_WeaponVariantDefPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_ATTACHMENT) {
    varWeaponAttachmentPtr = &varXAssetHeader->attachment;
    Load_WeaponAttachmentPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_ATTACHMENT_UNIQUE) {
    varWeaponAttachmentUniquePtr = &varXAssetHeader->attachmentUnique;
    Load_WeaponAttachmentUniquePtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_WEAPON_CAMO) {
    varWeaponCamoPtr = &varXAssetHeader->weaponCamo;
    Load_WeaponCamoPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_SNDDRIVER_GLOBALS) {
    varSndDriverGlobalsPtr = &varXAssetHeader->sndDriverGlobals;
    Load_SndDriverGlobalsPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_FX) {
    varFxEffectDefHandle = &varXAssetHeader->fx;
    Load_FxEffectDefHandle(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_IMPACT_FX) {
    varFxImpactTablePtr = &varXAssetHeader->impactFx;
    Load_FxImpactTablePtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_RAWFILE) {
    varRawFilePtr = &varXAssetHeader->rawfile;
    Load_RawFilePtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_STRINGTABLE) {
    varStringTablePtr = &varXAssetHeader->stringTable;
    Load_StringTablePtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_LEADERBOARD) {
    varLeaderboardDefPtr = &varXAssetHeader->leaderboardDef;
    Load_LeaderboardDefPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_XGLOBALS) {
    varXGlobalsPtr = &varXAssetHeader->xGlobals;
    Load_XGlobalsPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_DDL) {
    varddlRoot_ptr = &varXAssetHeader->ddlRoot;
    Load_ddlRoot_ptr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_GLASSES) {
    varGlassesPtr = &varXAssetHeader->glasses;
    Load_GlassesPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_EMBLEMSET) {
    varEmblemSetPtr = &varXAssetHeader->emblemSet;
    Load_EmblemSetPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_SCRIPTPARSETREE) {
    varScriptParseTreePtr = &varXAssetHeader->scriptParseTree;
    Load_ScriptParseTreePtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_KEYVALUEPAIRS) {
    varKeyValuePairsPtr = &varXAssetHeader->keyValuePairs;
    Load_KeyValuePairsPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_VEHICLEDEF) {
    varVehicleDefPtr = &varXAssetHeader->vehicleDef;
    Load_VehicleDefPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_MEMORYBLOCK) {
    varMemoryBlockPtr = &varXAssetHeader->memoryBlock;
    Load_MemoryBlockPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_ADDON_MAP_ENTS) {
    varAddonMapEntsPtr = &varXAssetHeader->addonMapEnts;
    Load_AddonMapEntsPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_TRACER) {
    varTracerDefPtr = &varXAssetHeader->tracerDef;
    Load_TracerDefPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_SKINNEDVERTS) {
    varSkinnedVertsDefPtr = &varXAssetHeader->skinnedVertsDef;
    Load_SkinnedVertsDefPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_QDB) {
    varQdbPtr = &varXAssetHeader->qdb;
    Load_QdbPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_SLUG) {
    varSlugPtr = &varXAssetHeader->slug;
    Load_SlugPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_FOOTSTEP_TABLE) {
    varFootstepTableDefPtr = &varXAssetHeader->footstepTableDef;
    Load_FootstepTableDefPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_FOOTSTEPFX_TABLE) {
    varFootstepFXTableDefPtr = &varXAssetHeader->footstepFXTableDef;
    Load_FootstepFXTableDefPtr(param_1);
    return;
  }
  if (XVar1 == ASSET_TYPE_ZBARRIER) {
    varZBarrierDefPtr = &varXAssetHeader->zbarrierDef;
    Load_ZBarrierDefPtr(param_1);
    return;
  }
  return;
}

