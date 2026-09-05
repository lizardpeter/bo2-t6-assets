#include <cstddef>
#include <cstdint>
#include <cstdio>
#include "Game/T6/T6_Assets.h"

#define OFF(T, F) std::printf("\"%s\":%zu,", #F, offsetof(T, F))

int main() {
    std::printf("{");
    std::printf("\"ptrSize\":%zu,", sizeof(void*));

    std::printf("\"GfxWorld\":{\"size\":%zu,", sizeof(T6::GfxWorld));
    OFF(T6::GfxWorld, name);
    OFF(T6::GfxWorld, surfaceCount);
    OFF(T6::GfxWorld, dpvs);
    std::printf("\"_end\":0},");

    std::printf("\"GfxWorldDpvsStatic\":{\"size\":%zu,", sizeof(T6::GfxWorldDpvsStatic));
    OFF(T6::GfxWorldDpvsStatic, smodelCount);
    OFF(T6::GfxWorldDpvsStatic, surfaces);
    OFF(T6::GfxWorldDpvsStatic, smodelDrawInsts);
    std::printf("\"_end\":0},");

    std::printf("\"GfxSurface\":{\"size\":%zu,", sizeof(T6::GfxSurface));
    OFF(T6::GfxSurface, material);
    std::printf("\"_end\":0},");

    std::printf("\"GfxStaticModelDrawInst\":{\"size\":%zu,", sizeof(T6::GfxStaticModelDrawInst));
    OFF(T6::GfxStaticModelDrawInst, model);
    std::printf("\"_end\":0},");

    std::printf("\"XModel\":{\"size\":%zu,", sizeof(T6::XModel));
    OFF(T6::XModel, name);
    OFF(T6::XModel, numsurfs);
    OFF(T6::XModel, materialHandles);
    OFF(T6::XModel, lodInfo);
    std::printf("\"_end\":0},");

    std::printf("\"XModelLodInfo\":{\"size\":%zu,", sizeof(T6::XModelLodInfo));
    OFF(T6::XModelLodInfo, numsurfs);
    OFF(T6::XModelLodInfo, surfIndex);
    std::printf("\"_end\":0},");

    std::printf("\"MaterialInfo\":{\"size\":%zu,", sizeof(T6::MaterialInfo));
    OFF(T6::MaterialInfo, name);
    std::printf("\"_end\":0}");

    std::printf("}\n");
    return 0;
}
