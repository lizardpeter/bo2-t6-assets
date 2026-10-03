
uint __cdecl R_CalcReflectionProbeIndex(vec3_t *param_1)

{
  code *pcVar1;
  bool bVar2;
  uint uVar3;
  vec3_t *unaff_EDI;
  int iVar4;
  char *pcVar5;
  char *pcVar6;
  
  uVar3 = R_FindProbeFromVolume((GfxWorldDraw *)&param_1->_s_0,unaff_EDI);
  if (uVar3 == 0) {
    iVar4 = R_CellForPoint(param_1);
    if (iVar4 == -1) {
      uVar3 = R_FindNearestReflectionProbe((GfxWorldDraw *)&param_1->_s_0,unaff_EDI);
    }
    else {
      uVar3 = R_FindNearestReflectionProbeInCell(iVar4,param_1);
    }
    if (uVar3 < 0x20) {
      return uVar3;
    }
    pcVar6 = "probeIndex doesn\'t index 1 << MTL_SORT_ENVMAP_BITS\n\t%i not in [0, %i)";
    pcVar5 = "(unsigned)(probeIndex) < (unsigned)(1 << 5)";
    iVar4 = 0x534;
  }
  else {
    if (uVar3 < 0x20) {
      return uVar3;
    }
    pcVar6 = "bestProbe doesn\'t index 1 << MTL_SORT_ENVMAP_BITS\n\t%i not in [0, %i)";
    pcVar5 = "(unsigned)(bestProbe) < (unsigned)(1 << 5)";
    iVar4 = 0x519;
  }
  bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",iVar4,0,pcVar5,pcVar6);
  if (bVar2) {
    return uVar3;
  }
  pcVar1 = (code *)swi(3);
  uVar3 = (*pcVar1)();
  return uVar3;
}

