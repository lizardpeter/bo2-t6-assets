// Locate exact current-client T6 character-XAsset DB runtime without relying on build VAs.
//
//@category T6 Current Client

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Set;
import java.util.TreeSet;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class FindT6CurrentClientCharacterXAssetRuntime extends GhidraScript {
    private static String scalarString(Data d) {
        if (d == null || !d.hasStringValue()) return null;
        Object value = d.getValue();
        return value == null ? null : value.toString();
    }

    private void exportFunction(Function f, Path out, DecompInterface di, Listing listing) throws Exception {
        String stem = f.getEntryPoint().toString().toLowerCase();
        StringBuilder asm = new StringBuilder();
        for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
            asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
        }
        Files.writeString(out.resolve("xref_" + stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
        di.flushCache();
        DecompileResults dr = di.decompileFunction(f, 180, monitor);
        String c = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction() != null
            ? dr.getDecompiledFunction().getC() : "";
        Files.writeString(out.resolve("xref_" + stem + ".c"), c, StandardCharsets.UTF_8);
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException(
            "usage: FindT6CurrentClientCharacterXAssetRuntime.java <output-dir>");
        Path out = Paths.get(args[0]).toAbsolutePath().normalize();
        Files.createDirectories(out);

        Listing listing = currentProgram.getListing();
        DecompInterface di = new DecompInterface();
        di.toggleCCode(true);
        di.toggleSyntaxTree(true);
        di.setSimplificationStyle("decompile");
        if (!di.openProgram(currentProgram)) throw new IllegalStateException("decompiler open failed");

        String[] needles = {
            "DB_GetXAssetSizeHandler[type]",
            "db_assetnames.cpp"
        };
        StringBuilder hits = new StringBuilder(
            "needle\tstring_address\tfrom_address\tfunction_entry\tfunction_name\treference_type\n");
        Set<Address> exported = new TreeSet<>();

        for (Data d : listing.getDefinedData(true)) {
            monitor.checkCancelled();
            String value = scalarString(d);
            if (value == null) continue;
            for (String needle : needles) {
                if (!value.contains(needle)) continue;
                ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(d.getAddress());
                while (refs.hasNext()) {
                    Reference ref = refs.next();
                    Address from = ref.getFromAddress();
                    Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                    hits.append(needle).append("\t")
                        .append(d.getAddress()).append("\t")
                        .append(from).append("\t")
                        .append(f == null ? "" : f.getEntryPoint()).append("\t")
                        .append(f == null ? "" : f.getName(true)).append("\t")
                        .append(ref.getReferenceType()).append("\n");
                    if (f != null && exported.add(f.getEntryPoint())) {
                        exportFunction(f, out, di, listing);
                    }
                }
            }
        }
        Files.writeString(out.resolve("string_xrefs.tsv"), hits.toString(), StandardCharsets.UTF_8);
        if (exported.isEmpty()) {
            throw new IllegalStateException("no current-client DB_GetXAssetTypeSize string xrefs found");
        }
        di.dispose();
        println("exported " + exported.size() + " exact current-client DB asset-name function(s)");
    }
}
