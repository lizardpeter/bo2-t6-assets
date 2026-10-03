
/* WARNING: Enum "ClientNum_t": Some values do not have unique names */
/* WARNING: Enum "team_t": Some values do not have unique names */
/* WARNING: Enum "nodeType": Some values do not have unique names */
/* WARNING: Enum "AISpecies": Some values do not have unique names */
/* WARNING: Enum "ai_state_t": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

void __cdecl SV_DObjGetBounds(gentity_t *param_1,vec3_t *param_2,vec3_t *param_3)

{
  code *pcVar1;
  bool bVar2;
  DObj *pDVar3;
  
  pDVar3 = Com_GetServerDObj((param_1->s).number);
  if (pDVar3 == (DObj *)0x0) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\server\\sv_game.cpp",0x325,0,"(obj)","");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  DObjGetBounds(pDVar3,param_2,param_3);
  return;
}

