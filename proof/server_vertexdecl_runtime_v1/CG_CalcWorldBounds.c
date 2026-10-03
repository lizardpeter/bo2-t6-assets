
/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* WARNING: Enum "ClientNum_t": Some values do not have unique names */
/* WARNING: Enum "team_t": Some values do not have unique names */
/* WARNING: Enum "nodeType": Some values do not have unique names */
/* WARNING: Enum "AISpecies": Some values do not have unique names */
/* WARNING: Enum "ai_state_t": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "eAttachment": Some values do not have unique names */

void __cdecl CG_CalcWorldBounds(centity_t *param_1,DObj *param_2,float param_3)

{
  short sVar1;
  float fVar2;
  float fVar3;
  float fVar4;
  bool bVar5;
  byte bVar6;
  bool bVar7;
  int iVar8;
  uint uVar9;
  uint uVar10;
  uint uVar11;
  uint uVar12;
  uint uVar13;
  uint uVar14;
  uint uVar15;
  uint uVar16;
  uint uVar17;
  uint uVar18;
  uint uVar19;
  uint uVar20;
  uint uVar21;
  float fVar22;
  uint uVar23;
  float fVar24;
  uint uVar25;
  float fVar26;
  float fVar27;
  float fVar28;
  float fVar29;
  float fVar30;
  float fVar31;
  float fVar32;
  float fVar33;
  float fVar34;
  float fVar35;
  vec3_t vStack_60;
  vec3_t vStack_50;
  vec3_t vStack_3c;
  uint uStack_30;
  uint uStack_2c;
  uint uStack_28;
  uint uStack_24;
  uint uStack_20;
  uint uStack_1c;
  uint uStack_14;
  
  uStack_14 = __security_cookie ^ (uint)&stack0xfffffff0;
  iVar8 = DObjHasCollmap(param_2);
  sVar1 = (param_1->nextState).eType;
  if (((param_1->nextState).surfType == '\a') && (iVar8 == 0)) {
    bVar6 = 1;
  }
  else {
    bVar6 = 0;
  }
  bVar5 = (bool)((sVar1 == 2 || sVar1 == 1) | (sVar1 == 0x12 || sVar1 == 0x10) | bVar6);
  bVar7 = G_IsSpeciesBigDog((param_1->nextState).lerp.u.loopFx.period);
  if (bVar7) {
    bVar5 = false;
  }
  if ((param_1->pose).isRagdoll == '\0') {
    if (!bVar5) {
      DObjCalcBounds(param_2,&vStack_50,&vStack_60);
      vStack_50._s_0.x = vStack_50._s_0.x * param_3;
      vStack_50._s_0.y = vStack_50._s_0.y * param_3;
      vStack_50._s_0.z = vStack_50._s_0.z * param_3;
      vStack_60._s_0.x = vStack_60._s_0.x * param_3;
      vStack_60._s_0.y = vStack_60._s_0.y * param_3;
      vStack_60._s_0.z = vStack_60._s_0.z * param_3;
      uVar21 = (uint)vStack_50._s_0.x & g_keepXYZ.m128_u32[0];
      uVar23 = (uint)vStack_50._s_0.y & g_keepXYZ.m128_u32[1];
      uVar25 = (uint)vStack_50._s_0.z & g_keepXYZ.m128_u32[2];
      uVar18 = g_keepXYZ.m128_u32[0] & (uint)vStack_60._s_0.x;
      uVar19 = g_keepXYZ.m128_u32[1] & (uint)vStack_60._s_0.y;
      uVar20 = g_keepXYZ.m128_u32[2] & (uint)vStack_60._s_0.z;
      AnglesToAxis(&(param_1->pose).angles,&vStack_3c);
      uVar9 = g_keepXYZ.m128_u32[0];
      fVar30 = (float)(uStack_24 & uVar9);
      uVar10 = g_keepXYZ.m128_u32[1];
      fVar32 = (float)(uStack_20 & uVar10);
      uVar11 = g_keepXYZ.m128_u32[2];
      fVar34 = (float)(uStack_1c & uVar11);
      fVar22 = (float)((uint)vStack_3c._s_0.x & uVar9);
      fVar24 = (float)((uint)vStack_3c._s_0.y & uVar10);
      fVar26 = (float)((uint)vStack_3c._s_0.z & uVar11);
      fVar31 = (float)((uint)(param_1->pose).origin._s_0.x & uVar9);
      fVar33 = (float)((uint)(param_1->pose).origin._s_0.y & uVar10);
      fVar35 = (float)((uint)(param_1->pose).origin._s_0.z & uVar11);
      fVar27 = (float)(uStack_30 & uVar9);
      fVar28 = (float)(uStack_2c & uVar10);
      fVar29 = (float)(uStack_28 & uVar11);
      fVar2 = g_zero.m128_f32[0];
      fVar3 = g_zero.m128_f32[1];
      fVar4 = g_zero.m128_f32[2];
      uVar9 = -(uint)(fVar22 < fVar2);
      uVar12 = -(uint)(fVar24 < fVar3);
      uVar15 = -(uint)(fVar26 < fVar4);
      uVar10 = -(uint)(fVar27 < fVar2);
      uVar13 = -(uint)(fVar28 < fVar3);
      uVar16 = -(uint)(fVar29 < fVar4);
      uVar11 = -(uint)(fVar30 < fVar2);
      uVar14 = -(uint)(fVar32 < fVar3);
      uVar17 = -(uint)(fVar34 < fVar4);
      (param_1->pose).absmin._s_0.x =
           (float)(uVar9 & uVar18 | ~uVar9 & uVar21) * fVar22 + fVar31 +
           (float)(uVar10 & uVar19 | ~uVar10 & uVar23) * fVar27 +
           (float)(uVar11 & uVar20 | ~uVar11 & uVar25) * fVar30;
      (param_1->pose).absmin._s_0.y =
           (float)(uVar12 & uVar18 | ~uVar12 & uVar21) * fVar24 + fVar33 +
           (float)(uVar13 & uVar19 | ~uVar13 & uVar23) * fVar28 +
           (float)(uVar14 & uVar20 | ~uVar14 & uVar25) * fVar32;
      (param_1->pose).absmin._s_0.z =
           (float)(uVar15 & uVar18 | ~uVar15 & uVar21) * fVar26 + fVar35 +
           (float)(uVar16 & uVar19 | ~uVar16 & uVar23) * fVar29 +
           (float)(uVar17 & uVar20 | ~uVar17 & uVar25) * fVar34;
      (param_1->pose).absmax._s_0.x =
           (float)(uVar9 & uVar21 | ~uVar9 & uVar18) * fVar22 + fVar31 +
           (float)(uVar10 & uVar23 | ~uVar10 & uVar19) * fVar27 +
           (float)(~uVar11 & uVar20 | uVar11 & uVar25) * fVar30;
      (param_1->pose).absmax._s_0.y =
           (float)(uVar12 & uVar21 | ~uVar12 & uVar18) * fVar24 + fVar33 +
           (float)(uVar13 & uVar23 | ~uVar13 & uVar19) * fVar28 +
           (float)(~uVar14 & uVar20 | uVar14 & uVar25) * fVar32;
      (param_1->pose).absmax._s_0.z =
           (float)(uVar15 & uVar21 | ~uVar15 & uVar18) * fVar26 + fVar35 +
           (float)(uVar16 & uVar23 | ~uVar16 & uVar19) * fVar29 +
           (float)(~uVar17 & uVar20 | uVar17 & uVar25) * fVar34;
      return;
    }
    (param_1->pose).absmin._s_0.x = (param_1->pose).origin._s_0.x + actorLocationalMins._s_0.x;
    (param_1->pose).absmin._s_0.y = (param_1->pose).origin._s_0.y + actorLocationalMins._s_0.y;
    (param_1->pose).absmin._s_0.z = actorLocationalMins._s_0.z + (param_1->pose).origin._s_0.z;
    (param_1->pose).absmax._s_0.x = (param_1->pose).origin._s_0.x + actorLocationalMaxs._s_0.x;
    (param_1->pose).absmax._s_0.y = (param_1->pose).origin._s_0.y + actorLocationalMaxs._s_0.y;
    (param_1->pose).absmax._s_0.z = actorLocationalMaxs._s_0.z + (param_1->pose).origin._s_0.z;
    return;
  }
  (param_1->pose).absmin._s_0.x = (param_1->pose).origin._s_0.x + actorLocationalMinsBig._s_0.x;
  (param_1->pose).absmin._s_0.y = (param_1->pose).origin._s_0.y + actorLocationalMinsBig._s_0.y;
  (param_1->pose).absmin._s_0.z = actorLocationalMinsBig._s_0.z + (param_1->pose).origin._s_0.z;
  (param_1->pose).absmax._s_0.x = (param_1->pose).origin._s_0.x + actorLocationalMaxsBig._s_0.x;
  (param_1->pose).absmax._s_0.y = (param_1->pose).origin._s_0.y + actorLocationalMaxsBig._s_0.y;
  (param_1->pose).absmax._s_0.z = actorLocationalMaxsBig._s_0.z + (param_1->pose).origin._s_0.z;
  return;
}

