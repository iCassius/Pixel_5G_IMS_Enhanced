import java.util.*;
public final class CompatibilityTest {
    private static int count=0;
    private static void check(String name,boolean value){count++;if(!value)throw new AssertionError(name);}
    public static void main(String[] args) {
        for(int generation=6;generation<=11;generation++)
            check("Pixel family "+generation,Compatibility.eligible("Google","google","Pixel "+generation,36));
        check("unknown SDK",!Compatibility.eligible("Google","google","Pixel 11",37));
        check("old SDK",!Compatibility.eligible("Google","google","Pixel 6",30));
        check("wrong vendor",!Compatibility.eligible("Other","google","Pixel 10",36));
        check("wrong model",!Compatibility.eligible("Google","google","Pixel 5",36));
        check("full exact",Compatibility.fullIdentity("mustang","CP3A.260905.009","g5400i-260604-260807-B-16035863"));
        for(String value:new String[]{"","unknown","g5400i-250605-250825-B-13984049","g5400i-260604-260807-B-16035863,new"})
            check("wrong/empty modem",!Compatibility.fullIdentity("mustang","CP3A.260905.009",value));
        check("other device",!Compatibility.fullIdentity("other","CP3A.260905.009","g5400i-260604-260807-B-16035863"));
        check("OTA",!Compatibility.fullIdentity("mustang","new","g5400i-260604-260807-B-16035863"));
        for(String mnc:new String[]{"00","02","04","07","08","01","06","09","03","05","11","15"})
            check("domestic "+mnc,Compatibility.carrier("460",mnc)!=null);
        for(String mcc:new String[]{"310","234","454","466",""})check("international "+mcc,Compatibility.carrier(mcc,"11")==null);
        check("unknown China PLMN",Compatibility.carrier("460","99")==null);
        Map<String,Object> current=new HashMap<>();
        current.put("carrier_volte_available_bool",false);current.put("carrier_wfc_ims_available_bool",false);
        current.put("vonr_enabled_bool",false);current.put("vonr_on_by_default_bool",false);current.put("vonr_setting_visibility_bool",false);
        current.put("carrier_nr_availabilities_int_array",new int[]{1});
        current.put("vendor.ims.carrier_video_over_lte_bool",false);current.put("support_cdma_1x_voice_calls_bool",true);
        current.put("carrier_vt_available_bool",true);current.put("carrier_default_wfc_ims_mode_int",2);
        Map<String,Object> modern=Compatibility.fallback(current,36);
        check("all portable keys",modern.size()==6);
        check("SA and NSA",Arrays.equals((int[])modern.get("carrier_nr_availabilities_int_array"),new int[]{1,2}));
        check("API31 excludes VoNR",Compatibility.fallback(current,31).size()==3);
        check("input unchanged",Boolean.FALSE.equals(current.get("vonr_enabled_bool")));
        for(String excluded:new String[]{"vendor.ims.carrier_video_over_lte_bool","support_cdma_1x_voice_calls_bool","carrier_vt_available_bool","carrier_default_wfc_ims_mode_int"})
            check("native retained "+excluded,!modern.containsKey(excluded));
        check("absent keys skipped",Compatibility.fallback(Collections.emptyMap(),36).isEmpty());
        current.put("vonr_enabled_bool","false");check("wrong bool type skipped",!Compatibility.fallback(current,36).containsKey("vonr_enabled_bool"));
        current.put("carrier_nr_availabilities_int_array",new int[]{1,99});
        check("future enum preserved",!Compatibility.fallback(current,36).containsKey("carrier_nr_availabilities_int_array"));
        current.put("carrier_nr_availabilities_int_array","1,2");
        check("wrong array type skipped",!Compatibility.fallback(current,36).containsKey("carrier_nr_availabilities_int_array"));
        System.out.println("Compatibility assertions: "+count+" passed");
    }
}
