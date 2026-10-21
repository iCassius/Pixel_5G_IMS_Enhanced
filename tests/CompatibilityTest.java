import java.util.*;
public final class CompatibilityTest {
    private static int count=0;
    private static void check(String name,boolean value){count++;if(!value)throw new AssertionError(name);}
    public static void main(String[] args) {
        String boot="01234567-0123-4567-89ab-0123456789ab", digest=String.join("",Collections.nCopies(64,"a"));
        check("same boot and release",Compatibility.sameBootEvidence(boot,boot,digest,digest));
        check("old boot rejected",!Compatibility.sameBootEvidence("11234567-0123-4567-89ab-0123456789ab",boot,digest,digest));
        check("old release rejected",!Compatibility.sameBootEvidence(boot,boot,"b"+digest.substring(1),digest));
        check("empty evidence rejected",!Compatibility.sameBootEvidence("","","",""));
        check("missing evidence rejected",!Compatibility.sameBootEvidence(null,null,null,null));
        check("malformed boot rejected",!Compatibility.sameBootEvidence("bad","bad",digest,digest));
        check("malformed digest rejected",!Compatibility.sameBootEvidence(boot,boot,"bad","bad"));
        for(String model:Arrays.asList("Pixel 9","Pixel 9 Pro","Pixel 9 Pro XL","Pixel 9 Pro Fold","Pixel 9a",
            "Pixel 10","Pixel 10 Pro","Pixel 10 Pro XL","Pixel 10 Pro Fold","Pixel 10a"))
            check("allowed "+model,Compatibility.eligible("Google","google",model,36));
        for(String model:Arrays.asList("Pixel 6","Pixel 7","Pixel 8","Pixel 8a","Pixel 11","Pixel 90","Pixel 10 Other"))
            check("excluded "+model,!Compatibility.eligible("Google","google",model,36));
        check("no SDK ceiling",Compatibility.eligible("Google","google","Pixel 10",99));
        check("old SDK",!Compatibility.eligible("Google","google","Pixel 10",30));
        check("wrong vendor",!Compatibility.eligible("Other","google","Pixel 10",36));
        check("wrong brand",!Compatibility.eligible("Google","other","Pixel 10",36));
        for(String mnc:new String[]{"00","02","04","07","08","01","06","09","03","05","11","15"})
            check("domestic "+mnc,Compatibility.carrier("460",mnc)!=null);
        for(String mcc:new String[]{"310","234","454","466",""})check("international "+mcc,Compatibility.carrier(mcc,"11")==null);
        check("unknown China PLMN",Compatibility.carrier("460","99")==null);
        check("missing MNC",Compatibility.carrier("460",null)==null);
        Map<String,Object> current=new HashMap<>();
        current.put("carrier_volte_available_bool",false);current.put("carrier_wfc_ims_available_bool",false);
        current.put("vonr_enabled_bool",false);current.put("vonr_on_by_default_bool",false);current.put("vonr_setting_visibility_bool",false);
        current.put("carrier_nr_availabilities_int_array",new int[]{1});
        current.put("vendor.ims.carrier_video_over_lte_bool",false);current.put("support_cdma_1x_voice_calls_bool",true);
        current.put("carrier_vt_available_bool",true);current.put("carrier_default_wfc_ims_mode_int",2);
        Map<String,Object> modern=Compatibility.fallback(current);
        check("all portable keys",modern.size()==6);
        check("SA and NSA",Arrays.equals((int[])modern.get("carrier_nr_availabilities_int_array"),new int[]{1,2}));
        check("present backported keys accepted",Compatibility.fallback(current).size()==6);
        check("input unchanged",Boolean.FALSE.equals(current.get("vonr_enabled_bool")));
        for(String excluded:new String[]{"vendor.ims.carrier_video_over_lte_bool","support_cdma_1x_voice_calls_bool","carrier_vt_available_bool","carrier_default_wfc_ims_mode_int"})
            check("native retained "+excluded,!modern.containsKey(excluded));
        check("absent keys skipped",Compatibility.fallback(Collections.emptyMap()).isEmpty());
        current.put("vonr_enabled_bool","false");check("wrong bool type skipped",!Compatibility.fallback(current).containsKey("vonr_enabled_bool"));
        current.put("carrier_nr_availabilities_int_array",new int[]{1,99});
        check("future enum preserved",!Compatibility.fallback(current).containsKey("carrier_nr_availabilities_int_array"));
        current.put("carrier_nr_availabilities_int_array","1,2");
        check("wrong array type skipped",!Compatibility.fallback(current).containsKey("carrier_nr_availabilities_int_array"));
        System.out.println("Compatibility assertions: "+count+" passed");
    }
}
