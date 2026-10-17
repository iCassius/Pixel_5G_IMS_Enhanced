"""Pure Java rules plus real shell execution with mocked properties/mounts. No device writes."""
import hashlib,json,os,pathlib,re,shutil,subprocess,sys,tempfile,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime import bash_tool,java_tool
sys.path.insert(0,str(ROOT/'tools'))
from publish_update import validate as validate_update
from verify_package import verify as verify_package
from payload_test import run as test_payload
BASH=bash_tool()
results=[]
def write(path,text):path.write_text(text,encoding='utf-8',newline='\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check(name,value):
    results.append({'name':name,'passed':bool(value)})
    if not value:raise AssertionError(name)
def execute(path,env,*args):
    directory=path.parent.parent/'bin';posix=directory.as_posix();posix='/'+posix[0].lower()+posix[2:] if os.name=='nt' else posix
    return subprocess.run([str(BASH),'-c','export PATH="$1:$PATH"; shift; sh "$@"','fixtures',posix,path.as_posix(),*args],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
def fixture(work):
    mod=work/'module';shutil.copytree(ROOT/'module',mod)
    # Synthetic bytes suffice for mount control-flow tests; no proprietary data required.
    for relative in ('vendor_override/cfg.db','vendor_override/open_carrier_info.dat','product_override/others.pb','product_override/default.pb'):
        payload=mod/relative;payload.parent.mkdir(exist_ok=True)
        payload.write_bytes(('synthetic candidate '+relative).encode())
    (mod/'override.dex').write_bytes(b'test-only fake dex')
    bin=work/'bin';bin.mkdir();info=work/'mountinfo';write(info,'');actions=work/'actions';write(actions,'')
    write(bin/'getprop','''#!/bin/sh
case "$1" in
ro.product.device) echo "${TEST_DEVICE:-mustang}";;
ro.product.manufacturer) echo "${TEST_MANUFACTURER:-Google}";; ro.product.brand) echo "${TEST_BRAND:-google}";;
ro.product.model) echo "${TEST_MODEL:-Pixel 10 Pro XL}";;
ro.build.version.sdk) echo "${TEST_SDK:-36}";;
ro.build.display.id) echo "${TEST_BUILD:-CP3A.260905.009}";;
ro.build.expect.baseband) [ "$EARLY_FIXTURE" = 1 ] && echo "${EARLY_EXPECTED:-g5400i-260604-260807-B-16035863}";;
ro.boot.slot_suffix) echo "${EARLY_SLOT:-_a}";;
vendor.cbd.partition) echo "${EARLY_PARTITION:-modem_a}";;
init.svc.cpboot-daemon) [ "$EARLY_PROPERTY_FAILURE" = 1 ] && exit 1; echo "${EARLY_CBD_STATE:-stopped}";;
init.svc.zygote) echo "${EARLY_ZYGOTE_STATE:-stopped}";;
sys.boot_completed) echo "${TEST_BOOT_COMPLETED:-}";;
persist.vendor.cbd.modem_bin_path) echo "${EARLY_OVERRIDE:-}";;
vendor.cbd.modem_bin_type) echo "${EARLY_BIN_TYPE:-}";;
telephony.TnNtn.image_switch) echo "${EARLY_RADIO_IMAGE:-}";;
gsm.version.baseband) [ "$EMPTY_MODEM" = 1 ] || echo "${TEST_MODEM:-g5400i-260604-260807-B-16035863}";;
esac
''')
    write(bin/'chcon','#!/bin/sh\nexit 0\n')
    write(bin/'mount','''#!/bin/sh
src="$3"; tgt="$4"
echo "mount $tgt" >> "$ACTIONS"
case "$tgt" in *target2) [ "$FAIL_SECOND" = 1 ] && exit 1;; esac
cp "$tgt" "$tgt.original"; cp "$src" "$tgt"
printf '1 0 0:0 / %s rw - tmpfs tmpfs rw\n' "$tgt" >> "$INFO"
''')
    write(bin/'umount','''#!/bin/sh
echo "umount $1" >> "$ACTIONS"
[ "$FAIL_UNMOUNT" = 1 ] && exit 1
cp "$1.original" "$1"
awk -v t="$1" '$5 != t' "$INFO" > "$INFO.new"; mv "$INFO.new" "$INFO"
''')
    write(bin/'su','''#!/bin/sh
echo "su $*" >> "$ACTIONS"
[ "$SU_FAIL" = 1 ] && exit 1
echo '{"subscriptions":[],"targetCount":0}'
''')
    write(bin/'am','#!/bin/sh\necho "am $*" >> "$ACTIONS"\n[ "$AM_FAIL" != 1 ]\n')
    write(mod/'update-repository','iCassius/Pixel_5G_IMS_Enhanced\n')
    write(mod/'action.sh',(mod/'action.sh').read_text(encoding='utf-8').replace('/system/bin/am',(bin/'am').as_posix()))
    env=dict(os.environ,INFO=info.as_posix(),ACTIONS=actions.as_posix())
    script=(mod/'post-fs-data.sh').read_text(encoding='utf-8').replace('/proc/self/mountinfo',info.as_posix()).replace('/dev/enable_pixel_5g',(work/'mirror').as_posix())
    table=[]
    for i,relative in enumerate(['vendor_override/cfg.db','vendor_override/open_carrier_info.dat','product_override/others.pb','product_override/default.pb'],1):
        target=work/f'target{i}';target.write_bytes(b'original '+str(i).encode())
        script=re.sub(r'^TGT_'+str(i)+r'="[^"]+"',f'TGT_{i}="{target.as_posix()}"',script,flags=re.M)
        table.append(('vendor' if i<=2 else 'product')+' '+target.as_posix()+' '+sha(target)+','+sha(mod/relative)+'\n')
    write(mod/'full-files.tsv',''.join(table));write(mod/'post-fs-data.sh',script)
    write(mod/'control.sh',(mod/'control.sh').read_text(encoding='utf-8').replace('/dev/enable_pixel_5g',(work/'runtime').as_posix()))
    manifest={'outputs':{p.relative_to(mod).as_posix():{'sha256':sha(p)} for p in mod.rglob('*') if p.is_file()}}
    write(mod/'manifest.json',json.dumps(manifest,indent=2))
    for p in bin.iterdir():p.chmod(0o755)
    return mod,env,actions,info

def early_fixture(work):
    mod,env,actions,info=fixture(work)
    def posix(path):
        value=path.as_posix()
        return '/'+value[0].lower()+value[2:] if os.name=='nt' else value
    early=work/'early';early.mkdir()
    version='g5400i-260604-260807-B-16035863'
    paths={
        'partition':('772237701676d2485d5fa35ae111eaa3382d8288bdcbd2f298ca55b93d2af1b2',early/'block.img'),
        '/mnt/vendor/modem_img/images/default/modem.bin':('6e84cc9797c6281da41dda94009e566be1174ed3aa9267d94727ea28338aff7c',early/'images/default/modem.bin'),
        '/vendor/bin/cbd':('5d7d6cdd363a2735812f7ae47205b55c88d5a56f9db0ff02f8923b686795c4a9',early/'cbd'),
        '/vendor/etc/init/cbd.rc':('a4b1e90dddf2c246da2d5a4d33d0356f25acb0f1593bcef8652b3df160200bf1',early/'cbd.rc'),
        '/vendor/etc/fstab.modem':('c99236a10b2b97e3b637058ac18b04410de6d2c0e75697dd3012f35e61b448f8',early/'fstab.modem'),
        '/vendor/etc/init/hw/init.laguna.rc':('555ac2ec19840d36ee4760860b3d56ce42fac383fa99366f6c8e5d2193723a5a',early/'init.laguna.rc')}
    script=(mod/'early-modem.sh').read_text(encoding='utf-8')
    for original,(digest,path) in paths.items():
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('fixture '+original).encode())
        script=script.replace(digest,sha(path))
        if original!='partition':script=script.replace(original,posix(path))
    script=script.replace('/mnt/vendor/modem_img/images/$MODEM_VERSION/modem.bin',posix(early)+'/images/$MODEM_VERSION/modem.bin')
    script=script.replace('[ -b "$early_block" ]','[ -f "$early_block" ]').replace('/system/bin/sha256sum','sha256sum')
    early_info=early/'mountinfo';write(early_info,'1 0 1:1 / /mnt/vendor/modem_img ro - ext4 '+posix(early/'block.img')+' ro\n')
    script=script.replace('/proc/self/mountinfo',posix(early_info))
    write(mod/'early-modem.sh',script)
    # These shims model namespaces and block devices, not just a successful probe.
    write(work/'bin/readlink','''#!/bin/sh
case "$1" in
/proc/self/ns/mnt) echo 'mnt:[1]';;
/proc/1/ns/mnt) echo "mnt:[${EARLY_INIT_NS:-1}]";;
-f)
 case "$2" in
 /dev/block/by-name/modem_a) echo "$EARLY_BLOCK";;
 /dev/block/by-name/modem_b) echo "$EARLY_BLOCK.other";;
 */images/default/modem.bin) echo "$EARLY_IMAGE_RESOLVED";;
 *) echo "$2";;
 esac;;
*) exit 1;;
esac
''')
    write(work/'bin/blockdev','#!/bin/sh\necho "${EARLY_PART_SIZE:-314572800}"\n')
    write(work/'bin/timeout','''#!/bin/sh
[ "$EARLY_TIMEOUT" = 1 ] && exit 124
shift
exec "$@"
''')
    for p in (work/'bin').iterdir():p.chmod(0o755)
    env.update(EMPTY_MODEM='1',EARLY_FIXTURE='1',EARLY_BLOCK=posix(early/'block.img'),
        EARLY_IMAGE_RESOLVED=posix(early/'images'/version/'modem.bin'))
    manifest={'outputs':{p.relative_to(mod).as_posix():{'sha256':sha(p)} for p in mod.rglob('*') if p.is_file() and p.name!='manifest.json'}}
    write(mod/'manifest.json',json.dumps(manifest,indent=2))
    return mod,env,actions,info,early
def main():
    from service_test import run as test_supervisor
    test_supervisor(ROOT,BASH,fixture,execute,write,sha,check)
    test_payload();check('lossless native-video payload correction',True)
    repo='iCassius/Pixel_5G_IMS_Enhanced';tag='v2.6.2'
    prefix='https://github.com/'+repo+'/releases/download/'+tag+'/'
    public_name='Pixel_5G_IMS_Enhanced-'+tag+'.zip'
    metadata={'version':tag,'versionCode':29,'zipUrl':prefix+public_name,'changelog':'https://raw.githubusercontent.com/'+repo+'/updates/release-notes.md'}
    validate_update(metadata,repo,tag,{public_name})
    check('release metadata valid',True)
    for name,patch,assets in [('foreign URL',{'zipUrl':'https://other.invalid/test.zip'},{'test-framework.zip','CHANGELOG.md'}),
        ('missing asset',{}, {'CHANGELOG.md'}),('private payload',{'zipUrl':prefix+'test-private.zip'},{'test-private.zip','CHANGELOG.md'}),
        ('version mismatch',{'version':'v0.0.0'},{'test-framework.zip','CHANGELOG.md'})]:
        try:validate_update(dict(metadata,**patch),repo,tag,assets)
        except ValueError:check('feed rejects '+name,True)
        else:check('feed rejects '+name,False)
    with tempfile.TemporaryDirectory(prefix='pixelims-java-test-') as temp:
        subprocess.run([java_tool('javac'),'--release','8','-encoding','UTF-8','-d',temp,str(ROOT/'src/Compatibility.java'),str(ROOT/'tests/CompatibilityTest.java')],check=True)
        java=subprocess.run([java_tool('java'),'-cp',temp,'CompatibilityTest'],check=True,capture_output=True,text=True)
        print(java.stdout.strip());check('Java compatibility assertions',java.returncode==0)
        subprocess.run([java_tool('javac'),'--release','8','-encoding','UTF-8','-d',temp,str(ROOT/'src/HealthRules.java'),str(ROOT/'tests/HealthRulesTest.java')],check=True)
        health=subprocess.run([java_tool('java'),'-cp',temp,'HealthRulesTest'],check=True,capture_output=True,text=True)
        print(health.stdout.strip());check('Java health assertions',health.returncode==0)
    policy=json.loads((ROOT/'module/policy.json').read_text(encoding='utf-8'))
    check('no video profiles',not {'base','vcrbt'}.intersection(policy))
    check('no video overrides',all(not any(word in key for word in ('video','imsvt','carrier_vt','crbt')) for group in ('fallback',) for key in policy[group]))
    for p in (ROOT/'module').glob('*.sh'):
        check('shell syntax '+p.name,subprocess.run([str(BASH),'-n',str(p)],capture_output=True).returncode==0)
    scenarios={'full':{},'non Google':{'TEST_MANUFACTURER':'Other'},'wrong brand':{'TEST_BRAND':'other'},'non Pixel':{'TEST_MODEL':'Other 10'},'baseband mismatch':{'TEST_MODEM':'unknown'},'empty baseband':{'EMPTY_MODEM':'1'},
        'old report baseband':{'TEST_MODEM':'g5400i-250605-250825-B-13984049'},'OTA':{'TEST_BUILD':'NEW'},
        'Pixel6':{'TEST_DEVICE':'oriole','TEST_MODEL':'Pixel 6','TEST_SDK':'31','TEST_MODEM':'other'},
        'other Pixel same modem':{'TEST_DEVICE':'future','TEST_MODEL':'Pixel 11','TEST_SDK':'37'},
        'API37':{'TEST_SDK':'37'},'future API':{'TEST_SDK':'99'},
        'dual modem':{'TEST_MODEM':'g5400i-260604-260807-B-16035863,g5400i-260604-260807-B-16035863'},
        'mixed modem':{'TEST_MODEM':'g5400i-260604-260807-B-16035863,other'},
        'trailing empty modem':{'TEST_MODEM':'g5400i-260604-260807-B-16035863,'},
        'leading empty modem':{'TEST_MODEM':',g5400i-260604-260807-B-16035863'},
        'multiline modem':{'TEST_MODEM':'g5400i-260604-260807-B-16035863\ng5400i-260604-260807-B-16035863'},
        'missing files':{},'corrupt mount gate':{},'changed ROM files':{},'changed product files':{},'corrupt payload':{},'partial mount failure':{'FAIL_SECOND':'1'},
        'rollback failure':{'FAIL_SECOND':'1','FAIL_UNMOUNT':'1'},'reentry':{},'framework package':{}}
    for name,variables in scenarios.items():
        with tempfile.TemporaryDirectory(prefix='pixelims-shell-test-') as temp:
            work=pathlib.Path(temp);mod,env,actions,info=fixture(work);env.update(variables)
            if name=='missing files':(mod/'full-files.tsv').unlink()
            if name=='corrupt mount gate':write(mod/'compatibility.sh','corrupt')
            if name=='changed ROM files':(work/'target1').write_bytes(b'OTA data')
            if name=='changed product files':(work/'target3').write_bytes(b'OTA PB')
            if name=='corrupt payload':(mod/'vendor_override/cfg.db').write_bytes(b'corrupted payload')
            if name=='framework package':
                write(mod/'full-files.tsv','')
                manifest=json.loads((mod/'manifest.json').read_text());manifest['outputs']['full-files.tsv']['sha256']=sha(mod/'full-files.tsv');write(mod/'manifest.json',json.dumps(manifest,indent=2))
            result=execute(mod/'post-fs-data.sh',env)
            observation=json.loads((mod/'boot-mount.json').read_text())
            check(name+' boot record',observation['schema']==1 and observation['stage']=='post-fs-data' and
                observation['manifestSha256']==sha(mod/'manifest.json'))
            check(name+' mount lock released',not (work/'mirror_mount.lock').exists())
            if name in ('full','reentry','API37','future API','dual modem','OTA','other Pixel same modem'):
                check(name+' mounts',result.returncode==0 and actions.read_text().count('mount ')==4)
                check(name+' per-file evidence',observation['result']=='verified_in_script_namespace' and
                    set(observation['files'].values())=={'mounted_verified'})
                if name=='reentry':
                    second=execute(mod/'post-fs-data.sh',env)
                    check('reentry avoids remount',second.returncode==0 and actions.read_text().count('mount ')==4)
                    check('reentry recorded',set(json.loads((mod/'boot-mount.json').read_text())['files'].values())=={'already_mounted'})
            elif name=='changed product files':
                check(name+' vendor only',result.returncode==0 and actions.read_text().count('mount ')==2 and 'mount '+(work/'target3').as_posix() not in actions.read_text())
            elif name=='changed ROM files':
                check(name+' product only',result.returncode==0 and actions.read_text().count('mount ')==2 and 'mount '+(work/'target1').as_posix() not in actions.read_text())
            elif name in ('corrupt payload','missing files','corrupt mount gate'):check(name,result.returncode!=0 and not actions.read_text())
            elif name=='partial mount failure':
                check(name,result.returncode!=0 and not info.read_text() and (work/'target1').read_bytes()==b'original 1')
                check('rollback recorded',observation['result']=='rolled_back' and observation['files']['vendor_override/cfg.db']=='rolled_back')
            elif name=='rollback failure':
                check(name,result.returncode!=0 and bool(info.read_text()) and any((work/'mirror').glob('session.*')))
                check('rollback failure recorded',observation['result']=='rollback_failed' and observation['files']['vendor_override/cfg.db']=='rollback_failed')
            else:check(name+' zero mounts',result.returncode==0 and not actions.read_text())
            if name=='empty baseband':check('unregistered early profile rejected',observation['groups']['vendor']['reason']=='early_expected_version_mismatch')
            if name in ('baseband mismatch','mixed modem','trailing empty modem','leading empty modem','multiline modem'):
                check(name+' unverified reason',observation['groups']['vendor']['reason']=='modem_unverified')
            if name=='changed ROM files':check('unknown vendor hash reason',observation['groups']['vendor']['reason']=='target_hash_unverified')
    early_cases={
        'audited early image':{},
        'early placeholder partition':{'EARLY_PARTITION':'modem'},
        'runtime mismatch overrides early image':{'EMPTY_MODEM':'0','TEST_MODEM':'unknown'},
        'wrong early device':{'TEST_DEVICE':'future'},
        'unknown expected version':{'EARLY_EXPECTED':'unknown'},
        'unknown slot':{'EARLY_SLOT':'_c'},
        'wrong selected partition':{'EARLY_PARTITION':'modem_b'},
        'wrong partition size':{'EARLY_PART_SIZE':'1'},
        'alternate namespace':{'EARLY_INIT_NS':'2'},
        'selection override':{'EARLY_OVERRIDE':'/data/other.bin'},
        'alternate binary type':{'EARLY_BIN_TYPE':'1'},
        'alternate radio image':{'EARLY_RADIO_IMAGE':'ntn'},
        'consumer already running':{'EARLY_CBD_STATE':'running'},
        'zygote already running':{'EARLY_ZYGOTE_STATE':'running'},
        'boot already complete':{'TEST_BOOT_COMPLETED':'1'},
        'probe timeout':{'EARLY_TIMEOUT':'1'},
        'phase property read failure':{'EARLY_PROPERTY_FAILURE':'1'},
        'runtime version does not allow hot mounting':{'EMPTY_MODEM':'0','TEST_BOOT_COMPLETED':'1'},
        'changed early partition':{},'changed early modem':{},'changed loader':{},
        'writable modem mount':{},'nested modem override':{},'wrong mounted slot':{},
        'placeholder does not bypass mounted slot':{'EARLY_PARTITION':'modem'},
        'corrupt early guard':{}}
    for name,variables in early_cases.items():
        with tempfile.TemporaryDirectory(prefix='pixelims-early-test-') as temp:
            work=pathlib.Path(temp);mod,env,actions,info,early=early_fixture(work);env.update(variables)
            if name=='changed early partition':(early/'block.img').write_bytes(b'new firmware')
            if name=='changed early modem':(early/'images/default/modem.bin').write_bytes(b'new modem')
            if name=='changed loader':(early/'cbd').write_bytes(b'new loader')
            if name=='writable modem mount':write(early/'mountinfo',(early/'mountinfo').read_text().replace(' ro',' rw'))
            if name=='nested modem override':
                with (early/'mountinfo').open('a') as f:f.write('2 1 1:2 / /mnt/vendor/modem_img/images/default ro - tmpfs tmpfs ro\n')
            if name in ('wrong mounted slot','placeholder does not bypass mounted slot'):write(early/'mountinfo',(early/'mountinfo').read_text().replace('block.img','other.img'))
            if name=='corrupt early guard':write(mod/'early-modem.sh','corrupted')
            result=execute(mod/'post-fs-data.sh',env)
            observation=json.loads((mod/'boot-mount.json').read_text())
            if name in ('audited early image','early placeholder partition'):
                check(name+' mounts before runtime property',result.returncode==0 and actions.read_text().count('mount ')==4 and
                    observation['modemEvidence']=='verified_active_modem_partition')
            else:
                check(name+' zero mounts',not actions.read_text() and observation['result'] in ('skipped','aborted'))
                if name=='probe timeout':check('timeout reason',observation['groups']['vendor']['reason']=='early_probe_failed_or_timed_out')
    for sdk in ('31','37','99','30','invalid'):
        with tempfile.TemporaryDirectory(prefix='pixelims-install-test-') as temp:
            mod,env,actions,info=fixture(pathlib.Path(temp));env.update(TEST_SDK=sdk,MODPATH=mod.as_posix())
            wrapper=mod/'install-probe.sh'
            write(wrapper,'abort() { exit 1; }; ui_print() { :; }; set_perm_recursive() { :; }; set_perm() { :; }; . "$MODPATH/customize.sh"\n')
            result=execute(wrapper,env)
            check('installer SDK '+sdk,(result.returncode==0)==(sdk in ('31','37','99')))
    for name in ('status','success','failure','maintain','saved legacy profile','legacy video action','corrupt helper','corrupt policy','corrupt gate'):
        with tempfile.TemporaryDirectory(prefix='pixelims-control-test-') as temp:
            mod,env,actions,info=fixture(pathlib.Path(temp))
            if name=='failure':env['SU_FAIL']='1'
            if name=='saved legacy profile':write(mod/'profile.conf','vcrbt\n')
            if name.startswith('corrupt'):
                target={'corrupt helper':'override.dex','corrupt policy':'policy.json','corrupt gate':'compatibility.sh'}[name]
                write(mod/target,'corrupt')
            action=name if name in ('status','maintain') else ('vcrbt' if name=='legacy video action' else 'apply')
            result=execute(mod/'control.sh',env,action)
            if name=='saved legacy profile':
                check('saved video profile ignored',result.returncode==0 and '--profile' not in actions.read_text() and (mod/'profile.conf').read_text()=='vcrbt\n')
            elif name in ('status','success','maintain'):
                check('control '+name,result.returncode==0 and '--profile' not in actions.read_text() and not (mod/'profile.conf').exists())
                if name=='status':check('status read flag','--status' in actions.read_text())
            else:check('control '+name,result.returncode!=0 and (name=='failure' or not actions.read_text()))
    for name in ('open releases','browser unavailable','invalid repository'):
        with tempfile.TemporaryDirectory(prefix='pixelims-action-test-') as temp:
            mod,env,actions,info=fixture(pathlib.Path(temp))
            if name=='browser unavailable':env['AM_FAIL']='1'
            if name=='invalid repository':write(mod/'update-repository','owner/repo;bad\n')
            result=execute(mod/'action.sh',env,'releases')
            if name=='open releases':check(name,result.returncode==0 and 'https://github.com/iCassius/Pixel_5G_IMS_Enhanced/releases' in actions.read_text() and 'su ' not in actions.read_text())
            else:check(name,result.returncode!=0 and (name!='invalid repository' or not actions.read_text()))
    current=dict(line.split('=',1) for line in (ROOT/'module/module.prop').read_text(encoding='utf-8').splitlines() if '=' in line)
    archives=[p for kind in ('release','private','development') for p in (ROOT/'dist'/kind/current['version']).glob('*.zip')]
    check('current release package exists',any(p.name==current['name']+'-'+current['version']+'.zip' for p in archives))
    for archive in archives:
        verify_package(archive,official='/release/' in archive.as_posix());check(archive.name+' package semantics',True)
        with zipfile.ZipFile(archive) as zipped:
            check(archive.name+' LF scripts',all(b'\r' not in zipped.read(n) for n in zipped.namelist() if n.endswith('.sh')))
            manifest=json.loads(zipped.read('manifest.json'))
            check(archive.name+' manifest hashes',all(hashlib.sha256(zipped.read(n)).hexdigest()==v['sha256'] for n,v in manifest['outputs'].items()))
            if manifest['module_version']==current['version']:
                props=dict(line.split('=',1) for line in zipped.read('module.prop').decode().splitlines() if '=' in line)
                check('module display name',props['name']==current['name'])
                label='private-mustang-base' if '/private/' in archive.as_posix() else 'framework'
                update=json.loads((archive.parent/('update-'+label+'.json')).read_text(encoding='utf-8'))
                check(label+' update channel',props['updateJson'].endswith('/update-'+label+'.json'))
                check(label+' update version',update['version']==props['version'] and update['versionCode']==int(props['versionCode']))
                check(label+' release asset',update['zipUrl'].endswith('/'+props['version']+'/'+archive.name))
                repository=zipped.read('update-repository').decode().strip()
                check(label+' action included','action.sh' in zipped.namelist() and props['updateJson']=='https://raw.githubusercontent.com/'+repository+'/updates/update-'+label+'.json')
                check(label+' ZIP script mode',(zipped.getinfo('action.sh').external_attr>>16)&0o777==0o755)
    out=ROOT/'build';out.mkdir(exist_ok=True)
    write(out/'validation.json',json.dumps({'evidence':'Pure Java and Windows Git Bash mock fixtures; not Android Binder/SELinux/device validation','results':results,'all_passed':True},indent=2))
    print('Checks:',len(results),'passed')
if __name__=='__main__':main()
