"""Pure Java rules plus real shell execution with mocked properties/mounts. No device writes."""
import hashlib,json,os,pathlib,re,shutil,subprocess,sys,tempfile,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime import bash_tool,java_tool
sys.path.insert(0,str(ROOT/'tools'))
from publish_update import validate as validate_update
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
ro.product.manufacturer) echo Google;; ro.product.brand) echo google;;
ro.product.model) echo "${TEST_MODEL:-Pixel 10 Pro XL}";;
ro.build.version.sdk) echo "${TEST_SDK:-36}";;
ro.build.display.id) echo "${TEST_BUILD:-CP3A.260905.009}";;
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
        table.append(target.as_posix()+' '+sha(target)+','+sha(mod/relative)+'\n')
    write(mod/'full-files.tsv',''.join(table));write(mod/'post-fs-data.sh',script)
    write(mod/'control.sh',(mod/'control.sh').read_text(encoding='utf-8').replace('/dev/enable_pixel_5g',(work/'runtime').as_posix()))
    manifest={'outputs':{p.relative_to(mod).as_posix():{'sha256':sha(p)} for p in mod.rglob('*') if p.is_file()}}
    write(mod/'manifest.json',json.dumps(manifest,indent=2));write(mod/'profile.conf','base\n')
    for p in bin.iterdir():p.chmod(0o755)
    return mod,env,actions,info
def main():
    repo='iCassius/Pixel_5G_IMS_Enhanced';tag='v2.6.2-experimental'
    prefix='https://github.com/'+repo+'/releases/download/'+tag+'/'
    metadata={'version':tag,'versionCode':28,'zipUrl':prefix+'test-framework.zip','changelog':prefix+'CHANGELOG.md'}
    validate_update(metadata,repo,tag,{'test-framework.zip','CHANGELOG.md'})
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
    for p in (ROOT/'module').glob('*.sh'):
        check('shell syntax '+p.name,subprocess.run([str(BASH),'-n',str(p)],capture_output=True).returncode==0)
    scenarios={'full':{},'baseband mismatch':{'TEST_MODEM':'unknown'},'empty baseband':{'EMPTY_MODEM':'1'},
        'old report baseband':{'TEST_MODEM':'g5400i-250605-250825-B-13984049'},'OTA':{'TEST_BUILD':'NEW'},
        'Pixel6':{'TEST_DEVICE':'oriole','TEST_MODEL':'Pixel 6','TEST_SDK':'31'},
        'Pixel11 unknown SDK':{'TEST_DEVICE':'future','TEST_MODEL':'Pixel 11','TEST_SDK':'37'},
        'missing files':{},'changed ROM files':{},'partial mount failure':{'FAIL_SECOND':'1'},
        'rollback failure':{'FAIL_SECOND':'1','FAIL_UNMOUNT':'1'},'reentry':{},'framework package':{}}
    for name,variables in scenarios.items():
        with tempfile.TemporaryDirectory(prefix='pixelims-shell-test-') as temp:
            work=pathlib.Path(temp);mod,env,actions,info=fixture(work);env.update(variables)
            if name=='missing files':(mod/'full-files.tsv').unlink()
            if name=='changed ROM files':(work/'target1').write_bytes(b'OTA data')
            if name=='framework package':write(mod/'full-files.tsv','')
            result=execute(mod/'post-fs-data.sh',env)
            if name in ('full','reentry'):
                check(name+' mounts',result.returncode==0 and actions.read_text().count('mount ')==4)
                if name=='reentry':
                    second=execute(mod/'post-fs-data.sh',env)
                    check('reentry avoids remount',second.returncode==0 and actions.read_text().count('mount ')==4)
            elif name=='partial mount failure':
                check(name,result.returncode!=0 and not info.read_text() and (work/'target1').read_bytes()==b'original 1')
            elif name=='rollback failure':
                check(name,result.returncode!=0 and bool(info.read_text()) and any((work/'mirror').glob('session.*')))
            else:check(name+' zero mounts',result.returncode==0 and not actions.read_text())
    for name in ('status','success','failure','maintain','corrupt helper','corrupt policy','corrupt gate'):
        with tempfile.TemporaryDirectory(prefix='pixelims-control-test-') as temp:
            mod,env,actions,info=fixture(pathlib.Path(temp))
            if name=='failure':env['SU_FAIL']='1'
            if name=='maintain':write(mod/'profile.conf','vcrbt\n')
            if name.startswith('corrupt'):
                target={'corrupt helper':'override.dex','corrupt policy':'policy.json','corrupt gate':'compatibility.sh'}[name]
                write(mod/target,'corrupt')
            result=execute(mod/'control.sh',env,name if name in ('status','maintain') else 'vcrbt')
            if name=='maintain':check('supervisor preserves selected profile',result.returncode==0 and (mod/'profile.conf').read_text()=='vcrbt\n' and '--profile vcrbt' in actions.read_text())
            elif name in ('status','success'):
                check('control '+name,result.returncode==0 and (mod/'profile.conf').read_text()==('base\n' if name=='status' else 'vcrbt\n'))
                if name=='status':check('status read flag','--status' in actions.read_text())
            else:check('control '+name,result.returncode!=0 and (mod/'profile.conf').read_text()=='base\n' and (not name.startswith('corrupt') or not actions.read_text()))
    for name in ('open releases','browser unavailable','invalid repository'):
        with tempfile.TemporaryDirectory(prefix='pixelims-action-test-') as temp:
            mod,env,actions,info=fixture(pathlib.Path(temp))
            if name=='browser unavailable':env['AM_FAIL']='1'
            if name=='invalid repository':write(mod/'update-repository','owner/repo;bad\n')
            result=execute(mod/'action.sh',env)
            if name=='open releases':check(name,result.returncode==0 and 'https://github.com/iCassius/Pixel_5G_IMS_Enhanced/releases' in actions.read_text() and 'su ' not in actions.read_text())
            else:check(name,result.returncode!=0 and (name!='invalid repository' or not actions.read_text()))
    current=dict(line.split('=',1) for line in (ROOT/'module/module.prop').read_text(encoding='utf-8').splitlines() if '=' in line)
    archives=list((ROOT/'dist/release'/current['version']).glob('*.zip'))+list((ROOT/'dist/private'/current['version']).glob('*.zip'))
    check('current release package exists',any('framework.zip' in p.name for p in archives))
    for archive in archives:
        with zipfile.ZipFile(archive) as zipped:
            check(archive.name+' LF scripts',all(b'\r' not in zipped.read(n) for n in zipped.namelist() if n.endswith('.sh')))
            if 'framework' in archive.name:check('default no proprietary payload',not any(n.startswith(('vendor_override/','product_override/')) for n in zipped.namelist()))
            manifest=json.loads(zipped.read('manifest.json'))
            check(archive.name+' manifest hashes',all(hashlib.sha256(zipped.read(n)).hexdigest()==v['sha256'] for n,v in manifest['outputs'].items()))
            if manifest['module_version']==current['version']:
                props=dict(line.split('=',1) for line in zipped.read('module.prop').decode().splitlines() if '=' in line)
                check('module display name',props['name']==current['name'])
                label=archive.name.removeprefix(current['name']+'-'+current['version']+'-').removesuffix('.zip')
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
