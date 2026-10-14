import android.os.IBinder;
import android.os.PersistableBundle;
import android.os.SystemClock;
import android.telephony.SubscriptionInfo;
import android.telephony.TelephonyManager;
import android.telephony.CarrierConfigManager;
import java.security.MessageDigest;
import org.json.JSONObject;
import org.json.JSONArray;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

/** Single Binder boundary; no Xposed/companion API or package dependency. */
public final class ApplyCarrierOverride {
    // control.sh runs this helper as system UID 1000; use that UID's package identity.
    private static final String CALLER_PACKAGE="android";
    private static Object service(String name, String stub) throws Exception {
        Object binder = Class.forName("android.os.ServiceManager").getMethod("getService", String.class).invoke(null,name);
        if (binder == null) throw new IllegalStateException("Service unavailable: " + name);
        return Class.forName(stub).getMethod("asInterface", IBinder.class).invoke(null,binder);
    }
    private static String prop(String key) throws Exception {
        return (String) Class.forName("android.os.SystemProperties").getMethod("get",String.class).invoke(null,key);
    }
    private static PersistableBundle bundle(JSONObject values) throws Exception {
        PersistableBundle result = new PersistableBundle();
        Iterator<String> keys = values.keys();
        while(keys.hasNext()) {
            String k=keys.next(); Object v=values.get(k);
            if(v instanceof Boolean) result.putBoolean(k,(Boolean)v);
            else if(v instanceof Integer) result.putInt(k,(Integer)v);
            else if(v instanceof JSONArray) {
                JSONArray a=(JSONArray)v; int[] data=new int[a.length()];
                for(int i=0;i<data.length;i++) data[i]=a.getInt(i);
                result.putIntArray(k,data);
            } else throw new IllegalArgumentException("Unsupported policy value: "+k);
        }
        return result;
    }
    private static PersistableBundle read(Object loader, int sid) throws Exception {
        try {
            return (PersistableBundle)loader.getClass().getMethod("getConfigForSubIdWithFeature",int.class,String.class,String.class)
                    .invoke(loader,sid,CALLER_PACKAGE,null);
        } catch(NoSuchMethodException older) {
            return (PersistableBundle)loader.getClass().getMethod("getConfigForSubId",int.class,String.class)
                    .invoke(loader,sid,CALLER_PACKAGE);
        }
    }
    private static boolean equal(PersistableBundle current,PersistableBundle desired) {
        if(current==null) return false;
        for(String k:desired.keySet()) {
            if(!current.containsKey(k))return false;
            Object a=current.get(k),b=desired.get(k);
            if(a instanceof int[] && b instanceof int[]) { if(!Arrays.equals((int[])a,(int[])b))return false; }
            else if(!Objects.equals(a,b))return false;
        }
        return true;
    }
    private interface ConfigReader {PersistableBundle get() throws Exception;}
    private static PersistableBundle await(ConfigReader reader,PersistableBundle desired,long timeout)throws Exception {
        long until=SystemClock.elapsedRealtime()+timeout;
        PersistableBundle actual;
        do {actual=reader.get();if(equal(actual,desired))return actual;SystemClock.sleep(250);}while(SystemClock.elapsedRealtime()<until);
        throw new IllegalStateException("Full managed read-back timed out");
    }
    private static void selfTest(JSONObject policy)throws Exception {
        PersistableBundle desired=bundle(policy.getJSONObject("common"));desired.putAll(bundle(policy.getJSONObject("base")));
        final PersistableBundle previous=bundle(policy.getJSONObject("common"));previous.putAll(bundle(policy.getJSONObject("vcrbt")));
        previous.putString("other_owner_key","retained");
        if(equal(previous,desired))throw new AssertionError("Stale vcrbt matched base");
        long start=SystemClock.elapsedRealtime();
        PersistableBundle result=await(()->{if(SystemClock.elapsedRealtime()-start>=300)previous.putAll(desired);return previous;},desired,2000);
        if(!"retained".equals(result.getString("other_owner_key")))throw new AssertionError("Unrelated owner erased");
        PersistableBundle missing=new PersistableBundle(desired);missing.remove("carrier_vt_available_bool");
        if(equal(missing,desired))throw new AssertionError("Missing false key accepted");
        PersistableBundle wrongArray=new PersistableBundle(desired);wrongArray.putIntArray("ims.capability_type_video_int_array",new int[]{0,1});
        if(equal(wrongArray,desired))throw new AssertionError("Array mismatch accepted");
        try {await(()->missing,desired,300);throw new AssertionError("Timeout not enforced");}catch(IllegalStateException expected){}
        System.out.println("{\"selfTest\":\"passed\",\"assertions\":5,\"evidence\":\"android_bundle_and_async_model_not_binder_write\"}");
    }
    @SuppressWarnings("unchecked")
    private static List<SubscriptionInfo> subscriptions(Object sub) throws Exception {
        List<SubscriptionInfo> result;
        try {result=(List<SubscriptionInfo>)sub.getClass().getMethod("getActiveSubscriptionInfoList",String.class,String.class,boolean.class)
            .invoke(sub,CALLER_PACKAGE,null,false);}
        catch(NoSuchMethodException older) {result=(List<SubscriptionInfo>)sub.getClass().getMethod("getActiveSubscriptionInfoList",String.class,String.class)
            .invoke(sub,CALLER_PACKAGE,null);}
        return result==null?Collections.emptyList():result;
    }
    private static boolean loaded(SubscriptionInfo info) throws Exception {
        String[] states=prop("gsm.sim.state").split(",",-1);int slot=info.getSimSlotIndex();
        return slot>=0 && slot<states.length && "LOADED".equals(states[slot]);
    }
    private static boolean callIdle() throws Exception {
        Object telecom=service("telecom","com.android.internal.telecom.ITelecomService$Stub");
        return !(Boolean)telecom.getClass().getMethod("isInCall",String.class,String.class).invoke(telecom,CALLER_PACKAGE,null);
    }
    private static void idle() throws Exception {
        if(!callIdle())
            throw new IllegalStateException("Call in progress; policy write deferred");
    }
    private static boolean fullFiles(JSONObject policy) {
        try {
            JSONObject files=policy.getJSONObject("full_files");Iterator<String> names=files.keys();
            while(names.hasNext()) {
                String path=names.next();byte[] digest=MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Paths.get(path)));
                StringBuilder text=new StringBuilder();for(byte value:digest)text.append(String.format("%02x",value & 255));
                JSONArray accepted=files.getJSONArray(path);boolean found=false;
                for(int i=0;i<accepted.length();i++)if(text.toString().equals(accepted.getString(i)))found=true;
                if(!found)return false;
            }
            return files.length()==4;
        }catch(Exception unavailable){return false;}
    }
    private static PersistableBundle fallback(PersistableBundle current) {
        Map<String,Object> values=new HashMap<>();for(String key:current.keySet())values.put(key,current.get(key));
        PersistableBundle result=new PersistableBundle();
        for(Map.Entry<String,Object> entry:Compatibility.fallback(values).entrySet()) {
            if(entry.getValue() instanceof Boolean)result.putBoolean(entry.getKey(),(Boolean)entry.getValue());
            else result.putIntArray(entry.getKey(),(int[])entry.getValue());
        }
        return result;
    }
    private static void stillTarget(Object sub,SubscriptionInfo previous)throws Exception {
        for(SubscriptionInfo now:subscriptions(sub))if(now.getSubscriptionId()==previous.getSubscriptionId() &&
            now.getSimSlotIndex()==previous.getSimSlotIndex() && now.getCarrierId()==previous.getCarrierId() &&
            Objects.equals(now.getMccString(),previous.getMccString()) && Objects.equals(now.getMncString(),previous.getMncString()) && loaded(now))return;
        throw new IllegalStateException("Subscription changed; write deferred");
    }
    public static void main(String[] args) {
        try {
            String profile="base",path=null; boolean status=false,transientOnly=false,selfTest=false;String cdma="keep";
            for(int i=0;i<args.length;i++) {
                switch(args[i]) {
                    case "--policy": path=args[++i];break;
                    case "--profile": profile=args[++i];break;
                    case "--status": status=true;break;
                    case "--self-test": selfTest=true;break;
                    case "--transient": transientOnly=true;break;
                    case "--cdma": cdma=args[++i];break;
                    case "--disable-cdma": cdma="disable";break;
                    case "--restore": throw new IllegalArgumentException("Full override clear is unsafe in a shared store. Use managed base policy; factory restore requires ownership audit.");
                    default: throw new IllegalArgumentException("Unknown argument: "+args[i]);
                }
            }
            if(path==null || !(profile.equals("base")||profile.equals("vcrbt")) ||
                    !(cdma.equals("keep")||cdma.equals("disable")||cdma.equals("enable")))
                throw new IllegalArgumentException("Required: --policy FILE --profile base|vcrbt [--cdma keep|disable|enable] [--status]");
            JSONObject policy=new JSONObject(new String(Files.readAllBytes(Paths.get(path)),"UTF-8"));
            int sdk=Integer.parseInt(prop("ro.build.version.sdk"));
            if(policy.getInt("schema")!=1 || !Compatibility.eligible(prop("ro.product.manufacturer"),prop("ro.product.brand"),prop("ro.product.model"),sdk))
                throw new IllegalStateException("Unsupported Pixel/platform; no writes");
            if(selfTest){selfTest(policy);return;}
            boolean full=Compatibility.fullIdentity(prop("ro.product.device"),prop("ro.build.display.id"),prop("gsm.version.baseband")) && fullFiles(policy);
            if(!full && !cdma.equals("keep"))throw new IllegalStateException("CDMA changes forbidden in framework fallback");
            Object loader=service("carrier_config","com.android.internal.telephony.ICarrierConfigLoader$Stub");
            Object sub=service("isub","com.android.internal.telephony.ISub$Stub");
            Method writer=null;
            try {writer=loader.getClass().getMethod("overrideConfig",int.class,PersistableBundle.class,boolean.class);}
            catch(NoSuchMethodException unavailable) {if(!status)throw new IllegalStateException("CarrierConfig write interface unavailable");}
            int matches=0;JSONArray reports=new JSONArray();
            List<SubscriptionInfo> active=subscriptions(sub);
            Set<Integer> seen=new HashSet<>();
            for(SubscriptionInfo info:active)if(!seen.add(info.getSubscriptionId()))throw new IllegalStateException("Duplicate active subscription");
            for(SubscriptionInfo info:active) {
                String operator=Compatibility.carrier(info.getMccString(),info.getMncString());
                if(operator==null)continue; // International and unknown PLMNs retain native policy.
                if(!loaded(info))continue;
                matches++;int sid=info.getSubscriptionId();PersistableBundle actual=read(loader,sid);
                if(!CarrierConfigManager.isConfigForIdentifiedCarrier(actual))throw new IllegalStateException("Carrier config not identified");
                boolean fullTarget=full && info.getCarrierId()==policy.getInt("carrier_id") &&
                    policy.getString("mcc").equals(info.getMccString()) && policy.getString("mnc").equals(info.getMncString());
                PersistableBundle desired;
                if(fullTarget) {
                    desired=fallback(actual);
                    desired.putAll(bundle(policy.getJSONObject("common")));desired.putAll(bundle(policy.getJSONObject(profile)));
                    if(!cdma.equals("keep"))desired.putBoolean("support_cdma_1x_voice_calls_bool",cdma.equals("enable"));
                } else desired=fallback(actual);
                boolean wrote=false;
                if(!status && !desired.isEmpty() && !equal(actual,desired)) {
                    stillTarget(sub,info);idle();
                    // Fallback never stores portable guesses as persistent overrides across an OTA.
                    writer.invoke(loader,sid,desired,fullTarget && !transientOnly);
                    wrote=true;actual=await(()->read(loader,sid),desired,12000);
                }
                JSONObject row=new JSONObject();row.put("subId",sid);row.put("slot",info.getSimSlotIndex());
                row.put("operator",operator);row.put("tier",fullTarget?"full":"framework-only");row.put("wrote",wrote);
                row.put("observedAt",System.currentTimeMillis());row.put("requestedProfile",profile);
                row.put("effectiveProfile",fullTarget?profile:"framework");row.put("managedKeyCount",desired.size());
                row.put("matchesPolicy",equal(actual,desired));row.put("evidence","effective_config_readback");
                JSONObject values=new JSONObject();
                for(String k:desired.keySet())if(actual!=null&&actual.containsKey(k)) {
                    Object v=actual.get(k);values.put(k,v instanceof int[]?new JSONArray((int[])v):v);
                }
                row.put("values",values);reports.put(row);
            }
            JSONObject result=new JSONObject();result.put("fullBaseline",full);result.put("subscriptions",reports);
            result.put("apiLevel",sdk);result.put("writeInterfaceAvailable",writer!=null);
            result.put("modemBaseline",Compatibility.modemMatches(prop("gsm.version.baseband")));
            try {result.put("callIdle",callIdle());result.put("callStateInterfaceAvailable",true);}
            catch(Exception unavailable) {result.put("callStateInterfaceAvailable",false);}
            result.put("targetCount",matches);result.put("internationalPolicy","unchanged");System.out.println(result.toString());
        }catch(Throwable t){System.err.println("[ERROR] "+t);System.exit(1);}
    }
}
