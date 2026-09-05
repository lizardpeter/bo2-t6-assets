#include <cstddef>
#include <cstdint>
#include <cstdio>
#include "Game/T6/T6_Assets.h"

#define OFF(T, F) std::printf("\"%s\":%zu,", #F, offsetof(T, F))

int main() {
    std::printf("{");
    std::printf("\"ptrSize\":%zu,", sizeof(void*));

    std::printf("\"Material\":{\"size\":%zu,", sizeof(T6::Material));
    OFF(T6::Material, info);
    OFF(T6::Material, textureCount);
    OFF(T6::Material, techniqueSet);
    OFF(T6::Material, textureTable);
    std::printf("\"_end\":0},");

    std::printf("\"MaterialTextureDef\":{\"size\":%zu,", sizeof(T6::MaterialTextureDef));
    OFF(T6::MaterialTextureDef, nameHash);
    OFF(T6::MaterialTextureDef, nameStart);
    OFF(T6::MaterialTextureDef, nameEnd);
    OFF(T6::MaterialTextureDef, samplerState);
    OFF(T6::MaterialTextureDef, semantic);
    OFF(T6::MaterialTextureDef, isMatureContent);
    OFF(T6::MaterialTextureDef, image);
    std::printf("\"_end\":0},");

    std::printf("\"GfxImage\":{\"size\":%zu,", sizeof(T6::GfxImage));
    OFF(T6::GfxImage, mapType);
    OFF(T6::GfxImage, semantic);
    OFF(T6::GfxImage, category);
    OFF(T6::GfxImage, delayLoadPixels);
    OFF(T6::GfxImage, width);
    OFF(T6::GfxImage, height);
    OFF(T6::GfxImage, depth);
    OFF(T6::GfxImage, levelCount);
    OFF(T6::GfxImage, streaming);
    OFF(T6::GfxImage, baseSize);
    OFF(T6::GfxImage, pixels);
    OFF(T6::GfxImage, streamedParts);
    OFF(T6::GfxImage, streamedPartCount);
    OFF(T6::GfxImage, loadedSize);
    OFF(T6::GfxImage, skippedMipLevels);
    OFF(T6::GfxImage, name);
    OFF(T6::GfxImage, hash);
    std::printf("\"_end\":0},");

    std::printf("\"GfxStreamedPartInfo\":{\"size\":%zu,", sizeof(T6::GfxStreamedPartInfo));
    OFF(T6::GfxStreamedPartInfo, hash);
    OFF(T6::GfxStreamedPartInfo, width);
    OFF(T6::GfxStreamedPartInfo, height);
    std::printf("\"_end\":0}");

    std::printf("}\n");
    return 0;
}
