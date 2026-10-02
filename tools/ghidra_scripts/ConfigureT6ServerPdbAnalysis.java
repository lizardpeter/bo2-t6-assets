// Conservative PDB-backed analysis profile for the exact T6 dedicated server.
//
//@category T6 Cross Build

import java.util.Map;
import ghidra.app.script.GhidraScript;

public class ConfigureT6ServerPdbAnalysis extends GhidraScript {
    private static final String[] DISABLED_ANALYZERS = {
        "x86 Constant Reference Analyzer",
        "Stack",
    };

    @Override
    protected void run() throws Exception {
        Map<String,String> options=getCurrentAnalysisOptionsAndValues(currentProgram);
        for(String analyzer:DISABLED_ANALYZERS){
            if(!options.containsKey(analyzer)){
                throw new IllegalStateException("Required Ghidra analysis option is missing: "+analyzer);
            }
            setAnalysisOption(currentProgram,analyzer,"false");
            println("Disabled "+analyzer+" for exact T6 server PDB-backed analysis");
        }
    }
}
