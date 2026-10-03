
/* WARNING: Enum "ClientNum_t": Some values do not have unique names */
/* WARNING: Enum "team_t": Some values do not have unique names */
/* WARNING: Enum "nodeType": Some values do not have unique names */
/* WARNING: Enum "AISpecies": Some values do not have unique names */
/* WARNING: Enum "ai_state_t": Some values do not have unique names */
/* WARNING: Enum "LocalClientNum_t": Some values do not have unique names */

int __cdecl TransferRandomAmmoToWeaponEntity(gentity_t *param_1,Weapon param_2)

{
  code *pcVar1;
  bool bVar2;
  int in_EAX;
  WeaponDef *pWVar3;
  WeaponDef *pWVar4;
  int iVar5;
  uint uVar6;
  uint uVar7;
  int iVar8;
  int iVar9;
  int iStack_18;
  int *piStack_10;
  int iStack_c;
  Weapon WStack_8;
  
  iVar8 = 0;
  piStack_10 = (int *)(in_EAX + 0x230);
  iStack_c = 0;
  WStack_8 = (Weapon)param_1;
  iStack_18 = 0;
  do {
    if ((byte)param_1 != 0) {
      pWVar3 = BG_GetWeaponDef((Weapon)param_1);
      if ((-1 < pWVar3->iSharedAmmoCapIndex) && (iStack_18 != 0)) {
        return iVar8;
      }
      pWVar4 = BG_GetWeaponDef((Weapon)param_1);
      if (pWVar4->ammoCountClipRelative == false) {
        iVar8 = pWVar4->iDropAmmoMax;
      }
      else {
        iVar8 = BG_GetClipSize((Weapon)param_1);
        iVar8 = iVar8 * pWVar4->iDropAmmoMax;
      }
      pWVar4 = BG_GetWeaponDef((Weapon)param_1);
      if (pWVar4->ammoCountClipRelative == false) {
        iVar5 = pWVar4->iDropAmmoMin;
      }
      else {
        iVar5 = BG_GetClipSize(WStack_8);
        iVar5 = iVar5 * (pWVar4->iDropAmmoMin + -1) + 1;
      }
      if (iVar8 < iVar5) {
        pWVar4 = BG_GetWeaponDef(WStack_8);
        iVar8 = iVar5;
        if (pWVar4->ammoCountClipRelative == false) {
          iVar5 = pWVar4->iDropAmmoMax;
        }
        else {
          iVar5 = BG_GetClipSize(WStack_8);
          iVar5 = iVar5 * pWVar4->iDropAmmoMax;
        }
      }
      if (iVar8 < 0) {
        iVar9 = 0;
        iVar8 = 0;
      }
      else {
        if ((iVar8 < iVar5) &&
           (bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\game\\g_items.cpp",0x46d,0,"(iMax >= iMin)"
                                     ,""), !bVar2)) {
          pcVar1 = (code *)swi(3);
          iVar8 = (*pcVar1)();
          return iVar8;
        }
        iVar9 = G_rand();
        iVar5 = iVar5 + iVar9 % ((iVar8 - iVar5) + 1);
        if (iVar5 < 1) {
          iVar9 = 0;
          iVar8 = 0;
        }
        else {
          uVar6 = BG_GetClipSize(WStack_8);
          if (((int)uVar6 < 0) &&
             (bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\game\\g_items.cpp",0x478,0,
                                       "(clipSize >= 0)",""), !bVar2)) {
            pcVar1 = (code *)swi(3);
            iVar8 = (*pcVar1)();
            return iVar8;
          }
          if (uVar6 == 1) {
            iVar8 = 1;
          }
          else {
            uVar7 = pWVar3->iDropClipAmmoMin;
            if ((int)uVar6 <= pWVar3->iDropClipAmmoMin) {
              uVar7 = uVar6;
            }
            uVar7 = ((int)uVar7 < 1) - 1 & uVar7;
            if (pWVar3->iDropClipAmmoMax < (int)uVar6) {
              uVar6 = pWVar3->iDropClipAmmoMax;
            }
            iVar8 = G_rand();
            iVar8 = iVar8 % (int)(((uVar6 & ((int)uVar6 < 1) - 1) - uVar7) + 1) + uVar7;
          }
          if (iVar8 < iVar5) {
            iVar9 = iVar5 - iVar8;
          }
          else {
            iVar9 = 0;
            iVar8 = iVar5;
          }
        }
      }
      *(Weapon *)(piStack_10 + 1) = WStack_8;
      piStack_10[-1] = iVar9;
      *piStack_10 = iVar8;
      bVar2 = BG_IsDualWield(WStack_8);
      if (bVar2) {
        param_1 = (gentity_t *)BG_GetDualWieldWeapon(WStack_8);
      }
      else {
        param_1 = (gentity_t *)BG_GetAltWeapon(WStack_8);
      }
      iVar8 = iStack_c + piStack_10[-1] + *piStack_10;
      iStack_c = iVar8;
      WStack_8 = (Weapon)param_1;
    }
    piStack_10 = piStack_10 + 3;
    iStack_18 = iStack_18 + 1;
    if (1 < iStack_18) {
      return iVar8;
    }
  } while( true );
}

