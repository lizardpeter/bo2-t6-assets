
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Removing unreachable block (ram,0x00a7b440) */
/* WARNING: Removing unreachable block (ram,0x00a7b465) */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl
R_SetStaticModelLightingConsts
          (ushort param_1,uchar param_2,GfxLightingSHQuantized *param_3,vec4_t *param_4,
          vec4_t *param_5,vec4_t *param_6,vec4_t *param_7)

{
  code *pcVar1;
  float fVar2;
  float fVar3;
  bool bVar4;
  vec4_t vStack_38;
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
  if (((param_1 == 0) || (modelLightGlob.totalEntryLimit < param_1)) &&
     (bVar4 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_model_lighting.cpp",0xcc,0,
                               "(1) <= (handle) && (handle) <= (modelLightGlob.totalEntryLimit)",
                               "handle not in [1, modelLightGlob.totalEntryLimit]\n\t%i not in [%i, %i]"
                              ), !bVar4)) {
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  fVar3 = __real_3f000000;
  fVar2 = ((float)(param_1 - 1 >> 5 & 0x7fffffc) + ___real_40000000) * modelLightGlob.invImageHeight
  ;
  param_4->v[0] = ((float)((param_1 - 1 & 0x7f) * 4) + ___real_40000000) * ___real_3b000000;
  param_4->v[1] = fVar2;
  param_4->v[2] = fVar3;
  param_4->v[3] = (float)param_2 * ___real_3b808081;
  R_DecodeLightingSH(param_3,(GfxLightingSH *)&vStack_38._s_1);
  param_5->v[0] = vStack_38.v[0];
  param_5->v[1] = vStack_38.v[1];
  param_5->v[2] = vStack_38.v[2];
  param_5->v[3] = vStack_38.v[3];
  param_6->v[0] = fStack_28;
  param_6->v[1] = fStack_24;
  param_6->v[2] = fStack_20;
  param_6->v[3] = fStack_1c;
  param_7->v[0] = fStack_18;
  param_7->v[1] = fStack_14;
  param_7->v[2] = fStack_10;
  param_7->v[3] = fStack_c;
  return;
}

