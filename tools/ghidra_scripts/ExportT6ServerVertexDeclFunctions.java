// Targeted T6 server vertex declaration/runtime stream decompile.
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class ExportT6ServerVertexDeclFunctions extends GhidraScript {
    private static final String[][] TARGETS = {
        {"00A7B040", "R_EncodeLightingSH_internal"},
        {"00A7B150", "R_DecodeLightingSH_internal"},
        {"00A7B890", "R_InitModelLightingGlobals"},
        {"00A7BC60", "R_InitStaticModelLighting"},
        {"00A7B270", "R_SetModelLightingConsts_internal"},
        {"00A7B3D0", "R_SetStaticModelLightingConsts_internal"},
        {"00A6FAE0", "R_SetLightGridColorsFromIndex"},
        {"00A714B0", "R_GetLightingAtPoint"},
        {"00A7B6C0", "R_SetStaticModelLightingForSource"},
        {"00A7B7B0", "R_SetupDynamicModelLighting"},
        {"00A7BA50", "R_ResetModelLighting"},
        {"00A7BC70", "R_SetModelLightingForSource"},
        {"00A7BCD0", "R_AllocStaticModelLighting"},
        {"00A7C110", "R_SetAllStaticModelLighting"},
        {"00A7C230", "R_AllocModelLighting"},
        {"00A8D770", "R_SetReflectionProbe"},
        {"00A24EC0", "R_SetCodeConstant"},
        {"00A3F600", "R_SetCodeConstantFromVec4"},
        {"00A9F200", "R_SetVertexDeclTypeWorldSurface"},
        {"00A9F270", "R_SetVertexDeclTypeModel"},
        {"00AA39E0", "R_UpdateVertexDecl"},
        {"00AA3C40", "R_SetVertexData"}
    };

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("usage: ExportT6ServerVertexDeclFunctions <out_dir>");
        Path out = Path.of(args[0]);
        Files.createDirectories(out);
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        Listing listing = currentProgram.getListing();
        StringBuilder summary = new StringBuilder("name\taddress\tghidra_name\tbody_size\tinstructions\tdecompile_completed\n");
        try {
            for (String[] target : TARGETS) {
                monitor.checkCancelled();
                Address a = toAddr(target[0]);
                Function f = currentProgram.getFunctionManager().getFunctionAt(a);
                if (f == null) f = currentProgram.getFunctionManager().getFunctionContaining(a);
                if (f == null) throw new IllegalStateException("no function at "+target[0]);
                StringBuilder asm = new StringBuilder();
                long insnCount = 0;
                for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                    insnCount++;
                }
                Files.writeString(out.resolve(target[1]+".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr = di.decompileFunction(f, 180, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                String body = ok ? dr.getDecompiledFunction().getC() : "";
                Files.writeString(out.resolve(target[1]+".c"), body, StandardCharsets.UTF_8);
                summary.append(target[1]).append("\t").append(target[0]).append("\t")
                    .append(f.getName(true)).append("\t").append(f.getBody().getNumAddresses()).append("\t")
                    .append(insnCount).append("\t").append(ok).append("\n");
            }
        } finally { di.dispose(); }
        // The MSVC MAP/PDB proves a private R_SetStaticModelLighting family
        // between R_AllocStaticModelLighting and R_SetAllStaticModelLighting,
        // but the private symbol is not part of the public export list above.
        // Dump every Ghidra function in that exact address interval so the
        // writer/quantizer chain can be identified from code rather than by
        // guessing a function start.
        Address gapStart = toAddr("00A7BEB2");
        Address gapEnd = toAddr("00A7C110");
        StringBuilder gapSummary = new StringBuilder("address\tname\tbody_size\tinstructions\tdecompile_completed\n");
        FunctionIterator gapFunctions = currentProgram.getFunctionManager().getFunctions(gapStart, true);
        while (gapFunctions.hasNext()) {
            monitor.checkCancelled();
            Function f = gapFunctions.next();
            Address entry = f.getEntryPoint();
            if (entry.compareTo(gapEnd) >= 0) break;
            if (entry.compareTo(gapStart) < 0) continue;
            String stem = "model_lighting_gap_" + entry.toString().toLowerCase();
            StringBuilder asm = new StringBuilder();
            long insnCount = 0;
            for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                insnCount++;
            }
            Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
            di.flushCache();
            DecompileResults dr = di.decompileFunction(f, 180, monitor);
            boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
            String body = ok ? dr.getDecompiledFunction().getC() : "";
            Files.writeString(out.resolve(stem + ".c"), body, StandardCharsets.UTF_8);
            gapSummary.append(entry).append("\t").append(f.getName(true)).append("\t")
                .append(f.getBody().getNumAddresses()).append("\t")
                .append(insnCount).append("\t").append(ok).append("\n");
        }
        Files.writeString(out.resolve("model_lighting_private_gap_summary.tsv"), gapSummary.toString(), StandardCharsets.UTF_8);

        String[][] constants = {
            {"00B8F520", "xm_mask", "16"},
            {"00B8F590", "xm_flip", "16"},
            {"00B8F570", "xm_fixup", "16"},
            {"00C6D4B0", "xm_fixadd", "16"},
            {"00D23B70", "lighting_decode_mul0", "16"},
            {"00D23B80", "lighting_decode_mul1", "16"},
            {"00D23B90", "lighting_decode_add", "16"}
        };
        StringBuilder data = new StringBuilder("name\taddress\thex\n");
        for (String[] item : constants) {
            Address address = toAddr(item[0]);
            int len = Integer.parseInt(item[2]);
            byte[] bytes = new byte[len];
            int got = currentProgram.getMemory().getBytes(address, bytes);
            if (got != len) throw new IllegalStateException("short read at "+item[0]+": "+got);
            StringBuilder hex = new StringBuilder();
            for (byte b : bytes) hex.append(String.format("%02x", b & 0xff));
            data.append(item[1]).append("\t").append(item[0]).append("\t").append(hex).append("\n");
        }
        Files.writeString(out.resolve("R_DecodeLightingSH_constants.tsv"), data.toString(), StandardCharsets.UTF_8);
    }
}
