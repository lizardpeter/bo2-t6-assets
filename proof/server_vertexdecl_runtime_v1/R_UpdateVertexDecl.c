
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl R_UpdateVertexDecl(GfxCmdBufState *param_1)

{
  MaterialPass *pMVar1;
  ID3D11DeviceContext *pIVar2;
  code *pcVar3;
  bool bVar4;
  ID3D11InputLayout *pIVar5;
  MaterialVertexShader *unaff_EDI;
  
  pMVar1 = (param_1->field10_0x25ac).localPass;
  if (pMVar1->vertexDecl == (MaterialVertexDeclaration *)0x0) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_shade.cpp",0x4b1,0,"(pass->vertexDecl)",
                             "");
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  if (pMVar1->vertexShader == (MaterialVertexShader *)0x0) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_shade.cpp",0x4d0,0,"(vertexShader)","");
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  if (pMVar1->vertexDecl == (MaterialVertexDeclaration *)0x0) {
    pIVar5 = (ID3D11InputLayout *)0x0;
  }
  else {
    pIVar5 = (pMVar1->vertexDecl->routing).decl[(param_1->prim).vertDeclType];
  }
  if ((param_1->prim).vertexDecl != pIVar5) {
    pIVar2 = (param_1->prim).field0_0x0.device;
    if (pIVar2 == (ID3D11DeviceContext *)0x0) {
      bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_state.h",0x792,0,"(device)","");
      if (!bVar4) {
        pcVar3 = (code *)swi(3);
        (*pcVar3)();
        return;
      }
    }
    (**(code **)((int)*pIVar2 + 0x44))(pIVar2,pIVar5);
    (param_1->prim).vertexDecl = pIVar5;
  }
  if ((pMVar1->field2_0x8).pixelShader == (MaterialPixelShader *)0x0) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_shade.cpp",0x4de,0,"(pass->pixelShader)"
                             ,"");
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  if (pMVar1->vertexDecl == (MaterialVertexDeclaration *)0xffffffdc) {
    bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_shade.cpp",0x4e1,0,
                             "(pass->vertexDecl->routing.decl)","");
    if (!bVar4) {
      pcVar3 = (code *)swi(3);
      (*pcVar3)();
      return;
    }
  }
  if ((pMVar1->vertexDecl->routing).decl[(param_1->prim).vertDeclType] == (ID3D11InputLayout *)0x0)
  {
    Com_Error(ERR_FATAL,
              "Vertex type %i doesn\'t have the information used by shader %s in material %s\n");
  }
  R_SetVertexShader(param_1,unaff_EDI);
  return;
}

