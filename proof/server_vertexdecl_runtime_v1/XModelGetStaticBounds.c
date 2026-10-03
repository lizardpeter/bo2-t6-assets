
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

int __cdecl XModelGetStaticBounds(XModel *param_1,vec3_t *param_2,vec3_t *param_3,vec3_t *param_4)

{
  XModelCollSurf_s *pXVar1;
  code *pcVar2;
  bool bVar3;
  int iVar4;
  uint uVar5;
  float fVar6;
  float fVar7;
  float fVar8;
  int iStack_1c;
  int iStack_18;
  float afStack_14 [3];
  uint uStack_8;
  
  fVar8 = ___real_7f7fffff;
  uStack_8 = __security_cookie ^ (uint)&stack0xfffffffc;
  if (param_1->numCollSurfs != 0) {
    (param_3->_s_0).x = ___real_7f7fffff;
    (param_3->_s_0).y = fVar8;
    (param_3->_s_0).z = fVar8;
    fVar8 = ___real_ff7fffff;
    (param_4->_s_0).x = ___real_ff7fffff;
    (param_4->_s_0).y = fVar8;
    (param_4->_s_0).z = fVar8;
    iStack_1c = 0;
    if (0 < param_1->numCollSurfs) {
      iStack_18 = 0;
      do {
        pXVar1 = param_1->collSurfs;
        uVar5 = 0;
        do {
          if ((uVar5 & 1) == 0) {
            fVar8 = *(float *)((int)&pXVar1->maxs + iStack_18);
          }
          else {
            fVar8 = *(float *)((int)&pXVar1->mins + iStack_18);
          }
          if ((uVar5 & 2) == 0) {
            fVar7 = *(float *)((int)&pXVar1->maxs + iStack_18 + 4);
          }
          else {
            fVar7 = *(float *)((int)&pXVar1->mins + iStack_18 + 4);
          }
          if ((uVar5 & 4) == 0) {
            fVar6 = *(float *)((int)&pXVar1->maxs + iStack_18 + 8);
          }
          else {
            fVar6 = *(float *)((int)&pXVar1->mins + iStack_18 + 8);
          }
          afStack_14[0] =
               (param_2->_s_0).x * fVar8 + fVar7 * param_2[1]._s_0.x + fVar6 * param_2[2]._s_0.x;
          afStack_14[1] =
               *(float *)((int)param_2 + 0x10) * fVar7 + (param_2->_s_0).y * fVar8 +
               *(float *)((int)param_2 + 0x1c) * fVar6;
          afStack_14[2] =
               *(float *)((int)param_2 + 0x14) * fVar7 + (param_2->_s_0).z * fVar8 +
               fVar6 * *(float *)((int)param_2 + 0x20);
          iVar4 = 0;
          do {
            fVar8 = afStack_14[iVar4];
            if (fVar8 < param_3->v[iVar4]) {
              param_3->v[iVar4] = fVar8;
            }
            if (param_4->v[iVar4] <= fVar8 && fVar8 != param_4->v[iVar4]) {
              param_4->v[iVar4] = fVar8;
            }
            iVar4 = iVar4 + 1;
          } while (iVar4 < 3);
          uVar5 = uVar5 + 1;
        } while ((int)uVar5 < 8);
        iStack_18 = iStack_18 + 0x2c;
        iStack_1c = iStack_1c + 1;
      } while (iStack_1c < param_1->numCollSurfs);
    }
    return 1;
  }
  if ((param_1->contents != 0) &&
     (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\xanim\\xmodel_load_obj.cpp",0x640,0,
                               "(!model->contents)",""), !bVar3)) {
    pcVar2 = (code *)swi(3);
    iVar4 = (*pcVar2)();
    return iVar4;
  }
  return 0;
}

