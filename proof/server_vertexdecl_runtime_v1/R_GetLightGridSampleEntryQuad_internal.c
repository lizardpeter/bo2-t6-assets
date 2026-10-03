
void __cdecl
R_GetLightGridSampleEntryQuad
          (GfxLightGrid *param_1,uint *param_2,GfxLightGridEntry **param_3,uint *param_4)

{
  byte *pbVar1;
  byte bVar2;
  ushort uVar3;
  code *pcVar4;
  bool bVar5;
  uint uVar6;
  ushort *puVar7;
  int iVar8;
  uint uVar9;
  int iVar10;
  uint uVar11;
  ushort *puVar12;
  GfxLightGridEntry *pGVar13;
  int iStack_8;
  
  uVar11 = param_1->rowAxis;
  uVar6 = param_2[uVar11] - (uint)param_1->mins[uVar11];
  if ((((uint)param_1->maxs[uVar11] - (uint)param_1->mins[uVar11]) + 1 <= uVar6) ||
     (param_1->rowDataStart[uVar6] == 0xffff)) {
    *param_3 = (GfxLightGridEntry *)0x0;
    param_3[1] = (GfxLightGridEntry *)0x0;
    param_3[2] = (GfxLightGridEntry *)0x0;
    param_3[3] = (GfxLightGridEntry *)0x0;
    return;
  }
  uVar11 = (uint)param_1->rowDataStart[uVar6] * 4;
  if ((param_1->rawRowDataSize <= uVar11) &&
     (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\rb_light.cpp",0x48a,0,
                               "(unsigned)(rowDataStart * 4) < (unsigned)(lightGrid->rawRowDataSize)"
                               ,
                               "rowDataStart * 4 doesn\'t index lightGrid->rawRowDataSize\n\t%i not in [0, %i)"
                              ), !bVar5)) {
    pcVar4 = (code *)swi(3);
    (*pcVar4)();
    return;
  }
  puVar12 = (ushort *)(param_1->rawRowData + uVar11);
  if ((param_1->entryCount <= *(uint *)(param_1->rawRowData + uVar11 + 8)) &&
     (bVar5 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\rb_light.cpp",0x48f,0,
                               "(unsigned)(row->firstEntry) < (unsigned)(lightGrid->entryCount)",
                               "row->firstEntry doesn\'t index lightGrid->entryCount\n\t%i not in [0, %i)"
                              ), !bVar5)) {
    pcVar4 = (code *)swi(3);
    (*pcVar4)();
    return;
  }
  uVar6 = param_2[param_1->colAxis] - (uint)*puVar12;
  uVar11 = param_2[2] - (uint)puVar12[2];
  if ((uint)puVar12[1] < uVar6 + 1) {
    *param_3 = (GfxLightGridEntry *)0x0;
    param_3[1] = (GfxLightGridEntry *)0x0;
    param_3[2] = (GfxLightGridEntry *)0x0;
    param_3[3] = (GfxLightGridEntry *)0x0;
    return;
  }
  uVar3 = puVar12[3];
  if ((uint)uVar3 < uVar11 + 1) {
    *param_3 = (GfxLightGridEntry *)0x0;
    param_3[1] = (GfxLightGridEntry *)0x0;
    param_3[2] = (GfxLightGridEntry *)0x0;
    param_3[3] = (GfxLightGridEntry *)0x0;
    if (param_2[2] < (uint)puVar12[2]) {
      *param_4 = 0;
      return;
    }
  }
  else {
    iStack_8 = *(int *)(puVar12 + 4);
    iVar8 = (0xff < uVar3) + 3;
    puVar7 = puVar12 + 6;
    if (uVar6 == 0xffffffff) {
      *param_3 = (GfxLightGridEntry *)0x0;
      param_3[1] = (GfxLightGridEntry *)0x0;
      uVar6 = (uint)(byte)puVar12[7];
      if (0xff < puVar12[3]) {
        uVar6 = (uint)CONCAT11(*(undefined1 *)((int)puVar12 + 0xf),(byte)puVar12[7]);
      }
      uVar9 = uVar11 - uVar6;
      if (uVar9 < *(byte *)((int)puVar12 + 0xd)) {
        pGVar13 = param_1->entries + iStack_8 + uVar9;
      }
      else {
        pGVar13 = (GfxLightGridEntry *)0x0;
      }
      param_3[2] = pGVar13;
      if (uVar9 + 1 < (uint)*(byte *)((int)puVar12 + 0xd)) {
        pGVar13 = param_1->entries + iStack_8 + uVar9 + 1;
      }
      else {
        pGVar13 = (GfxLightGridEntry *)0x0;
      }
      param_3[3] = pGVar13;
      if (uVar11 < uVar6) {
        *param_4 = 0;
        return;
      }
    }
    else {
      uVar9 = (uint)(byte)*puVar7;
      if (uVar9 <= uVar6) {
        do {
          iStack_8 = iStack_8 + *(byte *)((int)puVar7 + 1) * uVar9;
          uVar6 = uVar6 - uVar9;
          iVar10 = 2;
          if (*(byte *)((int)puVar7 + 1) != 0) {
            iVar10 = iVar8;
          }
          puVar7 = (ushort *)((int)puVar7 + iVar10);
          uVar9 = (uint)(byte)*puVar7;
        } while (uVar9 <= uVar6);
      }
      if (*(byte *)((int)puVar7 + 1) == 0) {
        *param_3 = (GfxLightGridEntry *)0x0;
        param_3[1] = (GfxLightGridEntry *)0x0;
        if (*(byte *)((int)puVar7 + 3) != 0) {
          uVar9 = (uint)(byte)puVar7[2];
          if (0xff < puVar12[3]) {
            uVar9 = (uint)CONCAT11(*(byte *)((int)puVar7 + 5),(byte)puVar7[2]);
          }
          if (uVar11 < *(byte *)((int)puVar7 + 3) + uVar9) {
            *param_4 = 0;
          }
        }
        if (uVar6 + 1 < (uint)(byte)*puVar7) {
          param_3[2] = (GfxLightGridEntry *)0x0;
          param_3[3] = (GfxLightGridEntry *)0x0;
          return;
        }
      }
      else {
        uVar9 = (uint)(byte)puVar7[1];
        if (0xff < uVar3) {
          uVar9 = (uint)CONCAT11(*(byte *)((int)puVar7 + 3),(byte)puVar7[1]);
        }
        if (uVar11 < uVar9) {
          *param_4 = 0;
        }
        uVar9 = uVar11 - uVar9;
        iVar10 = *(byte *)((int)puVar7 + 1) * uVar6 + uVar9 + iStack_8;
        if (uVar9 < *(byte *)((int)puVar7 + 1)) {
          pGVar13 = param_1->entries + iVar10;
        }
        else {
          pGVar13 = (GfxLightGridEntry *)0x0;
        }
        *param_3 = pGVar13;
        if (uVar9 + 1 < (uint)*(byte *)((int)puVar7 + 1)) {
          pGVar13 = param_1->entries + iVar10 + 1;
        }
        else {
          pGVar13 = (GfxLightGridEntry *)0x0;
        }
        param_3[1] = pGVar13;
        if (uVar6 + 1 < (uint)(byte)*puVar7) {
          iVar10 = iVar10 + (uint)*(byte *)((int)puVar7 + 1);
          if (uVar9 < *(byte *)((int)puVar7 + 1)) {
            pGVar13 = param_1->entries + iVar10;
          }
          else {
            pGVar13 = (GfxLightGridEntry *)0x0;
          }
          param_3[2] = pGVar13;
          if (uVar9 + 1 < (uint)*(byte *)((int)puVar7 + 1)) {
            param_3[3] = param_1->entries + iVar10 + 1;
            return;
          }
          param_3[3] = (GfxLightGridEntry *)0x0;
          return;
        }
      }
      if (param_2[param_1->colAxis] + 1 == (uint)puVar12[1] + (uint)*puVar12) {
        param_3[2] = (GfxLightGridEntry *)0x0;
        param_3[3] = (GfxLightGridEntry *)0x0;
        return;
      }
      iVar10 = 2;
      if (*(byte *)((int)puVar7 + 1) != 0) {
        iVar10 = iVar8;
      }
      bVar2 = *(byte *)(iVar10 + 2 + (int)puVar7);
      uVar6 = (uint)bVar2;
      if (0xff < puVar12[3]) {
        uVar6 = (uint)CONCAT11(*(byte *)(iVar10 + 3 + (int)puVar7),bVar2);
      }
      uVar11 = uVar11 - uVar6;
      pbVar1 = (byte *)(iVar10 + 1 + (int)puVar7);
      iVar8 = iStack_8 + (uint)*(byte *)((int)puVar7 + 1) * (uint)(byte)*puVar7 + uVar11;
      if (uVar11 < *pbVar1) {
        pGVar13 = param_1->entries + iVar8;
      }
      else {
        pGVar13 = (GfxLightGridEntry *)0x0;
      }
      param_3[2] = pGVar13;
      if ((uint)*pbVar1 <= uVar11 + 1) {
        param_3[3] = (GfxLightGridEntry *)0x0;
        return;
      }
      param_3[3] = param_1->entries + iVar8 + 1;
    }
  }
  return;
}

