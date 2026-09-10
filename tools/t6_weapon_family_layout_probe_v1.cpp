#include <cstddef>
#include <cstdint>
#include <cstdio>

#ifndef ARCH_x86
#error "This proof must be compiled for the T6 x86 ABI with ARCH_x86 defined"
#endif

#include "Common/Game/T6/T6_Assets.h"

#define ASSERT_SIZE(type, expected) static_assert(sizeof(T6::type) == expected, "unexpected sizeof(" #type ")")
#define ASSERT_OFF(type, field, expected) static_assert(offsetof(T6::type, field) == expected, "unexpected offsetof(" #type ", " #field ")")
#define SIZEOF_ROW(type) std::printf("SIZE\t%s\t%zu\n", #type, sizeof(T6::type))
#define OFF_ROW(type, field) std::printf("OFF\t%s\t%s\t%zu\n", #type, #field, offsetof(T6::type, field))

ASSERT_SIZE(WeaponAttachment, 284);
ASSERT_OFF(WeaponAttachment, szInternalName, 0);
ASSERT_OFF(WeaponAttachment, szDisplayName, 4);
ASSERT_OFF(WeaponAttachment, attachmentType, 8);
ASSERT_OFF(WeaponAttachment, attachmentPoint, 12);

ASSERT_SIZE(WeaponAttachmentUnique, 424);
ASSERT_OFF(WeaponAttachmentUnique, szInternalName, 0);
ASSERT_OFF(WeaponAttachmentUnique, attachmentType, 4);
ASSERT_OFF(WeaponAttachmentUnique, siblingLink, 8);
ASSERT_OFF(WeaponAttachmentUnique, childLink, 12);
ASSERT_OFF(WeaponAttachmentUnique, combinedAttachmentTypeMask, 16);
ASSERT_OFF(WeaponAttachmentUnique, szAltWeaponName, 20);
ASSERT_OFF(WeaponAttachmentUnique, altWeaponIndex, 24);
ASSERT_OFF(WeaponAttachmentUnique, szDualWieldWeaponName, 28);
ASSERT_OFF(WeaponAttachmentUnique, dualWieldWeaponIndex, 32);
ASSERT_OFF(WeaponAttachmentUnique, hideTags, 36);
ASSERT_OFF(WeaponAttachmentUnique, viewModelTag, 60);
ASSERT_OFF(WeaponAttachmentUnique, worldModelTag, 64);
ASSERT_OFF(WeaponAttachmentUnique, weaponCamo, 164);
ASSERT_OFF(WeaponAttachmentUnique, szXAnims, 232);
ASSERT_OFF(WeaponAttachmentUnique, locationDamageMultipliers, 248);
ASSERT_OFF(WeaponAttachmentUnique, fireSound, 256);
ASSERT_OFF(WeaponAttachmentUnique, fireSoundPlayer, 260);
ASSERT_OFF(WeaponAttachmentUnique, fireLoopSound, 264);
ASSERT_OFF(WeaponAttachmentUnique, fireLoopSoundPlayer, 268);
ASSERT_OFF(WeaponAttachmentUnique, fireLoopEndSound, 272);
ASSERT_OFF(WeaponAttachmentUnique, fireLoopEndSoundPlayer, 276);
ASSERT_OFF(WeaponAttachmentUnique, fireStartSound, 280);
ASSERT_OFF(WeaponAttachmentUnique, fireStopSound, 284);
ASSERT_OFF(WeaponAttachmentUnique, fireStartSoundPlayer, 288);
ASSERT_OFF(WeaponAttachmentUnique, fireStopSoundPlayer, 292);
ASSERT_OFF(WeaponAttachmentUnique, fireLastSound, 296);
ASSERT_OFF(WeaponAttachmentUnique, fireLastSoundPlayer, 300);
ASSERT_OFF(WeaponAttachmentUnique, fireKillcamSound, 304);
ASSERT_OFF(WeaponAttachmentUnique, fireKillcamSoundPlayer, 308);
ASSERT_OFF(WeaponAttachmentUnique, viewFlashEffect, 316);
ASSERT_OFF(WeaponAttachmentUnique, worldFlashEffect, 320);
ASSERT_OFF(WeaponAttachmentUnique, tracerType, 324);
ASSERT_OFF(WeaponAttachmentUnique, enemyTracerType, 328);

ASSERT_SIZE(WeaponCamo, 28);
ASSERT_OFF(WeaponCamo, name, 0);
ASSERT_OFF(WeaponCamo, solidBaseImage, 4);
ASSERT_OFF(WeaponCamo, patternBaseImage, 8);
ASSERT_OFF(WeaponCamo, camoSets, 12);
ASSERT_OFF(WeaponCamo, numCamoSets, 16);
ASSERT_OFF(WeaponCamo, camoMaterials, 20);
ASSERT_OFF(WeaponCamo, numCamoMaterials, 24);

ASSERT_SIZE(WeaponCamoSet, 20);
ASSERT_OFF(WeaponCamoSet, solidCamoImage, 0);
ASSERT_OFF(WeaponCamoSet, patternCamoImage, 4);
ASSERT_OFF(WeaponCamoSet, patternOffset, 8);
ASSERT_OFF(WeaponCamoSet, patternScale, 16);

