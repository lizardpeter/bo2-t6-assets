// Export detailed, function-relative references for selected T6 cross-build candidates.
//
// Input TSV columns: pair_id, va
// Output directory receives functions.tsv, calls.tsv, data_refs.tsv, strings.tsv.
//
// Evidence only: this script never renames, retypes, or modifies the program.
//
//@category T6 Cross Build

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;

public class ExportT6CandidateDetails extends GhidraScript {
    private BufferedWriter funcs,calls,dataRefs,strings;
    private FunctionManager fm;
    private Listing listing;

    @Override
    protected void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2) throw new IllegalArgumentException(
            "usage: ExportT6CandidateDetails.java <selection.tsv> <output-dir>");
        Path selection=Paths.get(args[0]).toAbsolutePath().normalize();
        Path out=Paths.get(args[1]).toAbsolutePath().normalize();
        Files.createDirectories(out);

        fm=currentProgram.getFunctionManager();
        listing=currentProgram.getListing();
        funcs=writer(out.resolve("functions.tsv"));
        calls=writer(out.resolve("calls.tsv"));
        dataRefs=writer(out.resolve("data_refs.tsv"));
        strings=writer(out.resolve("strings.tsv"));
        funcs.write("pair_id\trequested_va\tfound\tentry_va\tname\tinstruction_count\tbody_address_count\n");
        calls.write("pair_id\tfunction_va\tfunction_name\tfrom_offset\tfrom_va\tmnemonic\tref_type\ttarget_va\ttarget_function_va\ttarget_function_name\n");
        dataRefs.write("pair_id\tfunction_va\tfunction_name\tfrom_offset\tfrom_va\tmnemonic\tref_type\ttarget_va\tdata_type\n");
        strings.write("pair_id\tfunction_va\tfunction_name\tfrom_offset\tfrom_va\ttarget_va\ttext\n");

        int selected=0,found=0;
        try(BufferedReader r=Files.newBufferedReader(selection,StandardCharsets.UTF_8)){
            String line=r.readLine();
            if(line==null || !line.equals("pair_id\tva"))
                throw new IllegalArgumentException("unexpected selection header: "+line);
            while((line=r.readLine())!=null){
                monitor.checkCancelled();
                if(line.trim().isEmpty()) continue;
                String[] p=line.split("\t",-1);
                if(p.length!=2) throw new IllegalArgumentException("bad selection row: "+line);
                selected++;
                String pair=p[0];
                Address requested=toAddr(p[1]);
                Function f=fm.getFunctionAt(requested);
                if(f==null){
                    funcs.write(clean(pair)+"\t"+clean(requested.toString())+"\tfalse\t\t\t0\t0\n");
                    continue;
                }
                found++;
                exportFunction(pair,requested,f);
            }
        } finally {
            funcs.close(); calls.close(); dataRefs.close(); strings.close();
        }
        println("Candidate details: selected="+selected+" found="+found);
        if(selected!=found) throw new IllegalStateException(
            "selection did not resolve exactly: selected="+selected+" found="+found);
    }

    private void exportFunction(String pair,Address requested,Function f) throws Exception {
        int insCount=0;
        InstructionIterator countIt=listing.getInstructions(f.getBody(),true);
        while(countIt.hasNext()){countIt.next();insCount++;}
        funcs.write(String.join("\t",
            clean(pair),clean(requested.toString()),"true",clean(f.getEntryPoint().toString()),
            clean(f.getName(true)),Integer.toString(insCount),Long.toString(f.getBody().getNumAddresses())));
        funcs.newLine();

        InstructionIterator ii=listing.getInstructions(f.getBody(),true);
        while(ii.hasNext()){
            monitor.checkCancelled();
            Instruction ins=ii.next();
            long off=ins.getAddress().subtract(f.getEntryPoint());
            for(Reference ref:ins.getReferencesFrom()){
                if(ref.getReferenceType().isCall()){
                    Function target=fm.getFunctionAt(ref.getToAddress());
                    if(target==null) target=fm.getFunctionContaining(ref.getToAddress());
                    calls.write(String.join("\t",
                        clean(pair),clean(f.getEntryPoint().toString()),clean(f.getName(true)),
                        hexOff(off),clean(ins.getAddress().toString()),clean(ins.getMnemonicString()),
                        clean(ref.getReferenceType().toString()),clean(ref.getToAddress().toString()),
                        target==null?"":clean(target.getEntryPoint().toString()),
                        target==null?"":clean(target.getName(true))));
                    calls.newLine();
                }
                if(ref.getReferenceType().isData()){
                    Data d=listing.getDefinedDataContaining(ref.getToAddress());
                    String dt=d==null?"":d.getDataType().getDisplayName();
                    dataRefs.write(String.join("\t",
                        clean(pair),clean(f.getEntryPoint().toString()),clean(f.getName(true)),
                        hexOff(off),clean(ins.getAddress().toString()),clean(ins.getMnemonicString()),
                        clean(ref.getReferenceType().toString()),clean(ref.getToAddress().toString()),clean(dt)));
                    dataRefs.newLine();
                    if(d!=null){
                        Object val=d.getValue();
                        if(val instanceof String){
                            strings.write(String.join("\t",
                                clean(pair),clean(f.getEntryPoint().toString()),clean(f.getName(true)),
                                hexOff(off),clean(ins.getAddress().toString()),clean(ref.getToAddress().toString()),
                                clean((String)val)));
                            strings.newLine();
                        }
                    }
                }
            }
        }
    }

    private BufferedWriter writer(Path p) throws Exception {
        return Files.newBufferedWriter(p,StandardCharsets.UTF_8,
            StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE);
    }

    private String hexOff(long x){ return String.format("0x%x",x); }

    private String clean(String s){
        if(s==null) return "";
        return s.replace('\t',' ').replace('\r',' ').replace('\n',' ');
    }
}
