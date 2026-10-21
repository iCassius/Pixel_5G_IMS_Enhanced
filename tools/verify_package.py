"""Verify the actual ZIP, its manifest, modem table and native-video correction."""
import argparse,hashlib,json,pathlib,zipfile
from payload import fields,named

PAYLOADS={'/vendor/firmware/carrierconfig/cfg.db':'vendor_override/cfg.db',
          '/vendor/etc/open_carrier_info.dat':'vendor_override/open_carrier_info.dat',
          '/product/etc/CarrierSettings/others.pb':'product_override/others.pb',
          '/product/etc/CarrierSettings/default.pb':'product_override/default.pb'}

def verify(path,official=False):
    with zipfile.ZipFile(path) as package:
        names=package.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP entries')
        for name in names:
            relative=pathlib.PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe ZIP path')
        manifest=json.loads(package.read('manifest.json'))
        if set(names)!=(set(manifest['outputs'])|{'manifest.json'}):raise ValueError('Unregistered ZIP contents')
        for name,record in manifest['outputs'].items():
            data=package.read(name)
            if hashlib.sha256(data).hexdigest()!=record['sha256'] or len(data)!=record['size_bytes']:raise ValueError('Payload integrity mismatch: '+name)
        props=dict(line.split('=',1) for line in package.read('module.prop').decode().splitlines() if '=' in line)
        policy=json.loads(package.read('policy.json'))
        if manifest['module_version']!=props['version']:raise ValueError('Version mismatch')
        if 'profile.conf' in names or 'common' in policy or 'vcrbt' in policy:raise ValueError('Legacy video policy present')
        full=manifest['payload']=='experimental-pixel9-10'
        if official:
            if not full or path.name!='Pixel_5G_IMS_Enhanced-'+props['version']+'.zip':raise ValueError('Official package must include audited modem/PB payloads')
            if not props['updateJson'].endswith('/updates/update-framework.json'):raise ValueError('Wrong official update feed')
        if policy.get('compatibilityMode')!='pixel9_10_experimental':raise ValueError('Wrong compatibility mode')
        if 'early-modem.sh' in names:raise ValueError('Retired modem attestation shipped')
        if full:
            if set(policy['full_files'])!=set(PAYLOADS):raise ValueError('Incomplete file baseline')
            table={}
            for line in package.read('full-files.tsv').decode().splitlines():
                group,target,accepted=line.split(' ')
                if target in table or group!=('vendor' if target.startswith('/vendor/') else 'product'):raise ValueError('Invalid grouped baseline')
                table[target]=accepted.split(',')
            if table!=policy['full_files']:raise ValueError('Shell/Java baseline mismatch')
            for target,name in PAYLOADS.items():
                if hashlib.sha256(package.read(name)).hexdigest() not in table[target]:raise ValueError('Missing generated payload baseline')
            found=0
            for carrier in fields(package.read('product_override/others.pb')):
                if carrier.number!=2 or carrier.wire!=2 or not named(carrier.value,b'46011'):continue
                for config in fields(carrier.value):
                    if config.number!=4 or config.wire!=2:continue
                    for entry in fields(config.value):
                        if entry.number==2 and entry.wire==2 and named(entry.value,b'carrier_vt_available_bool'):
                            if [f.value for f in fields(entry.value) if f.number==5 and f.wire==0]!=[1]:raise ValueError('Native video disabled')
                            found+=1
            if found!=1:raise ValueError('Native-video check missing or ambiguous')
        elif any(name in names for name in PAYLOADS.values()):raise ValueError('Unexpected proprietary payload in framework build')
        return {'version':props['version'],'versionCode':int(props['versionCode']),'payload':manifest['payload'],
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'nativeVideoChecked':full}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=pathlib.Path);parser.add_argument('--official',action='store_true')
    args=parser.parse_args();print(json.dumps(verify(args.archive,args.official),ensure_ascii=False))
