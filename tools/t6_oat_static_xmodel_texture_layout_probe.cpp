#include <cstddef>
#include <cstdint>
#include <cstdio>
#include "Game/T6/T6_Assets.h"
#define OFF(T, F) std::printf("\"%s\":%zu,", #F, offsetof(T, F))
int main() {
    std::printf("{");
    std::printf("\"ptrSize\":%zu,", sizeof(void*));
    std::printf("\"GfxStaticModelDrawInst\":{\"size\":%zu,", sizeof(T6::GfxStaticModelDrawInst));
    OFF(T6::GfxStaticModelDrawInst, model); std::printf("\"_end\":0},");
    std::printf("\"XModel\":{\"size\":%zu,", sizeof(T6::XModel));
    OFF(T6::XModel, name); OFF(T6::XModel, numsurfs); OFF(T6::XModel, materialHandles); std::printf("\"_end\":0}");
    std::printf("}\n");
    return 0;
}
