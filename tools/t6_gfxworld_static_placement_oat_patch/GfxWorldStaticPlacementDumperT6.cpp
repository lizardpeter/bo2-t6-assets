#include "GfxWorldStaticPlacementDumperT6.h"

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
            case '/': case '\\': case ':': case '*': case '?': case '"': case '<': case '>': case '|':
                c = '_'; break;
            default: break;
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
            case '"': out << "\\\""; break;
            case '\\': out << "\\\\"; break;
            case '\b': out << "\\b"; break;
            case '\f': out << "\\f"; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (*p < 0x20)
                    out << "\\u" << std::hex << std::uppercase << std::setw(4) << std::setfill('0')
                        << static_cast<unsigned int>(*p) << std::dec << std::nouppercase << std::setfill(' ');
                else
                    out << static_cast<char>(*p);
                break;
            }
        }
        out << '"';
        return out.str();
    }

    void WriteVec3(std::ostream& out, const vec3_t& v)
    {
        out << '[' << std::setprecision(9) << v.v[0] << ',' << v.v[1] << ',' << v.v[2] << ']';
    }
}

namespace gfx_world_static_placement
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

        const auto count = world->dpvs.smodelCount;
        if (count > 0 && (!world->dpvs.smodelDrawInsts || !world->dpvs.smodelInsts))
        {
            con::error("T6 GfxWorld \"{}\" has {} smodels but null placement arrays", asset.m_name, count);
            return;
        }

        const auto outputName = std::string("gfxworld_static_placements/") + SafeName(asset.m_name) + ".json";
        const auto outputFile = context.OpenAssetFile(outputName);
        if (!outputFile)
            return;

        auto& out = *outputFile;
        out << "{\n";
        out << "  \"format\": \"t6-gfxworld-static-placement-catalog-v1\",\n";
        out << "  \"map\": " << JsonString(asset.m_name.c_str()) << ",\n";
        out << "  \"source\": {\n";
        out << "    \"kind\": \"OpenAssetTools loaded T6::GfxWorld.dpvs\",\n";
        out << "    \"policy\": \"exact in-memory smodelDrawInsts + smodelInsts; no placement inference\"\n";
        out << "  },\n";
        out << "  \"smodelCount\": " << count << ",\n";
        out << "  \"placements\": [\n";

        for (unsigned int i = 0; i < count; ++i)
        {
            const auto& draw = world->dpvs.smodelDrawInsts[i];
            const auto& inst = world->dpvs.smodelInsts[i];
            if (!draw.model || !draw.model->name)
            {
                con::error("T6 GfxWorld \"{}\" smodel {} has null/unnamed XModel", asset.m_name, i);
                return;
            }

            out << "    {\n";
            out << "      \"index\": " << i << ",\n";
            out << "      \"model\": " << JsonString(draw.model->name) << ",\n";
            out << "      \"cullDist\": " << std::setprecision(9) << draw.cullDist << ",\n";
            out << "      \"origin\": "; WriteVec3(out, draw.placement.origin); out << ",\n";
            out << "      \"axis\": [";
            for (int a = 0; a < 3; ++a)
            {
                if (a) out << ',';
                WriteVec3(out, draw.placement.axis[a]);
            }
            out << "],\n";
            out << "      \"scale\": " << std::setprecision(9) << draw.placement.scale << ",\n";
            out << "      \"flags\": " << draw.flags << ",\n";
            out << "      \"mins\": "; WriteVec3(out, inst.mins); out << ",\n";
            out << "      \"maxs\": "; WriteVec3(out, inst.maxs); out << ",\n";
            out << "      \"lightingOrigin\": "; WriteVec3(out, inst.lightingOrigin); out << "\n";
            out << "    }";
            if (i + 1 != count) out << ',';
            out << "\n";
        }

        out << "  ]\n";
        out << "}\n";

        con::info("Dumped T6 GfxWorld static placement catalog \"{}\": {} instances -> {}",
                  asset.m_name, count, outputName);
    }
} // namespace gfx_world_static_placement
