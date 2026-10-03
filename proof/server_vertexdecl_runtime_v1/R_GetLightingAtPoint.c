
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

uint __cdecl
R_GetLightingAtPoint
          (GfxLightGrid *param_1,vec3_t *param_2,ushort param_3,float *param_4,
          GfxLightingSH *param_5,GfxModelLightExtrapolation param_6,bool param_7)

{
  float fVar1;
  uint uVar2;
  code *pcVar3;
  bool bVar4;
  byte bVar5;
  uint uVar6;
  float *pfVar7;
  uint *unaff_EBX;
  float *pfVar8;
  GfxLightGridEntry **unaff_ESI;
  vec3_t *unaff_EDI;
  float fVar9;
  float fVar10;
  float fVar11;
  undefined2 in_stack_0000000e;
  undefined4 in_stack_ffffff60;
  float *pfStack_80;
  uint uStack_6c;
  byte bStack_5e;
  float afStack_58 [8];
  float afStack_38 [8];
  ushort auStack_18 [8];
  float fStack_8;
  
  fStack_8 = (float)(__security_cookie ^ (uint)&stack0xfffffffc);
  if ((param_1 == (GfxLightGrid *)0x0) &&
     (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\rb_light.cpp",0x691,0,
                               "(remoteLightGrid)",""), !bVar4)) {
    pcVar3 = (code *)swi(3);
    uVar6 = (*pcVar3)();
    return uVar6;
  }
  bVar5 = R_LightGridLookup((GfxLightGrid *)&param_2->_s_0,(vec3_t *)&stack0xffffff60,unaff_EDI->v,
                            unaff_ESI,unaff_EBX);
  uStack_6c = (uint)bVar5;
  if (uStack_6c == 0xff) {
    uStack_6c = (uint)(byte)param_1->sunPrimaryLightIndex;
  }
  pfVar8 = (float *)0x0;
  fVar11 = 0.0;
  fVar10 = 0.0;
  fVar9 = 0.0;
  uVar6 = 0;
  do {
    if (*(uint **)(&stack0xffffff60 + uVar6) != (uint *)0x0) {
      uVar2 = **(uint **)(&stack0xffffff60 + uVar6);
      bStack_5e = (byte)(uVar2 >> 0x10);
      if ((bStack_5e == uStack_6c) ||
         ((uStack_6c == param_1->sunPrimaryLightIndex && (bStack_5e == 0xff)))) {
        fVar10 = *(float *)((int)afStack_38 + uVar6) + fVar10;
        fVar9 = fVar9 + (float)(uVar2 >> 0x18) * *(float *)((int)afStack_38 + uVar6);
      }
      fVar1 = *(float *)((int)afStack_38 + uVar6);
      pfVar7 = (float *)0x0;
      fVar11 = fVar11 + fVar1;
      if (pfVar8 != (float *)0x0) {
        do {
          if (auStack_18[(int)pfVar7] == (ushort)uVar2) {
            afStack_58[(int)pfVar7] = afStack_58[(int)pfVar7] + fVar1;
            goto LAB_00a715ec;
          }
          pfVar7 = (float *)((int)pfVar7 + 1);
        } while (pfVar7 < pfVar8);
      }
      auStack_18[(int)pfVar8] = (ushort)uVar2;
      afStack_58[(int)pfVar8] = fVar1;
      pfVar8 = (float *)((int)pfVar8 + 1);
    }
LAB_00a715ec:
    uVar6 = uVar6 + 4;
    if (0x1f < uVar6) {
      if ((fVar11 < 0.0) &&
         (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\rb_light.cpp",0x6c0,0,
                                   "((maxWeight >= 0.0f))","(maxWeight) = %g"), !bVar4)) {
        pcVar3 = (code *)swi(3);
        uVar6 = (*pcVar3)();
        return uVar6;
      }
      if (pfVar8 == (float *)0x0) {
        bVar5 = R_ExtrapolateLightingAtPoint
                          ((GfxLightGrid *)&((vec3_t *)(-(uint)param_7 & (uint)param_2))->_s_0,
                           _param_3,(vec3_t *)param_5,(ushort)param_6,pfStack_80,
                           (GfxLightingSH *)&unaff_EDI->_s_0,(GfxModelLightExtrapolation)unaff_ESI,
                           (uint)unaff_EBX);
        return (uint)bVar5;
      }
      if ((fVar11 <= 0.0) &&
         (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\rb_light.cpp",0x6c9,1,
                                   "(maxWeight > 0.0f)",""), !bVar4)) {
        pcVar3 = (code *)swi(3);
        uVar6 = (*pcVar3)();
        return uVar6;
      }
      *param_4 = fVar9 / (fVar10 * ___real_437f0000);
      if (pfVar8 != (float *)&DAT_00000001) {
        R_BlendAndSetLightGridColors
                  ((GfxLightGrid *)auStack_18,(ushort *)afStack_58,pfVar8,
                   (uint)(__real_3f800000 / fVar11),unaff_EDI,(float)unaff_ESI,(ushort)unaff_EBX,
                   (GfxLightingSH *)in_stack_ffffff60);
        return uStack_6c;
      }
      R_SetLightGridColorsFromIndex
                (param_1,(uint)auStack_18[0],(vec3_t *)(-(uint)param_7 & (uint)param_2),param_3,
                 param_5);
      return uStack_6c;
    }
  } while( true );
}

