
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl R_EncodeLightingSH(GfxLightingSH *param_1,GfxLightingSHQuantized *param_2)

{
  float fVar1;
  float fVar2;
  float fVar3;
  float fVar4;
  float fVar5;
  ushort *puVar6;
  vec4_t *pvVar7;
  int iVar8;
  float fVar9;
  
  fVar5 = ___real_44ffff00;
  fVar4 = __real_41800000;
  fVar3 = ___real_c1800000;
  fVar2 = __real_3f000000;
  puVar6 = param_2->V2;
  pvVar7 = &param_1->V2;
  iVar8 = 4;
  do {
    fVar1 = (((GfxLightingSH *)(pvVar7 + -2))->V0).v[0];
    fVar9 = fVar1;
    if (0.0 <= fVar1 - fVar4) {
      fVar9 = fVar4;
    }
    if (0.0 <= fVar3 - fVar1) {
      fVar9 = fVar3;
    }
    ((GfxLightingSHQuantized *)(puVar6 + -8))->V0[0] =
         (ushort)(int)((fVar9 - fVar3) * fVar5 + fVar2);
    fVar1 = pvVar7[-1].v[0];
    fVar9 = fVar1;
    if (0.0 <= fVar1 - fVar4) {
      fVar9 = fVar4;
    }
    if (0.0 <= fVar3 - fVar1) {
      fVar9 = fVar3;
    }
    puVar6[-4] = (ushort)(int)((fVar9 - fVar3) * fVar5 + fVar2);
    fVar1 = pvVar7->v[0];
    fVar9 = fVar1;
    if (0.0 <= fVar1 - fVar4) {
      fVar9 = fVar4;
    }
    if (0.0 <= fVar3 - fVar1) {
      fVar9 = fVar3;
    }
    *puVar6 = (ushort)(int)((fVar9 - fVar3) * fVar5 + fVar2);
    pvVar7 = (vec4_t *)((int)pvVar7 + 4);
    puVar6 = puVar6 + 1;
    iVar8 = iVar8 + -1;
  } while (iVar8 != 0);
  return;
}

