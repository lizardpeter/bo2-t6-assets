// Conservative analysis profile for the exact T6 current client.
// Whole-image symbolic analyzers that are pathological on large PE32 images are disabled;
// direct-call/reference inventory already exists independently and targeted decompilation
// performs per-function stack recovery.
//
//@category T6 Current Client

import java.util.Map;
import ghidra.app.script.GhidraScript;

public class ConfigureT6CurrentClientAnalysis extends GhidraScript {
    private static final String[] DISABLED_ANALYZERS = {
        "x86 Constant Reference Analyzer",
        "Stack",
    };

    @Override
    protected void run() throws Exception {
        Map<String,String> options=getCurrentAnalysisOptionsAndValues(currentProgram);
        for(String analyzer:DISABLED_ANALYZERS){
            if(options.containsKey(analyzer)){
                setAnalysisOption(currentProgram,analyzer,"false");
                println("Disabled "+analyzer+" for exact T6 current-client analysis");
            } else {
                println("Analyzer not present in this Ghidra build: "+analyzer);
            }
        }
    }
}
