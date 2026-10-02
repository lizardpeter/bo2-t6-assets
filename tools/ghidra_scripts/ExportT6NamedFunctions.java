// Export exact PDB-backed T6 server functions selected by Ghidra function name.
//
//@category T6 Server PDB

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;

public class ExportT6NamedFunctions extends GhidraScript {
    private static class Row {
        final String id, name, tier;
        Row(String id, String name, String tier) { this.id=id; this.name=name; this.tier=tier; }
    }

    @Override
    protected void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length < 2 || args.length > 3)
            throw new IllegalArgumentException("usage: <selection.tsv> <output-dir> [timeout-seconds]");
        Path selection=Paths.get(args[0]).toAbsolutePath().normalize();
        Path output=Paths.get(args[1]).toAbsolutePath().normalize();
        int timeout=args.length==3 ? Integer.parseInt(args[2]) : 30;
        Files.createDirectories(output.resolve("decompile"));
        Files.createDirectories(output.resolve("disassembly"));

        List<Row> rows=readRows(selection);
        List<Function> functions=new ArrayList<>();
        FunctionIterator fit=currentProgram.getFunctionManager().getFunctions(true);
        while(fit.hasNext()) functions.add(fit.next());

        DecompInterface dc=new DecompInterface();
        dc.toggleCCode(true);
        dc.toggleSyntaxTree(true);
        dc.setSimplificationStyle("decompile");
        if(!dc.openProgram(currentProgram)) throw new IllegalStateException("decompiler open failed");

        try(BufferedWriter out=Files.newBufferedWriter(output.resolve("results.tsv"), StandardCharsets.UTF_8)) {
            out.write("function_id\trequested_name\ttier\tmatch_count\tentry\tname\tfull_name\tbody_addresses\tdecompile_completed\tmessage\n");
            for(Row row: rows) {
                monitor.checkCancelled();
                List<Function> matches=new ArrayList<>();
                for(Function f:functions) {
                    String simple=f.getName();
                    String full=f.getName(true);
                    if(simple.equals(row.name) || full.equals(row.name) || full.endsWith("::"+row.name))
                        matches.add(f);
                }
                if(matches.size()!=1) {
                    out.write(tsv(row.id,row.name,row.tier,Integer.toString(matches.size()),"","","","", "false",
                        matches.isEmpty() ? "no unique PDB-backed function name match" : "ambiguous function name"));
                    out.newLine();
                    continue;
                }
                Function f=matches.get(0);
                exportDisassembly(row.id,f,output.resolve("disassembly"));
                DecompileResults dr=dc.decompileFunction(f,timeout,monitor);
                boolean done=dr.decompileCompleted();
                String c=done && dr.getDecompiledFunction()!=null ? dr.getDecompiledFunction().getC() : "";
                String metadata=
                    "/* GENERATED/UNREVIEWED GHIDRA OUTPUT -- PDB-BACKED SERVER EVIDENCE\n"+
                    " * function_id: "+row.id+"\n"+
                    " * requested_name: "+row.name+"\n"+
                    " * entry_point: "+f.getEntryPoint()+"\n"+
                    " * ghidra_name: "+f.getName(true)+"\n"+
                    " * body_addresses: "+f.getBody().getNumAddresses()+"\n"+
                    " */\n\n";
                Files.writeString(output.resolve("decompile").resolve(row.id+".c"),metadata+c,StandardCharsets.UTF_8);
                out.write(tsv(row.id,row.name,row.tier,"1",f.getEntryPoint().toString(),f.getName(),f.getName(true),
                    Long.toString(f.getBody().getNumAddresses()),Boolean.toString(done),sanitize(dr.getErrorMessage())));
                out.newLine();
            }
        } finally {
            dc.dispose();
        }
    }

    private List<Row> readRows(Path path) throws Exception {
        List<Row> rows=new ArrayList<>();
        try(BufferedReader in=Files.newBufferedReader(path,StandardCharsets.UTF_8)) {
            String h=in.readLine();
            if(h==null || !h.startsWith("function_id\trequested_name\ttier"))
                throw new IllegalArgumentException("unexpected selection header: "+h);
            String line;
            while((line=in.readLine())!=null) {
                if(line.isBlank()) continue;
                String[] c=line.split("\\t",-1);
                if(c.length<3) throw new IllegalArgumentException("bad selection row: "+line);
                rows.add(new Row(c[0],c[1],c[2]));
            }
        }
        return rows;
    }

    private void exportDisassembly(String id, Function f, Path dir) throws Exception {
        StringBuilder b=new StringBuilder();
        b.append("# PDB-BACKED SERVER FUNCTION\n# entry: ").append(f.getEntryPoint())
         .append("\n# name: ").append(f.getName(true))
         .append("\n# body_addresses: ").append(f.getBody().getNumAddresses()).append("\n\n");
        InstructionIterator it=currentProgram.getListing().getInstructions(f.getBody(),true);
        while(it.hasNext()) {
            Instruction ins=it.next();
            b.append(ins.getAddress()).append('\t').append(hex(ins.getBytes())).append('\t').append(ins).append('\n');
        }
        Files.writeString(dir.resolve(id+".asm"),b.toString(),StandardCharsets.UTF_8);
    }

    private String hex(byte[] bytes) {
        StringBuilder b=new StringBuilder();
        for(byte x:bytes) b.append(String.format("%02x",x&0xff));
        return b.toString();
    }

    private String tsv(String... values) {
        List<String> clean=new ArrayList<>();
        for(String v:values) clean.add(sanitize(v));
        return String.join("\t",clean);
    }

    private String sanitize(String v) {
        if(v==null) return "";
        return v.replace('\t',' ').replace('\r',' ').replace('\n',' ');
    }
}
