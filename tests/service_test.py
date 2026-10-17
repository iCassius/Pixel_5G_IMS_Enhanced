"""Run supervisor transitions with finite sleeps and synthetic helpers; no Android writes."""
import json,os,pathlib,subprocess,tempfile

def run(root,bash,fixture,execute,write,sha,check):
    for name in ('success','helper failure','service missing','boot timeout','collector failure','corrupt gate'):
        with tempfile.TemporaryDirectory(prefix='pixelims-supervisor-') as temp:
            work=pathlib.Path(temp);mod,env,actions,info=fixture(work)
            # Each loop stops at its first sleep. A boot timeout is reached without wall-clock delay.
            script=(mod/'service.sh').read_text(encoding='utf-8').replace('/dev/enable_pixel_5g_supervisor.lock',(work/'supervisor.lock').as_posix()).replace('/data/adb/ksud',(work/'bin/ksud').as_posix())
            if name=='boot timeout':script=script.replace('[ "$waited" -ge 180 ]','[ "$waited" -ge 2 ]')
            write(mod/'service.sh',script)
            write(mod/'health.sh','#!/bin/sh\necho "health $1 $2" >> "$ACTIONS"\n[ "$COLLECTOR_FAIL" != 1 ]\n')
            write(mod/'control.sh','#!/bin/sh\necho "control $1" >> "$ACTIONS"\n[ "$HELPER_FAIL" = 1 ] && exit 1\necho \'{"targetCount":0,"subscriptions":[]}\'\n')
            write(work/'bin/service','#!/bin/sh\n[ "$SERVICE_MISSING" != 1 ] && echo "Service carrier_config: found"\n')
            write(work/'bin/sleep','#!/bin/sh\n[ "$BOOT_TIMEOUT" = 1 ] || touch "$TEST_MOD/disable"\n')
            write(work/'bin/timeout','#!/bin/sh\nshift\nexec "$@"\n')
            write(work/'bin/ksud','#!/bin/sh\necho "card $*" >> "$ACTIONS"\n')
            for p in (work/'bin').iterdir():p.chmod(0o755)
            env.update(TEST_MOD=mod.as_posix(),TEST_BOOT_COMPLETED='1')
            if name=='helper failure':env['HELPER_FAIL']='1'
            if name=='service missing':env['SERVICE_MISSING']='1'
            if name=='collector failure':env['COLLECTOR_FAIL']='1'
            if name=='boot timeout':env.update(TEST_BOOT_COMPLETED='0',BOOT_TIMEOUT='1')
            manifest=json.loads((mod/'manifest.json').read_text())
            manifest['outputs']['compatibility.sh']['sha256']=sha(mod/'compatibility.sh')
            write(mod/'manifest.json',json.dumps(manifest,indent=2))
            if name=='corrupt gate':write(mod/'compatibility.sh','invalid shell gate')
            result=execute(mod/'service.sh',env);observed=actions.read_text()
            expected={'success':'health checked framework_readback_completed','helper failure':'health failed framework_check_failed',
                'service missing':'health waiting carrier_service_unavailable','boot timeout':'health stopped boot_wait_timeout',
                'collector failure':'card module config set --temp override.description','corrupt gate':'health stopped module_integrity_failed'}[name]
            check('supervisor '+name,expected in observed and not (work/'supervisor.lock').exists())
            if name in ('helper failure','service missing','boot timeout','corrupt gate'):
                check('supervisor '+name+' no stale success','health checked' not in observed)
    for name in ('readback','failure'):
        with tempfile.TemporaryDirectory(prefix='pixelims-diagnose-') as temp:
            work=pathlib.Path(temp);mod,env,actions,info=fixture(work)
            write(work/'bin/timeout','#!/bin/sh\nshift\nexec "$@"\n');(work/'bin/timeout').chmod(0o755)
            write(mod/'health.sh','#!/bin/sh\necho "health $1 $2" >> "$ACTIONS"\n')
            if name=='failure':env['SU_FAIL']='1'
            result=execute(mod/'action.sh',env)
            observed=actions.read_text()
            check('manual '+name,(result.returncode==0)==(name=='readback') and '--status' in observed and 'am ' not in observed)
            check('manual '+name+' health',('health checked manual_readback' if name=='readback' else 'health failed framework_check_failed') in observed)
