// Locate exact current-client fog writer candidates from distinctive T6 float constants.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class FindT6CurrentClientFogWriters extends GhidraScript {
    private List<Address> findAll(byte[] pattern) throws Exception {
        List<Address> out = new ArrayList<>();
        Memory mem = currentProgram.getMemory();
        Address cur = currentProgram.getMinAddress();
        Address max = currentProgram.getMaxAddress();
        while (cur != null && cur.compareTo(max) <= 0) {
            Address hit = mem.findBytes(cur, pattern, null, true, monitor);
            if (hit == null) break;
            out.add(hit);
            if (hit.equals(max)) break;
            cur = hit.next();
        }
        return out;
    }

    private Set<Function> refFunctions(List<Address> values) {
        Set<Function> out = new LinkedHashSet<>();
        for (Address value : values) {
            ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(value);
            while (it.hasNext()) {
                Reference ref = it.next();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(ref.getFromAddress());
                if (f != null) out.add(f);
            }
        }
        return out;
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("usage: FindT6CurrentClientFogWriters <out_dir>");
        Path out = Path.of(args[0]);
        Files.createDirectories(out);

        // 100.0f = 0x42c80000; pi/180 = 0x3c8efa35.
        List<Address> hundred = findAll(new byte[]{0x00,0x00,(byte)0xc8,0x42});
        List<Address> deg2rad = findAll(new byte[]{0x35,(byte)0xfa,(byte)0x8e,0x3c});
        Set<Function> hFns = refFunctions(hundred);
        Set<Function> dFns = refFunctions(deg2rad);
        Set<Function> candidates = new LinkedHashSet<>(hFns);
        candidates.retainAll(dFns);

        StringBuilder manifest = new StringBuilder();
        manifest.append("client_sha256\t770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf\n");
        manifest.append("hundred_value_addresses\t").append(hundred).append("\n");
        manifest.append("deg2rad_value_addresses\t").append(deg2rad).append("\n");
        manifest.append("hundred_ref_functions\t").append(hFns.size()).append("\n");
        manifest.append("deg2rad_ref_functions\t").append(dFns.size()).append("\n");
        manifest.append("intersection_candidates\t").append(candidates.size()).append("\n");
        Files.writeString(out.resolve("manifest.txt"), manifest.toString(), StandardCharsets.UTF_8);

        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        StringBuilder rows = new StringBuilder("entry\tname\tbody_size\tdecompile_completed\terror\n");
        try {
            for (Function f : candidates) {
                monitor.checkCancelled();
                di.flushCache();
                DecompileResults dr = di.decompileFunction(f, 180, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction() != null;
                String err = dr == null ? "null" : String.valueOf(dr.getErrorMessage());
                String c = ok ? dr.getDecompiledFunction().getC() : "";
                String stem = f.getEntryPoint().toString();
                Files.writeString(out.resolve(stem + ".c"), c, StandardCharsets.UTF_8);
                rows.append(stem).append("\t")
                    .append(f.getName(true).replace("\t"," ")).append("\t")
                    .append(f.getBody().getNumAddresses()).append("\t")
                    .append(ok).append("\t")
                    .append(err == null ? "" : err.replace("\t"," ").replace("\n"," ")).append("\n");
            }
        } finally {
            di.dispose();
        }
        Files.writeString(out.resolve("candidates.tsv"), rows.toString(), StandardCharsets.UTF_8);
    }
}
