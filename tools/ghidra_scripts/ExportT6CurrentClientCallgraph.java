// Export the complete direct-call reference census for the exact T6 current client.
//
// Generated evidence only. Targets are marked exact only when the CALL destination is
// exactly a Ghidra-recognized function entry in the same program.
//
//@category T6 Current Client

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;

public class ExportT6CurrentClientCallgraph extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=1){
            throw new IllegalArgumentException("usage: ExportT6CurrentClientCallgraph.java <output.tsv>");
        }
        Path out=Paths.get(args[0]).toAbsolutePath().normalize();
        Files.createDirectories(out.getParent());

        FunctionManager fm=currentProgram.getFunctionManager();
        Listing listing=currentProgram.getListing();
        long functionCount=0;
        long callRefCount=0;
        long exactTargetCount=0;

        try(BufferedWriter w=Files.newBufferedWriter(
                out,StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE)){
            w.write("source_entry\tsource_name\tcallsite\treference_type\ttarget_address\t"+
                    "target_exact_function\ttarget_entry\ttarget_name\ttarget_is_thunk\n");

            FunctionIterator it=fm.getFunctions(true);
            while(it.hasNext()){
                monitor.checkCancelled();
                Function source=it.next();
                functionCount++;
                InstructionIterator ii=listing.getInstructions(source.getBody(),true);
                while(ii.hasNext()){
                    Instruction ins=ii.next();
                    for(Reference ref:ins.getReferencesFrom()){
                        if(!ref.getReferenceType().isCall()) continue;
                        callRefCount++;
                        Address to=ref.getToAddress();
                        Function target=to==null ? null : fm.getFunctionAt(to);
                        boolean exact=target!=null;
                        if(exact) exactTargetCount++;
                        w.write(String.join("\t",
                            sanitize(source.getEntryPoint().toString()),
                            sanitize(source.getName(true)),
                            sanitize(ins.getAddress().toString()),
                            sanitize(ref.getReferenceType().toString()),
                            to==null ? "" : sanitize(to.toString()),
                            Boolean.toString(exact),
                            exact ? sanitize(target.getEntryPoint().toString()) : "",
                            exact ? sanitize(target.getName(true)) : "",
                            exact ? Boolean.toString(target.isThunk()) : ""
                        ));
                        w.newLine();
                    }
                }
            }
        }
        println("Exported "+callRefCount+" CALL references from "+functionCount+
                " functions; "+exactTargetCount+" resolve to exact function entries.");
    }

    private String sanitize(String value){
        if(value==null) return "";
        return value.replace('\t',' ').replace('\r',' ').replace('\n',' ');
    }
}
