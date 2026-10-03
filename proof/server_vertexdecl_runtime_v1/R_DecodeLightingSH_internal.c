
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl R_DecodeLightingSH(GfxLightingSHQuantized *param_1,GfxLightingSH *param_2)

{
  uint uVar1;
  float fVar2;
  float fVar3;
  float fVar4;
  uint uVar5;
  uint uVar6;
  uint uVar7;
  float fVar8;
  float fVar9;
  float fVar10;
  float fVar11;
  float fVar12;
  float fVar13;
  float fVar14;
  float fVar15;
  float fVar16;
  float fVar17;
  float fVar18;
  float fVar19;
  uint uVar20;
  uint uVar21;
  uint uVar22;
  float fVar23;
  uint uVar24;
  float fVar25;
  float fVar26;
  
  fVar19 = _UNK_00d23b9c;
  fVar18 = _UNK_00d23b98;
  fVar17 = _UNK_00d23b94;
  fVar16 = _DAT_00d23b90;
  fVar15 = _UNK_00d23b8c;
  fVar14 = _UNK_00d23b88;
  fVar13 = _UNK_00d23b84;
  fVar12 = _DAT_00d23b80;
  fVar11 = _UNK_00d23b7c;
  fVar10 = _UNK_00d23b78;
  fVar9 = _UNK_00d23b74;
  fVar8 = _DAT_00d23b70;
  uVar20 = (uint)*(undefined8 *)param_1->V0;
  uVar22 = (uint)((ulonglong)*(undefined8 *)param_1->V0 >> 0x20);
  fVar23 = ((float)(int)(uVar20 & g_XMMaskX16Y16Z16W16.field0_0x0._8_4_ ^
                        g_XMFlipZW.field0_0x0._8_4_) * g_XMFixupY16W16.field0_0x0._8_4_ +
           `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0.
           _8_4_) * _UNK_00d23b74 * _UNK_00d23b84 + _UNK_00d23b94;
  fVar25 = ((float)(int)(uVar22 & g_XMMaskX16Y16Z16W16.field0_0x0._4_4_ ^
                        g_XMFlipZW.field0_0x0._4_4_) * g_XMFixupY16W16.field0_0x0._4_4_ +
           `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0.
           _4_4_) * _UNK_00d23b78 * _UNK_00d23b88 + _UNK_00d23b98;
  fVar26 = ((float)(int)(uVar22 & g_XMMaskX16Y16Z16W16.field0_0x0._12_4_ ^
                        g_XMFlipZW.field0_0x0._12_4_) * g_XMFixupY16W16.field0_0x0._12_4_ +
           `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0.
           _12_4_) * _UNK_00d23b7c * _UNK_00d23b8c + _UNK_00d23b9c;
  (param_2->V0).v[0] =
       ((float)(int)(uVar20 & g_XMMaskX16Y16Z16W16.field0_0x0._0_4_ ^ g_XMFlipZW.field0_0x0._0_4_) *
        g_XMFixupY16W16.field0_0x0._0_4_ +
       `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0._0_4_)
       * _DAT_00d23b70 * _DAT_00d23b80 + _DAT_00d23b90;
  (param_2->V0).v[1] = fVar23;
  (param_2->V0).v[2] = fVar25;
  (param_2->V0).v[3] = fVar26;
  uVar21 = (uint)*(undefined8 *)param_1->V1;
  uVar24 = (uint)((ulonglong)*(undefined8 *)param_1->V1 >> 0x20);
  uVar20 = g_XMMaskX16Y16Z16W16.field0_0x0._4_4_;
  uVar22 = g_XMMaskX16Y16Z16W16.field0_0x0._8_4_;
  uVar1 = g_XMMaskX16Y16Z16W16.field0_0x0._12_4_;
  uVar5 = g_XMFlipZW.field0_0x0._4_4_;
  uVar6 = g_XMFlipZW.field0_0x0._8_4_;
  uVar7 = g_XMFlipZW.field0_0x0._12_4_;
  fVar2 = g_XMFixupY16W16.field0_0x0._4_4_;
  fVar3 = g_XMFixupY16W16.field0_0x0._8_4_;
  fVar4 = g_XMFixupY16W16.field0_0x0._12_4_;
  fVar23 = `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0.
           _4_4_;
  fVar25 = `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0.
           _8_4_;
  fVar26 = `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0.
           _12_4_;
  (param_2->V1).v[0] =
       ((float)(int)(uVar21 & g_XMMaskX16Y16Z16W16.field0_0x0._0_4_ ^ g_XMFlipZW.field0_0x0._0_4_) *
        g_XMFixupY16W16.field0_0x0._0_4_ +
       `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0._0_4_)
       * fVar8 * fVar12 + fVar16;
  (param_2->V1).v[1] =
       ((float)(int)(uVar21 & uVar22 ^ uVar6) * fVar3 + fVar25) * fVar9 * fVar13 + fVar17;
  (param_2->V1).v[2] =
       ((float)(int)(uVar24 & uVar20 ^ uVar5) * fVar2 + fVar23) * fVar10 * fVar14 + fVar18;
  (param_2->V1).v[3] =
       ((float)(int)(uVar24 & uVar1 ^ uVar7) * fVar4 + fVar26) * fVar11 * fVar15 + fVar19;
  uVar21 = (uint)*(undefined8 *)param_1->V2;
  uVar24 = (uint)((ulonglong)*(undefined8 *)param_1->V2 >> 0x20);
  uVar20 = g_XMMaskX16Y16Z16W16.field0_0x0._4_4_;
  uVar22 = g_XMMaskX16Y16Z16W16.field0_0x0._8_4_;
  uVar1 = g_XMMaskX16Y16Z16W16.field0_0x0._12_4_;
  uVar5 = g_XMFlipZW.field0_0x0._4_4_;
  uVar6 = g_XMFlipZW.field0_0x0._8_4_;
  uVar7 = g_XMFlipZW.field0_0x0._12_4_;
  fVar2 = g_XMFixupY16W16.field0_0x0._4_4_;
  fVar3 = g_XMFixupY16W16.field0_0x0._8_4_;
  fVar4 = g_XMFixupY16W16.field0_0x0._12_4_;
  fVar23 = `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0.
           _4_4_;
  fVar25 = `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0.
           _8_4_;
  fVar26 = `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0.
           _12_4_;
  (param_2->V2).v[0] =
       ((float)(int)(uVar21 & g_XMMaskX16Y16Z16W16.field0_0x0._0_4_ ^ g_XMFlipZW.field0_0x0._0_4_) *
        g_XMFixupY16W16.field0_0x0._0_4_ +
       `union___m128___cdecl_XMLoadUShort4(_XMUSHORT4_const*)'::__l2::FixaddY16W16.field0_0x0._0_4_)
       * fVar8 * fVar12 + fVar16;
  (param_2->V2).v[1] =
       ((float)(int)(uVar21 & uVar22 ^ uVar6) * fVar3 + fVar25) * fVar9 * fVar13 + fVar17;
  (param_2->V2).v[2] =
       ((float)(int)(uVar24 & uVar20 ^ uVar5) * fVar2 + fVar23) * fVar10 * fVar14 + fVar18;
  (param_2->V2).v[3] =
       ((float)(int)(uVar24 & uVar1 ^ uVar7) * fVar4 + fVar26) * fVar11 * fVar15 + fVar19;
  return;
}

