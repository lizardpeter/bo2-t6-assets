// Exact-binary Super Mario Galaxy RMGE01 whole-image catalog + decompile shard exporter.
// No external symbol map or community decompilation source is consumed.
//@category SMG RMGE01

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.Base64;
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.Memory;

public class ExportSmgRmge01NativeDecompile extends GhidraScript {
    private static String clean(String s) { return s == null ? "" : s.replace("\t"," ").replace("\r"," ").replace("\n"," "); }
    private static String hex(byte[] b) { StringBuilder sb=new StringBuilder(b.length*2); for(byte x:b) sb.append(String.format("%02x",x&0xff)); return sb.toString(); }
    private String bodySha(Function f) throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256"); Memory mem=currentProgram.getMemory();
        for(AddressRange range:f.getBody()) {
            Address cur=range.getMinAddress(); long left=range.getLength(); byte[] buf=new byte[65536];
            while(left>0) { int n=(int)Math.min(left,buf.length); int got=mem.getBytes(cur,buf,0,n); if(got!=n) throw new IOException("short memory read at "+cur); md.update(buf,0,n); cur=cur.add(n); left-=n; }
        }
        return hex(md.digest());
    }
    private long instructionCount(Function f) { long n=0; InstructionIterator it=currentProgram.getListing().getInstructions(f.getBody(),true); while(it.hasNext()){it.next();n++;} return n; }
    @Override protected void run() throws Exception {
        String[] a=getScriptArgs(); if(a.length<3) throw new IllegalArgumentException("usage: <catalog.tsv> <decompile.tsv> <summary.json> [limit] [minSize]");
        Path catalog=Paths.get(a[0]), decomp=Paths.get(a[1]), summary=Paths.get(a[2]);
        int limit=a.length>3?Integer.parseInt(a[3]):1500; long minSize=a.length>4?Long.parseLong(a[4]):12;
        Files.createDirectories(catalog.toAbsolutePath().getParent());
        List<Function> fs=new ArrayList<>(); FunctionIterator fi=currentProgram.getFunctionManager().getFunctions(true);
        while(fi.hasNext()){monitor.checkCancelled();Function f=fi.next();if(!f.isExternal())fs.add(f);}
        fs.sort(Comparator.comparingLong((Function f)->f.getBody().getNumAddresses()).thenComparing(f->f.getEntryPoint()));
        long cataloged=0,totalInstructions=0;
        try(BufferedWriter w=Files.newBufferedWriter(catalog,StandardCharsets.UTF_8)){
            w.write("entry\tname\tbody_size\tbody_min\tbody_max\tinstruction_count\tbody_sha256\tis_thunk\tcalling_convention\tparameter_count\n");
            for(Function f:fs){monitor.checkCancelled();long ic=instructionCount(f),sz=f.getBody().getNumAddresses();totalInstructions+=ic;cataloged++;
                w.write(String.join("\t",f.getEntryPoint().toString(),clean(f.getName(true)),Long.toString(sz),f.getBody().getMinAddress().toString(),f.getBody().getMaxAddress().toString(),Long.toString(ic),bodySha(f),Boolean.toString(f.isThunk()),clean(f.getCallingConventionName()),Integer.toString(f.getParameterCount())));w.newLine();}
        }
        DecompInterface di=new DecompInterface();di.setSimplificationStyle("decompile");if(!di.openProgram(currentProgram))throw new RuntimeException("Decompiler failed to open program");
        int attempted=0,ok=0,failed=0;
        try(BufferedWriter w=Files.newBufferedWriter(decomp,StandardCharsets.UTF_8)){
            w.write("entry\tname\tbody_size\tbody_min\tbody_max\tinstruction_count\tbody_sha256\tdecompile_completed\tc_sha256\tc_base64\n");
            for(Function f:fs){monitor.checkCancelled();long sz=f.getBody().getNumAddresses();if(sz<minSize)continue;if(attempted>=limit)break;attempted++;
                DecompileResults dr=di.decompileFunction(f,30,monitor);boolean done=dr!=null&&dr.decompileCompleted()&&dr.getDecompiledFunction()!=null;String c=done?dr.getDecompiledFunction().getC():"";String csha="";
                if(done){MessageDigest md=MessageDigest.getInstance("SHA-256");csha=hex(md.digest(c.getBytes(StandardCharsets.UTF_8)));ok++;}else failed++;
                w.write(String.join("\t",f.getEntryPoint().toString(),clean(f.getName(true)),Long.toString(sz),f.getBody().getMinAddress().toString(),f.getBody().getMaxAddress().toString(),Long.toString(instructionCount(f)),bodySha(f),Boolean.toString(done),csha,Base64.getEncoder().encodeToString(c.getBytes(StandardCharsets.UTF_8))));w.newLine();}
        } finally {di.dispose();}
        String json="{\n  \"producer\": \"ghidra-12.1.3-gamecube-loader-rmge01-native-v1\",\n  \"program\": \""+clean(currentProgram.getName())+"\",\n  \"image_base\": \""+currentProgram.getImageBase()+"\",\n  \"functions_cataloged\": "+cataloged+",\n  \"instructions_cataloged\": "+totalInstructions+",\n  \"decompile_attempted\": "+attempted+",\n  \"decompile_completed\": "+ok+",\n  \"decompile_failed\": "+failed+",\n  \"decompile_min_body_bytes\": "+minSize+",\n  \"external_symbol_map_used\": false,\n  \"community_decomp_source_used\": false\n}\n";
        Files.writeString(summary,json,StandardCharsets.UTF_8);println("SMG RMGE01 cataloged="+cataloged+" decompile attempted="+attempted+" completed="+ok+" failed="+failed);
    }
}
