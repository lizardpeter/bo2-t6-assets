#include "GfxWorldReflectionProbeDumperT6.h"

#include "Utils/Logging/Log.h"

#include <cmath>
#include <cstdint>
#include <iomanip>
#include <limits>
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

    bool Finite3(const T6::vec3_t& value)
    {
        return std::isfinite(value.v[0]) && std::isfinite(value.v[1])
            && std::isfinite(value.v[2]);
    }

    bool Finite4(const T6::vec4_t& value)
    {
        return std::isfinite(value.v[0]) && std::isfinite(value.v[1])
            && std::isfinite(value.v[2]) && std::isfinite(value.v[3]);
    }

    void WriteVec3(std::ostream& out, const T6::vec3_t& value)
    {
        out << '[' << value.v[0] << ',' << value.v[1] << ',' << value.v[2] << ']';
    }

    void WriteVec4(std::ostream& out, const T6::vec4_t& value)
    {
        out << '[' << value.v[0] << ',' << value.v[1] << ',' << value.v[2] << ','
            << value.v[3] << ']';
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

namespace gfx_world_reflection_probe
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

        const auto& draw = world->draw;
        if (draw.reflectionProbeCount > 0 && !draw.reflectionProbes)
        {
            con::error(
                "T6 GfxWorld \"{}\" has draw.reflectionProbeCount {} but null draw.reflectionProbes",
                asset.m_name,
                draw.reflectionProbeCount);
            return;
        }

        // Validate the entire structural payload before opening the output file.
        // A null reflectionImage is preserved as a nullable retail role. A
        // non-null image without a name is not a stable archival identity.
        for (unsigned int i = 0; i < draw.reflectionProbeCount; ++i)
        {
            const auto& probe = draw.reflectionProbes[i];
            if (!Finite3(probe.origin) || !Finite4(probe.lightingSH.V0)
                || !Finite4(probe.lightingSH.V1) || !Finite4(probe.lightingSH.V2)
                || !std::isfinite(probe.mipLodBias))
            {
                con::error(
                    "T6 GfxWorld \"{}\" reflection probe {} contains non-finite origin/SH/mipLodBias",
                    asset.m_name,
                    i);
                return;
            }
            if (probe.reflectionImage && !probe.reflectionImage->name)
            {
                con::error(
                    "T6 GfxWorld \"{}\" reflection probe {} has non-null unnamed reflectionImage",
                    asset.m_name,
                    i);
                return;
            }
            if (probe.probeVolumeCount > 0 && !probe.probeVolumes)
            {
                con::error(
                    "T6 GfxWorld \"{}\" reflection probe {} has probeVolumeCount {} but null probeVolumes",
                    asset.m_name,
                    i,
                    probe.probeVolumeCount);
                return;
            }
            for (unsigned int volumeIndex = 0; volumeIndex < probe.probeVolumeCount;
                 ++volumeIndex)
            {
                const auto& volume = probe.probeVolumes[volumeIndex];
                for (unsigned int planeIndex = 0; planeIndex < 6; ++planeIndex)
                {
                    if (!Finite4(volume.volumePlanes[planeIndex]))
                    {
                        con::error(
                            "T6 GfxWorld \"{}\" reflection probe {} volume {} plane {} is non-finite",
                            asset.m_name,
                            i,
                            volumeIndex,
                            planeIndex);
                        return;
                    }
                }
            }
        }

        const auto outputName = std::string("gfxworld_reflection_probes/")
            + SafeName(asset.m_name) + ".json";
        const auto outputFile = context.OpenAssetFile(outputName);
        if (!outputFile)
            return;

        auto& out = *outputFile;
        out << std::setprecision(std::numeric_limits<float>::max_digits10);
        out << "{\n";
        out << "  \"format\": \"t6-gfxworld-reflection-probe-catalog-v1\",\n";
        out << "  \"map\": " << JsonString(asset.m_name.c_str()) << ",\n";
        out << "  \"source\": {\n";
        out << "    \"kind\": \"OpenAssetTools loaded T6::GfxWorld::draw\",\n";
        out << "    \"assetName\": " << JsonString(asset.m_name.c_str()) << ",\n";
        out << "    \"policy\": \"exact in-memory GfxWorld.draw.reflectionProbes[] structural payload; runtime reflectionProbeTextures pointers omitted; no renderer semantics inferred\"\n";
        out << "  },\n";
        out << "  \"reflectionProbeCount\": " << draw.reflectionProbeCount << ",\n";
        out << "  \"reflectionProbes\": [\n";

        for (unsigned int i = 0; i < draw.reflectionProbeCount; ++i)
        {
            const auto& probe = draw.reflectionProbes[i];
            out << "    {\n";
            out << "      \"index\": " << i << ",\n";
            out << "      \"origin\": ";
            WriteVec3(out, probe.origin);
            out << ",\n";
            out << "      \"lightingSH\": {\n";
            out << "        \"V0\": ";
            WriteVec4(out, probe.lightingSH.V0);
            out << ",\n";
            out << "        \"V1\": ";
            WriteVec4(out, probe.lightingSH.V1);
            out << ",\n";
            out << "        \"V2\": ";
            WriteVec4(out, probe.lightingSH.V2);
            out << "\n";
            out << "      },\n";
            out << "      \"reflectionImage\": ";
            WriteNullableImageName(out, probe.reflectionImage);
            out << ",\n";
            out << "      \"probeVolumeCount\": " << probe.probeVolumeCount << ",\n";
            out << "      \"probeVolumes\": [\n";
            for (unsigned int volumeIndex = 0; volumeIndex < probe.probeVolumeCount;
                 ++volumeIndex)
            {
                const auto& volume = probe.probeVolumes[volumeIndex];
                out << "        {\n";
                out << "          \"volumeIndex\": " << volumeIndex << ",\n";
                out << "          \"volumePlanes\": [\n";
                for (unsigned int planeIndex = 0; planeIndex < 6; ++planeIndex)
                {
                    out << "            ";
                    WriteVec4(out, volume.volumePlanes[planeIndex]);
                    if (planeIndex + 1 != 6)
                        out << ',';
                    out << "\n";
                }
                out << "          ]\n";
                out << "        }";
                if (volumeIndex + 1 != probe.probeVolumeCount)
                    out << ',';
                out << "\n";
            }
            out << "      ],\n";
            out << "      \"mipLodBias\": " << probe.mipLodBias << "\n";
            out << "    }";
            if (i + 1 != draw.reflectionProbeCount)
                out << ',';
            out << "\n";
        }

        out << "  ]\n";
        out << "}\n";

        con::info(
            "Dumped T6 GfxWorld reflection probe catalog \"{}\": {} probes -> {}",
            asset.m_name,
            draw.reflectionProbeCount,
            outputName);
    }
} // namespace gfx_world_reflection_probe
