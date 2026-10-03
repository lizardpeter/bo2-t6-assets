
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl R_SetVertexDeclTypeWorldSurface(GfxCmdBufState *param_1,GfxSurface *param_2)

{
  MaterialVertexDeclType MVar1;
  
  MVar1 = VERTDECL_PACKED_WORLD;
  if ((param_1->technique->flags & 8) != 0) {
    MVar1 = ((param_1->material->field8_0x5c).localTechniqueSet)->worldVertFormat +
            VERTDECL_PACKED_WORLD;
  }
  (param_1->prim).vertDeclType = MVar1;
  R_UpdateVertexDecl(param_1);
  return;
}

