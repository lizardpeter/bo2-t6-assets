// Export a deterministic batch of exact BO2 original PC Server functions as unreviewed evidence.
//
//@category T6 PC Server

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;

public class ExportT6ServerFullBatch extends GhidraScript {
    private static final int DEFAULT_DECOMPILE_TIMEOUT_SECONDS=15;

    @Override
    protected void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2 && args.length!=3) throw new IllegalArgumentException(
            "usage: ExportT6ServerFullBatch.java <selection.tsv> <output-dir> [timeout-seconds]");

        Path selection=Paths.get(args[0]).toAbsolutePath().normalize();
        Path output=Paths.get(args[1]).toAbsolutePath().normalize();
        int decompileTimeout=args.length==3 ? Integer.parseInt(args[2]) : DEFAULT_DECOMPILE_TIMEOUT_SECONDS;
        if(decompileTimeout<1) throw new IllegalArgumentException("timeout must be positive");
        Path cDir=output.resolve("unreviewed");
        Path asmDir=output.resolve("disassembly");
        Files.createDirectories(cDir);
        Files.createDirectories(asmDir);

        List<Row> rows=readRows(selection);
        FunctionManager fm=currentProgram.getFunctionManager();
        Listing listing=currentProgram.getListing();
        SymbolTable symbols=currentProgram.getSymbolTable();

        DecompInterface dc=new DecompInterface();
        dc.toggleCCode(true);
        dc.toggleSyntaxTree(true);
        dc.setSimplificationStyle("decompile");
        if(!dc.openProgram(currentProgram)) throw new IllegalStateException("decompiler open failed");

        try(BufferedWriter results=Files.newBufferedWriter(
                output.resolve("results.tsv"),StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE);
            BufferedWriter refs=Files.newBufferedWriter(
                output.resolve("references.tsv"),StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE)) {

            results.write("function_id\trequested_va\ttier\tfound_exact\tresolved_entry\tghidra_name\tprototype"+
                          "\tparameter_count\tlocal_count\tcalling_convention\tdecompile_completed"+
                          "\tdecompiler_message\telapsed_ms\tc_bytes\tinstruction_count\treference_count\tasm_bytes\n");
            refs.write("function_id\tfrom_address\tmnemonic\toperand_index\treference_type\tto_address\ttarget_symbol\ttarget_data_type\n");

            for(Row row:rows){
                monitor.checkCancelled();
                Function f=resolveFunction(fm,row.va);
                if(f==null){
                    writeResult(results,row,false,"","","",0,0,"",false,
                        row.va.startsWith("name:")
                            ? "No unique exact Ghidra function with requested name"
                            : "No exact Ghidra function at requested address",
                        0,0,0,0,0);
                    continue;
                }

                Evidence ev=exportDisassembly(row.id,f,listing,symbols,asmDir,refs);
                long start=System.nanoTime();
                DecompileResults dr=dc.decompileFunction(f,decompileTimeout,monitor);
                long elapsed=(System.nanoTime()-start)/1_000_000L;
                boolean done=dr.decompileCompleted();
                String msg=dr.getErrorMessage();
                String c="";
                if(done && dr.getDecompiledFunction()!=null) c=dr.getDecompiledFunction().getC();

                String metadata=
                    "/* GENERATED/UNREVIEWED GHIDRA OUTPUT -- NOT RECONSTRUCTED SOURCE\n"+
                    " * function_id: "+row.id+"\n"+
                    " * requested_va: "+row.va+"\n"+
                    " * tier: "+row.tier+"\n"+
                    " * exact_pc_server_sha256: f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d\n"+
                    " * entry_point: "+f.getEntryPoint()+"\n"+
                    " * ghidra_name: "+f.getName(true)+"\n"+
                    " * decompile_completed: "+done+"\n"+
                    " * decompiler_message: "+sanitize(msg)+"\n"+
                    " */\n\n";
                String fileName=row.id.substring(row.id.lastIndexOf(':')+1)+".c";
                Files.writeString(cDir.resolve(fileName),metadata+c,StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE);

                writeResult(results,row,true,f.getEntryPoint().toString(),f.getName(true),
                    f.getPrototypeString(true,true),f.getParameterCount(),f.getLocalVariables().length,
                    f.getCallingConventionName(),done,msg,elapsed,
                    c.getBytes(StandardCharsets.UTF_8).length,
                    ev.instructions,ev.references,ev.asmBytes);
            }
        }
        dc.dispose();
        println("Exported "+rows.size()+" BO2 original PC Server Ghidra batch rows with timeout "+decompileTimeout+"s");
    }

    private Function resolveFunction(FunctionManager fm,String selector){
        if(selector.startsWith("name:")){
            String wanted=selector.substring("name:".length());
            Function found=null;
            for(Function candidate:fm.getFunctions(true)){
                if(!(wanted.equals(candidate.getName()) || wanted.equals(candidate.getName(true)))) continue;
                if(found!=null && !found.getEntryPoint().equals(candidate.getEntryPoint())) return null;
                found=candidate;
            }
            return found;
        }
        Address requested=toAddr(Long.decode(selector));
        return fm.getFunctionAt(requested);
    }

    private List<Row> readRows(Path p) throws Exception {
        List<Row> rows=new ArrayList<>();
        try(BufferedReader r=Files.newBufferedReader(p,StandardCharsets.UTF_8)){
            String h=r.readLine();
            if(h==null || !h.startsWith("function_id\trequested_va\ttier\t"))
                throw new IllegalArgumentException("unexpected selection header: "+h);
            String line;
            while((line=r.readLine())!=null){
                if(line.isEmpty()) continue;
                String[] c=line.split("\t",-1);
                if(c.length<3) throw new IllegalArgumentException("bad selection row");
                rows.add(new Row(c[0],c[1],c[2]));
            }
        }
        return rows;
    }

    private Evidence exportDisassembly(
            String id,Function f,Listing listing,SymbolTable symbols,Path asmDir,BufferedWriter refs) throws Exception {
        StringBuilder text=new StringBuilder();
        text.append("# GENERATED EXACT GHIDRA LISTING -- EVIDENCE ONLY\n");
        text.append("# function_id: ").append(id).append('\n');
        text.append("# entry_point: ").append(f.getEntryPoint()).append("\n\n");
        int insCount=0,refCount=0;
        InstructionIterator it=listing.getInstructions(f.getBody(),true);
        while(it.hasNext()){
            Instruction ins=it.next();
            insCount++;
            text.append(ins.getAddress()).append('\t').append(hex(ins.getBytes())).append('\t').append(ins).append('\n');
            for(Reference ref:ins.getReferencesFrom()){
                refCount++;
                Symbol s=symbols.getPrimarySymbol(ref.getToAddress());
                Data d=listing.getDefinedDataContaining(ref.getToAddress());
                refs.write(String.join("\t",
                    sanitize(id),sanitize(ins.getAddress().toString()),sanitize(ins.getMnemonicString()),
                    Integer.toString(ref.getOperandIndex()),sanitize(ref.getReferenceType().toString()),
                    sanitize(ref.getToAddress().toString()),sanitize(s==null?"":s.getName(true)),
                    sanitize(d==null?"":d.getDataType().getDisplayName())));
                refs.newLine();
            }
        }
        String fileName=id.substring(id.lastIndexOf(':')+1)+".asm";
        Files.writeString(asmDir.resolve(fileName),text.toString(),StandardCharsets.UTF_8,
            StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE);
        return new Evidence(insCount,refCount,text.toString().getBytes(StandardCharsets.UTF_8).length);
    }

    private void writeResult(BufferedWriter w,Row row,boolean found,String entry,String name,String proto,
        int params,int locals,String cc,boolean done,String msg,long ms,int cBytes,int instructions,int refs,int asmBytes) throws Exception {
        w.write(String.join("\t",
            sanitize(row.id),sanitize(row.va),sanitize(row.tier),Boolean.toString(found),sanitize(entry),
            sanitize(name),sanitize(proto),Integer.toString(params),Integer.toString(locals),sanitize(cc),
            Boolean.toString(done),sanitize(msg),Long.toString(ms),Integer.toString(cBytes),
            Integer.toString(instructions),Integer.toString(refs),Integer.toString(asmBytes)));
        w.newLine();
    }

    private String hex(byte[] b){
        StringBuilder s=new StringBuilder(b.length*2);
        for(byte x:b) s.append(String.format("%02x",x&0xff));
        return s.toString();
    }
    private String sanitize(String v){
        if(v==null) return "";
        return v.replace('\t',' ').replace('\r',' ').replace('\n',' ');
    }
    private static class Row {
        final String id,va,tier;
        Row(String id,String va,String tier){this.id=id;this.va=va;this.tier=tier;}
    }
    private static class Evidence {
        final int instructions,references,asmBytes;
        Evidence(int a,int b,int c){instructions=a;references=b;asmBytes=c;}
    }
}
