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

        // Global caller/xref census for the static-lighting update, image
        // constructor, upload routine and scalar brick writer. This separates
        // one-time static initialization from per-frame dynamic updates.
        String[][] modelLightingAnchors = {
            {"00760BF0","static_update_candidate"},
            {"00761110","model_lighting_image_constructor"},
            {"00760D60","volume_upload"},
            {"00758B20","brick_writer"}
        };
        StringBuilder anchorRefs=new StringBuilder(
            "anchor\tanchor_address\tfrom\ttype\tcaller_entry\tcaller_name\n");
        Set<Address> anchorCallers=new TreeSet<>();
        for(String[] item:modelLightingAnchors){
            Address target=toAddr(item[0]);
            for(Reference ref:currentProgram.getReferenceManager().getReferencesTo(target)){
                Function caller=fm.getFunctionContaining(ref.getFromAddress());
                anchorRefs.append(item[1]).append("\t").append(target).append("\t")
                    .append(ref.getFromAddress()).append("\t")
                    .append(ref.getReferenceType()).append("\t")
                    .append(caller==null?"":caller.getEntryPoint()).append("\t")
                    .append(caller==null?"":caller.getName(true)).append("\n");
                if(caller!=null) anchorCallers.add(caller.getEntryPoint());
            }
        }
        Files.writeString(out.resolve("model_lighting_anchor_callers.tsv"),
            anchorRefs.toString(),StandardCharsets.UTF_8);

        DecompInterface callerDi=new DecompInterface();
        callerDi.openProgram(currentProgram);
        StringBuilder callerSummary=new StringBuilder(
            "entry\tname\tbody_size\tinstructions\tdecompile_completed\n");
        try{
            for(Address entry:anchorCallers){
                monitor.checkCancelled();
                Function f=fm.getFunctionAt(entry);
                if(f==null) continue;
                String stem="anchor_caller_"+entry.toString().toLowerCase();
                StringBuilder asm=new StringBuilder();
                long count=0;
                for(Instruction ins:listing.getInstructions(f.getBody(),true)){
                    asm.append(ins.getAddress()).append("\t").append(ins).append("\n");
                    count++;
                }
                Files.writeString(out.resolve(stem+".asm.txt"),asm.toString(),
                    StandardCharsets.UTF_8);
                callerDi.flushCache();
                DecompileResults dr=callerDi.decompileFunction(f,240,monitor);
                boolean ok=dr!=null && dr.decompileCompleted() &&
                    dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem+".c"),
                    ok?dr.getDecompiledFunction().getC():"",
                    StandardCharsets.UTF_8);
                callerSummary.append(entry).append("\t").append(f.getName(true)).append("\t")
                    .append(f.getBody().getNumAddresses()).append("\t")
                    .append(count).append("\t").append(ok).append("\n");
            }
        } finally {
            callerDi.dispose();
        }
        Files.writeString(out.resolve("model_lighting_anchor_caller_functions.tsv"),
            callerSummary.toString(),StandardCharsets.UTF_8);

        // Export the exact light-grid routines feeding static and dynamic
        // model-lighting allocation. These may also append the 56-direction
        // 0x384 update records as a side effect.
        String[][] lightingFeeders = {
            {"0075AEE0","static_grid_no_dynamic_lights"},
            {"0075A3F0","static_grid_with_dynamic_lights"},
            {"0075BB80","dynamic_model_lighting_at_point"}
        };
        DecompInterface feederDi=new DecompInterface();
        feederDi.openProgram(currentProgram);
        StringBuilder feederSummary=new StringBuilder(
            "label\tentry\tname\tbody_size\tinstructions\tdecompile_completed\n");
        StringBuilder feederRefs=new StringBuilder(
            "label\tentry\tfrom\ttype\ttarget\ttarget_function\n");
        try{
            for(String[] item:lightingFeeders){
                Address entry=toAddr(item[0]);
                Function f=fm.getFunctionAt(entry);
                if(f==null) continue;
                String stem="lighting_feeder_"+entry.toString().toLowerCase();
                StringBuilder asm=new StringBuilder();
                long count=0;
                for(Instruction ins:listing.getInstructions(f.getBody(),true)){
                    asm.append(ins.getAddress()).append("\t").append(ins).append("\n");
                    count++;
                    for(Reference ref:ins.getReferencesFrom()){
                        Address target=ref.getToAddress();
                        Function tf=fm.getFunctionAt(target);
                        feederRefs.append(item[1]).append("\t").append(entry).append("\t")
                            .append(ins.getAddress()).append("\t")
                            .append(ref.getReferenceType()).append("\t")
                            .append(target).append("\t")
                            .append(tf==null?"":tf.getName(true)).append("\n");
                    }
                }
                Files.writeString(out.resolve(stem+".asm.txt"),asm.toString(),
                    StandardCharsets.UTF_8);
                feederDi.flushCache();
                DecompileResults dr=feederDi.decompileFunction(f,300,monitor);
                boolean ok=dr!=null && dr.decompileCompleted() &&
                    dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem+".c"),
                    ok?dr.getDecompiledFunction().getC():"",
                    StandardCharsets.UTF_8);
                feederSummary.append(item[1]).append("\t").append(entry).append("\t")
                    .append(f.getName(true)).append("\t")
                    .append(f.getBody().getNumAddresses()).append("\t")
                    .append(count).append("\t").append(ok).append("\n");
            }
        } finally {
            feederDi.dispose();
        }
        Files.writeString(out.resolve("lighting_feeder_functions.tsv"),
            feederSummary.toString(),StandardCharsets.UTF_8);
        Files.writeString(out.resolve("lighting_feeder_references.tsv"),
            feederRefs.toString(),StandardCharsets.UTF_8);

        // Export the helper chain that constructs/modifies the 56-direction
        // static-model sample array before the feeder appends its 0x384 patch.
        String[][] staticSampleHelpers = {
            {"00758720","build_static_directional_samples"},
            {"007587F0","build_empty_or_fallback_static_samples"},
            {"00762770","apply_static_sample_runtime_lights"}
        };
        DecompInterface helperDi=new DecompInterface();
        helperDi.openProgram(currentProgram);
        StringBuilder helperSummary=new StringBuilder(
            "label\tentry\tname\tbody_size\tinstructions\tdecompile_completed\n");
        StringBuilder helperRefs=new StringBuilder(
            "label\tentry\tfrom\ttype\ttarget\ttarget_function\n");
        try{
            for(String[] item:staticSampleHelpers){
                Address entry=toAddr(item[0]);
                Function f=fm.getFunctionAt(entry);
                if(f==null) continue;
                String stem="static_sample_helper_"+entry.toString().toLowerCase();
                StringBuilder asm=new StringBuilder();
                long count=0;
                for(Instruction ins:listing.getInstructions(f.getBody(),true)){
                    asm.append(ins.getAddress()).append("\t").append(ins).append("\n");
                    count++;
                    for(Reference ref:ins.getReferencesFrom()){
                        Address target=ref.getToAddress();
                        Function tf=fm.getFunctionAt(target);
                        helperRefs.append(item[1]).append("\t").append(entry).append("\t")
                            .append(ins.getAddress()).append("\t")
                            .append(ref.getReferenceType()).append("\t")
                            .append(target).append("\t")
                            .append(tf==null?"":tf.getName(true)).append("\n");
                    }
                }
                Files.writeString(out.resolve(stem+".asm.txt"),asm.toString(),
                    StandardCharsets.UTF_8);
                helperDi.flushCache();
                DecompileResults dr=helperDi.decompileFunction(f,300,monitor);
                boolean ok=dr!=null && dr.decompileCompleted() &&
                    dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem+".c"),
                    ok?dr.getDecompiledFunction().getC():"",
                    StandardCharsets.UTF_8);
                helperSummary.append(item[1]).append("\t").append(entry).append("\t")
                    .append(f.getName(true)).append("\t")
                    .append(f.getBody().getNumAddresses()).append("\t")
                    .append(count).append("\t").append(ok).append("\n");
            }
        } finally {
            helperDi.dispose();
        }
        Files.writeString(out.resolve("static_sample_helper_functions.tsv"),
            helperSummary.toString(),StandardCharsets.UTF_8);
        Files.writeString(out.resolve("static_sample_helper_references.tsv"),
            helperRefs.toString(),StandardCharsets.UTF_8);

        // Expand the complete sample-production chain. These helpers are the
        // remaining semantic boundary between a static draw-instance/light-grid
        // record and the 56 vec4 values copied into modelLightingPatchList.
        String[][] sampleProducerChain = {
            {"00758680","static_sample_basis_accumulate"},
            {"0075A6A0","blend_static_grid_samples"},
            {"0075B1B0","fallback_model_lighting_at_point"},
            {"0075B860","lookup_model_light_grid_entries"},
            {"00762060","accumulate_runtime_light_samples"},
            {"00762280","finalize_runtime_light_samples"},
            {"00762410","test_runtime_light_leaf"},
            {"00762580","prepare_runtime_light_tree"},
            {"00760BF0","submit_static_model_lighting_patches"},
            {"00761200","alloc_static_model_lighting_client"},
            {"007613F0","calc_model_lighting_client"},
            {"007614C0","set_static_model_lighting_client"},
            {"00761640","set_all_static_model_lighting_client"},
            {"00761760","alloc_model_lighting_client"}
        };
        DecompInterface producerDi=new DecompInterface();
        producerDi.openProgram(currentProgram);
        StringBuilder producerSummary=new StringBuilder(
            "label\tentry\tname\tbody_size\tinstructions\tdecompile_completed\n");
        StringBuilder producerRefs=new StringBuilder(
            "label\tentry\tfrom\ttype\ttarget\ttarget_function\n");
        try{
            for(String[] item:sampleProducerChain){
                Address entry=toAddr(item[0]);
                Function f=fm.getFunctionAt(entry);
                if(f==null){
                    producerSummary.append(item[1]).append("\t").append(entry)
                        .append("\t<missing>\t0\t0\tfalse\n");
                    continue;
                }
                String stem="sample_producer_"+entry.toString().toLowerCase();
                StringBuilder asm=new StringBuilder();
                long count=0;
                for(Instruction ins:listing.getInstructions(f.getBody(),true)){
                    asm.append(ins.getAddress()).append("\t").append(ins).append("\n");
                    count++;
                    for(Reference ref:ins.getReferencesFrom()){
                        Address target=ref.getToAddress();
                        Function tf=fm.getFunctionAt(target);
                        producerRefs.append(item[1]).append("\t").append(entry).append("\t")
                            .append(ins.getAddress()).append("\t")
                            .append(ref.getReferenceType()).append("\t")
                            .append(target).append("\t")
                            .append(tf==null?"":tf.getName(true)).append("\n");
                    }
                }
                Files.writeString(out.resolve(stem+".asm.txt"),asm.toString(),
                    StandardCharsets.UTF_8);
                producerDi.flushCache();
                DecompileResults dr=producerDi.decompileFunction(f,360,monitor);
                boolean ok=dr!=null && dr.decompileCompleted() &&
                    dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem+".c"),
                    ok?dr.getDecompiledFunction().getC():"",
                    StandardCharsets.UTF_8);
                producerSummary.append(item[1]).append("\t").append(entry).append("\t")
                    .append(f.getName(true)).append("\t")
                    .append(f.getBody().getNumAddresses()).append("\t")
                    .append(count).append("\t").append(ok).append("\n");
            }
        } finally {
            producerDi.dispose();
        }
        Files.writeString(out.resolve("sample_producer_functions.tsv"),
            producerSummary.toString(),StandardCharsets.UTF_8);
        Files.writeString(out.resolve("sample_producer_references.tsv"),
            producerRefs.toString(),StandardCharsets.UTF_8);

        // Also preserve every direct caller of the two base sample builders so
        // register-passed arguments hidden by Ghidra's current prototypes can
        // be reconstructed from their callsites.
        Address[] sampleBuilderEntries = {toAddr("00758720"),toAddr("007587F0")};
        StringBuilder sampleBuilderCallers=new StringBuilder(
            "callee\tcallsite\tcaller_entry\tcaller_name\n");
        Set<Address> sampleBuilderCallerSet=new TreeSet<>();
        for(Address target:sampleBuilderEntries){
            for(Reference ref:currentProgram.getReferenceManager().getReferencesTo(target)){
                if(!ref.getReferenceType().isCall()) continue;
                Function caller=fm.getFunctionContaining(ref.getFromAddress());
                sampleBuilderCallers.append(target).append("\t")
                    .append(ref.getFromAddress()).append("\t")
                    .append(caller==null?"":caller.getEntryPoint()).append("\t")
                    .append(caller==null?"":caller.getName(true)).append("\n");
                if(caller!=null) sampleBuilderCallerSet.add(caller.getEntryPoint());
            }
        }
        DecompInterface builderCallerDi=new DecompInterface();
        builderCallerDi.openProgram(currentProgram);
        try{
            for(Address entry:sampleBuilderCallerSet){
                Function f=fm.getFunctionAt(entry);
                if(f==null) continue;
                String stem="sample_builder_caller_"+entry.toString().toLowerCase();
                StringBuilder asm=new StringBuilder();
                for(Instruction ins:listing.getInstructions(f.getBody(),true)){
                    asm.append(ins.getAddress()).append("\t").append(ins).append("\n");
                }
                Files.writeString(out.resolve(stem+".asm.txt"),asm.toString(),
                    StandardCharsets.UTF_8);
                builderCallerDi.flushCache();
                DecompileResults dr=builderCallerDi.decompileFunction(f,360,monitor);
                boolean ok=dr!=null && dr.decompileCompleted() &&
                    dr.getDecompiledFunction()!=null;
                Files.writeString(out.resolve(stem+".c"),
                    ok?dr.getDecompiledFunction().getC():"",
                    StandardCharsets.UTF_8);
            }
        } finally {
            builderCallerDi.dispose();
        }
        Files.writeString(out.resolve("sample_builder_callers.tsv"),
            sampleBuilderCallers.toString(),StandardCharsets.UTF_8);

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
