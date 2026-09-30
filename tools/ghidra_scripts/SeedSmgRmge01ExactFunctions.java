// Seed exact graph-verified RMGE01 function boundaries before Ghidra analysis.
//@category SMG RMGE01
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.*;
import java.util.*;

public class SeedSmgRmge01ExactFunctions extends GhidraScript {
    public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=1) throw new IllegalArgumentException("usage: <manifest.tsv>");
        List<String> lines=Files.readAllLines(Paths.get(args[0]));
        FunctionManager fm=currentProgram.getFunctionManager();
        AddressSpace sp=currentProgram.getAddressFactory().getDefaultAddressSpace();
        int seeded=0, existing=0, failed=0;
        for(int i=1;i<lines.size();i++){
            monitor.checkCancelled();
            String line=lines.get(i);
            if(line.trim().isEmpty()) continue;
            String[] p=line.split("\t",-1);
            long av=Long.parseUnsignedLong(p[1].substring(2),16);
            long sz=Long.parseLong(p[2]);
            Address start=sp.getAddress(av);
            Address end=start.add(sz-1);
            AddressSet body=new AddressSet(start,end);
            Function f=fm.getFunctionAt(start);
            try {
                if(f==null){
                    Function containing=fm.getFunctionContaining(start);
                    if(containing!=null && !containing.getEntryPoint().equals(start)){
                        fm.removeFunction(containing.getEntryPoint());
                    }
                    fm.createFunction("FUN_"+String.format("%08X",av),start,body,SourceType.USER_DEFINED);
                    seeded++;
                } else {
                    try { f.setBody(body); } catch(Exception ignored) {}
                    existing++;
                }
            } catch(Exception e){
                println("seed-failed "+p[1]+" "+e.getMessage());
                failed++;
            }
        }
        println("SMG seed exact functions seeded="+seeded+" existing="+existing+" failed="+failed);
    }
}
