public final class HealthRulesTest {
    private static int n;
    private static void check(boolean condition){n++;if(!condition)throw new AssertionError("health assertion "+n);}
    public static void main(String[] args){
        String h=new String(new char[64]).replace('\0','a');
        check(HealthRules.fresh("boot","boot",h,h,100,100));
        check(HealthRules.fresh("boot","boot",h,h,100,400));
        check(!HealthRules.fresh("boot","boot",h,h,100,401));
        check(!HealthRules.fresh("old","boot",h,h,100,101));
        check(!HealthRules.fresh("boot","boot",h,h.replace('a','b'),100,101));
        check(!HealthRules.fresh("boot","boot","","",100,101));
        check(!HealthRules.fresh("boot","boot",h,h,102,101));
        check(!HealthRules.fresh("boot","boot",h,h,-1,101));
        check(!HealthRules.fresh("","",h,h,100,101));
        check("healthy".equals(HealthRules.state("checked",true,1,true,true,true,true,true)));
        check("healthy".equals(HealthRules.state("checked",true,2,true,true,true,true,true)));
        check("waiting".equals(HealthRules.state("checked",true,0,true,true,true,true,true)));
        check("waiting".equals(HealthRules.state("waiting",true,1,true,true,true,true,true)));
        check("waiting".equals(HealthRules.state("stopped",true,1,true,true,true,true,true)));
        check("error".equals(HealthRules.state("failed",true,1,true,true,true,true,true)));
        check("error".equals(HealthRules.state("checked",true,1,true,true,true,true,false)));
        check("warning".equals(HealthRules.state("checked",false,1,true,true,true,true,true)));
        check("warning".equals(HealthRules.state("checked",true,1,false,true,true,true,true)));
        check("warning".equals(HealthRules.state("checked",true,1,true,false,true,true,true)));
        check("warning".equals(HealthRules.state("checked",true,1,true,true,false,true,true)));
        check("warning".equals(HealthRules.state("checked",true,1,true,true,true,false,true)));
        System.out.println("Health assertions: "+n+" passed");
    }
}
