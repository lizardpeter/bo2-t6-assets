// Targeted exact retail-client model-lighting neighborhood export.
//
// Evidence only: addresses are exact for SHA-pinned t6mp.exe. Cross-build names
// remain hypotheses unless independently accepted.
//
//@category T6 Model Lighting

import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class ExportT6CurrentClientModelLighting extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=1) throw new IllegalArgumentException(
            "usage: ExportT6CurrentClientModelLighting.java <out_dir>");
        Path out=Path.of(args[0]);
        Files.createDirectories(out);

        final Address start=toAddr("00760000");
        final Address end=toAddr("00762000");
        Listing listing=currentProgram.getListing();
        FunctionManager fm=currentProgram.getFunctionManager();
        DecompInterface di=new DecompInterface();
        di.openProgram(currentProgram);

        StringBuilder summary=new StringBuilder(
            "entry\tname\tbody_size\tinstructions\tdecompile_completed\n");
        StringBuilder refs=new StringBuilder(
            "function_entry\tfrom\ttype\ttarget\ttarget_function\tdelta_from_function\n");

        try {
            FunctionIterator it=fm.getFunctions(start,true);
            while(it.hasNext()){
                monitor.checkCancelled();
                Function f=it.next();
                Address entry=f.getEntryPoint();
                if(entry.compareTo(end)>=0) break;
                if(entry.compareTo(start)<0) continue;

                String stem="fn_"+entry.toString().toLowerCase();
                StringBuilder asm=new StringBuilder();
                long count=0;
                for(Instruction ins:listing.getInstructions(f.getBody(),true)){
                    asm.append(ins.getAddress()).append("\t").append(ins).append("\n");
                    count++;
                    for(Reference ref:ins.getReferencesFrom()){
                        Address target=ref.getToAddress();
                        Function tf=fm.getFunctionAt(target);
                        refs.append(entry).append("\t")
                            .append(ins.getAddress()).append("\t")
                            .append(ref.getReferenceType()).append("\t")
                            .append(target).append("\t")
                            .append(tf==null?"":tf.getName(true)).append("\t")
                            .append(ins.getAddress().subtract(entry)).append("\n");
                    }
                }
                Files.writeString(out.resolve(stem+".asm.txt"),asm.toString(),
                    StandardCharsets.UTF_8);
                di.flushCache();
                DecompileResults dr=di.decompileFunction(f,120,monitor);
                boolean ok=dr!=null && dr.decompileCompleted() &&
                    dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem+".c"),
                    ok?dr.getDecompiledFunction().getC():"",
                    StandardCharsets.UTF_8);
                summary.append(entry).append("\t").append(f.getName(true)).append("\t")
                    .append(f.getBody().getNumAddresses()).append("\t")
                    .append(count).append("\t").append(ok).append("\n");
            }
        } finally {
            di.dispose();
        }

        Files.writeString(out.resolve("functions.tsv"),summary.toString(),StandardCharsets.UTF_8);
        Files.writeString(out.resolve("references.tsv"),refs.toString(),StandardCharsets.UTF_8);

        // Export the generic image setup routine invoked by the exact
        // _model_lighting initializer, plus every direct callee. This closes
        // the width/height/depth/format/usage argument contract without
        // interpreting numeric enums by guesswork.
        Address imageSetupAddress=toAddr("00780AD0");
        Function imageSetup=fm.getFunctionAt(imageSetupAddress);
        if(imageSetup==null) throw new IllegalStateException("no function at 00780AD0");
        Set<Address> setupTargets=new TreeSet<>();
        setupTargets.add(imageSetup.getEntryPoint());
        for(Instruction ins:listing.getInstructions(imageSetup.getBody(),true)){
            for(Reference ref:ins.getReferencesFrom()){
                if(!ref.getReferenceType().isCall()) continue;
                Function callee=fm.getFunctionAt(ref.getToAddress());
                if(callee!=null) setupTargets.add(callee.getEntryPoint());
            }
        }
        DecompInterface imageDi=new DecompInterface();
        imageDi.openProgram(currentProgram);
        StringBuilder imageSummary=new StringBuilder(
            "entry\tname\tbody_size\tinstructions\tdecompile_completed\n");
        try {
            for(Address entry:setupTargets){
                monitor.checkCancelled();
                Function f=fm.getFunctionAt(entry);
                if(f==null) continue;
                String stem="image_setup_"+entry.toString().toLowerCase();
                StringBuilder asm=new StringBuilder();
                long count=0;
                for(Instruction ins:listing.getInstructions(f.getBody(),true)){
                    asm.append(ins.getAddress()).append("\t").append(ins).append("\n");
                    count++;
                }
                Files.writeString(out.resolve(stem+".asm.txt"),asm.toString(),
                    StandardCharsets.UTF_8);
                imageDi.flushCache();
                DecompileResults dr=imageDi.decompileFunction(f,120,monitor);
                boolean ok=dr!=null && dr.decompileCompleted() &&
                    dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem+".c"),
                    ok?dr.getDecompiledFunction().getC():"",
                    StandardCharsets.UTF_8);
                imageSummary.append(entry).append("\t").append(f.getName(true)).append("\t")
                    .append(f.getBody().getNumAddresses()).append("\t")
                    .append(count).append("\t").append(ok).append("\n");
            }
        } finally {
            imageDi.dispose();
        }
        Files.writeString(out.resolve("image_setup_functions.tsv"),
            imageSummary.toString(),StandardCharsets.UTF_8);

        // Trace exact references to the retail modelLightGlob.image field
        // established by the accepted R_ToggleModelLightingFrame field map.
        Address imageField=toAddr("03A36A9C");
        StringBuilder imageFieldRefs=new StringBuilder(
            "from\ttype\tfunction_entry\tfunction_name\n");
        for(Reference ref:currentProgram.getReferenceManager().getReferencesTo(imageField)){
            Function f=fm.getFunctionContaining(ref.getFromAddress());
            imageFieldRefs.append(ref.getFromAddress()).append("\t")
                .append(ref.getReferenceType()).append("\t")
                .append(f==null?"":f.getEntryPoint()).append("\t")
                .append(f==null?"":f.getName(true)).append("\n");
        }
        Files.writeString(out.resolve("model_lighting_image_field_xrefs.tsv"),
            imageFieldRefs.toString(),StandardCharsets.UTF_8);

        // Exact current-client per-brick model-lighting writer. FUN_00760D60
        // computes the atlas destination for each handle and calls 0x00758B20
        // before copying the CPU volume into the mapped 3D texture. Export this
        // function and all direct callees so the retail float->RGBA8 transfer
        // can be closed from t6mp.exe itself.
        Address brickWriterAddress=toAddr("00758B20");
        Function brickWriter=fm.getFunctionAt(brickWriterAddress);
        if(brickWriter==null) throw new IllegalStateException("no function at 00758B20");
        Set<Address> writerTargets=new TreeSet<>();
        writerTargets.add(brickWriter.getEntryPoint());
        StringBuilder writerRefs=new StringBuilder(
            "function_entry\tfrom\ttype\ttarget\ttarget_function\tdelta_from_function\n");
        for(Instruction ins:listing.getInstructions(brickWriter.getBody(),true)){
            for(Reference ref:ins.getReferencesFrom()){
                Address target=ref.getToAddress();
                Function tf=fm.getFunctionAt(target);
                writerRefs.append(brickWriter.getEntryPoint()).append("\t")
                    .append(ins.getAddress()).append("\t")
                    .append(ref.getReferenceType()).append("\t")
                    .append(target).append("\t")
                    .append(tf==null?"":tf.getName(true)).append("\t")
                    .append(ins.getAddress().subtract(brickWriter.getEntryPoint())).append("\n");
                if(ref.getReferenceType().isCall() && tf!=null){
                    writerTargets.add(tf.getEntryPoint());
                }
            }
        }
        Files.writeString(out.resolve("brick_writer_references.tsv"),writerRefs.toString(),
            StandardCharsets.UTF_8);
        DecompInterface writerDi=new DecompInterface();
        writerDi.openProgram(currentProgram);
        StringBuilder writerSummary=new StringBuilder(
            "entry\tname\tbody_size\tinstructions\tdecompile_completed\n");
        try{
            for(Address entry:writerTargets){
                monitor.checkCancelled();
                Function f=fm.getFunctionAt(entry);
                if(f==null) continue;
                String stem="brick_writer_"+entry.toString().toLowerCase();
                StringBuilder asm=new StringBuilder();
                long count=0;
                for(Instruction ins:listing.getInstructions(f.getBody(),true)){
                    asm.append(ins.getAddress()).append("\t").append(ins).append("\n");
                    count++;
                }
                Files.writeString(out.resolve(stem+".asm.txt"),asm.toString(),
                    StandardCharsets.UTF_8);
                writerDi.flushCache();
                DecompileResults dr=writerDi.decompileFunction(f,240,monitor);
                boolean ok=dr!=null && dr.decompileCompleted() &&
                    dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem+".c"),
                    ok?dr.getDecompiledFunction().getC():"",
                    StandardCharsets.UTF_8);
                writerSummary.append(entry).append("\t").append(f.getName(true)).append("\t")
                    .append(f.getBody().getNumAddresses()).append("\t")
                    .append(count).append("\t").append(ok).append("\n");
            }
        } finally {
            writerDi.dispose();
        }
        Files.writeString(out.resolve("brick_writer_functions.tsv"),
            writerSummary.toString(),StandardCharsets.UTF_8);

        // Exact scalar constants read by the brick writer. Preserve raw bits
        // and decoded float values so the native reimplementation can match
        // CVTTSS2SI/truncation semantics without decimal-rounding ambiguity.
        String[][] writerConstants = {
            {"00BFA448","clamp_max"},
            {"00C6982C","pre_sqrt_scale"},
            {"00C0FAEC","post_sqrt_scale"},
            {"00BD8A88","interior_rgb_source"}
        };
        StringBuilder writerConstantReport = new StringBuilder(
            "name\taddress\tu32_bits\tf32\n");
        for(String[] item:writerConstants){
            Address address=toAddr(item[0]);
            int bits=currentProgram.getMemory().getInt(address);
            float value=Float.intBitsToFloat(bits);
            writerConstantReport.append(item[1]).append("\t").append(address).append("\t")
                .append(String.format("0x%08X",bits)).append("\t")
                .append(Float.toString(value)).append("\n");
        }
        Files.writeString(out.resolve("brick_writer_constants.tsv"),
            writerConstantReport.toString(),StandardCharsets.UTF_8);

        // Trace the mapped-volume upload function and its CPU staging buffer.
        // 0x00760D60 maps the source texture, calls the brick writer repeatedly,
        // then memcpy's staging bytes into the mapped resource. The producer of
        // 0x03A36ADC determines whether static bricks may be reconstructed
        // directly from colorsIndex or require the same runtime SH/light-grid
        // path, so export every caller/xref before promoting that assumption.
        Address uploadAddress=toAddr("00760D60");
        Function upload=fm.getFunctionAt(uploadAddress);
        if(upload==null) throw new IllegalStateException("no function at 00760D60");
        StringBuilder uploadCallers=new StringBuilder(
            "from\ttype\tcaller_entry\tcaller_name\n");
        Set<Address> uploadCallerTargets=new TreeSet<>();
        for(Reference ref:currentProgram.getReferenceManager().getReferencesTo(uploadAddress)){
            Function caller=fm.getFunctionContaining(ref.getFromAddress());
            uploadCallers.append(ref.getFromAddress()).append("\t")
                .append(ref.getReferenceType()).append("\t")
                .append(caller==null?"":caller.getEntryPoint()).append("\t")
                .append(caller==null?"":caller.getName(true)).append("\n");
            if(caller!=null) uploadCallerTargets.add(caller.getEntryPoint());
        }
        Files.writeString(out.resolve("volume_upload_callers.tsv"),
            uploadCallers.toString(),StandardCharsets.UTF_8);

        Address stagingPtr=toAddr("03A36ADC");
        StringBuilder stagingRefs=new StringBuilder(
            "from\ttype\tfunction_entry\tfunction_name\n");
        Set<Address> stagingFunctions=new TreeSet<>();
        for(Reference ref:currentProgram.getReferenceManager().getReferencesTo(stagingPtr)){
            Function f=fm.getFunctionContaining(ref.getFromAddress());
            stagingRefs.append(ref.getFromAddress()).append("\t")
                .append(ref.getReferenceType()).append("\t")
                .append(f==null?"":f.getEntryPoint()).append("\t")
                .append(f==null?"":f.getName(true)).append("\n");
            if(f!=null) stagingFunctions.add(f.getEntryPoint());
        }
        Files.writeString(out.resolve("volume_staging_xrefs.tsv"),
            stagingRefs.toString(),StandardCharsets.UTF_8);

        Set<Address> volumeTraceTargets=new TreeSet<>();
        volumeTraceTargets.addAll(uploadCallerTargets);
        volumeTraceTargets.addAll(stagingFunctions);
        DecompInterface volumeDi=new DecompInterface();
        volumeDi.openProgram(currentProgram);
        StringBuilder volumeSummary=new StringBuilder(
            "entry\tname\tbody_size\tinstructions\tdecompile_completed\n");
        try{
            for(Address entry:volumeTraceTargets){
                monitor.checkCancelled();
                Function f=fm.getFunctionAt(entry);
                if(f==null) continue;
                String stem="volume_trace_"+entry.toString().toLowerCase();
                StringBuilder asm=new StringBuilder();
                long count=0;
                for(Instruction ins:listing.getInstructions(f.getBody(),true)){
                    asm.append(ins.getAddress()).append("\t").append(ins).append("\n");
                    count++;
                }
                Files.writeString(out.resolve(stem+".asm.txt"),asm.toString(),
                    StandardCharsets.UTF_8);
                volumeDi.flushCache();
                DecompileResults dr=volumeDi.decompileFunction(f,240,monitor);
                boolean ok=dr!=null && dr.decompileCompleted() &&
                    dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem+".c"),
                    ok?dr.getDecompiledFunction().getC():"",
                    StandardCharsets.UTF_8);
                volumeSummary.append(entry).append("\t").append(f.getName(true)).append("\t")
                    .append(f.getBody().getNumAddresses()).append("\t")
                    .append(count).append("\t").append(ok).append("\n");
            }
        } finally {
            volumeDi.dispose();
        }
        Files.writeString(out.resolve("volume_trace_functions.tsv"),
            volumeSummary.toString(),StandardCharsets.UTF_8);

        // Explicitly record the already-accepted anchor and the object-local
        // address-delta hypotheses it suggests. This file is not identity proof.
        String hypotheses=
            "server\tclient_candidate\tname\tstate\n"+
            "00A7B600\t00760B30\tR_ToggleModelLightingFrame\taccepted-cross-build-anchor\n"+
            "00A7B540\t00760A70\tR_AllocModelLightingPixel\tobject-local-delta-hypothesis\n"+
            "00A7B7B0\t00760CE0\tR_SetupDynamicModelLighting\tobject-local-delta-hypothesis\n"+
            "00A7B890\t00760DC0\tR_InitModelLightingGlobals\tobject-local-delta-hypothesis\n"+
            "00A7BA50\t00760F80\tR_ResetModelLighting\tobject-local-delta-hypothesis\n"+
            "00A7BC70\t007611A0\tR_SetModelLightingForSource\tobject-local-delta-hypothesis\n"+
            "00A7BCD0\t00761200\tR_AllocStaticModelLighting\tobject-local-delta-hypothesis\n"+
            "00A7BEC0\t007613F0\tR_CalcModelLighting\tobject-local-delta-hypothesis\n"+
            "00A7BF90\t007614C0\tR_SetStaticModelLighting\tobject-local-delta-hypothesis\n"+
            "00A7C110\t00761640\tR_SetAllStaticModelLighting\tobject-local-delta-hypothesis\n"+
            "00A7C230\t00761760\tR_AllocModelLighting\tobject-local-delta-hypothesis\n";
        Files.writeString(out.resolve("cross_build_hypotheses.tsv"),hypotheses,
            StandardCharsets.UTF_8);
    }
}
