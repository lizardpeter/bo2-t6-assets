#include "ClipMapDumperT6.h"

#include "Utils/Logging/Log.h"

#include <cstdint>
#include <string>

using namespace T6;

namespace
{
    constexpr std::uint32_t FRC_VERSION = 1;

    std::string SafeName(std::string value)
    {
        if (value.empty())
            return "unnamed";

        for (auto& c : value)
        {
            switch (c)
            {
            case '/':
            case '\\':
            case ':':
            case '*':
            case '?':
            case '"':
            case '<':
            case '>':
            case '|':
                c = '_';
                break;
            default:
                break;
            }
        }
        return value;
    }

    void WriteU32(std::ostream& stream, const std::uint32_t value)
    {
        stream.write(reinterpret_cast<const char*>(&value), sizeof(value));
    }

    void WriteF32(std::ostream& stream, const float value)
    {
        stream.write(reinterpret_cast<const char*>(&value), sizeof(value));
    }

    void DumpClipMap(
        AssetDumpingContext& context,
        const clipMap_t* clip,
        const std::string& assetName,
        const char* assetKind)
    {
        if (!clip)
        {
            con::error("Cannot dump null T6 clipmap asset \"{}\"", assetName);
            return;
        }
        if (clip->vertCount == 0 || !clip->verts)
        {
            con::error("T6 clipmap \"{}\" has no vertices", assetName);
            return;
        }
        if (clip->triCount <= 0 || !clip->triIndices)
        {
            con::error("T6 clipmap \"{}\" has no triangle collision", assetName);
            return;
        }

        const auto triangleCount = static_cast<std::uint32_t>(clip->triCount);
        const auto edgeBitCount = static_cast<std::uint64_t>(triangleCount) * 3ull;
        // T6 stores triEdgeIsWalkable padded to a 4-byte boundary.
        const auto walkabilityByteCount = static_cast<std::uint32_t>(((edgeBitCount + 31ull) / 32ull) * 4ull);

        const auto outputName = std::string("clipmap/") + assetKind + "_" + SafeName(assetName) + ".frc";
        const auto outputFile = context.OpenAssetFile(outputName);
        if (!outputFile)
            return;

        auto& stream = *outputFile;
        stream.write("FRC1", 4);
        WriteU32(stream, FRC_VERSION);
        WriteU32(stream, clip->vertCount);
        WriteU32(stream, triangleCount);
        WriteU32(stream, walkabilityByteCount);

        // Preserve raw T6 coordinates in the archive: X/Y horizontal, Z up.
        // The consuming renderer/game performs its own coordinate conversion.
        for (std::uint32_t i = 0; i < clip->vertCount; ++i)
        {
            WriteF32(stream, clip->verts[i][0]);
            WriteF32(stream, clip->verts[i][1]);
            WriteF32(stream, clip->verts[i][2]);
        }

        // T6 uses uint16 triangle indices. FRC uses uint32 so consumers do not
        // depend on the original engine's index-width restriction.
        for (std::uint32_t i = 0; i < triangleCount; ++i)
        {
            WriteU32(stream, static_cast<std::uint32_t>(clip->triIndices[i][0]));
            WriteU32(stream, static_cast<std::uint32_t>(clip->triIndices[i][1]));
            WriteU32(stream, static_cast<std::uint32_t>(clip->triIndices[i][2]));
        }

        if (clip->triEdgeIsWalkable && walkabilityByteCount > 0)
        {
            stream.write(clip->triEdgeIsWalkable, walkabilityByteCount);
        }
        else
        {
            const char zero = 0;
            for (std::uint32_t i = 0; i < walkabilityByteCount; ++i)
                stream.write(&zero, 1);
        }

        con::info(
            "Dumped T6 {} \"{}\": {} vertices, {} triangles, {} walkability bytes -> {}",
            assetKind,
            assetName,
            clip->vertCount,
            triangleCount,
            walkabilityByteCount,
            outputName);
    }
} // namespace

namespace clip_map
{
    void DumperT6::DumpAsset(AssetDumpingContext& context, const XAssetInfo<AssetClipMap::Type>& asset)
    {
        DumpClipMap(context, asset.Asset(), asset.m_name, "clipmap_unused");
    }

    void PvsDumperT6::DumpAsset(AssetDumpingContext& context, const XAssetInfo<AssetClipMapPvs::Type>& asset)
    {
        DumpClipMap(context, asset.Asset(), asset.m_name, "clipmap");
    }
} // namespace clip_map
