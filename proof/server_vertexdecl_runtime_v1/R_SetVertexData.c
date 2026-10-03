
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

int __cdecl R_SetVertexData(GfxCmdBufState *param_1,void *param_2,int param_3,int param_4)

{
  GfxVertexBufferState *pGVar1;
  ID3D11Buffer *pIVar2;
  int iVar3;
  code *pcVar4;
  bool bVar5;
  int iVar6;
  void *pvVar7;
  
  if (param_3 < 1) {
    bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_shade.cpp",0x579,0,"(vertexCount > 0)",
                             "");
    if (!bVar5) {
      pcVar4 = (code *)swi(3);
      iVar6 = (*pcVar4)();
      return iVar6;
    }
  }
  Sys_EnterCriticalSection(CRITSECT_DXCONTEXT);
  iVar6 = param_3 * param_4;
  pGVar1 = param_1->backEndData->dynamicVertexBuffer;
  if (iVar6 - pGVar1->total != 0 && pGVar1->total <= iVar6) {
    bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_shade.cpp",0x585,0,
                             "((totalSize <= bufferState->total))","(totalSize) = %i");
    if (!bVar5) {
      pcVar4 = (code *)swi(3);
      iVar6 = (*pcVar4)();
      return iVar6;
    }
  }
  if (pGVar1->total < pGVar1->used + iVar6) {
    bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_shade.cpp",0x58a,0,
                             "(bufferState->used + totalSize <= bufferState->total)","");
    if (!bVar5) {
      pcVar4 = (code *)swi(3);
      iVar6 = (*pcVar4)();
      return iVar6;
    }
  }
  pIVar2 = pGVar1->buffer;
  if (pIVar2 == (ID3D11Buffer *)0x0) {
    bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_shade.cpp",0x597,0,"(vb)","");
    if (!bVar5) {
      pcVar4 = (code *)swi(3);
      iVar6 = (*pcVar4)();
      return iVar6;
    }
  }
  pvVar7 = R_LockVertexBuffer(dx.context,pIVar2,pGVar1->used,iVar6,(pGVar1->used != 0) + 4);
  if (pvVar7 == (void *)0x0) {
    bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_shade.cpp",0x5a4,0,"(bufferData)","");
    if (!bVar5) {
      pcVar4 = (code *)swi(3);
      iVar6 = (*pcVar4)();
      return iVar6;
    }
  }
  else {
    Com_Memcpy(pvVar7,param_2,iVar6);
  }
  R_UnlockVertexBuffer(dx.context,pIVar2);
  iVar3 = pGVar1->used;
  pGVar1->used = pGVar1->used + iVar6;
  if ((_S1 & 1) == 0) {
    _S1 = _S1 | 1;
    __hwm_id = BB_RegisterHighWaterMark("vertexbuf");
  }
  BB_SetHighWaterMark(__hwm_id,(uint)pGVar1);
  Sys_LeaveCriticalSection(CRITSECT_DXCONTEXT);
  return iVar3;
}

