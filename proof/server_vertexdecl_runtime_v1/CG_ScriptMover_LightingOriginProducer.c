
/* WARNING: Enum "ClientNum_t": Some values do not have unique names */
/* WARNING: Enum "team_t": Some values do not have unique names */
/* WARNING: Enum "nodeType": Some values do not have unique names */
/* WARNING: Enum "AISpecies": Some values do not have unique names */
/* WARNING: Enum "ai_state_t": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */
/* WARNING: Enum "eAttachment": Some values do not have unique names */

void __cdecl CG_GetLightingOrigin(DObj *param_1,centity_t *param_2,vec3_t *param_3)

{
  code *pcVar1;
  float fVar2;
  bool bVar3;
  int unaff_ESI;
  float *unaff_EDI;
  
  if ((*(byte *)(unaff_ESI + 0x37c) & 0x80) != 0) {
    *unaff_EDI = *(float *)(unaff_ESI + 0x2c);
    unaff_EDI[1] = *(float *)(unaff_ESI + 0x30);
    unaff_EDI[2] = *(float *)(unaff_ESI + 0x34);
    return;
  }
  if (param_1 == (DObj *)0x0) {
    bVar3 = Assert_MyHandler("c:\\t6\\code\\src\\cgame_mp\\cg_ents_mp.cpp",0x7b,0,"(obj)","");
    if (!bVar3) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  fVar2 = __real_3f000000;
  *unaff_EDI = (*(float *)(unaff_ESI + 0x44) + *(float *)(unaff_ESI + 0x50)) * __real_3f000000;
  unaff_EDI[1] = (*(float *)(unaff_ESI + 0x48) + *(float *)(unaff_ESI + 0x54)) * fVar2;
  unaff_EDI[2] = (*(float *)(unaff_ESI + 0x4c) + *(float *)(unaff_ESI + 0x58)) * fVar2;
  return;
}

