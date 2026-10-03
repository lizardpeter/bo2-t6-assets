
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl
R_BlendAndSetLightGridColors
          (GfxLightGrid *param_1,ushort *param_2,float *param_3,uint param_4,vec3_t *param_5,
          float param_6,ushort param_7,GfxLightingSH *param_8)

{
  float fVar1;
  float fVar2;
  int iVar3;
  vec3_t *in_ECX;
  float *in_EDX;
  GfxDecodedLightGridColors *unaff_EBX;
  float *pfVar4;
  int unaff_ESI;
  vec3_t *unaff_EDI;
  float fVar5;
  float fVar6;
  float fVar7;
  float fVar8;
  float afStack_7e0 [224];
  undefined1 auStack_460 [8];
  float afStack_458 [222];
  float fStack_e0;
  float fStack_dc;
  float fStack_d8;
  float fStack_d4;
  float fStack_d0;
  float fStack_cc;
  float fStack_c8;
  float fStack_c4;
  float fStack_c0;
  float fStack_bc;
  float fStack_b8;
  float fStack_b4;
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
  float fStack_70;
  float fStack_6c;
  float fStack_68;
  float fStack_64;
  float fStack_60;
  float fStack_5c;
  float fStack_58;
  float fStack_54;
  float fStack_50;
  float fStack_4c;
  float fStack_48;
  float fStack_44;
  float fStack_40;
  float fStack_3c;
  float fStack_38;
  float fStack_34;
  float fStack_30;
  float fStack_2c;
  float fStack_28;
  float fStack_24;
  float fStack_20;
  float fStack_1c;
  float fStack_18;
  float fStack_14;
  float fStack_10;
  float fStack_c;
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  if (*(int *)(unaff_ESI + 0x38) == 0) {
    R_DecodeLightGridColorsWeighted
              ((GfxCompressedLightGridColors *)&unaff_EDI->_s_0,unaff_EBX,(float)in_ECX);
  }
  else {
    R_DecodeLightGridCoeffsWeighted
              ((GfxCompressedLightGridCoeffs *)&fStack_74,unaff_EDI,unaff_EBX,(float)in_ECX);
  }
  fVar1 = ___real_3e800000;
  fVar2 = __real_3f000000;
  fVar7 = fStack_1c;
  fVar6 = fStack_10;
  for (pfVar4 = (float *)&DAT_00000001; ___real_3e800000 = fVar1, __real_3f000000 = fVar2,
      pfVar4 < param_3; pfVar4 = (float *)((int)pfVar4 + 1)) {
    if (*(int *)(unaff_ESI + 0x38) == 0) {
      R_DecodeLightGridColorsWeighted
                ((GfxCompressedLightGridColors *)&unaff_EDI->_s_0,unaff_EBX,(float)in_ECX);
    }
    else {
      R_DecodeLightGridCoeffsWeighted
                ((GfxCompressedLightGridCoeffs *)&fStack_e0,unaff_EDI,unaff_EBX,(float)in_ECX);
      fStack_74 = fStack_e0 + fStack_74;
      fStack_70 = fStack_dc + fStack_70;
      fStack_6c = fStack_d8 + fStack_6c;
      fStack_68 = fStack_d4 + fStack_68;
      fStack_64 = fStack_d0 + fStack_64;
      fStack_60 = fStack_cc + fStack_60;
      fStack_5c = fStack_c8 + fStack_5c;
      fStack_58 = fStack_c4 + fStack_58;
      fStack_54 = fStack_c0 + fStack_54;
      fStack_50 = fStack_bc + fStack_50;
      fStack_4c = fStack_b8 + fStack_4c;
      fStack_48 = fStack_b4 + fStack_48;
      fStack_44 = fStack_b0 + fStack_44;
      fStack_40 = fStack_ac + fStack_40;
      fStack_3c = fStack_a8 + fStack_3c;
      fStack_38 = fStack_a4 + fStack_38;
      fVar7 = fVar7 + fStack_88;
      fStack_34 = fStack_a0 + fStack_34;
      fStack_30 = fStack_9c + fStack_30;
      fStack_2c = fStack_98 + fStack_2c;
      fStack_28 = fStack_94 + fStack_28;
      fStack_24 = fStack_90 + fStack_24;
      fStack_20 = fStack_8c + fStack_20;
      fStack_18 = fStack_84 + fStack_18;
      fVar6 = fVar6 + fStack_7c;
      fStack_14 = fStack_80 + fStack_14;
      fStack_c = fStack_78 + fStack_c;
    }
    iVar3 = 0;
    do {
      *(float *)(auStack_460 + iVar3) =
           *(float *)((int)afStack_7e0 + iVar3) + *(float *)(auStack_460 + iVar3);
      *(float *)(auStack_460 + iVar3 + 4) =
           *(float *)((int)afStack_7e0 + iVar3 + 4) + *(float *)(auStack_460 + iVar3 + 4);
      *(float *)((int)afStack_458 + iVar3) =
           *(float *)((int)afStack_7e0 + iVar3 + 8) + *(float *)((int)afStack_458 + iVar3);
      *(float *)((int)afStack_458 + iVar3 + 8) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x10) + *(float *)((int)afStack_458 + iVar3 + 8);
      *(float *)((int)afStack_458 + iVar3 + 0xc) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x14) + *(float *)((int)afStack_458 + iVar3 + 0xc);
      *(float *)((int)afStack_458 + iVar3 + 0x10) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x18) + *(float *)((int)afStack_458 + iVar3 + 0x10)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x18) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x20) + *(float *)((int)afStack_458 + iVar3 + 0x18)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x1c) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x24) + *(float *)((int)afStack_458 + iVar3 + 0x1c)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x20) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x28) + *(float *)((int)afStack_458 + iVar3 + 0x20)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x28) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x30) + *(float *)((int)afStack_458 + iVar3 + 0x28)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x2c) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x34) + *(float *)((int)afStack_458 + iVar3 + 0x2c)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x30) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x38) + *(float *)((int)afStack_458 + iVar3 + 0x30)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x38) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x40) + *(float *)((int)afStack_458 + iVar3 + 0x38)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x3c) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x44) + *(float *)((int)afStack_458 + iVar3 + 0x3c)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x40) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x48) + *(float *)((int)afStack_458 + iVar3 + 0x40)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x48) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x50) + *(float *)((int)afStack_458 + iVar3 + 0x48)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x4c) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x54) + *(float *)((int)afStack_458 + iVar3 + 0x4c)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x50) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x58) + *(float *)((int)afStack_458 + iVar3 + 0x50)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x58) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x60) + *(float *)((int)afStack_458 + iVar3 + 0x58)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x5c) =
           *(float *)((int)afStack_7e0 + iVar3 + 100) + *(float *)((int)afStack_458 + iVar3 + 0x5c);
      *(float *)((int)afStack_458 + iVar3 + 0x60) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x68) + *(float *)((int)afStack_458 + iVar3 + 0x60)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x68) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x70) + *(float *)((int)afStack_458 + iVar3 + 0x68)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x6c) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x74) + *(float *)((int)afStack_458 + iVar3 + 0x6c)
      ;
      *(float *)((int)afStack_458 + iVar3 + 0x70) =
           *(float *)((int)afStack_7e0 + iVar3 + 0x78) + *(float *)((int)afStack_458 + iVar3 + 0x70)
      ;
      iVar3 = iVar3 + 0x80;
    } while (iVar3 < 0x380);
    fVar1 = ___real_3e800000;
    fVar2 = __real_3f000000;
  }
  if (*(int *)(unaff_ESI + 0x38) == 0) {
    memset((uchar *)in_EDX,'\0',0x30);
  }
  else {
    fVar5 = fStack_70 * fVar2 + fStack_74 * fVar1 + fStack_6c * fVar1 + __real_38d1b717;
    fVar8 = fVar7 * fVar2 + fStack_20 * fVar1 + fStack_18 * fVar1;
    fVar7 = __real_3f800000 / fVar5;
    in_EDX[2] = fStack_6c * fVar7;
    in_EDX[3] = fVar8 * ___real_40400000;
    *in_EDX = fStack_74 * fVar7;
    in_EDX[1] = fStack_70 * fVar7;
    in_EDX[4] = fStack_64 * fVar2 + fStack_68 * fVar1 + fStack_60 * fVar1;
    in_EDX[5] = fStack_58 * fVar2 + fStack_5c * fVar1 + fStack_54 * fVar1;
    in_EDX[7] = fVar5 - fVar8;
    in_EDX[6] = fStack_4c * fVar2 + fStack_50 * fVar1 + fStack_48 * fVar1;
    in_EDX[8] = fStack_40 * fVar2 + fStack_44 * fVar1 + fStack_3c * fVar1;
    in_EDX[9] = fStack_34 * fVar2 + fStack_38 * fVar1 + fStack_30 * fVar1;
    in_EDX[10] = fStack_28 * fVar2 + fStack_2c * fVar1 + fStack_24 * fVar1;
    in_EDX[0xb] = fVar6 * fVar2 + fStack_14 * fVar1 + fStack_c * fVar1;
  }
  R_AddHeroOnlyLightsToGridColors((GfxDecodedLightGridColors *)auStack_460,in_ECX);
  return;
}

