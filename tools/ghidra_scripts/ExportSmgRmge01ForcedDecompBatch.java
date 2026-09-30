// Force exact graph-verified RMGE01 function boundaries one target at a time, then decompile immediately.
// This is a recovery path for exact entries lost because overlapping/nested functions cannot coexist
// simultaneously in Ghidra's FunctionManager.
//@category SMG RMGE01
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.io.*;
import java.util.*;
import java.util.Base64;

public class ExportSmgRmge01ForcedDecompBatch extends GhidraScript {
    private String b64(String s) {
        return Base64.getEncoder().encodeToString((s == null ? "" : s).getBytes(StandardCharsets.UTF_8));
    }

    private static class ForceResult {
        Function function;
        int removed;
        String error = "";
    }

    private ForceResult forceExactFunction(FunctionManager fm, Address start, Address end, long av) {
        ForceResult out = new ForceResult();
        AddressSet body = new AddressSet(start, end);
        LinkedHashSet<Address> remove = new LinkedHashSet<Address>();

        Function containing = fm.getFunctionContaining(start);
        if (containing != null) {
            remove.add(containing.getEntryPoint());
        }

        FunctionIterator it = fm.getFunctions(body, true);
        while (it.hasNext()) {
            Function f = it.next();
            remove.add(f.getEntryPoint());
        }

        for (Address ep : remove) {
            try {
                if (fm.getFunctionAt(ep) != null) {
                    fm.removeFunction(ep);
                    out.removed++;
                }
            }
            catch (Exception e) {
                out.error = "remove-conflict failed at " + ep + ": " + e.toString();
                return out;
            }
        }

        try {
            out.function = fm.createFunction(
                "FUN_" + String.format("%08X", av),
                start,
                body,
                SourceType.USER_DEFINED
            );
            if (out.function == null) {
                out.error = "force-create returned null";
            }
        }
        catch (Exception e) {
            out.error = "force-create failed: " + e.toString();
        }
        return out;
    }

    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2 || args.length > 3) {
            throw new IllegalArgumentException("usage: <manifest.tsv> <out.tsv> [missing-only|force-all]");
        }
        String mode = args.length == 3 ? args[2] : "missing-only";
        if (!mode.equals("missing-only") && !mode.equals("force-all")) {
            throw new IllegalArgumentException("mode must be missing-only or force-all");
        }

        List<String> lines = Files.readAllLines(Paths.get(args[0]));
        Path outPath = Paths.get(args[1]);
        Files.createDirectories(outPath.toAbsolutePath().getParent());

        FunctionManager fm = currentProgram.getFunctionManager();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();

        DecompInterface di = new DecompInterface();
        DecompileOptions opts = new DecompileOptions();
        di.setOptions(opts);
        di.toggleCCode(true);
        di.toggleSyntaxTree(true);
        if (!di.openProgram(currentProgram)) {
            throw new RuntimeException("decompiler open failed");
        }

        int examined = 0, skippedExisting = 0, forced = 0, ok = 0, fail = 0, removed = 0;

        try (BufferedWriter w = Files.newBufferedWriter(outPath, StandardCharsets.UTF_8)) {
            w.write("id\taddress\tsize\tsuccess\tforced\tconflicts_removed\tfunction_name_b64\tc_b64\terror_b64\n");

            for (int i = 1; i < lines.size(); i++) {
                monitor.checkCancelled();
                String line = lines.get(i);
                if (line.trim().isEmpty()) continue;
                String[] p = line.split("\t", -1);
                long av = Long.parseUnsignedLong(p[1].substring(2), 16);
                long sz = Long.parseLong(p[2]);
                Address start = sp.getAddress(av);
                Address end = start.add(sz - 1);
                examined++;

                Function initial = fm.getFunctionAt(start);
                if (mode.equals("missing-only") && initial != null) {
                    skippedExisting++;
                    continue;
                }

                ForceResult fr = forceExactFunction(fm, start, end, av);
                forced++;
                removed += fr.removed;

                boolean success = false;
                String name = "";
                String c = "";
                String err = fr.error;

                Function f = fr.function;
                if (f == null) {
                    fail++;
                }
                else {
                    name = f.getName(true);
                    try {
                        di.flushCache();
                        DecompileResults dr = di.decompileFunction(f, 180, monitor);
                        success = dr.decompileCompleted() && dr.getDecompiledFunction() != null;
                        if (success) {
                            c = dr.getDecompiledFunction().getC();
                            ok++;
                        }
                        else {
                            err = dr.getErrorMessage();
                            fail++;
                        }
                    }
                    catch (Exception e) {
                        err = e.toString();
                        fail++;
                    }
                }

                w.write(
                    p[0] + "\t" + p[1] + "\t" + p[2] + "\t" +
                    Boolean.toString(success) + "\ttrue\t" + Integer.toString(fr.removed) + "\t" +
                    b64(name) + "\t" + b64(c) + "\t" + b64(err) + "\n"
                );
            }
        }
        finally {
            di.dispose();
        }

        println(
            "SMG forced decompile mode=" + mode +
            " examined=" + examined +
            " skipped_existing=" + skippedExisting +
            " forced=" + forced +
            " conflicts_removed=" + removed +
            " ok=" + ok +
            " fail=" + fail
        );
    }
}
