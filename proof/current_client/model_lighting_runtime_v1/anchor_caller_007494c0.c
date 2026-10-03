
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_007494c0(void)

{
  undefined2 uVar1;
  bool bVar2;
  bool bVar3;
  uint uVar4;
  undefined1 uVar5;
  undefined1 uVar6;
  undefined4 uVar7;
  undefined4 uVar8;
  char cVar9;
  undefined1 *puVar10;
  int iVar11;
  int iVar12;
  char *pcVar13;
  undefined4 uVar14;
  bool bVar15;
  float10 fVar16;
  
  if (_DAT_035ebd8c == 0) {
    _DAT_035e6020 = _DAT_035e6020 + 1;
  }
  puVar10 = &DAT_03a26730;
  do {
    *puVar10 = 0;
    puVar10 = puVar10 + 0x14;
  } while ((int)puVar10 < 0x3a26cd0);
  DAT_035e6024 = 2;
  FUN_0057a430(0x2c);
  if (DAT_03a8e7a5 == '\0') {
    FUN_005262b0(0x2c);
    goto LAB_00749bbb;
  }
  if (_DAT_03a8e7ac != 0) {
    FUN_005262b0(0x2c);
    goto LAB_00749bbb;
  }
  FUN_0073b4f0();
  FUN_0057a430(0x2a);
  FUN_0073b920();
  if (((_DAT_035f08f8 == -1) && ((_DAT_035ef464 & 0x40) == 0)) &&
     ((_DAT_035ef248 != 0 || ((_DAT_035ef7a0 & 1) != 0)))) {
    bVar2 = true;
  }
  else {
    bVar2 = false;
  }
  bVar15 = false;
  if (bVar2) {
    if (((_DAT_035f08ec < 1) || ((_DAT_035ef7a0 & 1) == 0)) || ((_DAT_035ef7a0 & 0x100) == 0)) {
      bVar2 = false;
LAB_007495a9:
      bVar3 = bVar2;
      bVar15 = false;
    }
    else {
      bVar3 = true;
      bVar15 = true;
      bVar2 = true;
      if ((_DAT_035ef7a0 & 4) == 0) goto LAB_007495a9;
    }
    if (_DAT_035ef248 != 0) {
      FUN_006d62f0();
      if ((_DAT_035ef464 & 4) != 0) {
        FUN_006a26c0(_DAT_035f08f8,1);
      }
      _DAT_035ef464 = _DAT_035ef464 & 0xfffffffe;
      _DAT_035ef248 = 0;
      DAT_035ef250 = 0;
      (**(code **)(_DAT_035ef57c + 0x1c))(_DAT_035ef24c);
      iVar11 = FUN_0066a080(_DAT_035f08f8);
      while (iVar11 != 0) {
        FUN_004ca0c0(1);
        iVar11 = FUN_0066a080(_DAT_035f08f8);
      }
      _DAT_035f08f8 = -1;
      _DAT_035ef24c = 0;
    }
    iVar11 = _DAT_035ef57c;
    if (bVar3) {
      FUN_0073b890();
      if ((_DAT_035f0b54 != 0) &&
         ((!bVar15 ||
          (iVar12 = (**(code **)(_DAT_035ef57c + 0x40))(_DAT_035ef460), _DAT_035f0b54 != iVar12))))
      {
        (**(code **)(iVar11 + 0xc))();
        _DAT_035f0b54 = 0;
        _DAT_035f0b50 = 0;
      }
      if (!bVar15) {
        FUN_0073b550();
      }
      if ((_DAT_035ef460 & 4) == 0) {
        if (bVar15) {
          _DAT_035f08f8 = _DAT_035f08fc;
          _DAT_035f08fc = -1;
        }
        else {
          _DAT_035ef464 = _DAT_035ef464 | 4;
          _DAT_035f0b0c = _DAT_035ef460;
          FUN_00424f00(&DAT_035f090c,&DAT_035ef250,0x200);
          DAT_035f0b10 = 0;
          FUN_006075a0(500,500,2,&LAB_0073b860,&DAT_035f090c,&DAT_035f08f8);
        }
      }
      else {
        _DAT_035ef24c = FUN_0073b7b0(_DAT_035ef460,0);
        _DAT_035ef464 =
             CONCAT22(DAT_035ef464_2,
                      _DAT_035ef464 ^ ((ushort)(_DAT_035ef24c != 0) << 3 ^ _DAT_035ef464) & 8);
      }
    }
    _DAT_035f0b48 = 0;
  }
  if ((((_DAT_035ef460 & 8) == 0) || ((_DAT_035ef79c & 8) == 0)) ||
     (((DAT_035ef7a0 & 4) != 0 || ((_DAT_035ef7a0 & 0x100) == 0)))) {
LAB_007497df:
    if ((_DAT_035ef464 & 4) != 0) goto LAB_007497f0;
LAB_00749850:
    if ((_DAT_035ef464 & 8) != 0) {
      if ((_DAT_035ef464 & 0x10) == 0) {
        if (((_DAT_035ef460 & 0x40) != 0) && (cVar9 = FUN_0073c1f0(), cVar9 == '\0'))
        goto LAB_00749a6d;
      }
      else if (((_DAT_035ef464 & 0x40) != 0) &&
              (cVar9 = (**(code **)(_DAT_035ef57c + 0x38))(_DAT_035ef24c), cVar9 != '\0')) {
        if ((_DAT_035ef460 & 0x40) != 0) {
          FUN_0063ac10(_DAT_035ef470,0);
          _DAT_035f0b48 = 0;
          cVar9 = FUN_0073c1f0();
          if (cVar9 == '\0') goto LAB_00749a6d;
        }
        _DAT_035ef464 = _DAT_035ef464 & 0xffffffef;
        (**(code **)(_DAT_035ef57c + 0x30))(_DAT_035ef24c,_DAT_035ef450);
        (**(code **)(_DAT_035ef57c + 0x18))(_DAT_035ef24c,_DAT_035ef460);
      }
    }
    if (((DAT_035ef478 != '\0') && (_DAT_035ef24c != 0)) &&
       (fVar16 = (float10)(**(code **)(_DAT_035ef57c + 0x24))(_DAT_035ef24c), fVar16 <= (float10)1))
    {
      DAT_035ef478 = '\0';
      _DAT_035ef474 = 0xffffffff;
      if (DAT_035ef479 != '\0') {
        pcVar13 = &DAT_035ef479;
        do {
          cVar9 = *pcVar13;
          pcVar13 = pcVar13 + 1;
        } while (cVar9 != '\0');
        if (*pcVar13 != '\0') {
          uVar14 = FUN_00593820(&DAT_00bfd490,&DAT_00d2ec60,pcVar13);
          puVar10 = (undefined1 *)FUN_00a75120(uVar14,0x3b);
          if (puVar10 != (undefined1 *)0x0) {
            *puVar10 = 0;
          }
          iVar11 = FUN_00499fd0(uVar14);
          if (iVar11 != 0) {
            _DAT_035ef474 = FUN_006bffb0(uVar14,0,_DAT_00d2b3c8,0xfff,0,0,0,1);
          }
        }
      }
    }
    FUN_005262b0(0x2a);
    iVar11 = _DAT_035ef46c;
    uVar6 = 0;
    uVar5 = 0;
    if ((((_DAT_035ef464 & 0x40) != 0) && ((_DAT_035ef464 & 8) != 0)) &&
       (uVar5 = uVar6, (_DAT_035ef464 & 0x10) == 0)) {
      cVar9 = (**(code **)(_DAT_035ef57c + 0x34))(_DAT_035ef24c);
      if (cVar9 == '\0') {
        if (((_DAT_035ef460 & 0x10) == 0) || ((_DAT_035ef460 & 1) == 0)) {
          uVar5 = 0;
        }
        else {
          uVar5 = 1;
        }
        if (iVar11 != _DAT_035ef468) {
          (**(code **)(_DAT_035ef57c + 0x20))(_DAT_035ef24c,iVar11 != 0,DAT_035ef464 >> 5 & 1);
          _DAT_035ef468 = iVar11;
          uVar5 = 1;
        }
        _DAT_035ef464 = _DAT_035ef464 & 0xffffffdf;
      }
      else if (_DAT_035ef468 == 0) {
        _DAT_035ef464 = _DAT_035ef464 | 0x20;
        _DAT_035ef468 = 1;
        (**(code **)(_DAT_035ef57c + 0x20))(_DAT_035ef24c,1,1);
      }
    }
    FUN_00909da0(&DAT_035ef479 + _DAT_010651ac,_DAT_035f0b48);
    if (_DAT_035ef57c == 0) {
      (*(code *)PTR_LAB_01063874)(0);
    }
    else {
      (**(code **)(_DAT_035ef57c + 4))(uVar5);
    }
    if ((_DAT_035ef24c != 0) &&
       (fVar16 = (float10)(**(code **)(_DAT_035ef57c + 0x24))(_DAT_035ef24c), fVar16 == (float10)0))
    {
      FUN_006d62f0();
      _DAT_035ef464 = _DAT_035ef464 & 0xffffffbf | 0x80;
    }
    if (((_DAT_035f0b50 == 0) || (_DAT_035ef248 != 0)) || ((_DAT_035ef464 & 4) != 0)) {
      _DAT_035f0900 = 0;
    }
    else {
      _DAT_035f0900 = _DAT_035f0900 + 1;
      if (4 < _DAT_035f0900) {
        (**(code **)(_DAT_035ef57c + 0xc))();
        _DAT_035f0b54 = 0;
        _DAT_035f0b50 = 0;
        _DAT_035ef460 = 0;
        _DAT_035ef57c = 0;
      }
    }
    FUN_005262b0(0x2c);
  }
  else {
    if ((_DAT_035ef464 & 4) == 0) {
      _DAT_035ef7a0 = _DAT_035ef7a0 | 4;
      _DAT_035f0b0c = _DAT_035ef79c;
      FUN_00424f00(&DAT_035f090c,&DAT_035ef58c,0x200);
      DAT_035f0b10 = 1;
      FUN_006075a0(500,800,2,&LAB_0073b860,&DAT_035f090c,&DAT_035f08fc);
      goto LAB_007497df;
    }
LAB_007497f0:
    while ((iVar11 = FUN_0066a080(_DAT_035f08f8), iVar11 != 0 && ((iVar11 < 3 || (7 < iVar11))))) {
      if (!bVar15) goto LAB_00749850;
      FUN_004ca0c0(1);
    }
    uVar1 = (undefined2)_DAT_035ef464;
    _DAT_035f08f8 = -1;
    uVar4 = _DAT_035ef464 & 0xfffffffb;
    _DAT_035ef464 = uVar4 | 8;
    if (_DAT_035f0b14 != 0) {
      _DAT_035ef24c = _DAT_035f0b14;
      _DAT_035f0b14 = 0;
      goto LAB_00749850;
    }
    DAT_035ef464_2 = (undefined2)(uVar4 >> 0x10);
    _DAT_035ef464 = CONCAT22(DAT_035ef464_2,uVar1) & 0xffffffbb | 8;
LAB_00749a6d:
    FUN_005262b0(0x2a);
    FUN_005262b0(0x2c);
  }
LAB_00749bbb:
  uVar14 = _DAT_034347ec;
  cVar9 = FUN_004739d0(_DAT_034347ec);
  uVar7 = _DAT_03434864;
  if (((cVar9 != '\0') ||
      (cVar9 = FUN_004739d0(_DAT_03434864), uVar8 = _DAT_03434914, uVar14 = uVar7, cVar9 != '\0'))
     || ((cVar9 = FUN_004739d0(_DAT_03434914), uVar7 = _DAT_03434924, uVar14 = uVar8, cVar9 != '\0'
         || (cVar9 = FUN_004739d0(_DAT_03434924), uVar14 = uVar7, cVar9 != '\0')))) {
    FUN_0049fec0(uVar14);
  }
  FUN_00760d60(_DAT_035f12cc + 0xdec68,*(undefined4 *)(_DAT_035f12cc + 0x462c68));
  _DAT_03a22828 = 0;
  _DAT_03a2282c = 0;
  return;
}

