
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl DObjCalcBounds(DObj *param_1,vec3_t *param_2,vec3_t *param_3)

{
  float *pfVar1;
  float fVar2;
  byte bVar3;
  byte bVar4;
  XModel *pXVar5;
  XModel **ppXVar6;
  code *pcVar7;
  bool bVar8;
  DObjAnimMat *pDVar9;
  int iVar10;
  vec3_t *pvVar11;
  uint uVar12;
  vec4_t *pvVar13;
  uint uStack_58;
  vec3_t vStack_50;
  vec3_t vStack_44;
  vec3_t avStack_38 [4];
  uint uStack_8;
  
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  uVar12 = (uint)param_1->numModels;
  if ((uVar12 == 0) &&
     (bVar8 = Assert_MyHandler("c:\\t6\\code\\src\\xanim\\dobj.cpp",0x40b,0,"(numModels)",""),
     !bVar8)) {
    pcVar7 = (code *)swi(3);
    (*pcVar7)();
    return;
  }
  fVar2 = ___real_c0800000;
  pXVar5 = *(param_1->field15_0x78).localModels;
  (param_2->_s_0).x = ___real_c0800000;
  (param_2->_s_0).y = fVar2;
  (param_2->_s_0).z = 0.0;
  fVar2 = __real_40800000;
  (param_3->_s_0).x = __real_40800000;
  (param_3->_s_0).y = fVar2;
  (param_3->_s_0).z = __real_41200000;
  bVar3 = param_1->numModels;
  ppXVar6 = (param_1->field15_0x78).localModels;
  uStack_58 = 0;
  if (uVar12 != 0) {
    do {
      bVar4 = *(byte *)((int)ppXVar6 + uStack_58 + (uint)bVar3 * 4);
      if ((uStack_58 == 0) || (bVar4 == 0xff)) {
        XModelGetBounds(pXVar5,&vStack_50,&vStack_44);
LAB_007a1a4c:
        iVar10 = 3;
        pvVar11 = param_2;
        do {
          fVar2 = *(float *)(((int)&vStack_50 - (int)param_2) + (int)pvVar11);
          if (fVar2 < (pvVar11->_s_0).x) {
            (pvVar11->_s_0).x = fVar2;
          }
          fVar2 = *(float *)(((int)&vStack_44 - (int)param_2) + (int)pvVar11);
          pfVar1 = (float *)(((int)param_3 - (int)param_2) + (int)pvVar11);
          if (*pfVar1 <= fVar2 && fVar2 != *pfVar1) {
            *(float *)(((int)param_3 - (int)param_2) + (int)pvVar11) = fVar2;
          }
          pvVar11 = (vec3_t *)&(pvVar11->_s_0).y;
          iVar10 = iVar10 + -1;
        } while (iVar10 != 0);
      }
      else if (bVar4 < pXVar5->numBones) {
        pDVar9 = XModelGetBasePose(pXVar5);
        pvVar13 = &pDVar9[bVar4].quat;
        QuatToAxis(pvVar13,avStack_38);
        iVar10 = XModelGetStaticBounds
                           ((param_1->field15_0x78).localModels[uStack_58],avStack_38,&vStack_50,
                            &vStack_44);
        if (iVar10 == 0) {
          vStack_50._s_0.x = ___real_7f7fffff;
          vStack_50._s_0.y = ___real_7f7fffff;
          vStack_50._s_0.z = ___real_7f7fffff;
          vStack_44._s_0.x = ___real_ff7fffff;
          vStack_44._s_0.y = ___real_ff7fffff;
          vStack_44._s_0.z = ___real_ff7fffff;
        }
        else {
          vStack_50._s_0.x = pvVar13[1].v[0] + vStack_50._s_0.x;
          vStack_50._s_0.y = vStack_50._s_0.y + *(float *)((int)pvVar13 + 0x14);
          vStack_50._s_0.z = vStack_50._s_0.z + *(float *)((int)pvVar13 + 0x18);
          vStack_44._s_0.x = pvVar13[1].v[0] + vStack_44._s_0.x;
          vStack_44._s_0.y = vStack_44._s_0.y + *(float *)((int)pvVar13 + 0x14);
          vStack_44._s_0.z = vStack_44._s_0.z + *(float *)((int)pvVar13 + 0x18);
        }
        goto LAB_007a1a4c;
      }
      uStack_58 = uStack_58 + 1;
    } while (uStack_58 < uVar12);
  }
  return;
}

