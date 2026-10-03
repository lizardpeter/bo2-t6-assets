// Targeted T6 server vertex declaration/runtime stream decompile.
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;
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
        {"00A7B540", "R_AllocModelLightingPixel"},
        {"00A7B600", "R_ToggleModelLightingFrame"},
        {"00A6FAE0", "R_SetLightGridColorsFromIndex"},
        {"00A714B0", "R_GetLightingAtPoint"},
        {"00A7B6C0", "R_SetStaticModelLightingForSource"},
        {"00A7B7B0", "R_SetupDynamicModelLighting"},
        {"00A7BA50", "R_ResetModelLighting"},
        {"00A7BC70", "R_SetModelLightingForSource"},
        {"00A7BCD0", "R_AllocStaticModelLighting"},
        {"00A7C110", "R_SetAllStaticModelLighting"},
        {"00A7C230", "R_AllocModelLighting"},
        {"00A15FA0", "R_GenerateSortedDrawSurfs_PreModelLighting_0"},
        {"00A163D0", "R_GenerateSortedDrawSurfs_PreModelLighting_1"},
        {"00A15D50", "R_GenerateSortedDrawSurfs_PostModelLighting_0"},
        {"00A15E20", "R_GenerateSortedDrawSurfs_PostModelLighting_1"},
        {"00A1AA40", "R_GenerateSortedDrawSurfs_FrameSetup"},
        {"00A98020", "R_InitRenderCommands_PreModelLighting"},
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
        Files.writeString(out.resolve("summary.tsv"), summary.toString(), StandardCharsets.UTF_8);

        // Follow the exact modelLightGlob image pointer rather than relying on
        // function-name guesses. 0x084F6EA4 is the GfxImage* loaded by
        // R_SetupDynamicModelLighting. Export every containing function that
        // references it, plus invImageHeight as a useful cross-check.
        String[][] modelLightGlobals = {
            {"084F6EA4", "modelLightGlob_image"},
            {"084F6E88", "modelLightGlob_invImageHeight"}
        };
        StringBuilder xrefSummary = new StringBuilder("global\tglobal_address\tfrom_address\tfunction_entry\tfunction_name\n");
        Set<Address> exportedXrefFunctions = new TreeSet<>();
        for (String[] item : modelLightGlobals) {
            Address global = toAddr(item[0]);
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(global);
            while (refs.hasNext()) {
                monitor.checkCancelled();
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                if (f == null) continue;
                xrefSummary.append(item[1]).append("\t").append(global).append("\t")
                    .append(from).append("\t").append(f.getEntryPoint()).append("\t")
                    .append(f.getName(true)).append("\n");
                if (!exportedXrefFunctions.add(f.getEntryPoint())) continue;
                String stem = "model_lighting_xref_" + f.getEntryPoint().toString().toLowerCase();
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
                Files.writeString(out.resolve(stem + ".c"),
                    ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
            }
        }
        Files.writeString(out.resolve("model_lighting_global_xrefs.tsv"), xrefSummary.toString(), StandardCharsets.UTF_8);

        // modelLightGlob.image can itself be initialized as a data pointer,
        // which produces no code write xref to the field. Resolve its exact
        // stored pointer and then follow references to the pointed-to GfxImage
        // object as well.
        Address imageField = toAddr("084F6EA4");
        int imagePointerWord = currentProgram.getMemory().getInt(imageField);
        long imagePointer = Integer.toUnsignedLong(imagePointerWord);
        Address imageObject = toAddr(String.format("%08X", imagePointer));
        StringBuilder imageObjectReport = new StringBuilder();
        imageObjectReport.append("field\t084F6EA4\n");
        imageObjectReport.append("pointer\t").append(imageObject).append("\n");
        Symbol primaryImageSymbol = currentProgram.getSymbolTable().getPrimarySymbol(imageObject);
        imageObjectReport.append("symbol\t")
            .append(primaryImageSymbol == null ? "" : primaryImageSymbol.getName(true))
            .append("\n");
        imageObjectReport.append("from_address\tfunction_entry\tfunction_name\treference_type\n");
        ReferenceIterator imageRefs = currentProgram.getReferenceManager().getReferencesTo(imageObject);
        Set<Address> imageObjectFunctions = new TreeSet<>();
        while (imageRefs.hasNext()) {
            monitor.checkCancelled();
            Reference ref = imageRefs.next();
            Address from = ref.getFromAddress();
            Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
            imageObjectReport.append(from).append("\t")
                .append(f == null ? "" : f.getEntryPoint().toString()).append("\t")
                .append(f == null ? "" : f.getName(true)).append("\t")
                .append(ref.getReferenceType()).append("\n");
            if (f == null || !imageObjectFunctions.add(f.getEntryPoint())) continue;
            String stem = "model_lighting_image_object_xref_" + f.getEntryPoint().toString().toLowerCase();
            StringBuilder asm = new StringBuilder();
            for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
            }
            Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
            di.flushCache();
            DecompileResults dr = di.decompileFunction(f, 180, monitor);
            boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
            Files.writeString(out.resolve(stem + ".c"),
                ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
        }
        Files.writeString(out.resolve("model_lighting_image_object_xrefs.tsv"), imageObjectReport.toString(), StandardCharsets.UTF_8);

        // Scan every aligned address across the modelLightGlob neighbourhood.
        // Generic helpers often receive &modelLightGlob or &oneSubobject and
        // then reach image through a field offset, so an xref to the exact
        // 0x084F6EA4 field is not sufficient.
        Address globStart = toAddr("084F6E80");
        Address globEnd = toAddr("084F6F20");
        StringBuilder rangeRefs = new StringBuilder("target\tfrom_address\tfunction_entry\tfunction_name\treference_type\n");
        Set<Address> rangeFunctions = new TreeSet<>();
        for (Address target = globStart; target.compareTo(globEnd) < 0; target = target.add(4)) {
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
            while (refs.hasNext()) {
                monitor.checkCancelled();
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                rangeRefs.append(target).append("\t").append(from).append("\t")
                    .append(f == null ? "" : f.getEntryPoint().toString()).append("\t")
                    .append(f == null ? "" : f.getName(true)).append("\t")
                    .append(ref.getReferenceType()).append("\n");
                if (f == null || !rangeFunctions.add(f.getEntryPoint())) continue;
                String stem = "model_lighting_range_xref_" + f.getEntryPoint().toString().toLowerCase();
                StringBuilder asm = new StringBuilder();
                for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                }
                Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr = di.decompileFunction(f, 180, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem + ".c"),
                    ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
            }
        }
        Files.writeString(out.resolve("model_lighting_struct_range_xrefs.tsv"), rangeRefs.toString(), StandardCharsets.UTF_8);

        // Export callers of the two renderer-lifecycle anchors as well. Image
        // creation commonly lives next to R_InitModelLightingGlobals in a
        // higher-level init function rather than in r_model_lighting.obj.
        String[][] lifecycleTargets = {
            {"00A7B890", "R_InitModelLightingGlobals"},
            {"00A7B600", "R_ToggleModelLightingFrame"},
            {"00A7B7B0", "R_SetupDynamicModelLighting"}
        };
        StringBuilder lifecycleRefs = new StringBuilder("callee\tcallee_address\tcallsite\tcaller_entry\tcaller_name\n");
        Set<Address> lifecycleCallers = new TreeSet<>();
        for (String[] item : lifecycleTargets) {
            Address callee = toAddr(item[0]);
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(callee);
            while (refs.hasNext()) {
                monitor.checkCancelled();
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                lifecycleRefs.append(item[1]).append("\t").append(callee).append("\t")
                    .append(from).append("\t")
                    .append(f == null ? "" : f.getEntryPoint().toString()).append("\t")
                    .append(f == null ? "" : f.getName(true)).append("\n");
                if (f == null || !lifecycleCallers.add(f.getEntryPoint())) continue;
                String stem = "model_lighting_lifecycle_caller_" + f.getEntryPoint().toString().toLowerCase();
                StringBuilder asm = new StringBuilder();
                for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                }
                Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr = di.decompileFunction(f, 180, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem + ".c"),
                    ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
            }
        }
        Files.writeString(out.resolve("model_lighting_lifecycle_callers.tsv"), lifecycleRefs.toString(), StandardCharsets.UTF_8);

        // Resolve generic image construction functions directly from the PDB
        // by demangled Ghidra name, then export both the functions and every
        // caller. The model-lighting 3D volume is runtime-created, so its owner
        // is expected to call Image_Create3DTexture_PC and/or Image_Setup.
        String[] imageFunctionNeedles = {
            "Image_Create3DTexture_PC",
            "Image_Create2DTexture_PC",
            "Image_Setup",
            "Image_AllocProg",
            "Image_GetProg",
            "Image_Register",
            "Image_Alloc"
        };
        StringBuilder imageFunctions = new StringBuilder("entry\tname\tbody_size\n");
        StringBuilder imageCallers = new StringBuilder("callee_entry\tcallee_name\tcallsite\tcaller_entry\tcaller_name\n");
        Set<Address> exportedImageFunctions = new TreeSet<>();
        Set<Address> exportedImageCallers = new TreeSet<>();
        FunctionIterator allFunctions = currentProgram.getFunctionManager().getFunctions(true);
        while (allFunctions.hasNext()) {
            monitor.checkCancelled();
            Function f = allFunctions.next();
            String functionName = f.getName(true);
            boolean wanted = false;
            for (String needle : imageFunctionNeedles) {
                if (functionName.contains(needle)) {
                    wanted = true;
                    break;
                }
            }
            if (!wanted) continue;
            imageFunctions.append(f.getEntryPoint()).append("\t").append(functionName).append("\t")
                .append(f.getBody().getNumAddresses()).append("\n");
            if (exportedImageFunctions.add(f.getEntryPoint())) {
                String stem = "image_runtime_" + f.getEntryPoint().toString().toLowerCase();
                StringBuilder asm = new StringBuilder();
                for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                }
                Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr = di.decompileFunction(f, 180, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem + ".c"),
                    ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
            }
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
            while (refs.hasNext()) {
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function caller = currentProgram.getFunctionManager().getFunctionContaining(from);
                imageCallers.append(f.getEntryPoint()).append("\t").append(functionName).append("\t")
                    .append(from).append("\t")
                    .append(caller == null ? "" : caller.getEntryPoint().toString()).append("\t")
                    .append(caller == null ? "" : caller.getName(true)).append("\n");
                if (caller == null || !exportedImageCallers.add(caller.getEntryPoint())) continue;
                String stem = "image_runtime_caller_" + caller.getEntryPoint().toString().toLowerCase();
                StringBuilder asm = new StringBuilder();
                for (Instruction insn : listing.getInstructions(caller.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                }
                Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr = di.decompileFunction(caller, 180, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem + ".c"),
                    ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
            }
        }
        Files.writeString(out.resolve("image_runtime_functions.tsv"), imageFunctions.toString(), StandardCharsets.UTF_8);
        Files.writeString(out.resolve("image_runtime_callers.tsv"), imageCallers.toString(), StandardCharsets.UTF_8);

        // $model_lighting is not code-referenced directly: the string is held
        // by the program-image metadata table at 0x010BF814. Follow that table
        // slot and its surrounding words back into code, and dump the raw table
        // bytes so the exact program-image index/flags can be reconstructed.
        Address modelLightingNameSlot = toAddr("010BF814");
        StringBuilder progTableRefs = new StringBuilder("target\tfrom_address\tfunction_entry\tfunction_name\treference_type\n");
        Set<Address> progTableFunctions = new TreeSet<>();
        for (long off = -0x80; off <= 0x80; off += 4) {
            Address target = modelLightingNameSlot.add(off);
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
            while (refs.hasNext()) {
                monitor.checkCancelled();
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                progTableRefs.append(target).append("\t").append(from).append("\t")
                    .append(f == null ? "" : f.getEntryPoint().toString()).append("\t")
                    .append(f == null ? "" : f.getName(true)).append("\t")
                    .append(ref.getReferenceType()).append("\n");
                if (f == null || !progTableFunctions.add(f.getEntryPoint())) continue;
                String stem = "model_lighting_prog_table_xref_" + f.getEntryPoint().toString().toLowerCase();
                StringBuilder asm = new StringBuilder();
                for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                }
                Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr = di.decompileFunction(f, 180, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem + ".c"),
                    ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
            }
        }
        Files.writeString(out.resolve("model_lighting_prog_table_xrefs.tsv"), progTableRefs.toString(), StandardCharsets.UTF_8);

        Address progDumpStart = toAddr("010BF780");
        int progDumpSize = 0x180;
        byte[] progDump = new byte[progDumpSize];
        currentProgram.getMemory().getBytes(progDumpStart, progDump);
        StringBuilder progHex = new StringBuilder("address\tbytes\tu32_le\tprimary_symbol\n");
        for (int off = 0; off < progDumpSize; off += 4) {
            Address a = progDumpStart.add(off);
            int word = (progDump[off] & 0xff)
                | ((progDump[off + 1] & 0xff) << 8)
                | ((progDump[off + 2] & 0xff) << 16)
                | ((progDump[off + 3] & 0xff) << 24);
            Symbol sym = currentProgram.getSymbolTable().getPrimarySymbol(a);
            progHex.append(a).append("\t")
                .append(String.format("%02x %02x %02x %02x",
                    progDump[off] & 0xff, progDump[off+1] & 0xff,
                    progDump[off+2] & 0xff, progDump[off+3] & 0xff))
                .append("\t").append(String.format("0x%08x", word)).append("\t")
                .append(sym == null ? "" : sym.getName(true)).append("\n");
        }
        Files.writeString(out.resolve("model_lighting_prog_table_dump.tsv"), progHex.toString(), StandardCharsets.UTF_8);

        // Program image 25 ($model_lighting) lives at
        // 0x084E38A0 + 25 * sizeof(GfxImage=0x50) = 0x084E4070.
        // Follow exact references to this object and also inspect every caller
        // of Image_GetProg/Image_AllocProg for a literal 25 argument.
        Address modelLightingImageObject = toAddr("084E4070");
        StringBuilder modelImageObjectRefs = new StringBuilder("from_address\tfunction_entry\tfunction_name\treference_type\n");
        Set<Address> modelImageObjectFunctions = new TreeSet<>();
        ReferenceIterator modelImageRefs = currentProgram.getReferenceManager().getReferencesTo(modelLightingImageObject);
        while (modelImageRefs.hasNext()) {
            monitor.checkCancelled();
            Reference ref = modelImageRefs.next();
            Address from = ref.getFromAddress();
            Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
            modelImageObjectRefs.append(from).append("\t")
                .append(f == null ? "" : f.getEntryPoint().toString()).append("\t")
                .append(f == null ? "" : f.getName(true)).append("\t")
                .append(ref.getReferenceType()).append("\n");
            if (f == null || !modelImageObjectFunctions.add(f.getEntryPoint())) continue;
            String stem = "model_lighting_image25_xref_" + f.getEntryPoint().toString().toLowerCase();
            StringBuilder asm = new StringBuilder();
            for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
            }
            Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
            di.flushCache();
            DecompileResults dr = di.decompileFunction(f, 180, monitor);
            boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
            Files.writeString(out.resolve(stem + ".c"),
                ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
        }
        Files.writeString(out.resolve("model_lighting_image25_xrefs.tsv"), modelImageObjectRefs.toString(), StandardCharsets.UTF_8);

        Address imageAllocProgEntry = toAddr("00A603C0");
        Address imageGetProgEntry = toAddr("00A60450");
        StringBuilder image25Calls = new StringBuilder("callee\tcallsite\tcaller_entry\tcaller_name\tprev1\tprev2\tprev3\tprev4\n");
        Address[] imageProgCallees = { imageAllocProgEntry, imageGetProgEntry };
        String[] imageProgNames = { "Image_AllocProg", "Image_GetProg" };
        for (int ci = 0; ci < imageProgCallees.length; ci++) {
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(imageProgCallees[ci]);
            while (refs.hasNext()) {
                monitor.checkCancelled();
                Reference ref = refs.next();
                Address callsite = ref.getFromAddress();
                Function caller = currentProgram.getFunctionManager().getFunctionContaining(callsite);
                Instruction callInsn = listing.getInstructionAt(callsite);
                Instruction p1 = callInsn == null ? null : callInsn.getPrevious();
                Instruction p2 = p1 == null ? null : p1.getPrevious();
                Instruction p3 = p2 == null ? null : p2.getPrevious();
                Instruction p4 = p3 == null ? null : p3.getPrevious();
                String window = (p4 == null ? "" : p4.toString()) + " | "
                    + (p3 == null ? "" : p3.toString()) + " | "
                    + (p2 == null ? "" : p2.toString()) + " | "
                    + (p1 == null ? "" : p1.toString());
                String lowerWindow = window.toLowerCase();
                if (!(lowerWindow.contains("0x19") || lowerWindow.contains(",19h") || lowerWindow.contains(" 19"))) continue;
                image25Calls.append(imageProgNames[ci]).append("\t").append(callsite).append("\t")
                    .append(caller == null ? "" : caller.getEntryPoint().toString()).append("\t")
                    .append(caller == null ? "" : caller.getName(true)).append("\t")
                    .append(p1 == null ? "" : p1.toString()).append("\t")
                    .append(p2 == null ? "" : p2.toString()).append("\t")
                    .append(p3 == null ? "" : p3.toString()).append("\t")
                    .append(p4 == null ? "" : p4.toString()).append("\n");
                if (caller != null) {
                    String stem = "model_lighting_image25_call_" + caller.getEntryPoint().toString().toLowerCase();
                    StringBuilder asm = new StringBuilder();
                    for (Instruction insn : listing.getInstructions(caller.getBody(), true)) {
                        asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                    }
                    Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                    di.flushCache();
                    DecompileResults dr = di.decompileFunction(caller, 180, monitor);
                    boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                    Files.writeString(out.resolve(stem + ".c"),
                        ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
                }
            }
        }
        Files.writeString(out.resolve("model_lighting_image25_calls.tsv"), image25Calls.toString(), StandardCharsets.UTF_8);

        // Also find all exact references to the g_imageProgNames table itself.
        Address progNamesBase = toAddr("010BF7B0");
        StringBuilder progNamesRefs = new StringBuilder("target\tfrom_address\tfunction_entry\tfunction_name\treference_type\n");
        for (long off = 0; off < 0x100; off += 4) {
            Address target = progNamesBase.add(off);
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
            while (refs.hasNext()) {
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                progNamesRefs.append(target).append("\t").append(from).append("\t")
                    .append(f == null ? "" : f.getEntryPoint().toString()).append("\t")
                    .append(f == null ? "" : f.getName(true)).append("\t")
                    .append(ref.getReferenceType()).append("\n");
            }
        }
        Files.writeString(out.resolve("image_prog_names_xrefs.tsv"), progNamesRefs.toString(), StandardCharsets.UTF_8);

        // Find resource/debug strings tying model lighting to generic image
        // registration. Dump refs and containing functions for any defined
        // string that contains both "model" and "light".
        StringBuilder modelLightStrings = new StringBuilder("string_address\tvalue\tfrom_address\tfunction_entry\tfunction_name\n");
        Set<Address> modelLightStringFunctions = new TreeSet<>();
        for (DataIterator dataIt = listing.getDefinedData(true); dataIt.hasNext(); ) {
            Data data = dataIt.next();
            monitor.checkCancelled();
            Object valueObject = data.getValue();
            if (!(valueObject instanceof String)) continue;
            String value = (String)valueObject;
            String lower = value.toLowerCase();
            if (!(lower.contains("model") && lower.contains("light"))) continue;
            Address stringAddress = data.getAddress();
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(stringAddress);
            boolean any = false;
            while (refs.hasNext()) {
                any = true;
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                modelLightStrings.append(stringAddress).append("\t")
                    .append(value.replace("\t","\\t").replace("\n","\\n")).append("\t")
                    .append(from).append("\t")
                    .append(f == null ? "" : f.getEntryPoint().toString()).append("\t")
                    .append(f == null ? "" : f.getName(true)).append("\n");
                if (f == null || !modelLightStringFunctions.add(f.getEntryPoint())) continue;
                String stem = "model_lighting_string_xref_" + f.getEntryPoint().toString().toLowerCase();
                StringBuilder asm = new StringBuilder();
                for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                }
                Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr = di.decompileFunction(f, 180, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem + ".c"),
                    ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
            }
            if (!any) {
                modelLightStrings.append(stringAddress).append("\t")
                    .append(value.replace("\t","\\t").replace("\n","\\n"))
                    .append("\t\t\t\n");
            }
        }
        Files.writeString(out.resolve("model_lighting_strings.tsv"), modelLightStrings.toString(), StandardCharsets.UTF_8);

        // "$model_lighting" is referenced by data at 0x010BF814. The GfxImage
        // name field recovered from Image_Create3DTexture_PC is +0x48, making
        // 0x010BF7CC the candidate static GfxImage base. Trace both the name
        // field and the inferred object range to find its initialization and
        // assignment into modelLightGlob.image.
        Address modelLightingImageBase = toAddr("010BF7CC");
        Address modelLightingImageNameField = toAddr("010BF814");
        StringBuilder modelImage = new StringBuilder("target\tfrom_address\tfunction_entry\tfunction_name\treference_type\n");
        Set<Address> modelImageFunctions = new TreeSet<>();
        for (Address target = modelLightingImageBase;
             target.compareTo(modelLightingImageBase.add(0x60)) < 0;
             target = target.add(4)) {
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
            while (refs.hasNext()) {
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                modelImage.append(target).append("\t").append(from).append("\t")
                    .append(f == null ? "" : f.getEntryPoint()).append("\t")
                    .append(f == null ? "" : f.getName(true)).append("\t")
                    .append(ref.getReferenceType()).append("\n");
                if (f == null || !modelImageFunctions.add(f.getEntryPoint())) continue;
                String stem = "model_lighting_image_candidate_xref_" + f.getEntryPoint().toString().toLowerCase();
                StringBuilder asm = new StringBuilder();
                for (Instruction insn : listing.getInstructions(f.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                }
                Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr = di.decompileFunction(f, 180, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem + ".c"),
                    ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
            }
        }
        StringBuilder modelImageMemory = new StringBuilder("address\tu32\n");
        for (Address p = modelLightingImageBase;
             p.compareTo(modelLightingImageBase.add(0x60)) < 0;
             p = p.add(4)) {
            int word = currentProgram.getMemory().getInt(p);
            modelImageMemory.append(p).append("\t")
                .append(String.format("0x%08X", word)).append("\n");
        }
        Files.writeString(out.resolve("model_lighting_image_candidate_xrefs.tsv"), modelImage.toString(), StandardCharsets.UTF_8);
        Files.writeString(out.resolve("model_lighting_image_candidate_memory.tsv"), modelImageMemory.toString(), StandardCharsets.UTF_8);

        // Also trace the data slot containing the "$model_lighting" string
        // pointer itself. References to the slot can reveal table/registration
        // code even when nothing points to the inferred struct base.
        StringBuilder modelNameSlotRefs = new StringBuilder("from_address\tfunction_entry\tfunction_name\treference_type\n");
        ReferenceIterator nameSlotRefs = currentProgram.getReferenceManager().getReferencesTo(modelLightingImageNameField);
        while (nameSlotRefs.hasNext()) {
            Reference ref = nameSlotRefs.next();
            Function f = currentProgram.getFunctionManager().getFunctionContaining(ref.getFromAddress());
            modelNameSlotRefs.append(ref.getFromAddress()).append("\t")
                .append(f == null ? "" : f.getEntryPoint()).append("\t")
                .append(f == null ? "" : f.getName(true)).append("\t")
                .append(ref.getReferenceType()).append("\n");
        }
        Files.writeString(out.resolve("model_lighting_name_slot_xrefs.tsv"), modelNameSlotRefs.toString(), StandardCharsets.UTF_8);

        // Recover exact runtime static-model lighting handle allocation.
        // FastFile draw instances serialize lightingHandle=0, so replay needs
        // the same allocation order before modelLightingSampler coordinates
        // can be considered source-closed.
        String[][] staticHandleAnchors = {
            {"00A7BCD0", "R_AllocStaticModelLighting"},
            {"00A7BC60", "R_InitStaticModelLighting"},
            {"00A7BA50", "R_ResetModelLighting"}
        };
        StringBuilder staticHandleCallers = new StringBuilder(
            "callee\tcallee_address\tcallsite\tcaller_entry\tcaller_name\treference_type\n");
        Set<Address> staticHandleCallerFunctions = new TreeSet<>();
        for (String[] item : staticHandleAnchors) {
            Address target = toAddr(item[0]);
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
            while (refs.hasNext()) {
                monitor.checkCancelled();
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function caller = currentProgram.getFunctionManager().getFunctionContaining(from);
                staticHandleCallers.append(item[1]).append("\t").append(target).append("\t")
                    .append(from).append("\t")
                    .append(caller == null ? "" : caller.getEntryPoint()).append("\t")
                    .append(caller == null ? "" : caller.getName(true)).append("\t")
                    .append(ref.getReferenceType()).append("\n");
                if (caller == null || !staticHandleCallerFunctions.add(caller.getEntryPoint())) continue;
                String stem = "static_handle_caller_" + caller.getEntryPoint().toString().toLowerCase();
                StringBuilder asm = new StringBuilder();
                for (Instruction insn : listing.getInstructions(caller.getBody(), true)) {
                    asm.append(insn.getAddress()).append("\t").append(insn).append("\n");
                }
                Files.writeString(out.resolve(stem + ".asm.txt"), asm.toString(), StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr = di.decompileFunction(caller, 240, monitor);
                boolean ok = dr != null && dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem + ".c"),
                    ok ? dr.getDecompiledFunction().getC() : "", StandardCharsets.UTF_8);
            }
        }
        Files.writeString(out.resolve("static_model_lighting_handle_callers.tsv"),
            staticHandleCallers.toString(), StandardCharsets.UTF_8);

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
