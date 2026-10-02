// Apply provenance-safe server->retail cross-build naming hints to the exact T6 current-client Ghidra project.
//
// This script intentionally does NOT import server PDB types, prototypes, globals, locals,
// source lines, namespaces, data addresses, or struct layouts. A hint is applied only after
// recomputing the exact current-client function instruction-byte SHA-256 inside Ghidra.
//
//@category T6 Current Client

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.SourceType;

public class ApplyT6CrossBuildHints extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2) throw new IllegalArgumentException(
            "usage: ApplyT6CrossBuildHints.java <hints.tsv> <report.tsv>");

        Path hints=Paths.get(args[0]).toAbsolutePath().normalize();
        Path report=Paths.get(args[1]).toAbsolutePath().normalize();
        if(report.getParent()!=null) Files.createDirectories(report.getParent());

        List<Row> rows=readRows(hints);
        FunctionManager fm=currentProgram.getFunctionManager();
        Listing listing=currentProgram.getListing();

        int exact=0,renamed=0,commented=0,skipped=0;
        try(BufferedWriter w=Files.newBufferedWriter(
                report,StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE)) {
            w.write("client_va\texact_function\thash_match\toriginal_name\tfinal_name\trenamed\tcommented\tserver_symbol\tserver_object\tserver_variant_id\tnote\n");

            for(Row row:rows){
                monitor.checkCancelled();
                Address va=toAddr(Long.decode(row.clientVa));
                Function f=fm.getFunctionAt(va);
                if(f==null){
                    skipped++;
                    write(w,row,false,false,"","",false,false,"no exact Ghidra function at requested retail VA");
                    continue;
                }
                exact++;

                String observedHash=instructionHash(f,listing);
                if(!observedHash.equalsIgnoreCase(row.clientSha256)){
                    skipped++;
                    write(w,row,true,false,f.getName(true),f.getName(true),false,false,
                        "retail instruction-byte SHA-256 mismatch; hint rejected");
                    continue;
                }

                String original=f.getName(true);
                String shortHint=shortHint(row.serverSymbolName);
                boolean didRename=false;
                if(isAutoName(original) && !shortHint.isEmpty()){
                    String newName="xbuild_"+shortHint+"__"+f.getEntryPoint().toString().toLowerCase();
                    try{
                        f.setName(newName,SourceType.USER_DEFINED);
                        didRename=true;
                        renamed++;
                    }catch(Exception ex){
                        println("Rename skipped at "+row.clientVa+": "+ex.getMessage());
                    }
                }

                String warning=
                    "[T6 CROSS-BUILD HINT - NOT RETAIL-AUTHORITATIVE]\n"+
                    "Retail VA: "+row.clientVa+"\n"+
                    "Retail instruction bytes SHA-256: "+row.clientSha256+"\n"+
                    "Server PDB/MAP symbol hint: "+emptyDash(row.serverSymbolName)+"\n"+
                    "Server object hint: "+emptyDash(row.serverObjectName)+"\n"+
                    "Server VA (different build): "+emptyDash(row.serverVa)+"\n"+
                    "Server variant evidence: "+row.serverVariantId+"\n"+
                    "Evidence basis: "+row.identityBasis+"\n"+
                    "State: "+row.state+"\n"+
                    "Scope: exact-byte cross-build identity/name hint only. Do NOT infer server "+
                    "prototype, parameter types, globals, data addresses, source lines, struct layouts, "+
                    "neighbor functions, call targets, or address deltas. SHA-pinned retail evidence wins.";

                String prior=f.getRepeatableComment();
                if(prior==null || !prior.contains("[T6 CROSS-BUILD HINT - NOT RETAIL-AUTHORITATIVE]")){
                    f.setRepeatableComment(prior==null || prior.isEmpty() ? warning : prior+"\n\n"+warning);
                    commented++;
                }
                write(w,row,true,true,original,f.getName(true),didRename,true,"applied provenance-safe exact-byte hint");
            }
        }
        println("Cross-build hint pass: rows="+rows.size()+" exact="+exact+" renamed="+renamed+
                " commented="+commented+" skipped="+skipped);
    }

    private List<Row> readRows(Path p) throws Exception {
        List<Row> rows=new ArrayList<>();
        try(BufferedReader r=Files.newBufferedReader(p,StandardCharsets.UTF_8)){
            String h=r.readLine();
            String expected="client_va\tclient_sha256\toriginal_ghidra_name\tserver_va\tserver_size_bytes\tserver_symbol_name\tserver_object_name\tserver_variant_id\tidentity_basis\tstate";
            if(h==null || !h.equals(expected)) throw new IllegalArgumentException("unexpected hints header: "+h);
            String line;
            while((line=r.readLine())!=null){
                if(line.isEmpty()) continue;
                String[] c=line.split("\t",-1);
                if(c.length!=10) throw new IllegalArgumentException("bad hints row with "+c.length+" columns");
                rows.add(new Row(c));
            }
        }
        return rows;
    }

    private String instructionHash(Function f,Listing listing) throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        InstructionIterator it=listing.getInstructions(f.getBody(),true);
        while(it.hasNext()){
            Instruction ins=it.next();
            md.update(ins.getBytes());
        }
        return hex(md.digest());
    }

    private boolean isAutoName(String n){
        if(n==null) return true;
        String bare=n;
        int ns=bare.lastIndexOf("::");
        if(ns>=0) bare=bare.substring(ns+2);
        String l=bare.toLowerCase();
        return l.startsWith("fun_") || l.startsWith("thunk_fun_") || l.startsWith("sub_");
    }

    private String shortHint(String s){
        if(s==null || s.isEmpty()) return "";
        String x=s.trim();

        // Conservative MSVC decorated-name basename extraction. We deliberately do not
        // attempt to recover or apply the encoded prototype/type information.
        if(x.startsWith("??0")){
            int at=x.indexOf('@',3);
            if(at>3) x="ctor_"+x.substring(3,at);
        }else if(x.startsWith("??1")){
            int at=x.indexOf('@',3);
            if(at>3) x="dtor_"+x.substring(3,at);
        }else if(x.startsWith("?")){
            int at=x.indexOf('@',1);
            if(at>1) x=x.substring(1,at);
            else return "";
        }else if(x.startsWith("_") && x.length()>1){
            x=x.substring(1);
        }

        x=x.replaceAll("[^A-Za-z0-9_]+","_");
        x=x.replaceAll("_+","_");
        while(x.startsWith("_")) x=x.substring(1);
        while(x.endsWith("_")) x=x.substring(0,x.length()-1);
        if(x.isEmpty()) return "";
        if(Character.isDigit(x.charAt(0))) x="fn_"+x;
        if(x.length()>80) x=x.substring(0,80);
        return x;
    }

    private String emptyDash(String s){ return s==null || s.isEmpty() ? "<not materialized>" : s; }

    private void write(BufferedWriter w,Row row,boolean exact,boolean hash,String original,String fin,
                       boolean renamed,boolean commented,String note) throws Exception {
        w.write(String.join("\t",
            sanitize(row.clientVa),Boolean.toString(exact),Boolean.toString(hash),
            sanitize(original),sanitize(fin),Boolean.toString(renamed),Boolean.toString(commented),
            sanitize(row.serverSymbolName),sanitize(row.serverObjectName),sanitize(row.serverVariantId),
            sanitize(note)));
        w.newLine();
    }

    private String hex(byte[] bytes){
        StringBuilder b=new StringBuilder(bytes.length*2);
        for(byte x:bytes) b.append(String.format("%02x",x&0xff));
        return b.toString();
    }

    private String sanitize(String v){
        if(v==null) return "";
        return v.replace('\t',' ').replace('\r',' ').replace('\n',' ');
    }

    private static class Row {
        final String clientVa,clientSha256,originalGhidraName,serverVa,serverSizeBytes;
        final String serverSymbolName,serverObjectName,serverVariantId,identityBasis,state;
        Row(String[] c){
            clientVa=c[0]; clientSha256=c[1]; originalGhidraName=c[2]; serverVa=c[3];
            serverSizeBytes=c[4]; serverSymbolName=c[5]; serverObjectName=c[6];
            serverVariantId=c[7]; identityBasis=c[8]; state=c[9];
        }
    }
}
