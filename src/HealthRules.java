/** Pure health decisions. A successful historical observation is never a live guarantee. */
public final class HealthRules {
    public static final long MAX_AGE_SECONDS=300;
    public static boolean fresh(String boot,String expectedBoot,String manifest,String expectedManifest,
                                long checked,long now) {
        return boot!=null && !boot.isEmpty() && boot.equals(expectedBoot) && manifest!=null &&
            manifest.matches("[0-9a-f]{64}") && manifest.equals(expectedManifest) &&
            checked>=0 && now>=checked && now-checked<=MAX_AGE_SECONDS;
    }
    public static String state(String phase,boolean framework,int targets,boolean bootValid,
                               boolean modem,boolean mounts,boolean consumers,boolean integrity) {
        if(!integrity || "failed".equals(phase))return "error";
        if(!"checked".equals(phase))return "waiting";
        if(targets==0)return "waiting";
        if(!framework)return "warning";
        return bootValid && modem && mounts && consumers ? "healthy" : "warning";
    }
    private HealthRules(){}
}
