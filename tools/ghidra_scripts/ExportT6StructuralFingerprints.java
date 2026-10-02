// Export compact, address-normalized structural fingerprints for whole-program cross-build matching.
//
// This script emits evidence only. It does not assign cross-build identity.
//
//@category T6 Cross Build

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceType;

public class ExportT6StructuralFingerprints extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2) throw new IllegalArgumentException(
            "usage: ExportT6StructuralFingerprints.java <output-dir> <shard-count>");
        Path out=Paths.get(args[0]).toAbsolutePath().normalize();
        int shardCount=Integer.parseInt(args[1]);
        if(shardCount<1 || shardCount>64) throw new IllegalArgumentException("invalid shard count");
        Files.createDirectories(out);

        BufferedWriter[] ws=new BufferedWriter[shardCount];
        final String header=
            "entry_va\tname\tinstruction_count\tbody_address_count\tcall_ref_count\tdata_ref_count"+
            "\tstring_ref_count\tbranch_count\tis_thunk\texact_bytes_sha256\tmnemonic_sha256"+
            "\toperand_coarse_sha256\toperand_fine_sha256\tflow_sha256\tsmall_scalar_sha256\tstring_sha256\n";
        try{
            for(int i=0;i<shardCount;i++){
                Path p=out.resolve(String.format("fingerprints_%02d.tsv",i));
                ws[i]=Files.newBufferedWriter(p,StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE);
                ws[i].write(header);
            }

            FunctionManager fm=currentProgram.getFunctionManager();
            Listing listing=currentProgram.getListing();
            FunctionIterator it=fm.getFunctions(true);
            long count=0;
            while(it.hasNext()){
                monitor.checkCancelled();
                Function f=it.next();
                Row row=fingerprint(f,listing);
                int shard=(int)(count % shardCount);
                ws[shard].write(row.tsv());
                ws[shard].newLine();
                count++;
            }
            println("Exported "+count+" structural fingerprints across "+shardCount+" shards");
        } finally {
            for(BufferedWriter w:ws) if(w!=null) w.close();
        }
    }

    private Row fingerprint(Function f,Listing listing) throws Exception {
        MessageDigest exact=sha();
        MessageDigest mn=sha();
        MessageDigest coarse=sha();
        MessageDigest fine=sha();
        MessageDigest flow=sha();

        List<String> smallScalars=new ArrayList<>();
        List<String> strings=new ArrayList<>();
        int insCount=0,callRefs=0,dataRefs=0,stringRefs=0,branches=0;

        InstructionIterator ii=listing.getInstructions(f.getBody(),true);
        while(ii.hasNext()){
            Instruction ins=ii.next();
            insCount++;
            exact.update(ins.getBytes());
            feed(mn,ins.getMnemonicString().toUpperCase());

            StringBuilder c=new StringBuilder(ins.getMnemonicString().toUpperCase());
            StringBuilder fi=new StringBuilder(ins.getMnemonicString().toUpperCase());
            int nop=ins.getNumOperands();
            for(int op=0;op<nop;op++){
                c.append('|').append(op).append(':');
                fi.append('|').append(op).append(':');
                Object[] objs=ins.getOpObjects(op);
                if(objs==null || objs.length==0){
                    c.append("NONE");
                    fi.append("NONE");
                }else{
                    for(Object obj:objs){
                        if(obj instanceof Register){
                            c.append("R,");
                            fi.append("R:").append(((Register)obj).getName()).append(',');
                        }else if(obj instanceof Scalar){
                            Scalar s=(Scalar)obj;
                            long u=s.getUnsignedValue();
                            boolean flowOperand=ins.getFlowType().isCall() || ins.getFlowType().isJump();
                            c.append("S,");
                            if(flowOperand){
                                fi.append("FLOW_S,");
                            }else if(u<=0xffffL){
                                fi.append("S:").append(Long.toHexString(u)).append(',');
                                smallScalars.add(Long.toHexString(u));
                            }else{
                                fi.append("S_LARGE,");
                            }
                        }else if(obj instanceof Address){
                            Address a=(Address)obj;
                            if(f.getBody().contains(a)){
                                long rel=a.subtract(f.getEntryPoint());
                                c.append("A_IN,");
                                fi.append("A_IN:").append(Long.toHexString(rel)).append(',');
                            }else{
                                c.append("A_EXT,");
                                fi.append("A_EXT,");
                            }
                        }else{
                            String n=obj.getClass().getSimpleName();
                            c.append("O:").append(n).append(',');
                            fi.append("O:").append(n).append(',');
                        }
                    }
                }
            }
            feed(coarse,c.toString());
            feed(fine,fi.toString());

            if(ins.getFlowType().isJump()) branches++;
            StringBuilder fl=new StringBuilder(ins.getFlowType().toString());
            Address[] flows=ins.getFlows();
            if(flows!=null){
                for(Address a:flows){
                    if(f.getBody().contains(a)){
                        long rel=a.subtract(f.getEntryPoint());
                        fl.append("|I:").append(Long.toHexString(rel));
                    }else{
                        fl.append("|E");
                    }
                }
            }
            feed(flow,fl.toString());

            for(Reference ref:ins.getReferencesFrom()){
                ReferenceType rt=ref.getReferenceType();
                if(rt.isCall()) callRefs++;
                if(rt.isData()){
                    dataRefs++;
                    Data d=listing.getDefinedDataContaining(ref.getToAddress());
                    if(d!=null){
                        Object val=d.getValue();
                        if(val instanceof String){
                            strings.add((String)val);
                            stringRefs++;
                        }
                    }
                }
            }
        }

        Collections.sort(smallScalars);
        Collections.sort(strings);
        return new Row(
            f.getEntryPoint().toString(),
            f.getName(true),
            insCount,
            f.getBody().getNumAddresses(),
            callRefs,dataRefs,stringRefs,branches,f.isThunk(),
            hex(exact.digest()),hex(mn.digest()),hex(coarse.digest()),hex(fine.digest()),hex(flow.digest()),
            digestStrings(smallScalars),digestStrings(strings)
        );
    }

    private MessageDigest sha() throws Exception { return MessageDigest.getInstance("SHA-256"); }

    private void feed(MessageDigest md,String s){
        md.update(s.getBytes(StandardCharsets.UTF_8));
        md.update((byte)0);
    }

    private String digestStrings(List<String> xs) throws Exception {
        MessageDigest md=sha();
        for(String x:xs) feed(md,x);
        return hex(md.digest());
    }

    private String hex(byte[] b){
        StringBuilder s=new StringBuilder(b.length*2);
        for(byte x:b) s.append(String.format("%02x",x&0xff));
        return s.toString();
    }

    private String clean(String s){
        if(s==null) return "";
        return s.replace('\t',' ').replace('\r',' ').replace('\n',' ');
    }

    private class Row {
        final String va,name,exact,mn,coarse,fine,flow,small,stringHash;
        final int ins,callRefs,dataRefs,stringRefs,branches;
        final long body;
        final boolean thunk;
        Row(String va,String name,int ins,long body,int callRefs,int dataRefs,int stringRefs,int branches,boolean thunk,
            String exact,String mn,String coarse,String fine,String flow,String small,String stringHash){
            this.va=va;this.name=name;this.ins=ins;this.body=body;this.callRefs=callRefs;this.dataRefs=dataRefs;
            this.stringRefs=stringRefs;this.branches=branches;this.thunk=thunk;this.exact=exact;this.mn=mn;
            this.coarse=coarse;this.fine=fine;this.flow=flow;this.small=small;this.stringHash=stringHash;
        }
        String tsv(){
            return String.join("\t",
                clean(va),clean(name),Integer.toString(ins),Long.toString(body),Integer.toString(callRefs),
                Integer.toString(dataRefs),Integer.toString(stringRefs),Integer.toString(branches),
                Boolean.toString(thunk),exact,mn,coarse,fine,flow,small,stringHash);
        }
    }
}
