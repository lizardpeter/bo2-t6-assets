
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

bool __cdecl
R_IsValidLightGridSample
          (GfxLightGrid *param_1,GfxLightGridEntry *param_2,int param_3,uint *param_4,
          vec3_t *param_5)

{
  float *pfVar1;
  int iVar2;
  vec3_t *in_ECX;
  int *in_EDX;
  float fVar3;
  float fVar4;
  float fVar5;
  float fVar6;
  float fVar7;
  vec3_t vStack_14;
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  fVar7 = (float)*in_EDX;
  if (*in_EDX < 0) {
    fVar7 = fVar7 + ___real_4f800000;
  }
  vStack_14._s_0.x = fVar7 * __real_42000000 - ___real_48000000;
  fVar7 = (float)in_EDX[1];
  if (in_EDX[1] < 0) {
    fVar7 = fVar7 + ___real_4f800000;
  }
  vStack_14._s_0.y = fVar7 * __real_42000000 - ___real_48000000;
  fVar7 = (float)in_EDX[2];
  if (in_EDX[2] < 0) {
    fVar7 = fVar7 + ___real_4f800000;
  }
  fVar4 = (in_ECX->_s_0).y;
  fVar5 = (in_ECX->_s_0).z;
  vStack_14._s_0.z = fVar7 * ___real_42800000 - ___real_48000000;
  pfVar1 = (float *)((int)&vStack_14 + param_1->rowAxis * 4);
  *pfVar1 = (float)(((uint)param_2 & 4) * 8) + *pfVar1;
  *(float *)((int)&vStack_14 + param_1->colAxis * 4) =
       (float)(((uint)param_2 & 2) << 4) + *(float *)((int)&vStack_14 + param_1->colAxis * 4);
  fVar3 = (in_ECX->_s_0).x - vStack_14._s_0.x;
  fVar4 = fVar4 - vStack_14._s_0.y;
  fVar6 = (float)(((uint)param_2 & 1) << 6) + vStack_14._s_0.z;
  fVar5 = fVar5 - fVar6;
  fVar7 = SQRT(fVar4 * fVar4 + fVar3 * fVar3 + fVar5 * fVar5);
  if (___real_00000000 <= (float)((uint)fVar7 ^ ___mask__NegFloat_)) {
    fVar7 = __real_3f800000;
  }
  fVar7 = __real_3f800000 / fVar7;
  vStack_14._s_0.x = fVar3 * fVar7 * ___real_3c23d70a + vStack_14._s_0.x;
  vStack_14._s_0.y = fVar4 * fVar7 * ___real_3c23d70a + vStack_14._s_0.y;
  vStack_14._s_0.z = fVar5 * fVar7 * ___real_3c23d70a + fVar6;
  iVar2 = CM_BoxSightTrace(0,in_ECX,&vStack_14,&vec3_origin,&vec3_origin,0,0x2001);
  return (bool)('\x01' - (iVar2 != 0));
}

