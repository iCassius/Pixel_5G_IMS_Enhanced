import java.io.StringReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Static-file checks shared by the observer and host regression tests. */
public final class ModuleIntegrity {
    private static final Set<String> REQUIRED=new HashSet<>(Arrays.asList(
        "override.dex","health.sh","service.sh","control.sh","compatibility.sh","policy.json",
        "full-files.tsv","post-fs-data.sh","diagnose.sh","action.sh","module.prop"));
    public static String sha(Path path)throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256");byte[] bytes=new byte[65536];
        try(java.io.InputStream in=Files.newInputStream(path)){int n;while((n=in.read(bytes))!=-1)md.update(bytes,0,n);}
        StringBuilder out=new StringBuilder();for(byte b:md.digest())out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();
    }
    public static List<String> errors(Path directory,Map<String,String> outputs) {
        directory=directory.toAbsolutePath().normalize();
        List<String> errors=new ArrayList<>();
        for(String key:REQUIRED)if(!outputs.containsKey(key))errors.add(key);
        for(Map.Entry<String,String> entry:outputs.entrySet()) {
            String key=entry.getKey();
            // The manager removes the installer after a successful installation.
            if("customize.sh".equals(key))continue;
            try {
                Path relative=Paths.get(key),file=directory.resolve(relative).normalize();
                if(relative.isAbsolute() || !file.startsWith(directory.normalize()) ||
                    !entry.getValue().matches("[0-9a-f]{64}") ||
                    !Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS) ||
                    !entry.getValue().equals(sha(file)))throw new IllegalStateException();
            }catch(Exception invalid){errors.add(key);}
        }
        return errors;
    }
    public static boolean pendingUpdate(Path active,Path staged,Map<String,String> current,
                                        Map<String,String> next,String nextVersion) {
        try {
            String before=sha(staged.resolve("manifest.json"));
            if(!Files.isRegularFile(active.resolve("update"),LinkOption.NOFOLLOW_LINKS) ||
                !errors(active,current).equals(Collections.singletonList("module.prop")) ||
                !errors(staged,next).isEmpty())return false;
            for(String payload:Arrays.asList("vendor_override/cfg.db","vendor_override/open_carrier_info.dat",
                    "product_override/others.pb","product_override/default.pb"))
                if(current.containsKey(payload) && !next.containsKey(payload))return false;
            String stagedProp=sha(staged.resolve("module.prop"));
            if(!stagedProp.equals(sha(active.resolve("module.prop"))))return false;
            Properties props=new Properties();props.load(new StringReader(new String(Files.readAllBytes(staged.resolve("module.prop")),StandardCharsets.UTF_8)));
            return "EnablePixel5G".equals(props.getProperty("id")) && nextVersion!=null &&
                nextVersion.matches("v[0-9]+\\.[0-9]+\\.[0-9]+(?:-[A-Za-z0-9.-]+)?") &&
                nextVersion.equals(props.getProperty("version")) && Integer.parseInt(props.getProperty("versionCode"))>0 &&
                stagedProp.equals(sha(active.resolve("module.prop"))) && before.equals(sha(staged.resolve("manifest.json"))) &&
                Files.exists(active.resolve("update"));
        }catch(Exception invalid){return false;}
    }
    private ModuleIntegrity(){}
}
