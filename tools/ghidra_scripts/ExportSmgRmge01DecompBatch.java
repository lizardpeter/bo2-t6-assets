// Export Ghidra decompiler output for exact-byte-verified RMGE01 function seeds.
//@category SMG RMGE01
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.io.*;
import java.util.*;
import java.util.Base64;

public class ExportSmgRmge01DecompBatch extends GhidraScript {
    private String b64(String s){ return Base64.getEncoder().encodeToString((s==null?"":s).getBytes(StandardCharsets.UTF_8)); }
    public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2) throw new IllegalArgumentException("usage: <manifest.tsv> <out.tsv>");
        List<String> lines=Files.readAllLines(Paths.get(args[0]));
        Path out=Paths.get(args[1]);
        Files.createDirectories(out.toAbsolutePath().getParent());
        FunctionManager fm=currentProgram.getFunctionManager();
        AddressSpace sp=currentProgram.getAddressFactory().getDefaultAddressSpace();
        DecompInterface di=new DecompInterface();
        DecompileOptions opts=new DecompileOptions();
        di.setOptions(opts); di.toggleCCode(true); di.toggleSyntaxTree(true);
        if(!di.openProgram(currentProgram)) throw new RuntimeException("decompiler open failed");
        int ok=0, fail=0;
        try(BufferedWriter w=Files.newBufferedWriter(out,StandardCharsets.UTF_8)){
            w.write("id\taddress\tsize\tsuccess\tfunction_name_b64\tc_b64\terror_b64\n");
            for(int i=1;i<lines.size();i++){
                monitor.checkCancelled();
                String line=lines.get(i); if(line.trim().isEmpty()) continue;
                String[] p=line.split("\t",-1);
                long av=Long.parseUnsignedLong(p[1].substring(2),16);
                Address start=sp.getAddress(av);
                Function f=fm.getFunctionAt(start);
                boolean success=false; String name=""; String c=""; String err="";
                if(f==null){ err="no function at exact entry"; }
                else {
                    name=f.getName(true);
                    try {
                        DecompileResults dr=di.decompileFunction(f,90,monitor);
                        success=dr.decompileCompleted() && dr.getDecompiledFunction()!=null;
                        if(success){ c=dr.getDecompiledFunction().getC(); ok++; }
                        else { err=dr.getErrorMessage(); fail++; }
                    } catch(Exception e){ err=e.toString(); fail++; }
                }
                w.write(p[0]+"\t"+p[1]+"\t"+p[2]+"\t"+Boolean.toString(success)+"\t"+b64(name)+"\t"+b64(c)+"\t"+b64(err)+"\n");
            }
        } finally { di.dispose(); }
        println("SMG decompile batch ok="+ok+" fail="+fail);
    }
}
