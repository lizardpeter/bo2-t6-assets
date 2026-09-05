#include "GfxWorldLightmapDumperT6.h"

#include "Utils/Logging/Log.h"

#include <cstdint>
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
        const auto* text = value ? value : "";
        std::ostringstream out;
        out << '"';
        for (const auto* p = reinterpret_cast<const unsigned char*>(text); *p; ++p)
        {
            switch (*p)
            {
            case '"':
                out << "\\\"";
                break;
            case '\\':
                out << "\\\\";
                break;
            case '\b':
                out << "\\b";
                break;
            case '\f':
                out << "\\f";
                break;
            case '\n':
                out << "\\n";
                break;
            case '\r':
                out << "\\r";
                break;
            case '\t':
                out << "\\t";
                break;
            default:
                if (*p < 0x20)
                {
                    out << "\\u"
                        << std::hex << std::uppercase << std::setw(4)
                        << std::setfill('0') << static_cast<unsigned int>(*p)
                        << std::dec << std::nouppercase << std::setfill(' ');
                }
                else
                {
                    out << static_cast<char>(*p);
                }
                break;
            }
        }
        out << '"';
        return out.str();
    }

    void WriteNullableImageName(std::ostream& out, const T6::GfxImage* image)
    {
        if (!image)
        {
            out << "null";
            return;
        }
        out << JsonString(image->name);
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

        // Pinned OAT T6_Assets.h stores the lightmap array in GfxWorld::draw,
        // not directly in GfxWorld. Keep this indirection explicit so the
        // patch matches the exact upstream structure it claims to target.
        const auto& draw = world->draw;
        if (draw.lightmapCount < 0)
        {
            con::error(
                "T6 GfxWorld \"{}\" has invalid negative draw.lightmapCount {}",
                asset.m_name,
                draw.lightmapCount);
            return;
        }
        if (draw.lightmapCount > 0 && !draw.lightmaps)
        {
            con::error(
                "T6 GfxWorld \"{}\" has draw.lightmapCount {} but null draw.lightmaps",
                asset.m_name,
                draw.lightmapCount);
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
        out << "    \"kind\": \"OpenAssetTools loaded T6::GfxWorld::draw\",\n";
        out << "    \"assetName\": " << JsonString(asset.m_name.c_str()) << ",\n";
        out << "    \"policy\": \"exact in-memory GfxWorld.draw.lightmaps[] GfxImage identities; null retail roles preserved; no renderer semantics inferred\"\n";
        out << "  },\n";
        out << "  \"lightmapCount\": " << draw.lightmapCount << ",\n";
        out << "  \"lightmaps\": [\n";

        for (int i = 0; i < draw.lightmapCount; ++i)
        {
            const auto& lightmap = draw.lightmaps[i];

            // A null GfxImage pointer is a real nullable role in retained T6
            // data and is therefore archived as JSON null. A non-null image
            // with no name is not a stable archival identity and fails closed.
            if (lightmap.primary && !lightmap.primary->name)
            {
                con::error(
                    "T6 GfxWorld \"{}\" lightmap {} has non-null unnamed primary image",
                    asset.m_name,
                    i);
                return;
            }
            if (lightmap.secondary && !lightmap.secondary->name)
            {
                con::error(
                    "T6 GfxWorld \"{}\" lightmap {} has non-null unnamed secondary image",
                    asset.m_name,
                    i);
                return;
            }

            out << "    {\n";
            out << "      \"index\": " << i << ",\n";
            out << "      \"primaryImage\": ";
            WriteNullableImageName(out, lightmap.primary);
            out << ",\n";
            out << "      \"secondaryImage\": ";
            WriteNullableImageName(out, lightmap.secondary);
            out << "\n";
            out << "    }";
            if (i + 1 != draw.lightmapCount)
                out << ',';
            out << "\n";
        }

        out << "  ]\n";
        out << "}\n";

        con::info(
            "Dumped T6 GfxWorld lightmap catalog \"{}\": {} nullable primary/secondary pairs -> {}",
            asset.m_name,
            draw.lightmapCount,
            outputName);
    }
} // namespace gfx_world_lightmap
