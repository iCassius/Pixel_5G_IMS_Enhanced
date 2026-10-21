import android.os.SystemClock;
import android.system.Os;
import android.system.StructStat;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Root observer only: no Binder writes, mount operations or telephony process restarts. */
public final class ModuleHealth {
    private static Path mod;
    private static long now;
    private static final String[] TARGETS={"/vendor/firmware/carrierconfig/cfg.db",
        "/vendor/etc/open_carrier_info.dat","/product/etc/CarrierSettings/others.pb","/product/etc/CarrierSettings/default.pb"};
    private static final String[] PAYLOADS={"vendor_override/cfg.db","vendor_override/open_carrier_info.dat",
        "product_override/others.pb","product_override/default.pb"};
    private static final String[] CONSUMERS={"init","rild_exynos","cbd","com.shannon.imsservice",
        "com.android.phone","com.google.android.carrier"};
    private static String text(Path p)throws Exception {return new String(Files.readAllBytes(p),StandardCharsets.UTF_8).trim();}
    private static JSONObject json(Path p){try{return new JSONObject(text(p));}catch(Exception e){return new JSONObject();}}
    private static String sha(Path p)throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256");byte[] bytes=new byte[65536];
        try(InputStream in=Files.newInputStream(p)){int n;while((n=in.read(bytes))!=-1)md.update(bytes,0,n);}
        StringBuilder s=new StringBuilder();for(byte b:md.digest())s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();
    }
    private static void atomic(Path p,JSONObject value)throws Exception {
        Path tmp=p.resolveSibling(p.getFileName()+".new");
        Files.write(tmp,(value.toString()+"\n").getBytes(StandardCharsets.UTF_8));
        Files.move(tmp,p,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
    }
    private static String prop(String key)throws Exception {
        return (String)Class.forName("android.os.SystemProperties").getMethod("get",String.class).invoke(null,key);
    }
    private static String identity(Path proc)throws Exception {
        String s=text(proc.resolve("stat"));String[] fields=s.substring(s.lastIndexOf(')')+2).split(" +");
        return fields[19]+":"+Files.readSymbolicLink(proc.resolve("ns/mnt"));
    }
    private static String startTime(String pid)throws Exception {
        if(pid==null || !pid.matches("[0-9]+"))return "";
        String s=text(Paths.get("/proc",pid,"stat"));return s.substring(s.lastIndexOf(')')+2).split(" +")[19];
    }
    private static String fileIdentity(Path p)throws Exception {
        StructStat s=Os.stat(p.toString());return s.st_dev+":"+s.st_ino+":"+s.st_size+":"+s.st_mtime+":"+s.st_ctime;
    }
    private static JSONArray openTargets(Path proc,JSONArray files) {
        JSONArray opened=new JSONArray();
        try(DirectoryStream<Path> stream=Files.newDirectoryStream(proc.resolve("fd"))) {
            for(Path fd:stream)try {
                String target=Files.readSymbolicLink(fd).toString();int index=Arrays.asList(TARGETS).indexOf(target);
                if(index<0 || !files.getJSONObject(index).optBoolean("verified"))continue;
                String expected=fileIdentity(proc.resolve("root"+target));
                if(!expected.equals(fileIdentity(fd)))continue;
                if(!target.equals(Files.readSymbolicLink(fd).toString()) || !expected.equals(fileIdentity(fd)))continue;
                JSONObject evidence=new JSONObject();evidence.put("target",target);evidence.put("fd",fd.getFileName().toString());
                evidence.put("evidence","open_fd_same_inode_as_verified_payload");opened.put(evidence);
            }catch(Exception unavailable){}
        }catch(Exception unavailable){}
        return opened;
    }
    private static JSONObject view(Path proc,JSONObject manifest,JSONObject cache,JSONObject nextCache)throws Exception {
        JSONObject report=new JSONObject();String before=identity(proc);String mounts=text(proc.resolve("mountinfo"));
        JSONArray files=new JSONArray();int passed=0;
        for(int i=0;i<TARGETS.length;i++) {
            JSONObject f=new JSONObject();f.put("target",TARGETS[i]);boolean verified=false;
            try {
                int count=0;for(String line:mounts.split("\n")){String[] columns=line.split(" +");if(columns.length>5 && TARGETS[i].equals(columns[4]))count++;}
                Path p=proc.resolve("root"+TARGETS[i]);String stamp=before+":"+fileIdentity(p);
                String key=proc.getFileName()+":"+TARGETS[i];JSONObject old=cache.optJSONObject(key);
                String actual;long checked;
                if(old!=null && stamp.equals(old.optString("identity")) && now>=old.optLong("hashedAt",-1) && now-old.optLong("hashedAt",-1)<300) {
                    actual=old.getString("sha256");checked=old.getLong("hashedAt");
                } else {actual=sha(p);checked=now;}
                // Reject a file replaced during hashing, including changes hidden by the current PID.
                if(!stamp.equals(before+":"+fileIdentity(p)))throw new IllegalStateException("file_changed_during_check");
                String expected=manifest.getJSONObject("outputs").getJSONObject(PAYLOADS[i]).getString("sha256");
                verified=count==1 && expected.equals(actual);
                JSONObject entry=new JSONObject();entry.put("identity",stamp);entry.put("sha256",actual);entry.put("hashedAt",checked);nextCache.put(key,entry);
                f.put("mountEntries",count);f.put("matchesPayload",expected.equals(actual));f.put("hashedAtElapsedSeconds",checked);
            } catch(Exception e){f.put("reason",e.getClass().getSimpleName());}
            f.put("verified",verified);if(verified)passed++;files.put(f);
        }
        JSONArray opened=openTargets(proc,files);boolean stable=before.equals(identity(proc));report.put("pid",Integer.parseInt(proc.getFileName().toString()));
        report.put("processIdentity",before);report.put("stable",stable);report.put("files",files);
        report.put("verifiedFiles",stable?passed:0);report.put("verified",stable && passed==4);
        report.put("openedTargets",stable?opened:new JSONArray());return report;
    }
    private static String label(String reason) {
        switch(reason) {
            case "boot_record_missing_or_stale":return "等待重启后验证";
            case "modem_not_verified":return "当前基带尚未验证";
            case "no_ready_target_subscription":return "等待目标 SIM 就绪";
            case "framework_readback_incomplete":return "框架配置未全部通过";
            case "mounts_incomplete":return "挂载未全部通过";
            case "consumer_views_incomplete":return "相关进程尚未全部通过";
            case "module_integrity_failed":return "模块文件校验失败";
            case "framework_check_failed":return "框架检查失败，稍后重试";
            case "carrier_service_unavailable":return "等待系统配置服务";
            case "boot_in_progress":return "等待系统启动完成";
            case "boot_wait_timeout":return "等待系统启动超时";
            case "unsupported_platform":return "当前手机不在支持范围";
            case "status_record_write_failed":return "无法保存检查结果";
            case "observation_expired":return "上次检查已过期";
            case "module_disabled_or_removed":return "模块已停用";
            case "runtime_modem_conflict":return "基带与开机挂载条件不一致";
            case "boot_mount_not_completed":return "开机挂载未全部完成";
            case "boot_rollback_failed":return "开机挂载回滚失败";
            default:return "检查服务已停止";
        }
    }
    private static String card(String state,int mounts,int targets,int matched,String reason,long wall) {
        SimpleDateFormat format=new SimpleDateFormat("HH:mm",Locale.ROOT);format.setTimeZone(TimeZone.getTimeZone("Asia/Shanghai"));
        String time=format.format(new Date(wall));
        if("healthy".equals(state))return "✅ 挂载 4/4 · 框架 "+matched+"/"+targets+" 卡通过 · 适配待验证 · "+time;
        if("error".equals(state))return "❌ "+label(reason)+" · "+time;
        if("waiting".equals(state))return "⏳ "+label(reason)+" · "+time;
        return "⚠️ 挂载 "+mounts+"/4 · 框架 "+matched+"/"+targets+" 卡通过 · "+label(reason)+" · "+time;
    }
    private static boolean publish(String description)throws Exception {
        ProcessBuilder builder=new ProcessBuilder("/data/adb/ksud","module","config","set","--temp","override.description",description);
        builder.environment().put("KSU_MODULE","EnablePixel5G");
        builder.redirectOutput(ProcessBuilder.Redirect.to(new java.io.File("/dev/null")));
        builder.redirectError(ProcessBuilder.Redirect.to(new java.io.File("/dev/null")));
        Process p=builder.start();if(!p.waitFor(3,TimeUnit.SECONDS)){p.destroyForcibly();return false;}return p.exitValue()==0;
    }
    public static void main(String[] args)throws Exception {
        if(args.length!=3)throw new IllegalArgumentException("Expected module directory, phase, reason");
        mod=Paths.get(args[0]);String phase=args[1],reason=args[2];now=SystemClock.elapsedRealtime()/1000;
        String boot=text(Paths.get("/proc/sys/kernel/random/boot_id")),manifestHash=sha(mod.resolve("manifest.json"));
        JSONObject previous=json(mod.resolve("health.json"));
        if("inspect".equals(phase) || "summary".equals(phase)) {
            boolean fresh=HealthRules.fresh(previous.optString("bootId"),boot,previous.optString("manifestSha256"),manifestHash,
                previous.optLong("checkedAtElapsedSeconds",-1),now);
            String expiredReason="observation_expired";
            String owner=previous.optString("supervisorPid"),start=previous.optString("supervisorStart");
            if(!owner.isEmpty())try{if(start.isEmpty() || !start.equals(startTime(owner))){fresh=false;expiredReason="supervisor_stopped";}}
                catch(Exception dead){fresh=false;expiredReason="supervisor_stopped";}
            previous.put("fresh",fresh);if(!fresh){previous.put("state","waiting");
                previous.put("reason",expiredReason);previous.put("description",card("waiting",0,0,0,expiredReason,System.currentTimeMillis()));}
            System.out.println("summary".equals(phase)?previous.optString("description","尚无检查结果"):previous.toString());return;
        }
        JSONObject result=new JSONObject(),manifest=json(mod.resolve("manifest.json")),bootRecord=json(mod.resolve("boot-mount.json"));
        boolean bootValid=boot.equals(bootRecord.optString("bootId")) && manifestHash.equals(bootRecord.optString("manifestSha256")) && bootRecord.optInt("schema")==1;
        boolean bootPassed=bootValid && "verified_in_script_namespace".equals(bootRecord.optString("result"));
        boolean integrity=true;JSONArray integrityErrors=new JSONArray();
        for(String node:new String[]{"override.dex","health.sh","service.sh","control.sh","compatibility.sh","policy.json","full-files.tsv","post-fs-data.sh","diagnose.sh","action.sh","module.prop"}) {
            try {if(!sha(mod.resolve(node)).equals(manifest.getJSONObject("outputs").getJSONObject(node).getString("sha256")))throw new IllegalStateException();}
            catch(Exception e){integrity=false;integrityErrors.put(node);}
        }
        boolean platform=Compatibility.eligible(prop("ro.product.manufacturer"),prop("ro.product.brand"),prop("ro.product.model"),Integer.parseInt(prop("ro.build.version.sdk")));
        boolean probe="probe".equals(phase),checked="checked".equals(phase) || probe;
        if(probe)phase="checked";
        JSONObject framework=checked?json(mod.resolve("status.json")):new JSONObject();
        JSONObject observation=framework.optJSONObject("observation");
        boolean frameworkFresh=observation!=null && HealthRules.fresh(observation.optString("bootId"),boot,
            observation.optString("manifestSha256"),manifestHash,observation.optLong("checkedAtElapsedSeconds",-1),now);
        JSONArray rows=framework.optJSONArray("subscriptions");int targets=framework.optInt("targetCount",0),matched=0;
        if(rows!=null)for(int i=0;i<rows.length();i++) {
            JSONObject row=rows.optJSONObject(i);
            if(row!=null && row.optInt("managedKeyCount")==6 && row.optBoolean("matchesPolicy") && "framework".equals(row.optString("effectivePolicy")))matched++;
        }
        boolean frameworkGood=frameworkFresh && targets>0 && matched==targets && rows!=null && rows.length()==targets;
        JSONObject cache=new JSONObject();
        if(boot.equals(previous.optString("bootId")) && manifestHash.equals(previous.optString("manifestSha256")))cache=previous.optJSONObject("hashCache");
        if(cache==null)cache=new JSONObject();JSONObject nextCache=new JSONObject();JSONArray processes=new JSONArray();
        Set<String> names=new HashSet<>();int mountCount=0;boolean consumersGood=true;
        if(checked && integrity && platform) {
            try(DirectoryStream<Path> stream=Files.newDirectoryStream(Paths.get("/proc"))) {
                for(Path proc:stream) {
                    if(!proc.getFileName().toString().matches("[0-9]+"))continue;
                    String name;try{name=new String(Files.readAllBytes(proc.resolve("cmdline")),StandardCharsets.UTF_8).split("\u0000",-1)[0];name=name.substring(name.lastIndexOf('/')+1);}
                    catch(Exception e){continue;}
                    if(!Arrays.asList(CONSUMERS).contains(name))continue;
                    // init also has a vendor subcontext worker; only PID 1 proves the global view.
                    if("init".equals(name) && !"1".equals(proc.getFileName().toString()))continue;
                    names.add(name);JSONObject report;
                    try{report=view(proc,manifest,cache,nextCache);}catch(Exception e){report=new JSONObject();report.put("verified",false);report.put("reason","process_unavailable_or_changed");}
                    report.put("name",name);processes.put(report);
                    if("init".equals(name))mountCount=report.optInt("verifiedFiles");
                    if(!report.optBoolean("verified"))consumersGood=false;
                }
            }
        }
        JSONArray missing=new JSONArray();for(String name:CONSUMERS)if(!names.contains(name)){missing.put(name);consumersGood=false;}
        String state=HealthRules.state(phase,frameworkGood,targets,bootPassed,platform,mountCount==4,consumersGood,integrity);
        if(checked) {
            if(!integrity)reason="module_integrity_failed";
            else if(!bootValid)reason="boot_record_missing_or_stale";
            else if(!bootPassed)reason="boot_mount_not_completed";
            else if(!platform)reason="unsupported_platform";
            else if(targets==0)reason="no_ready_target_subscription";
            else if(!frameworkGood)reason="framework_readback_incomplete";
            else if(mountCount!=4)reason="mounts_incomplete";
            else if(!consumersGood)reason="consumer_views_incomplete";
            else reason="mounts_and_framework_verified";
        }
        if(checked && bootValid && "rollback_failed".equals(bootRecord.optString("result"))) {
            state="error";reason="boot_rollback_failed";
        }
        long wall=System.currentTimeMillis();result.put("schema",1);result.put("bootId",boot);result.put("manifestSha256",manifestHash);
        result.put("checkedAtElapsedSeconds",now);result.put("checkedAt",wall);result.put("validForSeconds",HealthRules.MAX_AGE_SECONDS);
        result.put("supervisorPid",System.getenv("PIXELIMS_SUPERVISOR_PID"));result.put("supervisorStart",System.getenv("PIXELIMS_SUPERVISOR_START"));
        result.put("state",state);result.put("phase",phase);result.put("reason",reason);result.put("bootRecordValid",bootValid);
        result.put("bootMountSucceeded",bootPassed);
        result.put("integrityErrors",integrityErrors);result.put("platformEligible",platform);result.put("compatibilityMode","pixel9_10_experimental");result.put("firmwareValidation","not_performed");result.put("observedBaseband",prop("gsm.version.baseband"));result.put("mountedFiles",mountCount);
        result.put("bootResult",bootRecord.optString("result","unknown"));result.put("bootReason",bootRecord.optString("reason","record_unavailable"));
        result.put("bootGroups",bootRecord.optJSONObject("groups"));result.put("modemEvidence",bootRecord.optString("modemEvidence","unknown"));
        result.put("device",prop("ro.product.device"));result.put("build",prop("ro.build.display.id"));
        result.put("slot",prop("ro.boot.slot_suffix"));
        result.put("targetCount",targets);result.put("matchedSubscriptions",matched);result.put("frameworkReadbackVerified",checked && frameworkGood);
        result.put("frameworkObservationFresh",frameworkFresh);
        result.put("consumerViewsVerified",consumersGood);result.put("processes",processes);result.put("missingProcesses",missing);result.put("hashCache",nextCache);
        result.put("consumerLoad","parsing_and_application_unproven");result.put("businessValidation","not_tested");
        String description=card(state,mountCount,targets,matched,reason,wall);result.put("description",description);
        // Save evidence before publishing. Card failures never erase the actual check result.
        atomic(mod.resolve("health.json"),result);
        boolean cardPublished=false;if(!probe)try{cardPublished=publish(description);}catch(Exception unsupported){}
        result.put("cardPublished",cardPublished);atomic(mod.resolve("health.json"),result);
        if("healthy".equals(state))atomic(mod.resolve("health-last-good.json"),result);
        // Bounded history contains only boot summary, no subscriber or hardware identities.
        if(!boot.equals(previous.optString("bootId")) || !manifestHash.equals(previous.optString("manifestSha256"))) {
            JSONObject history=json(mod.resolve("health-history.json"));JSONArray entries=history.optJSONArray("entries"), kept=new JSONArray();
            if(entries!=null)for(int i=Math.max(0,entries.length()-3);i<entries.length();i++)kept.put(entries.get(i));
            JSONObject summary=new JSONObject();summary.put("checkedAt",wall);summary.put("version",manifest.optString("module_version"));
            summary.put("bootRecordValid",bootValid);
            summary.put("bootResult",bootValid?bootRecord.optString("result","unknown"):"unknown");
            summary.put("bootReason",bootValid?bootRecord.optString("reason","record_unavailable"):"record_missing_or_stale");
            kept.put(summary);history.put("entries",kept);atomic(mod.resolve("health-history.json"),history);
        }
        System.out.println(result);
    }
}
