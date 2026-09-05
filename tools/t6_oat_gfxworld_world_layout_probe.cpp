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
    OFF(T6::GfxWorld, draw);
    OFF(T6::GfxWorld, dpvs);
    std::printf("\"_end\":0},");

    std::printf("\"GfxWorldDraw\":{\"size\":%zu,", sizeof(T6::GfxWorldDraw));
    OFF(T6::GfxWorldDraw, vertexCount);
    OFF(T6::GfxWorldDraw, vertexDataSize0);
    OFF(T6::GfxWorldDraw, vd0);
    OFF(T6::GfxWorldDraw, vertexDataSize1);
    OFF(T6::GfxWorldDraw, vd1);
    OFF(T6::GfxWorldDraw, indexCount);
    OFF(T6::GfxWorldDraw, indices);
    std::printf("\"_end\":0},");

    std::printf("\"GfxWorldVertexData0\":{\"size\":%zu,", sizeof(T6::GfxWorldVertexData0));
    OFF(T6::GfxWorldVertexData0, data);
    std::printf("\"_end\":0},");

    std::printf("\"GfxWorldVertexData1\":{\"size\":%zu,", sizeof(T6::GfxWorldVertexData1));
    OFF(T6::GfxWorldVertexData1, data);
    std::printf("\"_end\":0},");

    std::printf("\"GfxWorldDpvsStatic\":{\"size\":%zu,", sizeof(T6::GfxWorldDpvsStatic));
    OFF(T6::GfxWorldDpvsStatic, smodelCount);
    OFF(T6::GfxWorldDpvsStatic, surfaces);
    OFF(T6::GfxWorldDpvsStatic, smodelInsts);
    OFF(T6::GfxWorldDpvsStatic, smodelDrawInsts);
    std::printf("\"_end\":0},");

    std::printf("\"GfxSurface\":{\"size\":%zu,", sizeof(T6::GfxSurface));
    OFF(T6::GfxSurface, mins);
    OFF(T6::GfxSurface, vertexDataOffset0);
    OFF(T6::GfxSurface, maxs);
    OFF(T6::GfxSurface, vertexDataOffset1);
    OFF(T6::GfxSurface, firstVertex);
    OFF(T6::GfxSurface, himipRadiusInvSq);
    OFF(T6::GfxSurface, vertexCount);
    OFF(T6::GfxSurface, tris);
    OFF(T6::GfxSurface, material);
    std::printf("\"_end\":0},");

    std::printf("\"srfTriangles_t\":{\"size\":%zu,", sizeof(T6::srfTriangles_t));
    OFF(T6::srfTriangles_t, triCount);
    OFF(T6::srfTriangles_t, baseIndex);
    std::printf("\"_end\":0},");

    std::printf("\"Material\":{\"size\":%zu,", sizeof(T6::Material));
    OFF(T6::Material, info);
    OFF(T6::Material, techniqueSet);
    std::printf("\"_end\":0},");

    std::printf("\"MaterialInfo\":{\"size\":%zu,", sizeof(T6::MaterialInfo));
    OFF(T6::MaterialInfo, name);
    std::printf("\"_end\":0},");

    std::printf("\"MaterialTechniqueSet\":{\"size\":%zu,", sizeof(T6::MaterialTechniqueSet));
    OFF(T6::MaterialTechniqueSet, name);
    OFF(T6::MaterialTechniqueSet, worldVertFormat);
    std::printf("\"_end\":0}");

    std::printf("}\n");
    return 0;
}