ASSERT_SIZE(WeaponCamoMaterialSet, 8);
ASSERT_OFF(WeaponCamoMaterialSet, numMaterials, 0);
ASSERT_OFF(WeaponCamoMaterialSet, materials, 4);

ASSERT_SIZE(WeaponCamoMaterial, 44);
ASSERT_OFF(WeaponCamoMaterial, replaceFlags, 0);
ASSERT_OFF(WeaponCamoMaterial, numBaseMaterials, 2);
ASSERT_OFF(WeaponCamoMaterial, baseMaterials, 4);
ASSERT_OFF(WeaponCamoMaterial, camoMaterials, 8);
ASSERT_OFF(WeaponCamoMaterial, shaderConsts, 12);

int main()
{
    SIZEOF_ROW(WeaponAttachment);
    OFF_ROW(WeaponAttachment, szInternalName);
    OFF_ROW(WeaponAttachment, szDisplayName);
    OFF_ROW(WeaponAttachment, attachmentType);
    OFF_ROW(WeaponAttachment, attachmentPoint);

    SIZEOF_ROW(WeaponAttachmentUnique);
    OFF_ROW(WeaponAttachmentUnique, szInternalName);
    OFF_ROW(WeaponAttachmentUnique, attachmentType);
    OFF_ROW(WeaponAttachmentUnique, siblingLink);
    OFF_ROW(WeaponAttachmentUnique, childLink);
    OFF_ROW(WeaponAttachmentUnique, combinedAttachmentTypeMask);
    OFF_ROW(WeaponAttachmentUnique, szAltWeaponName);
    OFF_ROW(WeaponAttachmentUnique, altWeaponIndex);
    OFF_ROW(WeaponAttachmentUnique, szDualWieldWeaponName);
    OFF_ROW(WeaponAttachmentUnique, dualWieldWeaponIndex);
    OFF_ROW(WeaponAttachmentUnique, hideTags);
    OFF_ROW(WeaponAttachmentUnique, viewModelTag);
    OFF_ROW(WeaponAttachmentUnique, worldModelTag);
    OFF_ROW(WeaponAttachmentUnique, weaponCamo);
    OFF_ROW(WeaponAttachmentUnique, szXAnims);
    OFF_ROW(WeaponAttachmentUnique, locationDamageMultipliers);
    OFF_ROW(WeaponAttachmentUnique, fireSound);
    OFF_ROW(WeaponAttachmentUnique, fireSoundPlayer);
    OFF_ROW(WeaponAttachmentUnique, fireLoopSound);
    OFF_ROW(WeaponAttachmentUnique, fireLoopSoundPlayer);
    OFF_ROW(WeaponAttachmentUnique, fireLoopEndSound);
    OFF_ROW(WeaponAttachmentUnique, fireLoopEndSoundPlayer);
    OFF_ROW(WeaponAttachmentUnique, fireStartSound);
    OFF_ROW(WeaponAttachmentUnique, fireStopSound);
    OFF_ROW(WeaponAttachmentUnique, fireStartSoundPlayer);
    OFF_ROW(WeaponAttachmentUnique, fireStopSoundPlayer);
    OFF_ROW(WeaponAttachmentUnique, fireLastSound);
    OFF_ROW(WeaponAttachmentUnique, fireLastSoundPlayer);
    OFF_ROW(WeaponAttachmentUnique, fireKillcamSound);
    OFF_ROW(WeaponAttachmentUnique, fireKillcamSoundPlayer);
    OFF_ROW(WeaponAttachmentUnique, viewFlashEffect);
    OFF_ROW(WeaponAttachmentUnique, worldFlashEffect);
    OFF_ROW(WeaponAttachmentUnique, tracerType);
    OFF_ROW(WeaponAttachmentUnique, enemyTracerType);

    SIZEOF_ROW(WeaponCamo);
    OFF_ROW(WeaponCamo, name);
    OFF_ROW(WeaponCamo, solidBaseImage);
    OFF_ROW(WeaponCamo, patternBaseImage);
    OFF_ROW(WeaponCamo, camoSets);
    OFF_ROW(WeaponCamo, numCamoSets);
    OFF_ROW(WeaponCamo, camoMaterials);
    OFF_ROW(WeaponCamo, numCamoMaterials);

    SIZEOF_ROW(WeaponCamoSet);
    OFF_ROW(WeaponCamoSet, solidCamoImage);
    OFF_ROW(WeaponCamoSet, patternCamoImage);
    OFF_ROW(WeaponCamoSet, patternOffset);
    OFF_ROW(WeaponCamoSet, patternScale);

    SIZEOF_ROW(WeaponCamoMaterialSet);
    OFF_ROW(WeaponCamoMaterialSet, numMaterials);
    OFF_ROW(WeaponCamoMaterialSet, materials);

    SIZEOF_ROW(WeaponCamoMaterial);
    OFF_ROW(WeaponCamoMaterial, replaceFlags);
    OFF_ROW(WeaponCamoMaterial, numBaseMaterials);
    OFF_ROW(WeaponCamoMaterial, baseMaterials);
    OFF_ROW(WeaponCamoMaterial, camoMaterials);
    OFF_ROW(WeaponCamoMaterial, shaderConsts);

    return 0;
}
