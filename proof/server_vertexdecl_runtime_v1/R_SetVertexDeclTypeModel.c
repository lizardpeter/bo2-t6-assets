
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl R_SetVertexDeclTypeModel(XSurface *param_1,GfxCmdBufState *param_2)

{
  (param_2->prim).vertDeclType = VERTDECL_PACKED;
  R_UpdateVertexDecl(param_2);
  return;
}

