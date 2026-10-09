// Export the full PDB/Ghidra recovered original BO2 Server type universe.
// No C++ bodies are reconstructed here; this is the shared cross-TU type
// authority needed before whole-program typed source generation.
//
//@category T6 PC Server
import ghidra.app.script.GhidraScript;
import ghidra.program.model.data.*;
import ghidra.program.model.data.Enum;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.model.symbol.SymbolType;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

public class ExportT6ServerPdbSemanticsUniverseV2 extends GhidraScript {
    private String clean(String s) {
        return s == null ? "" : s.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ');
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1)
            throw new IllegalArgumentException("Usage: ExportT6ServerPdbSemanticsUniverseV2.java <out-dir>");
        Path root = Paths.get(args[0]).toAbsolutePath().normalize();
        Files.createDirectories(root);
        long datatypeCount = 0;
        long compoundCount = 0;
        long structFieldCount = 0;
        long enumCount = 0;
        long enumValues = 0;
        long typeAliasCount = 0;
        long functionCount = 0;
        long namedDataSymbols = 0;
        long importedNamedDataSymbols = 0;
        Map<String, Long> sourceKinds = new LinkedHashMap<>();
        try (
            BufferedWriter types = Files.newBufferedWriter(root.resolve("types.tsv"), StandardCharsets.UTF_8);
            BufferedWriter fields = Files.newBufferedWriter(root.resolve("fields.tsv"), StandardCharsets.UTF_8);
            BufferedWriter functions = Files.newBufferedWriter(root.resolve("functions.tsv"), StandardCharsets.UTF_8);
            BufferedWriter globals = Files.newBufferedWriter(root.resolve("globals.tsv"), StandardCharsets.UTF_8)
        ) {
            types.write("path\tcategory\tname\tkind\tlength\talignment\tcomponent_count\tbase_type_path\n");
            globals.write("analysis_va\tqualified_name\tsymbol_source\tdata_type_path\tdata_length\n");
            fields.write("type_path\ttype_kind\toffset\tlength\tordinal\tfield_name\tfield_type_path\tcomment\n");
            functions.write("entry_va\tqualified_name\tsymbol_source\tfunction_signature\treturn_type\tcalling_convention\tis_thunk\tparams\n");
            DataTypeManager dtm = currentProgram.getDataTypeManager();
            Iterator<DataType> all = dtm.getAllDataTypes();
            while (all.hasNext()) {
                monitor.checkCancelled();
                DataType t = all.next();
                datatypeCount++;
                String kind;
                DataTypeComponent[] components = null;
                if (t instanceof Structure) {
                    kind = "struct";
                    components = ((Structure)t).getComponents();
                    compoundCount++;
                } else if (t instanceof Union) {
                    kind = "union";
                    components = ((Union)t).getComponents();
                    compoundCount++;
                } else if (t instanceof Enum) {
                    kind = "enum";
                    enumCount++;
                } else if (t instanceof TypeDef) {
                    kind = "typedef";
                    typeAliasCount++;
                } else {
                    continue;
                }
                String path = clean(t.getPathName());
                String cat = clean(t.getCategoryPath().getPath());
                String name = clean(t.getName());
                int fieldsCount = components == null ? 0 : components.length;
                types.write(String.join("\t", path, cat, name, kind, 
                    Integer.toString(t.getLength()), Integer.toString(t.getAlignment()),
                    Integer.toString(fieldsCount),
                    t instanceof TypeDef ? clean(((TypeDef)t).getBaseDataType().getPathName()) : ""));
                types.newLine();
                if (components != null) {
                    for (DataTypeComponent c : components) {
                        structFieldCount++;
                        fields.write(String.join("\t", path, kind,
                            Integer.toString(c.getOffset()), Integer.toString(c.getLength()),
                            Integer.toString(c.getOrdinal()), clean(c.getFieldName()),
                            clean(c.getDataType().getPathName()), clean(c.getComment())));
                        fields.newLine();
                    }
                }
                if (t instanceof Enum) {
                    Enum e = (Enum)t;
                    for (String valueName : e.getNames()) {
                        enumValues++;
                        fields.write(String.join("\t", path, "enum_value",
                            Long.toString(e.getValue(valueName)), "0", "0",
                            clean(valueName), "", ""));
                        fields.newLine();
                    }
                }
            }
            FunctionIterator fi = currentProgram.getFunctionManager().getFunctions(true);
            while (fi.hasNext()) {
                monitor.checkCancelled();
                Function f = fi.next();
                functionCount++;
                SourceType source = f.getSymbol().getSource();
                sourceKinds.put(source.name(), sourceKinds.getOrDefault(source.name(), 0L) + 1L);
                StringBuilder params = new StringBuilder();
                for (Parameter p : f.getParameters()) {
                    if (params.length() > 0) params.append(';');
                    params.append(clean(p.getName())).append(':').append(clean(p.getDataType().getPathName()));
                }
                functions.write(String.join("\t", "0x" + f.getEntryPoint().toString(),
                    clean(f.getName(true)), source.name(), clean(f.getPrototypeString(true,true)),
                    clean(f.getReturnType().getPathName()),
                    clean(f.getCallingConventionName()),Boolean.toString(f.isThunk()),params.toString()));
                functions.newLine();
            }
            // Original imported global data labels, including typed Dvar pointers.
            // Exclude executable addresses; preserve names and exact locations.
            SymbolIterator symbols = currentProgram.getSymbolTable().getAllSymbols(true);
            while (symbols.hasNext()) {
                monitor.checkCancelled();
                Symbol symbol = symbols.next();
                if (symbol.getSymbolType() != SymbolType.LABEL ||
                    !currentProgram.getMemory().contains(symbol.getAddress()) ||
                    currentProgram.getMemory().getExecuteSet().contains(symbol.getAddress())) {
                    continue;
                }
                namedDataSymbols++;
                if (symbol.getSource() == SourceType.IMPORTED) importedNamedDataSymbols++;
                Data data = currentProgram.getListing().getDataAt(symbol.getAddress());
                globals.write(String.join("\t",
                    "0x" + symbol.getAddress().toString(),
                    clean(symbol.getName(true)), symbol.getSource().name(),
                    data == null ? "" : clean(data.getDataType().getPathName()),
                    data == null ? "0" : Integer.toString(data.getLength())));
                globals.newLine();
            }
        }
        StringBuilder summary = new StringBuilder();
        summary.append("{\n");
        summary.append("  \"schema\": \"t6-original-pc-pdb-semantics-universe-v2\",\n");
        summary.append("  \"original_pc_exe\": \"CoDMPServer_PC.exe\",\n");
        summary.append("  \"discovered_data_types\": ").append(datatypeCount).append(",\n");
        summary.append("  \"compound_structs_and_unions\": ").append(compoundCount).append(",\n");
        summary.append("  \"struct_union_components\": ").append(structFieldCount).append(",\n");
        summary.append("  \"enumerations\": ").append(enumCount).append(",\n");
        summary.append("  \"enumeration_values\": ").append(enumValues).append(",\n");
        summary.append("  \"typedefs\": ").append(typeAliasCount).append(",\n");
        summary.append("  \"typed_original_functions\": ").append(functionCount).append(",\n");
        summary.append("  \"named_data_symbols\": ").append(namedDataSymbols).append(",\n");
        summary.append("  \"imported_named_data_symbols\": ").append(importedNamedDataSymbols).append(",\n");
        summary.append("  \"function_symbol_sources\": {");
        boolean first = true;
        for (Map.Entry<String,Long> e : sourceKinds.entrySet()) {
            if (!first) summary.append(",");
            first = false;
            summary.append("\n    \"").append(e.getKey()).append("\": ").append(e.getValue());
        }
        summary.append("\n  },\n");
        summary.append("  \"boundary\": \"Ghidra recovered type universe, target aliases, named globals, original prototype map. Still no compilable gameplay proven.\"\n");
        summary.append("}\n");
        Files.writeString(root.resolve("summary.json"), summary.toString(), StandardCharsets.UTF_8);
        println("FULL ORIGINAL PDB TYPE UNIVERSE\n" + summary.toString());
        if (functionCount < 20000 || datatypeCount == 0) {
            throw new IllegalStateException("Incomplete cached original-image Ghidra program or type manager");
        }
    }
}
