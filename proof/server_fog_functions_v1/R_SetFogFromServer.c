
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsStage": Some values do not have unique names */
/* WARNING: Enum "GfxPrimStatsTarget": Some values do not have unique names */

void __cdecl
R_SetFogFromServer(LocalClientNum_t param_1,float param_2,float param_3,float param_4,float param_5,
                  float param_6,float param_7,float param_8,float param_9,float param_10,
                  float param_11,float param_12,float param_13,float param_14,float param_15,
                  float param_16,float param_17,float param_18)

{
  code *pcVar1;
  bool bVar2;
  float fVar3;
  
  if (3 < param_1) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\gfx_d3d\\r_fog.cpp",0x20,0,
                             "(unsigned)(localClientNum) < (unsigned)((sizeof( rg.clientFogs ) / (sizeof( rg.clientFogs[0] ) * (sizeof( rg.clientFogs ) != 4 || sizeof( rg.clientFogs[0] ) <= 4))))"
                             ,
                             "localClientNum doesn\'t index ARRAY_COUNT(rg.clientFogs)\n\t%i not in [0, %i)"
                            );
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  rg.clientFogs[param_1].settings[1].baseHeight = param_8;
  rg.clientFogs[param_1].settings[1].fogStart = param_2;
  rg.clientFogs[param_1].settings[1].heightDensity = param_7;
  rg.clientFogs[param_1].settings[1].density = param_6;
  rg.clientFogs[param_1].settings[1].color.v[0] = param_3;
  rg.clientFogs[param_1].settings[1].color.v[1] = param_4;
  fVar3 = param_6 * ___real_42c80000;
  rg.clientFogs[param_1].settings[1].color.v[2] = param_5;
  rg.clientFogs[param_1].settings[1].color.v[3] = param_9;
  rg.clientFogs[param_1].settings[1].sunFogColor.v[0] = param_10;
  rg.clientFogs[param_1].settings[1].sunFogColor.v[1] = param_11;
  rg.clientFogs[param_1].settings[1].sunFogColor.v[2] = param_12;
  rg.clientFogs[param_1].settings[1].sunFogColor.v[3] = param_18;
  rg.clientFogs[param_1].settings[1].sunFogDir._s_0.x = param_13;
  rg.clientFogs[param_1].settings[1].sunFogDir._s_0.y = param_14;
  rg.clientFogs[param_1].settings[1].sunFogDir._s_0.z = param_15;
  rg.clientFogs[param_1].settings[1].sunFogEndAng = param_17;
  rg.clientFogs[param_1].settings[1].sunFogStartAng = param_16;
  rg.clientFogs[param_1].settings[1].maxDensity = fVar3;
  return;
}

