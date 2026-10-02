// Export selected PDB-backed T6 data type layouts as deterministic TSV.
//@category T6

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Set;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.data.Composite;
import ghidra.program.model.data.DataType;
import ghidra.program.model.data.DataTypeComponent;
import ghidra.program.model.data.DataTypeManager;

public class ExportT6TypeLayout extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length<2) throw new IllegalArgumentException("usage: <output.tsv> <type-name> [type-name...]");
        Path out=Paths.get(args[0]).toAbsolutePath().normalize();
        Set<String> wanted=new HashSet<>();
        for(int i=1;i<args.length;i++) wanted.add(args[i]);

        try(BufferedWriter w=Files.newBufferedWriter(
                out,StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING,StandardOpenOption.WRITE)) {
            w.write("requested_type\tmatched_type\tcategory\ttotal_length\tordinal\toffset\tfield_name\tfield_length\tfield_type\n");
            DataTypeManager dtm=currentProgram.getDataTypeManager();
            Iterator<DataType> it=dtm.getAllDataTypes();
            Set<String> found=new HashSet<>();
            while(it.hasNext()) {
                monitor.checkCancelled();
                DataType dt=it.next();
                if(!wanted.contains(dt.getName())) continue;
                found.add(dt.getName());
                String category=dt.getCategoryPath()==null?"":dt.getCategoryPath().getPath();
                if(dt instanceof Composite) {
                    Composite c=(Composite)dt;
                    for(DataTypeComponent component:c.getComponents()) {
                        w.write(row(dt.getName(),dt.getName(),category,dt.getLength(),
                            component.getOrdinal(),component.getOffset(),component.getFieldName(),
                            component.getLength(),component.getDataType().getDisplayName()));
                        w.newLine();
                    }
                } else {
                    w.write(row(dt.getName(),dt.getName(),category,dt.getLength(),-1,0,"",dt.getLength(),dt.getDisplayName()));
                    w.newLine();
                }
            }
            for(String name:wanted) {
                if(!found.contains(name)) {
                    w.write(row(name,"","",0,-1,-1,"",0,""));
                    w.newLine();
                }
            }
        }
    }

    private String row(String requested,String matched,String category,int total,int ordinal,int offset,
                       String field,int length,String type) {
        return String.join("\t",
            clean(requested),clean(matched),clean(category),Integer.toString(total),
            Integer.toString(ordinal),Integer.toString(offset),clean(field),
            Integer.toString(length),clean(type));
    }

    private String clean(String s) {
        return s==null?"":s.replace('\t',' ').replace('\r',' ').replace('\n',' ');
    }
}
