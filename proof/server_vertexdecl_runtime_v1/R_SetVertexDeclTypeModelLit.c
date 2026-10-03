
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl R_SetVertexDeclTypeModelLit(XSurface *param_1,GfxCmdBufState *param_2)

{
  MaterialVertexDeclType MVar1;
  
  MVar1 = VERTDECL_PACKED;
  if (((param_2->field10_0x25ac).localPass)->materialType == '\x03') {
    MVar1 = VERTDECL_PACKED_LMAP_VC;
  }
  (param_2->prim).vertDeclType = MVar1;
  R_UpdateVertexDecl(param_2);
  return;
}

