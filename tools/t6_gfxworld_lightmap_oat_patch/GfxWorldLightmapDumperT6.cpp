#include "GfxWorldLightmapDumperT6.h"

#include "Utils/Logging/Log.h"

#include <iomanip>
#include <sstream>
#include <string>

using namespace T6;

namespace
{
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

    std::string JsonString(const char* value)
    {
        std::ostringstream out;
        out << std::quoted(value ? value : "");
        return out.str();
    }
} // namespace

namespace gfx_world_lightmap
{
    void DumperT6::DumpAsset(
        AssetDumpingContext& context,
        const XAssetInfo<T6::AssetGfxWorld::Type>& asset)
    {
        const auto* world = asset.Asset();
        if (!world)
        {
            con::error("Cannot dump null T6 GfxWorld asset \"{}\"", asset.m_name);
            return;
        }
        if (world->lightmapCount < 0)
        {
            con::error(
                "T6 GfxWorld \"{}\" has invalid negative lightmapCount {}",
                asset.m_name,
                world->lightmapCount);
            return;
        }
        if (world->lightmapCount > 0 && !world->lightmaps)
        {
            con::error(
                "T6 GfxWorld \"{}\" has lightmapCount {} but null lightmaps",
                asset.m_name,
                world->lightmapCount);
            return;
        }

        const auto outputName =
            std::string("gfxworld_lightmaps/") + SafeName(asset.m_name) + ".json";
        const auto outputFile = context.OpenAssetFile(outputName);
        if (!outputFile)
            return;

        auto& out = *outputFile;
        out << "{\n";
        out << "  \"format\": \"t6-gfxworld-lightmap-catalog-v1\",\n";
        out << "  \"map\": " << JsonString(asset.m_name.c_str()) << ",\n";
        out << "  \"source\": {\n";
        out << "    \"kind\": \"OpenAssetTools loaded T6::GfxWorld\",\n";
        out << "    \"assetName\": " << JsonString(asset.m_name.c_str()) << ",\n";
        out << "    \"policy\": \"exact in-memory GfxWorld.lightmaps[] GfxImage identities; no renderer semantics inferred\"\n";
        out << "  },\n";
        out << "  \"lightmapCount\": " << world->lightmapCount << ",\n";
        out << "  \"lightmaps\": [\n";

        for (int i = 0; i < world->lightmapCount; ++i)
        {
            const auto& lightmap = world->lightmaps[i];
            if (!lightmap.primary || !lightmap.secondary)
            {
                con::error(
                    "T6 GfxWorld \"{}\" lightmap {} has null {} image",
                    asset.m_name,
                    i,
                    !lightmap.primary ? "primary" : "secondary");
                return;
            }
            if (!lightmap.primary->name || !lightmap.secondary->name)
            {
                con::error(
                    "T6 GfxWorld \"{}\" lightmap {} has unnamed {} image",
                    asset.m_name,
                    i,
                    !lightmap.primary->name ? "primary" : "secondary");
                return;
            }

            out << "    {\n";
            out << "      \"index\": " << i << ",\n";
            out << "      \"primaryImage\": " << JsonString(lightmap.primary->name) << ",\n";
            out << "      \"secondaryImage\": " << JsonString(lightmap.secondary->name) << "\n";
            out << "    }";
            if (i + 1 != world->lightmapCount)
                out << ',';
            out << "\n";
        }

        out << "  ]\n";
        out << "}\n";

        con::info(
            "Dumped T6 GfxWorld lightmap catalog \"{}\": {} primary/secondary pairs -> {}",
            asset.m_name,
            world->lightmapCount,
            outputName);
    }
} // namespace gfx_world_lightmap
