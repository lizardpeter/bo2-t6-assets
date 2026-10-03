
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl
R_DrawStaticModelsSkinnedDrawSurfLighting
          (GfxStaticModelDrawStream *param_1,GfxCmdBufContext param_2)

{
  XSurface *pXVar1;
  ID3D11Buffer *pIVar2;
  GfxStaticModelDrawInst *pGVar3;
  ushort *puVar4;
  code *pcVar5;
  bool bVar6;
  uint uVar7;
  GfxStaticModelDrawInst *pGVar8;
  undefined4 uVar9;
  undefined4 uVar10;
  uint uStack_18;
  GfxDrawPrimArgs GStack_14;
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  pXVar1 = param_1->localSurf;
  R_SetVertexDeclTypeModel(pXVar1,param_2.field0_0x0._s_0.state);
  if (pXVar1 == (XSurface *)0x0) {
    bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_draw_staticmodel.cpp",0x647,0,"(xsurf)",
                             "");
    if (!bVar6) {
      pcVar5 = (code *)swi(3);
      (*pcVar5)();
      return;
    }
  }
  GStack_14.triCount = XSurfaceGetNumTris(pXVar1);
  GStack_14.vertexCount = XSurfaceGetNumVerts(pXVar1);
  GStack_14.baseIndex =
       R_SetIndexDataIndexCount
                 (param_2.field0_0x0._s_0.state,pXVar1->triIndices,GStack_14.triCount * 3);
  R_CheckVertexDataOverflow
            ((param_2.field0_0x0._s_0.state)->backEndData->dynamicVertexBuffer,
             GStack_14.vertexCount << 5);
  uVar7 = R_SetVertexData(param_2.field0_0x0._s_0.state,pXVar1->verts0,GStack_14.vertexCount,0x20);
  pIVar2 = (param_2.field0_0x0._s_0.state)->backEndData->dynamicVertexBuffer->buffer;
  if (pIVar2 == (ID3D11Buffer *)0x0) {
    bVar6 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_draw_staticmodel.cpp",0x664,0,"(vb)","")
    ;
    if (!bVar6) {
      pcVar5 = (code *)swi(3);
      (*pcVar5)();
      return;
    }
  }
  R_SetStreamSource(&(param_2.field0_0x0._s_0.state)->prim,pIVar2,uVar7,0x20,GStack_14.vertexCount);
  uVar7 = param_1->smodelCount;
  pGVar3 = ((rgp.world)->dpvs).smodelDrawInsts;
  puVar4 = param_1->smodelList;
  uStack_18 = 0;
  if (uVar7 != 0) {
    do {
      pGVar8 = pGVar3 + puVar4[uStack_18];
      uVar9 = param_2.field0_0x0._s_0.source;
      uVar10 = param_2.field0_0x0._s_0.state;
      R_SetReflectionProbe(param_2,(uint)pGVar8->reflectionProbeIndex);
      R_DrawStaticModelDrawSurfPlacement
                ((GfxStaticModelDrawInst *)uVar9,(GfxCmdBufSourceState *)uVar10);
      R_SetStaticModelLightingForSource(pGVar8,param_2.field0_0x0._s_0.source);
      R_SetupPassPerPrimArgs(param_2);
      R_DrawIndexedPrimitive
                (param_2.field0_0x0._s_0.state,&(param_2.field0_0x0._s_0.state)->prim,&GStack_14);
      uStack_18 = uStack_18 + 1;
    } while (uStack_18 < uVar7);
  }
  return;
}

