// Export a deterministic whole-program function catalog for the exact T6 PC Server.
//
// The catalog is generated evidence, not reconstructed source. Function identities remain
// build-scoped original PC Server occurrences until independently joined to semantic variants.
//
//@category T6 PC Server

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;

public class ExportT6ServerFullCatalog extends GhidraScript {

    @Override
    protected void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=1){
            throw new IllegalArgumentException("usage: ExportT6ServerFullCatalog.java <output.tsv>");
        }
        Path out=Paths.get(args[0]).toAbsolutePath().normalize();
        Files.createDirectories(out.getParent());

        FunctionManager fm=currentProgram.getFunctionManager();
        Listing listing=currentProgram.getListing();

        try(BufferedWriter w=Files.newBufferedWriter(
                out,StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE)){
            w.write("entry_va\tname\tprototype\tcalling_convention\tparameter_count\tlocal_count"+
                    "\tbody_address_count\tinstruction_count\tcall_reference_count\treference_count"+
                    "\tis_thunk\tinstruction_bytes_sha256\tmax_address\n");

            FunctionIterator it=fm.getFunctions(true);
            long count=0;
            while(it.hasNext()){
                monitor.checkCancelled();
                Function f=it.next();
                MessageDigest md=MessageDigest.getInstance("SHA-256");
                long instructionCount=0;
                long callRefs=0;
                long refs=0;
                Address max=null;

                InstructionIterator ii=listing.getInstructions(f.getBody(),true);
                while(ii.hasNext()){
                    Instruction ins=ii.next();
                    instructionCount++;
                    byte[] bytes=ins.getBytes();
                    md.update(bytes);
                    max=ins.getMaxAddress();
                    for(Reference ref:ins.getReferencesFrom()){
                        refs++;
                        if(ref.getReferenceType().isCall()){
                            callRefs++;
                        }
                    }
                }

                String hash=hex(md.digest());
                w.write(String.join("\t",
                    sanitize(f.getEntryPoint().toString()),
                    sanitize(f.getName(true)),
                    sanitize(f.getPrototypeString(true,true)),
                    sanitize(f.getCallingConventionName()),
                    Integer.toString(f.getParameterCount()),
                    Integer.toString(f.getLocalVariables().length),
                    Long.toString(f.getBody().getNumAddresses()),
                    Long.toString(instructionCount),
                    Long.toString(callRefs),
                    Long.toString(refs),
                    Boolean.toString(f.isThunk()),
                    hash,
                    max==null ? "" : sanitize(max.toString())
                ));
                w.newLine();
                count++;
            }
            println("Exported "+count+" exact Ghidra function catalog rows to "+out);
        }
    }

    private String hex(byte[] bytes){
        StringBuilder b=new StringBuilder(bytes.length*2);
        for(byte x:bytes) b.append(String.format("%02x",x&0xff));
        return b.toString();
    }

    private String sanitize(String value){
        if(value==null) return "";
        return value.replace('\t',' ').replace('\r',' ').replace('\n',' ');
    }
}
