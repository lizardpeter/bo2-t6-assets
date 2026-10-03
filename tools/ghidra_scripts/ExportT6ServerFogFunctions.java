// Targeted T6 server fog decompile/export for exact fog ABI recovery.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

public class ExportT6ServerFogFunctions extends GhidraScript {
    private static final String[][] TARGETS = {
        {"00A5C260", "R_SetFogFromServer"},
        {"00A8A9A0", "R_SetFrameFog"}
    };

    private static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte b : bytes) out.append(String.format("%02x", b & 0xff));
        return out.toString();
    }

    private static String json(String value) {
        return "\"" + value
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t") + "\"";
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("usage: ExportT6ServerFogFunctions <out_dir>");
        Path outDir = Path.of(args[0]);
        Files.createDirectories(outDir);

        Listing listing = currentProgram.getListing();
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);

        List<String> summaryRows = new ArrayList<>();
        try {
            for (String[] target : TARGETS) {
                monitor.checkCancelled();
                Address address = toAddr(target[0]);
                Function fn = currentProgram.getFunctionManager().getFunctionAt(address);
                if (fn == null) fn = currentProgram.getFunctionManager().getFunctionContaining(address);
                if (fn == null) throw new IllegalStateException("no function at/containing " + target[0]);

                String stem = target[1];
                StringBuilder asm = new StringBuilder();
                long instructionCount = 0;
                for (Instruction insn : listing.getInstructions(fn.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                    instructionCount++;
                }
                byte[] asmBytes = asm.toString().getBytes(StandardCharsets.UTF_8);
                String asmSha = hex(MessageDigest.getInstance("SHA-256").digest(asmBytes));
                Files.write(outDir.resolve(stem + ".asm.txt"), asmBytes);

                decompiler.flushCache();
                DecompileResults result = decompiler.decompileFunction(fn, 180, monitor);
                boolean completed = result != null && result.decompileCompleted() && result.getDecompiledFunction() != null;
                String c = completed ? result.getDecompiledFunction().getC() : "";
                String error = result == null ? "null decompile result" : String.valueOf(result.getErrorMessage());
                byte[] cBytes = c.getBytes(StandardCharsets.UTF_8);
                String cSha = hex(MessageDigest.getInstance("SHA-256").digest(cBytes));
                Files.write(outDir.resolve(stem + ".c"), cBytes);

                summaryRows.add(
                    "    {" +
                    "\"requested_name\":" + json(target[1]) + "," +
                    "\"address\":" + json(target[0]) + "," +
                    "\"ghidra_name\":" + json(fn.getName(true)) + "," +
                    "\"body_size\":" + fn.getBody().getNumAddresses() + "," +
                    "\"instruction_count\":" + instructionCount + "," +
                    "\"assembly_sha256\":" + json(asmSha) + "," +
                    "\"decompile_completed\":" + completed + "," +
                    "\"decompile_sha256\":" + json(cSha) + "," +
                    "\"decompile_error\":" + json(error == null ? "" : error) +
                    "}"
                );
            }
        } finally {
            decompiler.dispose();
        }

        String summary = "{\n" +
            "  \"format\": \"t6-server-fog-functions-v1\",\n" +
            "  \"build\": \"pc-server-2013-03-11\",\n" +
            "  \"exe_sha256\": \"f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d\",\n" +
            "  \"pdb_sha256\": \"7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc\",\n" +
            "  \"authority\": \"PDB-backed Ghidra export of exact T6 PC server functions\",\n" +
            "  \"proof_boundary\": \"Server-build facts only until transferred to the retail client by explicit cross-build evidence.\",\n" +
            "  \"functions\": [\n" + String.join(",\n", summaryRows) + "\n  ]\n}\n";
        Files.writeString(outDir.resolve("summary.json"), summary, StandardCharsets.UTF_8);
    }
}
