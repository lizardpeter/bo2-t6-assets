
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */

uchar __cdecl
R_ExtrapolateLightingAtPoint
          (GfxLightGrid *param_1,vec3_t *param_2,vec3_t *param_3,ushort param_4,float *param_5,
          GfxLightingSH *param_6,GfxModelLightExtrapolation param_7,uint param_8)

{
  float fVar1;
  bool bVar2;
  float *in_ECX;
  int iVar3;
  float *unaff_EBX;
  GfxLightGrid *unaff_ESI;
  ushort *unaff_EDI;
  undefined2 in_stack_00000012;
  vec3_t avStack_390 [75];
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  if (((float *)unaff_ESI->colorCount <= param_5) && ((float *)unaff_ESI->coeffCount <= param_5)) {
    iVar3 = 0x38;
    do {
      iVar3 = iVar3 + -1;
    } while (iVar3 != 0);
    if (in_ECX != (float *)0x0) {
      *in_ECX = 0.0;
    }
    fVar1 = __real_3f800000;
    if (param_3 != (vec3_t *)0x0) {
      (param_3->_s_0).x = __real_3f800000;
      (param_3->_s_0).y = fVar1;
      (param_3->_s_0).z = fVar1;
      param_3[1]._s_0.x = 0.0;
      *(undefined4 *)((int)param_3 + 0x10) = 0;
      *(undefined4 *)((int)param_3 + 0x14) = 0;
      param_3[2]._s_0.x = 0.0;
      *(float *)((int)param_3 + 0x1c) = fVar1;
      *(undefined4 *)((int)param_3 + 0x20) = 0;
      param_3[3]._s_0.x = 0.0;
      *(undefined4 *)((int)param_3 + 0x28) = 0;
      *(undefined4 *)((int)param_3 + 0x2c) = 0;
    }
    return '\0';
  }
  avStack_390[0]._7_1_ = (undefined1)unaff_ESI->sunPrimaryLightIndex;
  avStack_390[0]._0_4_ = (uint)param_5 & 0xffff;
  *in_ECX = __real_3f800000;
  bVar2 = R_LookupSkyGridVolumesAtPoint(unaff_ESI,avStack_390,unaff_EDI,unaff_EBX,(uchar *)param_1);
  if ((!bVar2) && ((_param_4 == 1 && (param_5 == (float *)0x0)))) {
    bVar2 = Dvar_GetBool(r_showMissingLightGrid);
    if (bVar2) {
      R_SetDebugLightGridColors((ushort)param_2,in_ECX,(GfxLightingSH *)&param_3->_s_0);
      return '\0';
    }
  }
  R_SetLightGridColorsFromIndex
            (unaff_ESI,avStack_390[0]._s_0.x & 0xffff,(vec3_t *)param_1,(ushort)param_2,
             (GfxLightingSH *)&param_3->_s_0);
  return avStack_390[0]._7_1_;
}

