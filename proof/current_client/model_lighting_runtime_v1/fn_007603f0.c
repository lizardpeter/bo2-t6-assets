
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __fastcall FUN_007603f0(int param_1)

{
  float fVar1;
  float fVar2;
  float fVar3;
  float fVar4;
  float fVar5;
  int in_EAX;
  undefined2 *puVar6;
  float *pfVar7;
  int iVar8;
  float fVar9;
  
  fVar5 = _DAT_00d33b58;
  fVar4 = _DAT_00c77ff4;
  fVar3 = _DAT_00c519c8;
  fVar2 = _DAT_00be5a68;
  puVar6 = (undefined2 *)(in_EAX + 0x10);
  pfVar7 = (float *)(param_1 + 0x20);
  iVar8 = 4;
  do {
    fVar1 = pfVar7[-8];
    fVar9 = fVar1;
    if (0.0 <= fVar1 - fVar4) {
      fVar9 = fVar4;
    }
    if (0.0 <= fVar2 - fVar1) {
      fVar9 = fVar2;
    }
    puVar6[-8] = (short)(int)((fVar9 - fVar2) * fVar5 + fVar3);
    fVar1 = pfVar7[-4];
    fVar9 = fVar1;
    if (0.0 <= fVar1 - fVar4) {
      fVar9 = fVar4;
    }
    if (0.0 <= fVar2 - fVar1) {
      fVar9 = fVar2;
    }
    puVar6[-4] = (short)(int)((fVar9 - fVar2) * fVar5 + fVar3);
    fVar1 = *pfVar7;
    fVar9 = fVar1;
    if (0.0 <= fVar1 - fVar4) {
      fVar9 = fVar4;
    }
    if (0.0 <= fVar2 - fVar1) {
      fVar9 = fVar2;
    }
    *puVar6 = (short)(int)((fVar9 - fVar2) * fVar5 + fVar3);
    pfVar7 = pfVar7 + 1;
    puVar6 = puVar6 + 1;
    iVar8 = iVar8 + -1;
  } while (iVar8 != 0);
  return;
}

