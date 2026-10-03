
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl AnglesToAxis(vec3_t *param_1,vec3_t *param_2)

{
  float fVar1;
  float fVar2;
  float fVar3;
  float fVar4;
  float fVar5;
  float fVar6;
  float10 fVar7;
  float10 fVar8;
  
  fVar5 = ___real_3c8efa35;
  fVar8 = (float10)((param_1->_s_0).y * ___real_3c8efa35);
  fVar7 = (float10)fcos(fVar8);
  fVar8 = (float10)fsin(fVar8);
  fVar1 = (float)fVar7;
  fVar2 = (float)fVar8;
  fVar8 = (float10)((param_1->_s_0).x * ___real_3c8efa35);
  fVar7 = (float10)fcos(fVar8);
  fVar8 = (float10)fsin(fVar8);
  fVar3 = (float)fVar7;
  fVar4 = (float)fVar8;
  (param_2->_s_0).y = fVar3 * fVar2;
  (param_2->_s_0).x = fVar3 * fVar1;
  (param_2->_s_0).z = (float)((uint)fVar4 ^ ___mask__NegFloat_);
  fVar8 = (float10)((param_1->_s_0).z * fVar5);
  fVar7 = (float10)fcos(fVar8);
  fVar8 = (float10)fsin(fVar8);
  fVar5 = (float)fVar7;
  fVar6 = (float)fVar8;
  param_2[1]._s_0.x = fVar6 * fVar4 * fVar1 - fVar5 * fVar2;
  *(float *)((int)param_2 + 0x10) = fVar6 * fVar4 * fVar2 + fVar5 * fVar1;
  *(float *)((int)param_2 + 0x14) = fVar6 * fVar3;
  param_2[2]._s_0.x = fVar5 * fVar4 * fVar1 + fVar6 * fVar2;
  *(float *)((int)param_2 + 0x1c) = fVar5 * fVar4 * fVar2 - fVar6 * fVar1;
  *(float *)((int)param_2 + 0x20) = fVar5 * fVar3;
  return;
}

