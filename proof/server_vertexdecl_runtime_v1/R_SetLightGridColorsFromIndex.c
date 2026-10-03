
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl
R_SetLightGridColorsFromIndex
          (GfxLightGrid *param_1,uint param_2,vec3_t *param_3,ushort param_4,GfxLightingSH *param_5)

{
  float fVar1;
  float fVar2;
  GfxDecodedLightGridColors *unaff_EBX;
  GfxDecodedLightGridColors *unaff_ESI;
  vec3_t *unaff_EDI;
  float fVar3;
  float fVar4;
  float fVar5;
  undefined4 in_stack_fffffc0c;
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
  if (param_1->coeffCount == 0) {
    R_DecodeLightGridColorsWeighted
              ((GfxCompressedLightGridColors *)unaff_ESI,unaff_EBX,(float)in_stack_fffffc0c);
    memset((uchar *)param_5,'\0',0x30);
  }
  else {
    fVar5 = __real_3f800000;
    R_DecodeLightGridCoeffsWeighted
              ((GfxCompressedLightGridCoeffs *)&fStack_74,unaff_EDI,unaff_ESI,(float)unaff_EBX);
    fVar2 = __real_3f000000;
    fVar1 = ___real_3e800000;
    fVar3 = fStack_70 * __real_3f000000 + fStack_74 * ___real_3e800000 +
            fStack_6c * ___real_3e800000 + __real_38d1b717;
    fVar4 = fStack_1c * __real_3f000000 + fStack_20 * ___real_3e800000 +
            fStack_18 * ___real_3e800000;
    fVar5 = fVar5 / fVar3;
    (param_5->V0).v[0] = fVar5 * fStack_74;
    (param_5->V0).v[2] = fVar5 * fStack_6c;
    (param_5->V0).v[3] = fVar4 * ___real_40400000;
    (param_5->V0).v[1] = fVar5 * fStack_70;
    (param_5->V1).v[0] = fStack_64 * fVar2 + fStack_68 * fVar1 + fStack_60 * fVar1;
    (param_5->V1).v[1] = fStack_58 * fVar2 + fStack_5c * fVar1 + fStack_54 * fVar1;
    (param_5->V1).v[3] = fVar3 - fVar4;
    (param_5->V1).v[2] = fStack_4c * fVar2 + fStack_50 * fVar1 + fStack_48 * fVar1;
    (param_5->V2).v[0] = fStack_40 * fVar2 + fStack_44 * fVar1 + fStack_3c * fVar1;
    (param_5->V2).v[1] = fStack_34 * fVar2 + fStack_38 * fVar1 + fStack_30 * fVar1;
    (param_5->V2).v[2] = fStack_28 * fVar2 + fStack_2c * fVar1 + fStack_24 * fVar1;
    (param_5->V2).v[3] = fStack_10 * fVar2 + fStack_14 * fVar1 + fStack_c * fVar1;
  }
  R_AddHeroOnlyLightsToGridColors((GfxDecodedLightGridColors *)&stack0xfffffc0c,param_3);
  return;
}

