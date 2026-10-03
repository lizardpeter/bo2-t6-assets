
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

uint FUN_0075bb80(uint *param_1,uint param_2,undefined4 param_3,float *param_4,undefined4 param_5,
                 char param_6)

{
  float fVar1;
  uint uVar2;
  uint uVar3;
  uint uVar4;
  uint uVar5;
  uint uVar6;
  float fVar7;
  float fVar8;
  float fVar9;
  byte bStack_7e;
  undefined4 uStack_7c;
  short asStack_78 [8];
  float afStack_68 [8];
  float afStack_48 [8];
  int aiStack_28 [9];
  
  uVar3 = FUN_0075b860(param_1,aiStack_28,&uStack_7c);
  uVar3 = uVar3 & 0xff;
  if (uVar3 == 0xff) {
    uVar3 = (uint)(byte)*param_1;
  }
  fVar7 = 0.0;
  param_2 = -(uint)(param_6 != '\0') & param_2;
  uVar5 = 0;
  fVar9 = 0.0;
  fVar8 = 0.0;
  uVar6 = 0;
  do {
    if (*(uint **)((int)aiStack_28 + uVar6) != (uint *)0x0) {
      uVar2 = **(uint **)((int)aiStack_28 + uVar6);
      bStack_7e = (byte)(uVar2 >> 0x10);
      if ((bStack_7e == uVar3) || ((uVar3 == *param_1 && (bStack_7e == 0xff)))) {
        fVar8 = *(float *)((int)afStack_68 + uVar6) + fVar8;
        fVar7 = fVar7 + (float)(uVar2 >> 0x18) * *(float *)((int)afStack_68 + uVar6);
      }
      fVar1 = *(float *)((int)afStack_68 + uVar6);
      uVar4 = 0;
      fVar9 = fVar9 + fVar1;
      if (uVar5 != 0) {
        do {
          if (asStack_78[uVar4] == (short)uVar2) {
            afStack_48[uVar4] = afStack_48[uVar4] + fVar1;
            goto LAB_0075bc48;
          }
          uVar4 = uVar4 + 1;
        } while (uVar4 < uVar5);
      }
      asStack_78[uVar5] = (short)uVar2;
      afStack_48[uVar5] = fVar1;
      uVar5 = uVar5 + 1;
    }
LAB_0075bc48:
    uVar6 = uVar6 + 4;
    if (0x1f < uVar6) {
      if (uVar5 == 0) {
        uVar3 = FUN_0075b1b0(param_2,param_3,param_4,param_5,uStack_7c);
        return uVar3 & 0xff;
      }
      *param_4 = fVar7 / (fVar8 * _DAT_00c0faec);
      if (uVar5 != 1) {
        FUN_0075a6a0(asStack_78,afStack_48,uVar5,param_2,_DAT_00d2b3c8 / fVar9,param_3,param_5);
        return uVar3;
      }
      FUN_0075a3f0(param_2,param_3,param_5);
      return uVar3;
    }
  } while( true );
}

