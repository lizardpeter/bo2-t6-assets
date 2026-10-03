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
        Files.writeString(out.resolve("summary.tsv"), summary.toString(), StandardCharsets.UTF_8);
    }
}
