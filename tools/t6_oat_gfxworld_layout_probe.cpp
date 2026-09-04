#include <cstddef>
#include <cstdint>
#include <cstdio>
#include "Game/T6/T6_Assets.h"

#define OFF(T, F) std::printf("\"%s\":%zu,", #F, offsetof(T, F))
int main() {
    std::printf("{");
    std::printf("\"ptrSize\":%zu,", sizeof(void*));
    std::printf("\"GfxWorld\":{\"size\":%zu,", sizeof(T6::GfxWorld));
    OFF(T6::GfxWorld, name); OFF(T6::GfxWorld, surfaceCount); OFF(T6::GfxWorld, dpvs);
    std::printf("\"_end\":0},");
    std::printf("\"GfxWorldDpvsStatic\":{\"size\":%zu,", sizeof(T6::GfxWorldDpvsStatic));
    OFF(T6::GfxWorldDpvsStatic, smodelCount); OFF(T6::GfxWorldDpvsStatic, smodelInsts); OFF(T6::GfxWorldDpvsStatic, smodelDrawInsts);
    std::printf("\"_end\":0},");
    std::printf("\"GfxStaticModelInst\":{\"size\":%zu,", sizeof(T6::GfxStaticModelInst));
    OFF(T6::GfxStaticModelInst, mins); OFF(T6::GfxStaticModelInst, maxs); OFF(T6::GfxStaticModelInst, lightingOrigin);
    std::printf("\"_end\":0},");
    std::printf("\"GfxStaticModelDrawInst\":{\"size\":%zu,", sizeof(T6::GfxStaticModelDrawInst));
    OFF(T6::GfxStaticModelDrawInst, cullDist); OFF(T6::GfxStaticModelDrawInst, placement); OFF(T6::GfxStaticModelDrawInst, model); OFF(T6::GfxStaticModelDrawInst, flags); OFF(T6::GfxStaticModelDrawInst, lightingHandle); OFF(T6::GfxStaticModelDrawInst, colorsIndex); OFF(T6::GfxStaticModelDrawInst, primaryLightIndex); OFF(T6::GfxStaticModelDrawInst, visibility); OFF(T6::GfxStaticModelDrawInst, reflectionProbeIndex); OFF(T6::GfxStaticModelDrawInst, smid);
    std::printf("\"_end\":0},");
    std::printf("\"GfxPackedPlacement\":{\"size\":%zu,", sizeof(T6::GfxPackedPlacement));
    OFF(T6::GfxPackedPlacement, origin); OFF(T6::GfxPackedPlacement, axis); OFF(T6::GfxPackedPlacement, scale);
    std::printf("\"_end\":0},");
    std::printf("\"XModel\":{\"size\":%zu,", sizeof(T6::XModel)); OFF(T6::XModel, name); std::printf("\"_end\":0}");
    std::printf("}\n");
    return 0;
}
