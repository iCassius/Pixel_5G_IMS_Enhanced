/** Pure health decisions. A successful historical observation is never a live guarantee. */
public final class HealthRules {
    public static final long MAX_AGE_SECONDS=300;
    public static boolean fresh(String boot,String expectedBoot,String manifest,String expectedManifest,
                                long checked,long now) {
        return boot!=null && !boot.isEmpty() && boot.equals(expectedBoot) && manifest!=null &&
            manifest.matches("[0-9a-f]{64}") && manifest.equals(expectedManifest) &&
            checked>=0 && now>=checked && now-checked<=MAX_AGE_SECONDS;
    }
    public static boolean fileVerified(int mountEntries,boolean matchesPayload,boolean sameBoot,String bootFileState) {
        return matchesPayload && (mountEntries==1 || (mountEntries==0 && sameBoot && "already_identical".equals(bootFileState)));
    }
    public static String state(String phase,boolean framework,int targets,boolean bootValid,
                               boolean platform,boolean mounts,boolean consumers,boolean integrity) {
        if(!integrity || "failed".equals(phase))return "error";
        if(!"checked".equals(phase))return "waiting";
        if(targets==0)return "waiting";
        if(!framework)return "warning";
        return bootValid && platform && mounts && consumers ? "healthy" : "warning";
    }
    private HealthRules(){}
}
