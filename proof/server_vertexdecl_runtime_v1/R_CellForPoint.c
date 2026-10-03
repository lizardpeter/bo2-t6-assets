
int __cdecl R_CellForPoint(vec3_t *param_1)

{
  cplane_s *pcVar1;
  code *pcVar2;
  bool bVar3;
  int iVar4;
  ushort *puVar5;
  int iVar6;
  uint uVar7;
  
  if ((rgp.world == (GfxWorld *)0x0) &&
     (bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_dpvs.cpp",0x3ca,0,"(rgp.world)",""),
     !bVar3)) {
    pcVar2 = (code *)swi(3);
    iVar4 = (*pcVar2)();
    return iVar4;
  }
  puVar5 = ((rgp.world)->dpvsPlanes).nodes;
  uVar7 = (uint)*puVar5;
  pcVar1 = ((rgp.world)->dpvsPlanes).planes;
  iVar6 = ((rgp.world)->dpvsPlanes).cellCount + 1;
  iVar4 = uVar7 - iVar6;
  if (-1 < iVar4) {
    do {
      puVar5 = puVar5 + (puVar5[1] - 2) *
                        (uint)((pcVar1[iVar4].normal._s_0.y * (param_1->_s_0).y +
                                pcVar1[iVar4].normal._s_0.x * (param_1->_s_0).x +
                               pcVar1[iVar4].normal._s_0.z * (param_1->_s_0).z) - pcVar1[iVar4].dist
                              <= 0.0) + 2;
      uVar7 = (uint)*puVar5;
      iVar4 = uVar7 - iVar6;
    } while (-1 < iVar4);
  }
  return uVar7 - 1;
}

