// Inventory ALL executable functions discovered by Ghidra in CoDMPServer_PC.exe.
// This is whole-program indexing, not the legacy PDB-claim subset.
// @category Black Ops II Reconstruction
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.address.Address;

public class ExportFullProgramFunctionIndex extends GhidraScript {
    private String tsv(String value) {
        if (value == null) return "";
        return value.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ');
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException("usage: ExportFullProgramFunctionIndex.java <output.tsv>");
        }
        Path destination = Paths.get(args[0]).toAbsolutePath().normalize();
        Files.createDirectories(destination.getParent());
        Memory memory = currentProgram.getMemory();
        long total = 0;
        long executable = 0;
        long nonExecutable = 0;
        long thunks = 0;
        try (BufferedWriter writer = Files.newBufferedWriter(destination, StandardCharsets.UTF_8)) {
            writer.write("analysis_va\tghidra_name\tprototype\tfunction_body_bytes\tis_thunk\tis_executable\n");
            FunctionIterator iterator = currentProgram.getFunctionManager().getFunctions(true);
            while (iterator.hasNext()) {
                monitor.checkCancelled();
                Function function = iterator.next();
                Address entry = function.getEntryPoint();
                ++total;
                boolean exec = memory.getExecuteSet().contains(entry);
                if (exec) ++executable; else ++nonExecutable;
                if (function.isThunk()) ++thunks;
                writer.write("0x" + entry.toString().toLowerCase() + "\t"
                    + tsv(function.getName(true)) + "\t"
                    + tsv(function.getPrototypeString(true, true)) + "\t"
                    + function.getBody().getNumAddresses() + "\t"
                    + function.isThunk() + "\t" + exec + "\n");
            }
        }
        println("FULL_EXECUTABLE_GHIDRA_INDEX path=" + destination
            + " total_functions=" + total + " executable_functions=" + executable
            + " non_executable=" + nonExecutable + " thunks=" + thunks);
        if (total == 0 || executable == 0) {
            throw new IllegalStateException("Ghidra produced no executable functions; refusing empty inventory");
        }
    }
}
