#include <cstddef>
#include <cstdio>

#include "Common/Game/T6/T6_Assets.h"

#define SIZEOF_ROW(type) std::printf("SIZE\t%s\t%zu\n", #type, sizeof(T6::type))
#define OFF_ROW(type, field) std::printf("OFF\t%s\t%s\t%zu\n", #type, #field, offsetof(T6::type, field))

int main()
{
    SIZEOF_ROW(WeaponAttachment);
    OFF_ROW(WeaponAttachment, szInternalName);
    OFF_ROW(WeaponAttachment, szDisplayName);
    OFF_ROW(WeaponAttachment, attachmentType);
    OFF_ROW(WeaponAttachment, siblingLink);

    SIZEOF_ROW(WeaponAttachmentUnique);
    OFF_ROW(WeaponAttachmentUnique, szInternalName);
    OFF_ROW(WeaponAttachmentUnique, combinedAttachmentTypeMask);
    OFF_ROW(WeaponAttachmentUnique, szAltWeaponName);
    OFF_ROW(WeaponAttachmentUnique, altWeaponIndex);
    OFF_ROW(WeaponAttachmentUnique, szDualWieldWeaponName);
    OFF_ROW(WeaponAttachmentUnique, dualWieldWeaponIndex);
    OFF_ROW(WeaponAttachmentUnique, viewModelTag);
    OFF_ROW(WeaponAttachmentUnique, worldModelTag);
    OFF_ROW(WeaponAttachmentUnique, szXAnims);
    OFF_ROW(WeaponAttachmentUnique, hideTags);
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

    SIZEOF_ROW(WeaponCamo);
    OFF_ROW(WeaponCamo, name);
    OFF_ROW(WeaponCamo, solidBaseImage);
    OFF_ROW(WeaponCamo, patternBaseImage);
    OFF_ROW(WeaponCamo, camoSets);
    OFF_ROW(WeaponCamo, numCamoSets);
    OFF_ROW(WeaponCamo, camoMaterials);
    OFF_ROW(WeaponCamo, numCamoMaterials);

    SIZEOF_ROW(WeaponCamoMaterialSet);
    OFF_ROW(WeaponCamoMaterialSet, materials);
    OFF_ROW(WeaponCamoMaterialSet, numMaterials);

    SIZEOF_ROW(WeaponCamoMaterial);
    OFF_ROW(WeaponCamoMaterial, baseMaterials);
    OFF_ROW(WeaponCamoMaterial, camoMaterials);
    OFF_ROW(WeaponCamoMaterial, numBaseMaterials);

    return 0;
}
