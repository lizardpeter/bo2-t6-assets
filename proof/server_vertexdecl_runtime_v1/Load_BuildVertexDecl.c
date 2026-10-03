
/* WARNING: Function: _chkstk replaced with injection: alloca_probe */
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */

void __cdecl Load_BuildVertexDecl(MaterialVertexDeclaration **param_1,MaterialPass *param_2)

{
  stream_source_info_t *psVar1;
  byte bVar2;
  MaterialVertexDeclaration *pMVar3;
  uint uVar4;
  uchar *puVar5;
  code *pcVar6;
  bool bVar7;
  byte **ppbVar8;
  int iVar9;
  byte *pbVar10;
  stream_source_info_t *unaff_EDI;
  int iVar11;
  byte *pbStack_1c44;
  MaterialVertexDeclaration **ppMStack_1c40;
  uint uStack_1c3c;
  int iStack_1c38;
  byte **ppbStack_1c34;
  int iStack_1c30;
  stream_source_info_t (*pasStack_1c2c) [11];
  uint auStack_1c28 [1792];
  undefined8 uStack_28;
  undefined8 uStack_20;
  undefined8 uStack_18;
  undefined8 uStack_10;
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  pMVar3 = *param_1;
  uStack_28 = *(undefined8 *)(pMVar3->routing).data;
  uStack_20 = *(undefined8 *)((pMVar3->routing).data + 4);
  uStack_18 = *(undefined8 *)((pMVar3->routing).data + 8);
  uStack_10 = *(undefined8 *)((pMVar3->routing).data + 0xc);
  ppMStack_1c40 = param_1;
  iStack_1c38 = 0x24;
  pasStack_1c2c = s_streamSourceInfo;
LAB_00a28e80:
  iVar11 = iStack_1c38;
  bVar7 = Dvar_GetBool(r_loadForRenderer);
  if (bVar7) {
    uVar4 = (param_2->vertexShader->prog).loadDef.programSize;
    puVar5 = (param_2->vertexShader->prog).loadDef.program;
    bVar2 = (*param_1)->streamCount;
    pbVar10 = (byte *)&uStack_28;
    iVar11 = 0;
    iStack_1c30 = 0;
    pbStack_1c44 = pbVar10;
    uStack_1c3c = (uint)bVar2;
    AssertValidVertexDeclOffsets(unaff_EDI);
    if (bVar2 != 0) {
      ppbStack_1c34 = &pbStack_1c44;
      do {
        bVar2 = *pbVar10;
        if ((10 < bVar2) &&
           (bVar7 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_material.cpp",0x51d,0,
                                     "(unsigned)(routingData->source) < (unsigned)(STREAM_SRC_COUNT)"
                                     ,
                                     "routingData->source doesn\'t index STREAM_SRC_COUNT\n\t%i not in [0, %i)"
                                    ), !bVar7)) {
          pcVar6 = (code *)swi(3);
          (*pcVar6)();
          return;
        }
        psVar1 = *pasStack_1c2c + bVar2;
        if (psVar1->Stream == 0xff) {
          iVar9 = 0;
          goto LAB_00a290ac;
        }
        if (psVar1->Stream != 0xfe) {
          bVar2 = pbVar10[1];
          iVar9 = iVar11;
          for (ppbVar8 = ppbStack_1c34; (0 < iVar9 && ((byte *)(uint)psVar1->Stream < ppbVar8[3]));
              ppbVar8 = ppbVar8 + -7) {
            *(undefined8 *)(ppbVar8 + 7) = *(undefined8 *)ppbVar8;
            *(undefined8 *)(ppbVar8 + 9) = *(undefined8 *)(ppbVar8 + 2);
            *(undefined8 *)(ppbVar8 + 0xb) = *(undefined8 *)(ppbVar8 + 4);
            ppbVar8[0xd] = ppbVar8[6];
            iVar9 = iVar9 + -1;
          }
          auStack_1c28[iVar9 * 7] = (uint)s_streamDestInfo[bVar2].Usage;
          auStack_1c28[iVar9 * 7 + 1] = (uint)s_streamDestInfo[bVar2].UsageIndex;
          auStack_1c28[iVar9 * 7 + 2] = (uint)psVar1->Type;
          auStack_1c28[iVar9 * 7 + 3] = (uint)psVar1->Stream;
          auStack_1c28[iVar9 * 7 + 4] = (uint)psVar1->Offset;
          iVar11 = iVar11 + 1;
          ppbStack_1c34 = ppbStack_1c34 + 7;
          auStack_1c28[iVar9 * 7 + 5] = 0;
          auStack_1c28[iVar9 * 7 + 6] = 0;
          pbVar10 = pbStack_1c44;
        }
        pbVar10 = pbVar10 + 2;
        uStack_1c3c = uStack_1c3c - 1;
        pbStack_1c44 = pbVar10;
      } while (uStack_1c3c != 0);
    }
    iVar9 = iStack_1c30;
    if (dx.device != (ID3D11Device *)0x0) {
      do {
        iVar9 = (**(code **)((int)*dx.device + 0x2c))
                          (dx.device,auStack_1c28,iVar11,puVar5,uVar4,&iStack_1c30);
        if (iVar9 < 0) goto LAB_00a29050;
      } while (alwaysfails != 0);
      goto LAB_00a2907a;
    }
    goto LAB_00a290ac;
  }
  *(undefined4 *)((int)(((*param_1)->routing).data + -2) + iVar11) = 0;
  goto LAB_00a290d0;
LAB_00a29050:
  do {
    g_disableRendering = g_disableRendering + 1;
    R_ErrorDescription(iVar9);
    Com_Error(ERR_FATAL,
              "c:\\t6\\code\\src\\gfx_d3d\\r_material.cpp (%i) dx.device->CreateInputLayout( elemTable, elemIndex, program, programSize, &decl ) failed: %s\n"
             );
  } while (alwaysfails != 0);
LAB_00a2907a:
  iVar9 = iStack_1c30;
  if ((iStack_1c30 == 0) &&
     (bVar7 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_material.cpp",0x54e,0,"(decl)",""),
     iVar9 = iStack_1c30, !bVar7)) {
    pcVar6 = (code *)swi(3);
    (*pcVar6)();
    return;
  }
LAB_00a290ac:
  *(int *)((int)(((*ppMStack_1c40)->routing).data + -2) + iStack_1c38) = iVar9;
  param_1 = ppMStack_1c40;
  iVar11 = iStack_1c38;
LAB_00a290d0:
  pasStack_1c2c = pasStack_1c2c + 1;
  iStack_1c38 = iVar11 + 4;
  if (0x73 < iStack_1c38) {
    (*param_1)->isLoaded = true;
    return;
  }
  goto LAB_00a28e80;
}

