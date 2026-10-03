// Relocation-independent finder for the exact T6 client XAsset size-handler table.
//
//@category T6 Current Client

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class FindT6CurrentClientXAssetSizeTable extends GhidraScript {
    // Shared server/client T6 XAsset sizes for indices 0..18. These are used
    // only as a table fingerprint; client-only indices are discovered, not
    // assumed.
    private static final int[] PREFIX = {
        12,84,2696,24,104,248,112,152,80,4756,12,332,332,16,44,44,36,1028,16
    };

    private Long constantReturn(Address target, Memory memory) {
        try {
            byte op = memory.getByte(target);
            if ((op & 0xff) != 0xB8) return null; // mov eax, imm32
            int value = memory.getInt(target.add(1));
            int ret = memory.getByte(target.add(5)) & 0xff;
            if (ret != 0xC3 && ret != 0xC2) return null;
            return Integer.toUnsignedLong(value);
        } catch (Exception e) {
            return null;
        }
    }

    private Address pointerAt(Address slot, Memory memory) {
        try {
            long raw = Integer.toUnsignedLong(memory.getInt(slot));
            if (raw == 0) return null;
            Address target = toAddr(raw);
            return memory.contains(target) ? target : null;
        } catch (Exception e) {
            return null;
        }
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException(
            "usage: FindT6CurrentClientXAssetSizeTable.java <output-dir>");
        Path out = Paths.get(args[0]).toAbsolutePath().normalize();
        Files.createDirectories(out);
        Memory memory = currentProgram.getMemory();

        Address found = null;
        for (MemoryBlock block : memory.getBlocks()) {
            monitor.checkCancelled();
            if (!block.isInitialized() || block.getSize() < 60L * 4L) continue;
            // Function-pointer registries live in non-executable data. Scanning
            // executable blocks only adds false positives.
            if (block.isExecute()) continue;
            long limit = block.getSize() - 60L * 4L;
            for (long offset = 0; offset <= limit; offset += 4) {
                if ((offset & 0xfff) == 0) monitor.checkCancelled();
                Address base = block.getStart().add(offset);
                boolean match = true;
                for (int i = 0; i < PREFIX.length; i++) {
                    Address target = pointerAt(base.add(i * 4L), memory);
                    if (target == null) { match = false; break; }
                    Long value = constantReturn(target, memory);
                    if (value == null || value.longValue() != PREFIX[i]) {
                        match = false;
                        break;
                    }
                }
                if (!match) continue;
                if (found != null && !found.equals(base)) {
                    throw new IllegalStateException(
                        "more than one exact XAsset size-table fingerprint: " + found + " and " + base);
                }
                found = base;
            }
        }
        if (found == null) throw new IllegalStateException(
            "exact current-client XAsset size-handler table fingerprint not found");

        StringBuilder rows = new StringBuilder(
            "asset_type\tslot_address\thandler_address\tconstant_return_size\n");
        for (int i = 0; i < 60; i++) {
            Address slot = found.add(i * 4L);
            Address target = pointerAt(slot, memory);
            Long size = target == null ? null : constantReturn(target, memory);
            rows.append(i).append("\t").append(slot).append("\t")
                .append(target == null ? "" : target.toString()).append("\t")
                .append(size == null ? "" : Long.toString(size)).append("\n");
        }
        Files.writeString(out.resolve("xasset_size_handlers.tsv"), rows.toString(), StandardCharsets.UTF_8);

        StringBuilder refs = new StringBuilder(
            "table_address\tfrom_address\tfunction_entry\tfunction_name\treference_type\n");
        ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(found);
        while (it.hasNext()) {
            Reference ref = it.next();
            Address from = ref.getFromAddress();
            var fn = currentProgram.getFunctionManager().getFunctionContaining(from);
            refs.append(found).append("\t").append(from).append("\t")
                .append(fn == null ? "" : fn.getEntryPoint()).append("\t")
                .append(fn == null ? "" : fn.getName(true)).append("\t")
                .append(ref.getReferenceType()).append("\n");
        }
        Files.writeString(out.resolve("xasset_size_table_xrefs.tsv"), refs.toString(), StandardCharsets.UTF_8);
        Files.writeString(out.resolve("table_address.txt"), found.toString() + "\n", StandardCharsets.UTF_8);
        println("exact current-client XAsset size table: " + found);
    }
}
