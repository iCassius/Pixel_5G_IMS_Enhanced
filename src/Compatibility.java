import java.util.*;

/** Pure compatibility and fallback rules, maintained by iCassius. */
public final class Compatibility {
    public static boolean eligible(String manufacturer, String brand, String model, int sdk) {
        if(!"Google".equals(manufacturer) || !"google".equals(brand) || sdk<31)return false;
        return Arrays.asList("Pixel 6","Pixel 6 Pro","Pixel 6a","Pixel 7","Pixel 7 Pro","Pixel 7a",
            "Pixel 8","Pixel 8 Pro","Pixel 8a","Pixel 9","Pixel 9 Pro","Pixel 9 Pro XL","Pixel 9 Pro Fold","Pixel 9a",
            "Pixel 10","Pixel 10 Pro","Pixel 10 Pro XL","Pixel 10 Pro Fold","Pixel 10a",
            "Pixel 11","Pixel 11 Pro","Pixel 11 Pro XL","Pixel 11 Pro Fold","Pixel 11a").contains(model);
    }
    public static boolean fullIdentity(String device,String build,String baseband) {
        return "mustang".equals(device) && "CP3A.260905.009".equals(build) &&
            modemMatches(baseband);
    }
    public static boolean modemMatches(String baseband) {
        if(baseband==null || baseband.isEmpty())return false;
        for(String modem:baseband.split(",",-1))
            if(!"g5400i-260604-260807-B-16035863".equals(modem.trim()))return false;
        return true;
    }
    public static String carrier(String mcc,String mnc) {
        if(!"460".equals(mcc))return null;
        switch(mnc) {
            case "00":case "02":case "04":case "07":case "08":return "China Mobile";
            case "01":case "06":case "09":return "China Unicom";
            case "03":case "05":case "11":return "China Telecom";
            case "15":return "China Broadnet";
            default:return null;
        }
    }
    public static Map<String,Object> fallback(Map<String,Object> current) {
        Map<String,Object> result=new LinkedHashMap<>();
        for(String key:new String[]{"carrier_volte_available_bool","carrier_wfc_ims_available_bool",
                "vonr_enabled_bool","vonr_on_by_default_bool","vonr_setting_visibility_bool"}) {
            if(current.get(key) instanceof Boolean)result.put(key,true);
        }
        if(current.get("carrier_nr_availabilities_int_array") instanceof int[]) {
            int[] old=(int[])current.get("carrier_nr_availabilities_int_array");
            // Preserve unknown future values: never replace an unfamiliar enum with guessed values.
            boolean known=true;for(int value:old)if(value!=1 && value!=2)known=false;
            if(known)result.put("carrier_nr_availabilities_int_array",new int[]{1,2});
        }
        return result;
    }
}
