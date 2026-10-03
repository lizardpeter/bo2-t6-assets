
bool __cdecl Material_StreamSourceForName(char **param_1,char *param_2,uchar *param_3)

{
  byte bVar1;
  byte *pbVar2;
  int iVar3;
  char *pcVar4;
  int *unaff_EBX;
  int unaff_ESI;
  byte *unaff_EDI;
  bool bVar5;
  char *pcStack_8;
  
  pcVar4 = "position";
  pbVar2 = unaff_EDI;
  do {
    bVar1 = *pbVar2;
    bVar5 = bVar1 < (byte)*pcVar4;
    if (bVar1 != *pcVar4) {
LAB_00a47fe2:
      iVar3 = (1 - (uint)bVar5) - (uint)(bVar5 != 0);
      goto LAB_00a47fe7;
    }
    if (bVar1 == 0) break;
    bVar1 = pbVar2[1];
    bVar5 = bVar1 < (byte)pcVar4[1];
    if (bVar1 != pcVar4[1]) goto LAB_00a47fe2;
    pbVar2 = pbVar2 + 2;
    pcVar4 = pcVar4 + 2;
  } while (bVar1 != 0);
  iVar3 = 0;
LAB_00a47fe7:
  if (iVar3 == 0) {
    *(undefined1 *)param_1 = 0;
    return true;
  }
  pcVar4 = "normal";
  pbVar2 = unaff_EDI;
  do {
    bVar1 = *pbVar2;
    bVar5 = bVar1 < (byte)*pcVar4;
    if (bVar1 != *pcVar4) {
LAB_00a48020:
      iVar3 = (1 - (uint)bVar5) - (uint)(bVar5 != 0);
      goto LAB_00a48025;
    }
    if (bVar1 == 0) break;
    bVar1 = pbVar2[1];
    bVar5 = bVar1 < (byte)pcVar4[1];
    if (bVar1 != pcVar4[1]) goto LAB_00a48020;
    pbVar2 = pbVar2 + 2;
    pcVar4 = pcVar4 + 2;
  } while (bVar1 != 0);
  iVar3 = 0;
LAB_00a48025:
  if (iVar3 == 0) {
    *(undefined1 *)param_1 = 3;
    return true;
  }
  pcVar4 = "tangent";
  pbVar2 = unaff_EDI;
  do {
    bVar1 = *pbVar2;
    bVar5 = bVar1 < (byte)*pcVar4;
    if (bVar1 != *pcVar4) {
LAB_00a48060:
      iVar3 = (1 - (uint)bVar5) - (uint)(bVar5 != 0);
      goto LAB_00a48065;
    }
    if (bVar1 == 0) break;
    bVar1 = pbVar2[1];
    bVar5 = bVar1 < (byte)pcVar4[1];
    if (bVar1 != pcVar4[1]) goto LAB_00a48060;
    pbVar2 = pbVar2 + 2;
    pcVar4 = pcVar4 + 2;
  } while (bVar1 != 0);
  iVar3 = 0;
LAB_00a48065:
  if (iVar3 == 0) {
    *(undefined1 *)param_1 = 4;
    return true;
  }
  pcVar4 = "color";
  pbVar2 = unaff_EDI;
  do {
    bVar1 = *pbVar2;
    bVar5 = bVar1 < (byte)*pcVar4;
    if (bVar1 != *pcVar4) {
LAB_00a480a0:
      iVar3 = (1 - (uint)bVar5) - (uint)(bVar5 != 0);
      goto LAB_00a480a5;
    }
    if (bVar1 == 0) break;
    bVar1 = pbVar2[1];
    bVar5 = bVar1 < (byte)pcVar4[1];
    if (bVar1 != pcVar4[1]) goto LAB_00a480a0;
    pbVar2 = pbVar2 + 2;
    pcVar4 = pcVar4 + 2;
  } while (bVar1 != 0);
  iVar3 = 0;
LAB_00a480a5:
  if (iVar3 == 0) {
    *(undefined1 *)param_1 = 1;
    return true;
  }
  pcVar4 = "texcoord";
  pbVar2 = unaff_EDI;
  do {
    bVar1 = *pbVar2;
    bVar5 = bVar1 < (byte)*pcVar4;
    if (bVar1 != *pcVar4) {
LAB_00a480e0:
      iVar3 = (1 - (uint)bVar5) - (uint)(bVar5 != 0);
      goto LAB_00a480e5;
    }
    if (bVar1 == 0) break;
    bVar1 = pbVar2[1];
    bVar5 = bVar1 < (byte)pcVar4[1];
    if (bVar1 != pcVar4[1]) goto LAB_00a480e0;
    pbVar2 = pbVar2 + 2;
    pcVar4 = pcVar4 + 2;
  } while (bVar1 != 0);
  iVar3 = 0;
LAB_00a480e5:
  if (iVar3 == 0) {
    bVar5 = Material_ParseIndex(&pcStack_8,unaff_ESI,unaff_EBX);
    if (bVar5) {
      if (pcStack_8 == (char *)0x0) {
        *(undefined1 *)param_1 = 2;
        return true;
      }
      *(char *)param_1 = (char)pcStack_8 + '\x04';
      return true;
    }
  }
  else {
    pcVar4 = "normalTransform";
    pbVar2 = unaff_EDI;
    do {
      bVar1 = *pbVar2;
      bVar5 = bVar1 < (byte)*pcVar4;
      if (bVar1 != *pcVar4) {
LAB_00a48147:
        iVar3 = (1 - (uint)bVar5) - (uint)(bVar5 != 0);
        goto LAB_00a4814c;
      }
      if (bVar1 == 0) break;
      bVar1 = pbVar2[1];
      bVar5 = bVar1 < (byte)pcVar4[1];
      if (bVar1 != pcVar4[1]) goto LAB_00a48147;
      pbVar2 = pbVar2 + 2;
      pcVar4 = pcVar4 + 2;
    } while (bVar1 != 0);
    iVar3 = 0;
LAB_00a4814c:
    if (iVar3 == 0) {
      bVar5 = Material_ParseIndex(&pcStack_8,unaff_ESI,unaff_EBX);
      if (bVar5) {
        *(char *)param_1 = (char)pcStack_8 + '\b';
        return true;
      }
    }
    else {
      pcVar4 = "blendweight";
      do {
        bVar1 = *unaff_EDI;
        bVar5 = bVar1 < (byte)*pcVar4;
        if (bVar1 != *pcVar4) {
LAB_00a481a0:
          iVar3 = (1 - (uint)bVar5) - (uint)(bVar5 != 0);
          goto LAB_00a481a5;
        }
        if (bVar1 == 0) break;
        bVar1 = unaff_EDI[1];
        bVar5 = bVar1 < (byte)pcVar4[1];
        if (bVar1 != pcVar4[1]) goto LAB_00a481a0;
        unaff_EDI = unaff_EDI + 2;
        pcVar4 = pcVar4 + 2;
      } while (bVar1 != 0);
      iVar3 = 0;
LAB_00a481a5:
      if (iVar3 == 0) {
        *(undefined1 *)param_1 = 10;
        return true;
      }
      Com_ScriptError("unknown stream source \'%s\'\n");
    }
  }
  return false;
}

