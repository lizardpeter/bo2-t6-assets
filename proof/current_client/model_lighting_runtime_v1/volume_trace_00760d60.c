
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00760d60(undefined4 param_1,int param_2)

{
  undefined4 uVar1;
  uint uVar2;
  int *piVar3;
  undefined4 uVar4;
  
  if (param_2 != 0) {
    uVar2 = _DAT_03a36ae0 & 0x80000001;
    if ((int)uVar2 < 0) {
      uVar2 = (uVar2 - 1 | 0xfffffffe) + 1;
    }
    uVar1 = *(undefined4 *)(&DAT_03a36ae4 + uVar2 * 4);
    _DAT_03a36ae0 = _DAT_03a36ae0 + 1;
    FUN_0057a430(0x22);
    do {
      (**(code **)(*_DAT_035ae488 + 0x38))(_DAT_035ae488,uVar1,0,2,0,&DAT_03a36aec);
    } while (_DAT_029e53c8 != 0);
    if (_DAT_03a36adc == (void *)0x0) {
      _DAT_03a36adc = (void *)FUN_00a795e0(_DAT_03a36af4 * 4);
      _memset(_DAT_03a36adc,0,_DAT_03a36af4 * 4);
    }
    FUN_00760cf0();
    _DAT_035f13d4 = _DAT_03a36af4 + _DAT_03a36af0 * -3;
    _DAT_036227fc = _DAT_03a36af0;
    for (; param_2 != 0; param_2 = param_2 + -1) {
      FUN_00758b20();
    }
    FID_conflict__memcpy(_DAT_03a36aec,_DAT_03a36adc,_DAT_03a36af4 * 4);
    uVar4 = 0;
    (**(code **)(*_DAT_035ae488 + 0x3c))(_DAT_035ae488,uVar1,0);
    _DAT_03a36aec = (void *)0x0;
    piVar3 = (int *)&stack0xffffffe4;
    (**(code **)(*(int *)*_DAT_03a36a9c + 0x1c))((int *)*_DAT_03a36a9c);
    (**(code **)(*_DAT_035ae488 + 0xbc))(_DAT_035ae488,uVar4,uVar1);
    FUN_005262b0(0x22);
    (**(code **)(*piVar3 + 8))(piVar3);
  }
  return;
}

