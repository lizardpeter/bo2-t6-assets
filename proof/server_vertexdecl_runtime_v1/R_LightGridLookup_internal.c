
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

uchar __cdecl
R_LightGridLookup(GfxLightGrid *param_1,vec3_t *param_2,float *param_3,GfxLightGridEntry **param_4,
                 uint *param_5)

{
  uint uVar1;
  undefined4 uVar2;
  code *pcVar3;
  bool bVar4;
  uchar uVar5;
  uint *in_ECX;
  int iVar6;
  float *in_EDX;
  uint *unaff_EBX;
  bool *unaff_ESI;
  GfxLightGrid *unaff_EDI;
  float fVar7;
  float fVar8;
  float fVar9;
  float fVar10;
  float fVar11;
  float fVar12;
  float fVar13;
  float fVar14;
  float fVar15;
  vec3_t *pvVar16;
  uchar uStack_36;
  GfxLightGridEntry **ppGStack_34;
  GfxLightGridEntry *pGStack_28;
  bool bStack_22;
  uchar uStack_21;
  uint auStack_20 [3];
  float fStack_14;
  vec3_t vStack_10;
  
  vStack_10._s_0.z = (float)(__security_cookie ^ (uint)&stack0xfffffffc);
  fVar13 = (float)param_1->sunPrimaryLightIndex;
  fVar7 = (float)(___real_80000000 & (uint)fVar13);
  fVar8 = (float)((uint)___real_4b000000 &
                  -(uint)((float)((uint)fVar13 ^ (uint)fVar7) < ___real_4b000000) | (uint)fVar7);
  fVar8 = (fVar13 + fVar8) - fVar8;
  fVar14 = *(float *)param_1->mins;
  fVar9 = (float)(___real_80000000 & (uint)fVar14);
  fVar10 = (float)((uint)___real_4b000000 &
                   -(uint)((float)((uint)fVar14 ^ (uint)fVar9) < ___real_4b000000) | (uint)fVar9);
  fVar10 = (fVar14 + fVar10) - fVar10;
  fVar15 = *(float *)(param_1->mins + 2);
  fVar11 = (float)(___real_80000000 & (uint)fVar15);
  fVar12 = (float)((uint)___real_4b000000 &
                   -(uint)((float)((uint)fVar15 ^ (uint)fVar11) < ___real_4b000000) | (uint)fVar11);
  fVar12 = (fVar15 + fVar12) - fVar12;
  auStack_20[1] =
       (int)(fVar10 - (float)(-(uint)(fVar9 < fVar10 - fVar14) & (uint)__real_3f800000)) + 0x20000
       >> 5;
  auStack_20[0] =
       (int)(fVar8 - (float)(-(uint)(fVar7 < fVar8 - fVar13) & (uint)__real_3f800000)) + 0x20000 >>
       5;
  auStack_20[2] =
       (int)(fVar12 - (float)(-(uint)(fVar11 < fVar12 - fVar15) & (uint)__real_3f800000)) + 0x20000
       >> 6;
  if ((((unaff_EDI->rowAxis != 0) || (unaff_EDI->colAxis != 1)) &&
      ((unaff_EDI->rowAxis != 1 || (unaff_EDI->colAxis != 0)))) &&
     (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\rb_light.cpp",0x54f,1,
                               "((lightGrid->rowAxis == 0 && lightGrid->colAxis == 1) || (lightGrid->rowAxis == 1 && lightGrid->colAxis == 0))"
                               ,""), !bVar4)) {
    pcVar3 = (code *)swi(3);
    uVar5 = (*pcVar3)();
    return uVar5;
  }
  uVar1 = unaff_EDI->rowAxis;
  fStack_14 = (float)(int)auStack_20[uVar1];
  if ((int)auStack_20[uVar1] < 0) {
    fStack_14 = fStack_14 + ___real_4f800000;
  }
  fStack_14 = (*(float *)(param_1->mins + uVar1 * 2 + -2) - ___real_c8000000) * ___real_3d000000 -
              fStack_14;
  fVar13 = (float)(int)auStack_20[unaff_EDI->colAxis];
  if ((int)auStack_20[unaff_EDI->colAxis] < 0) {
    fVar13 = fVar13 + ___real_4f800000;
  }
  vStack_10._s_0.x =
       (*(float *)(param_1->mins + unaff_EDI->colAxis * 2 + -2) - ___real_c8000000) *
       ___real_3d000000 - fVar13;
  fVar13 = (float)(int)auStack_20[2];
  if ((int)auStack_20[2] < 0) {
    fVar13 = fVar13 + ___real_4f800000;
  }
  vStack_10._s_0.y = (*(float *)(param_1->mins + 2) - ___real_c8000000) * ___real_3c800000 - fVar13;
  fVar13 = __real_3f800000 - vStack_10._s_0.y;
  fVar15 = (__real_3f800000 - vStack_10._s_0.x) * fVar13;
  fVar10 = __real_3f800000 - fStack_14;
  fVar14 = (__real_3f800000 - vStack_10._s_0.x) * vStack_10._s_0.y;
  in_EDX[4] = fVar15 * fStack_14;
  in_EDX[5] = fVar14 * fStack_14;
  fVar13 = fVar13 * vStack_10._s_0.x;
  *in_EDX = fVar10 * fVar15;
  in_EDX[1] = fVar10 * fVar14;
  in_EDX[2] = fVar10 * fVar13;
  in_EDX[6] = fVar13 * fStack_14;
  in_EDX[3] = fVar10 * vStack_10._s_0.y * vStack_10._s_0.x;
  in_EDX[7] = vStack_10._s_0.y * vStack_10._s_0.x * fStack_14;
  *in_ECX = 1;
  R_GetLightGridSampleEntryQuad(unaff_EDI,auStack_20,(GfxLightGridEntry **)param_2->v,in_ECX);
  auStack_20[unaff_EDI->rowAxis] = auStack_20[unaff_EDI->rowAxis] + 1;
  R_GetLightGridSampleEntryQuad
            (unaff_EDI,auStack_20,(GfxLightGridEntry **)((int)param_2 + 0x10),in_ECX);
  auStack_20[unaff_EDI->rowAxis] = auStack_20[unaff_EDI->rowAxis] - 1;
  uStack_21 = '\0';
  pvVar16 = (vec3_t *)0x0;
  bVar4 = Dvar_GetBool(r_disableLightGridSuppresion);
  iVar6 = (int)param_2 - (int)in_EDX;
  ppGStack_34 = (GfxLightGridEntry **)((uint)ppGStack_34 & 0xffffff00);
  bStack_22 = false;
  pGStack_28 = (GfxLightGridEntry *)0x0;
  do {
    if (*(undefined4 **)(iVar6 + (int)in_EDX) != (undefined4 *)0x0) {
      if (___real_3a83126f < *in_EDX || ___real_3a83126f == *in_EDX) {
        uVar2 = **(undefined4 **)(iVar6 + (int)in_EDX);
        if (!bVar4) {
          bStack_22 = R_IsValidLightGridSample
                                (unaff_EDI,pGStack_28,(int)unaff_ESI,unaff_EBX,pvVar16);
          bStack_22 = !bStack_22;
        }
        *(bool *)((int)&vStack_10 + (int)pGStack_28) = bStack_22;
        uStack_36 = (uchar)((uint)uVar2 >> 0x10);
        if (bStack_22 == false) {
          if ((char)ppGStack_34 != '\0') goto LAB_00a7142b;
          pvVar16 = (vec3_t *)*in_EDX;
          ppGStack_34 = (GfxLightGridEntry **)CONCAT31(ppGStack_34._1_3_,1);
          uStack_21 = uStack_36;
          memset((uchar *)param_2,'\0',(int)pGStack_28 * 4);
        }
        else if ((char)ppGStack_34 == '\0') {
LAB_00a7142b:
          if ((uStack_21 == '\0') ||
             ((uStack_36 != '\0' &&
              ((uStack_21 == 0xff || ((uStack_36 != 0xff && ((float)pvVar16 < *in_EDX)))))))) {
            pvVar16 = (vec3_t *)*in_EDX;
            uStack_21 = uStack_36;
          }
        }
        else {
          *(undefined4 *)(iVar6 + (int)in_EDX) = 0;
        }
      }
      else {
        *(undefined4 *)(iVar6 + (int)in_EDX) = 0;
      }
    }
    pGStack_28 = (GfxLightGridEntry *)((int)&pGStack_28->colorsIndex + 1);
    in_EDX = in_EDX + 1;
    if ((GfxLightGridEntry *)0x7 < pGStack_28) {
      bVar4 = Dvar_GetBool(r_showLightGrid);
      if (bVar4) {
        R_ShowLightGrid((GfxLightGrid *)auStack_20,&param_1->sunPrimaryLightIndex,&vStack_10,
                        ppGStack_34,unaff_ESI,SUB41(unaff_EBX,0));
      }
      return uStack_21;
    }
  } while( true );
}

