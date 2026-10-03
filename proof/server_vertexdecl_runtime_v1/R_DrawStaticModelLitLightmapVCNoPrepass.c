
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl
R_DrawStaticModelLitLightmapVCNoPrepass(GfxStaticModelDrawStream *param_1,GfxCmdBufContext param_2)

{
  undefined4 *puVar1;
  vec4_t *pvVar2;
  int iVar3;
  uint uVar4;
  int iVar5;
  GfxPrimStats *pGVar6;
  float *pfVar7;
  ID3D11DeviceContext IVar8;
  code *pcVar9;
  uint uVar10;
  uint uVar11;
  uint uVar12;
  uint uVar13;
  float fVar14;
  float fVar15;
  float fVar16;
  float fVar17;
  GfxStaticModelDrawInst *pGVar18;
  bool bVar19;
  uint uVar20;
  int *in_ECX;
  XSurface *unaff_ESI;
  GfxCmdBufPrimState *pGVar21;
  undefined4 *puVar22;
  GfxCmdBufPrimState *unaff_EDI;
  float fVar23;
  float fVar24;
  float fVar25;
  float fVar26;
  undefined4 uStack_e8;
  int iStack_e4;
  int iStack_e0;
  GfxTexture *pGStack_dc;
  GfxStaticModelDrawStream *pGStack_d8;
  GfxCmdBufState *pGStack_d4;
  GfxStaticModelDrawInst *pGStack_d0;
  int *piStack_cc;
  uint uStack_c8;
  uint uStack_c4;
  uint uStack_c0;
  ID3D11DeviceContext *pIStack_bc;
  uint uStack_b8;
  GfxTexture *pGStack_b4;
  float fStack_b0;
  float fStack_ac;
  float fStack_a8;
  float fStack_a4;
  float fStack_a0;
  float fStack_9c;
  float fStack_98;
  float fStack_94;
  float fStack_90;
  float fStack_8c;
  float fStack_88;
  float fStack_84;
  float fStack_80;
  float fStack_7c;
  float fStack_78;
  float fStack_74;
  GfxDrawPrimArgs GStack_64;
  vec4_t vStack_58;
  vec4_t vStack_48;
  vec4_t vStack_38;
  vec4_t vStack_28;
  uint uStack_14;
  
  uStack_14 = __security_cookie ^ (uint)&stack0xfffffff0;
  pGStack_d8 = param_1;
  pGStack_d4 = (GfxCmdBufState *)param_2.field0_0x0._s_0.source;
  pGVar21 = (GfxCmdBufPrimState *)(((param_2.field0_0x0._s_0.source)->matrices).matrix[2].m + 1);
  piStack_cc = in_ECX;
  if ((*in_ECX != 2) &&
     (bVar19 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_draw_staticmodel.cpp",0x373,0,
                                "((drawStream->precompiledIndex == VERTEX_SHADER_MODEL_LIT_LIGHTMAP_VC))"
                                ,"(drawStream->precompiledIndex) = %i"), !bVar19)) {
    pcVar9 = (code *)swi(3);
    (*pcVar9)();
    return;
  }
  iVar3 = in_ECX[0xd];
  if ((iVar3 == 0) &&
     (bVar19 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_draw_staticmodel.cpp",0x152,0,
                                "(xsurf)",""), !bVar19)) {
    pcVar9 = (code *)swi(3);
    (*pcVar9)();
    return;
  }
  GStack_64.vertexCount = (int)*(ushort *)(iVar3 + 4);
  GStack_64.triCount = (int)*(ushort *)(iVar3 + 6);
  GStack_64.baseIndex = 0;
  R_SetStaticModelIndexBuffer(unaff_EDI,unaff_ESI);
  uVar4 = piStack_cc[5];
  pGStack_dc = (g_worldDraw->field2_0x8).localReflectionProbeTextures;
  pIStack_bc = (pGVar21->field0_0x0).device;
  if ((float)piStack_cc[9] == ___real_00000000) {
    fVar23 = 0.0;
    fVar24 = 0.0;
    fVar25 = 0.0;
    fVar26 = 0.0;
  }
  else {
    fVar23 = (float)(piStack_cc[6] & g_keepXYZ.m128_u32[0]);
    fVar24 = (float)(piStack_cc[7] & g_keepXYZ.m128_u32[1]);
    fVar25 = (float)(piStack_cc[8] & g_keepXYZ.m128_u32[2]);
    fVar26 = (float)(piStack_cc[9] & g_keepXYZ.m128_u32[3]);
  }
  uStack_c4 = piStack_cc[2];
  fVar14 = g_unit.m128_f32[0];
  fVar15 = g_unit.m128_f32[1];
  fVar16 = g_unit.m128_f32[2];
  fVar17 = g_unit.m128_f32[3];
  pGStack_d0 = ((rgp.world)->dpvs).smodelDrawInsts;
  iStack_e0 = piStack_cc[3];
  iVar5 = piStack_cc[0xc];
  pGVar6 = pGStack_d8[0x65].primStats;
  uStack_b8 = 0;
  if (uStack_c4 != 0) {
    do {
      pGVar18 = pGStack_d0;
      uVar20 = (uint)*(ushort *)(iStack_e0 + uStack_b8 * 2);
      uStack_c8 = (uint)*(byte *)((int)pGVar6[iVar5 * 0x200 + 0x2008].counters + uVar20);
      if ((uVar4 & 1) != 0) {
        uStack_c0 = (uint)pGStack_d0[uVar20].reflectionProbeIndex;
        if ((g_worldDraw->reflectionProbeCount <= uStack_c0) &&
           (bVar19 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_draw_staticmodel.cpp",0x3cf,0,
                                      "(unsigned)(reflectionProbeIndex) < (unsigned)(g_worldDraw->reflectionProbeCount)"
                                      ,
                                      "reflectionProbeIndex doesn\'t index g_worldDraw->reflectionProbeCount\n\t%i not in [0, %i)"
                                     ), !bVar19)) {
          pcVar9 = (code *)swi(3);
          (*pcVar9)();
          return;
        }
        pGStack_b4 = pGStack_dc + uStack_c0;
        if ((GfxTexture *)piStack_cc[4] != pGStack_b4) {
          piStack_cc[4] = (int)pGStack_b4;
          if ((pGStack_b4 == (GfxTexture *)0x0) &&
             (bVar19 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_setstate_d3d.h",0x122,0,
                                        "(texture)",""), !bVar19)) {
            pcVar9 = (code *)swi(3);
            (*pcVar9)();
            return;
          }
          (**(code **)((int)*pIStack_bc + 0x20))(pIStack_bc,0xf,1,pGStack_b4);
          memcpy((uchar *)(*(int *)((int)((param_2.field0_0x0._s_0.source)->input).consts + 0x93c) +
                          0x80),
                 (uchar *)&(g_worldDraw->field1_0x4).localReflectionProbes[uStack_c0].lightingSH,
                 0x30);
          *(undefined1 *)((int)((param_2.field0_0x0._s_0.source)->input).consts + 0x943) = 1;
        }
      }
      pGStack_b4 = (GfxTexture *)(uint)pGVar18[uVar20].lightingHandle;
      uVar10 = g_keepXYZ.m128_u32[0];
      uVar11 = g_keepXYZ.m128_u32[1];
      uVar12 = g_keepXYZ.m128_u32[2];
      uVar13 = g_keepXYZ.m128_u32[3];
      fStack_84 = pGVar18[uVar20].placement.scale;
      fStack_80 = (float)((uint)pGVar18[uVar20].placement.origin._s_0.x & uVar10) -
                  (fVar23 - fVar14);
      fStack_7c = (float)((uint)pGVar18[uVar20].placement.origin._s_0.y & uVar11) -
                  (fVar24 - fVar15);
      fStack_78 = (float)((uint)pGVar18[uVar20].placement.origin._s_0.z & uVar12) -
                  (fVar25 - fVar16);
      fStack_74 = (float)((uint)pGVar18[uVar20].placement.axis[0]._s_0.x & uVar13) -
                  (fVar26 - fVar17);
      fStack_b0 = (float)((uint)pGVar18[uVar20].placement.axis[0]._s_0.x & uVar10) * fStack_84;
      fStack_ac = (float)((uint)pGVar18[uVar20].placement.axis[0]._s_0.y & uVar11) * fStack_84;
      fStack_a8 = (float)((uint)pGVar18[uVar20].placement.axis[0]._s_0.z & uVar12) * fStack_84;
      fStack_a4 = (float)((uint)pGVar18[uVar20].placement.axis[1]._s_0.x & uVar13) * fStack_84;
      fStack_a0 = (float)((uint)pGVar18[uVar20].placement.axis[1]._s_0.x & uVar10) * fStack_84;
      fStack_9c = (float)(*(uint *)((int)pGVar18[uVar20].placement.axis + 0x10) & uVar11) *
                  fStack_84;
      fStack_98 = (float)(*(uint *)((int)pGVar18[uVar20].placement.axis + 0x14) & uVar12) *
                  fStack_84;
      fStack_94 = (float)((uint)pGVar18[uVar20].placement.axis[2]._s_0.x & uVar13) * fStack_84;
      fStack_90 = (float)((uint)pGVar18[uVar20].placement.axis[2]._s_0.x & uVar10) * fStack_84;
      fStack_8c = (float)(*(uint *)((int)pGVar18[uVar20].placement.axis + 0x1c) & uVar11) *
                  fStack_84;
      fStack_88 = (float)(*(uint *)((int)pGVar18[uVar20].placement.axis + 0x20) & uVar12) *
                  fStack_84;
      fStack_84 = (float)((uint)pGVar18[uVar20].placement.scale & uVar13) * fStack_84;
      if ((pGVar18[uVar20].lmapVertexInfo[uStack_c8].lmapVertexColors == (uint *)0x0) &&
         (bVar19 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_draw_staticmodel.cpp",0x3fb,0,
                                    "(smodelDrawInst->lmapVertexInfo[lod].lmapVertexColors)",""),
         !bVar19)) {
        pcVar9 = (code *)swi(3);
        (*pcVar9)();
        return;
      }
      uStack_e8 = 4;
      iStack_e4 = (uint)*(ushort *)(iVar3 + 8) * 4;
      (**(code **)((int)*pIStack_bc + 0x48))
                (pIStack_bc,2,1,&pGVar18[uVar20].lmapVertexInfo[uStack_c8].lmapVertexColorsVB,
                 &uStack_e8,&iStack_e4);
      R_SetStaticModelLightingConsts
                ((ushort)pGStack_b4,pGVar18[uVar20].visibility,&pGVar18[uVar20].lightingSH,
                 &vStack_58,&vStack_48,&vStack_38,&vStack_28);
      memcpy((uchar *)(*(int *)((int)((param_2.field0_0x0._s_0.source)->input).consts + 0x93c) +
                      0x40),(uchar *)&vStack_58,0x40);
      *(undefined1 *)((int)((param_2.field0_0x0._s_0.source)->input).consts + 0x943) = 1;
      pfVar7 = *(float **)((int)((param_2.field0_0x0._s_0.source)->input).consts + 0x93c);
      *pfVar7 = fStack_b0;
      pfVar7[1] = fStack_a0;
      pfVar7[2] = fStack_90;
      pfVar7[3] = fStack_80;
      pfVar7[4] = fStack_ac;
      pfVar7[5] = fStack_9c;
      pfVar7[6] = fStack_8c;
      pfVar7[7] = fStack_7c;
      pfVar7[8] = fStack_a8;
      pfVar7[9] = fStack_98;
      pfVar7[10] = fStack_88;
      pfVar7[0xb] = fStack_78;
      pfVar7[0xc] = fStack_a4;
      pfVar7[0xd] = fStack_94;
      pfVar7[0xe] = fStack_84;
      pfVar7[0xf] = fStack_74;
      R_DrawIndexedPrimitive(pGStack_d4,pGVar21,&GStack_64);
      uStack_b8 = uStack_b8 + 1;
    } while (uStack_b8 < uStack_c4);
  }
  IVar8 = *pIStack_bc;
  puVar1 = (undefined4 *)((int)((param_2.field0_0x0._s_0.source)->matrices).matrix[2].m + 0x3c);
  pvVar2 = ((param_2.field0_0x0._s_0.source)->matrices).matrix[2].m + 3;
  puVar22 = (undefined4 *)((int)((param_2.field0_0x0._s_0.source)->matrices).matrix[2].m + 0x24);
  pvVar2->v[0] = 0.0;
  pcVar9 = *(code **)((int)IVar8 + 0x48);
  *puVar1 = 0;
  *puVar22 = 0;
  (*pcVar9)(pIStack_bc,2,1,pvVar2,puVar22,puVar1);
  return;
}

