import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public final class ModuleIntegrityTest {
    private static int count;
    private static void check(String name,boolean value){count++;if(!value)throw new AssertionError(name);}
    private static void write(Path path,String value)throws Exception{Files.write(path,value.getBytes(StandardCharsets.UTF_8));}
    public static void main(String[] args)throws Exception {
        Path root=Paths.get(args[0]),active=root.resolve("active"),staged=root.resolve("staged");
        Files.createDirectories(active);Files.createDirectories(staged);
        Map<String,String> old=new LinkedHashMap<>(),next=new LinkedHashMap<>();
        for(String file:Arrays.asList("override.dex","health.sh","service.sh","control.sh","compatibility.sh","policy.json",
                "full-files.tsv","post-fs-data.sh","diagnose.sh","action.sh","module.prop")) {
            write(active.resolve(file),"old "+file);write(staged.resolve(file),"new "+file);
            old.put(file,ModuleIntegrity.sha(active.resolve(file)));next.put(file,ModuleIntegrity.sha(staged.resolve(file)));
        }
        write(staged.resolve("manifest.json"),"manifest snapshot");
        check("unchanged active",ModuleIntegrity.errors(active,old).isEmpty());
        check("relative module directory",ModuleIntegrity.errors(Paths.get("").toAbsolutePath().relativize(active),old).isEmpty());
        String props="id=EnablePixel5G\nversion=v2.6.6-dev2\nversionCode=38\n";
        write(staged.resolve("module.prop"),props);next.put("module.prop",ModuleIntegrity.sha(staged.resolve("module.prop")));
        write(active.resolve("module.prop"),props);
        check("no marker is an error",!ModuleIntegrity.pendingUpdate(active,staged,old,next,"v2.6.6-dev2"));
        write(active.resolve("update"),"");
        check("complete staged update",ModuleIntegrity.pendingUpdate(active,staged,old,next,"v2.6.6-dev2"));
        write(active.resolve("service.sh"),"corrupt");
        check("active code corruption stays an error",!ModuleIntegrity.pendingUpdate(active,staged,old,next,"v2.6.6-dev2"));
        write(active.resolve("service.sh"),"old service.sh");
        write(staged.resolve("service.sh"),"corrupt");
        check("staged code corruption stays an error",!ModuleIntegrity.pendingUpdate(active,staged,old,next,"v2.6.6-dev2"));
        write(staged.resolve("service.sh"),"new service.sh");
        write(active.resolve("module.prop"),props+"description=unrelated edit\n");
        check("unrelated metadata change",!ModuleIntegrity.pendingUpdate(active,staged,old,next,"v2.6.6-dev2"));
        write(active.resolve("module.prop"),props);
        check("version mismatch",!ModuleIntegrity.pendingUpdate(active,staged,old,next,"v2.6.6-dev3"));
        Map<String,String> incomplete=new LinkedHashMap<>(next);incomplete.remove("override.dex");
        check("incomplete staged manifest",!ModuleIntegrity.pendingUpdate(active,staged,old,incomplete,"v2.6.6-dev2"));
        Map<String,String> unsafe=new LinkedHashMap<>(next);unsafe.put("../outside",next.get("module.prop"));
        check("unsafe manifest path",!ModuleIntegrity.errors(staged,unsafe).isEmpty());
        Files.createDirectories(active.resolve("vendor_override"));write(active.resolve("vendor_override/cfg.db"),"payload");
        old.put("vendor_override/cfg.db",ModuleIntegrity.sha(active.resolve("vendor_override/cfg.db")));
        check("cannot drop active payload from staged manifest",!ModuleIntegrity.pendingUpdate(active,staged,old,next,"v2.6.6-dev2"));
        Files.createDirectories(staged.resolve("vendor_override"));write(staged.resolve("vendor_override/cfg.db"),"next payload");
        next.put("vendor_override/cfg.db",ModuleIntegrity.sha(staged.resolve("vendor_override/cfg.db")));
        check("verified payload update",ModuleIntegrity.pendingUpdate(active,staged,old,next,"v2.6.6-dev2"));
        write(active.resolve("vendor_override/cfg.db"),"corrupt payload");
        check("active payload corruption",!ModuleIntegrity.pendingUpdate(active,staged,old,next,"v2.6.6-dev2"));
        System.out.println("Integrity assertions: "+count+" passed");
    }
}
