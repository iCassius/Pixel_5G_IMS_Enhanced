"""Isolated Android health tests. No installation, reboot, card update or CarrierConfig write.

The positive case deliberately substitutes a boot-record manifest in the staging directory;
it tests the observer, and is NOT evidence that this candidate ran during device boot.
"""
import argparse,datetime,hashlib,json,pathlib,shlex,subprocess,time

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=pathlib.Path)
    parser.add_argument('--out',type=pathlib.Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    stage='/data/adb/pixelims-health-probe-'+stamp
    remote='/data/local/tmp/pixelims-health-probe-'+stamp+'.zip'
    def adb(*command):
        return subprocess.run(['adb',*command],check=True,capture_output=True,text=True,encoding='utf-8',timeout=60).stdout.strip()
    def root(command):return adb('shell','su -c '+shlex.quote(command))
    def save(name,value):
        p=args.out/(name+'.json');p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        remote_json='/data/local/tmp/pixelims-health-probe-'+stamp+'-'+name+'.json'
        adb('push',str(p),remote_json)
        root('cp '+shlex.quote(remote_json)+' '+shlex.quote(stage+'/'+name+'.json')+' && chmod 600 '+shlex.quote(stage+'/'+name+'.json'))
    def run(phase):return json.loads(root('sh '+stage+'/health.sh '+phase+' fixture'))
    installed='/data/adb/modules/EnablePixel5G'
    boot=root('cat /proc/sys/kernel/random/boot_id');installed_hash=root('sha256sum '+installed+'/manifest.json').split()[0]
    card_before=root('KSU_MODULE=EnablePixel5G /data/adb/ksud module config list')
    adb('push',str(args.archive),remote)
    root('mkdir -m 700 '+stage+' && unzip -oq '+remote+' -d '+stage)
    source_boot=json.loads(root('cat '+installed+'/boot-mount.json'));save('boot-mount',source_boot)
    # system-UID status action is explicitly read-only; it never invokes overrideConfig.
    for attempt in range(3):
        try:
            framework=json.loads(root('sh '+stage+'/control.sh status'));break
        except subprocess.CalledProcessError:
            if attempt==2:raise
            time.sleep(2)
    assert all(not row['wrote'] for row in framework['subscriptions'])
    save('status',framework)
    outcomes=[]
    def check(name,result,condition):
        save('result-'+name,result);assert condition,result
        outcomes.append({'name':name,'passed':True,'state':result.get('state'),'reason':result.get('reason')})
    result=run('probe')
    check('candidate-not-booted',result,result['state']=='warning' and not result['bootRecordValid'] and result['mountedFiles']==4 and result['consumerViewsVerified'] and result['frameworkReadbackVerified'] and not result['cardPublished'])
    history=json.loads(root('cat '+stage+'/health-history.json'))
    check('stale-history',result,history['entries'][-1]['bootResult']=='unknown' and not history['entries'][-1]['bootRecordValid'])
    synthetic=dict(source_boot,manifestSha256=root('sha256sum '+stage+'/manifest.json').split()[0]);save('boot-mount',synthetic)
    result=run('probe')
    check('synthetic-record-positive',result,result['state']=='healthy' and result['mountedFiles']==4 and result['consumerViewsVerified'] and not result['cardPublished'] and
        any(p.get('name')=='init' and p.get('pid')==1 for p in result['processes']) and
        all(p.get('name')!='init' or p.get('pid')==1 for p in result['processes']))
    ril_open=any(p.get('name')=='rild_exynos' and any(f['target']=='/vendor/firmware/carrierconfig/cfg.db' for f in p.get('openedTargets',[])) for p in result['processes'])
    check('ril-open-cfg',result,ril_open)
    dead=dict(result,supervisorPid='99999999',supervisorStart='1');save('health',dead)
    inspected=run('inspect');check('dead-supervisor',inspected,not inspected['fresh'] and inspected['reason']=='supervisor_stopped')
    incomplete=json.loads(json.dumps(framework));incomplete['subscriptions'][0]['managedKeyCount']=0
    save('status',incomplete);result=run('probe');check('empty-keys',result,result['state']=='warning' and not result['frameworkReadbackVerified'])
    save('status',dict(framework,targetCount=0,subscriptions=[]));result=run('probe');check('no-sim',result,result['state']=='waiting')
    stale=json.loads(json.dumps(framework));stale['observation']['checkedAtElapsedSeconds']=-1
    save('status',stale);result=run('probe');check('expired-framework',result,result['state']=='warning' and not result['frameworkReadbackVerified'])
    save('status',framework)
    save('boot-mount',dict(synthetic,bootId='different-boot'));result=run('probe');check('old-boot',result,result['state']=='warning' and not result['bootRecordValid'])
    save('boot-mount',dict(synthetic,result='skipped'));result=run('probe');check('skipped-boot',result,result['state']=='warning' and not result['bootMountSucceeded'])
    save('boot-mount',dict(synthetic,result='rollback_failed'));result=run('probe');check('failed-rollback',result,result['state']=='error' and result['reason']=='boot_rollback_failed')
    save('boot-mount',synthetic)
    # Inspect an expired observation; probe is the only collecting mode used on this device.
    result=run('probe');result['checkedAtElapsedSeconds']=-1;save('health',result)
    result=run('inspect');check('expired-health',result,not result['fresh'] and result['state']=='waiting' and not result['description'].startswith('✅'))
    root("printf '\n# staged integrity fault\n' >> "+stage+'/service.sh')
    result=run('probe');check('corrupt-service',result,result['state']=='error' and 'service.sh' in result['integrityErrors'])
    assert boot==root('cat /proc/sys/kernel/random/boot_id')
    assert installed_hash==root('sha256sum '+installed+'/manifest.json').split()[0]
    assert card_before==root('KSU_MODULE=EnablePixel5G /data/adb/ksud module config list')
    report={'evidence':'Android isolated staging; synthetic positive boot record; not installed or boot validation; no business test',
        'archiveSha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),'checks':outcomes,'allPassed':True,'stage':stage,
        'installedManifestUnchanged':True,'bootUnchanged':True,'cardUnchanged':True,'frameworkWrote':False}
    save('probe-summary',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
