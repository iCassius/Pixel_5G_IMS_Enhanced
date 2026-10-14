"""Build standalone source; optional private payloads are never required or published by default."""
import argparse, hashlib, json, os, pathlib, re, shutil, subprocess, tempfile, zipfile
from runtime import android_sdk, java_tool
from tools.payload import restore_native_video
ROOT=pathlib.Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,text):path.write_text(text,encoding='utf-8',newline='\n')
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--with-private-payload',action='store_true')
    parser.add_argument('--official-release',action='store_true')
    parser.add_argument('--update-repository',default='iCassius/Pixel_5G_IMS_Enhanced')
    args=parser.parse_args()
    if args.official_release and not args.with_private_payload:
        parser.error('Official release requires audited modem and CarrierSettings payloads')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.update_repository):
        parser.error('Expected GitHub owner/repository')
    props=dict(line.split('=',1) for line in (ROOT/'module/module.prop').read_text(encoding='utf-8').splitlines() if '=' in line)
    version=props['version'];version_code=int(props['versionCode'])
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?',version) or version_code<=0:
        parser.error('Invalid module version/versionCode')
    label='framework' if args.official_release or not args.with_private_payload else 'private-mustang-base'
    sdk=android_sdk()
    jar=sdk/'platforms/android-36.1/android.jar'
    d8=sdk/'build-tools/35.0.0'/('d8.bat' if os.name=='nt' else 'd8')
    with tempfile.TemporaryDirectory(prefix='pixelims-build-') as temp:
        work=pathlib.Path(temp);mod=work/'module';shutil.copytree(ROOT/'module',mod)
        props['updateJson']='https://raw.githubusercontent.com/'+args.update_repository+'/updates/update-'+label+'.json'
        write(mod/'module.prop',''.join(key+'='+value+'\n' for key,value in props.items()))
        write(mod/'update-repository',args.update_repository+'\n')
        classes=work/'classes';classes.mkdir()
        subprocess.run([java_tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(jar),'-d',str(classes),*[str(p) for p in sorted((ROOT/'src').glob('*.java'))]],check=True)
        subprocess.run([str(d8),'--min-api','31','--lib',str(jar),'--output',str(classes),*[str(p) for p in classes.glob('*.class')]],check=True)
        shutil.copy2(classes/'classes.dex',mod/'override.dex')
        policy=json.loads((mod/'policy.json').read_text(encoding='utf-8'))
        policy['full_files']={}
        # Historical target hashes permit recognized upgrades; they select no video policy.
        baseline={'/vendor/firmware/carrierconfig/cfg.db': ['081dd5de6b755f4819f5ac4a127bd9ae6da3bf4b72dc0890324a92d7ecad8d8b', '94fda487766d798ad05a401d3d905fc7062433e5d535f0fa7b38ca51d2fa1dd0', 'e947d6631b7ba889f94606020ea8b53837662579ce155d2c5433e48f6d54227e'], '/vendor/etc/open_carrier_info.dat': ['3704b6d7e0f9fe8c792d68dbb75c4001d26137cf4edf6f1f7d51c26175867a8f', '53c90c629f1591255afb39a13868f8dce3cc1536f3bdd502110acd56fe802898'], '/product/etc/CarrierSettings/others.pb': ['58816cd566785a08322c2fde9ade2ff06fb9515522e02a1e59c062be9f6d2d82', '73fd5f172eee0a0064fbb8b41c936f68d8e8618c008c3384c337b4792eab1b3a', '9da25853b0ad26d4116824bface0d0a9395ae787b80f31759580d4b5995fa045', 'a294daaec7bf2c507cb2065828581e05221fdaa66a77f9d2195d47148876249f'], '/product/etc/CarrierSettings/default.pb': ['4f3b1bdff5c48397a419f1f7618512726dbce7b57c5cb76dd6ba5347ee5749f4', 'ebca9d7400fde7a060a02275a1705dc103ab1858b5d0304b742ed9b64eb037dc']}
        paths={'/vendor/firmware/carrierconfig/cfg.db':'vendor_override/cfg.db',
            '/vendor/etc/open_carrier_info.dat':'vendor_override/open_carrier_info.dat',
            '/product/etc/CarrierSettings/others.pb':'product_override/others.pb',
            '/product/etc/CarrierSettings/default.pb':'product_override/default.pb'}
        if args.with_private_payload:
            private=ROOT/'private/payloads'
            for target,relative in paths.items():
                accepted=list(baseline[target])
                candidate=private/'base'
                manifest=json.loads((candidate/'manifest.json').read_text(encoding='utf-8'))
                if sha(candidate/relative)!=manifest['outputs'][relative]['sha256']:
                    raise RuntimeError('Private payload hash mismatch: '+relative)
                accepted.append(sha(candidate/relative))
                policy['full_files'][target]=sorted(set(accepted))
            for directory in ('vendor_override','product_override'):
                shutil.copytree(private/'base'/directory,mod/directory)
            # Repair the inherited native-video disable without importing any VCRBT policy.
            others=mod/'product_override/others.pb'
            others.write_bytes(restore_native_video(others.read_bytes()))
            for target,relative in paths.items():
                policy['full_files'][target]=sorted(set(policy['full_files'][target]+[sha(mod/relative)]))
        write(mod/'policy.json',json.dumps(policy,ensure_ascii=False,indent=2)+'\n')
        write(mod/'full-files.tsv',''.join(('vendor' if path.startswith('/vendor/') else 'product')+' '+path+' '+','.join(hashes)+'\n' for path,hashes in policy['full_files'].items()))
        shutil.copy2(ROOT/'docs/COMPATIBILITY.md',mod/'COMPATIBILITY.md')
        manifest={'module_version':version,'maintainer':'iCassius','original_author':'Sun_Dream',
            'payload':'audited-mustang' if args.with_private_payload else 'framework-only','outputs':{}}
        for path in sorted(mod.rglob('*')):
            if path.is_file():manifest['outputs'][path.relative_to(mod).as_posix()]={'sha256':sha(path),'size_bytes':path.stat().st_size}
        write(mod/'manifest.json',json.dumps(manifest,indent=2)+'\n')
        out=ROOT/'dist'/('release' if args.official_release else ('private' if args.with_private_payload else 'development'))/version
        out.mkdir(parents=True,exist_ok=True)
        archive=out/(props['name']+'-'+version+('-'+label if args.with_private_payload and not args.official_release else '')+'.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as result:
            for path in sorted(mod.rglob('*')):
                if path.is_file():
                    entry=zipfile.ZipInfo(path.relative_to(mod).as_posix(),date_time=(2020,1,1,0,0,0))
                    entry.compress_type=zipfile.ZIP_DEFLATED;entry.create_system=3
                    entry.external_attr=(0o100755 if path.suffix=='.sh' else 0o100644)<<16
                    result.writestr(entry,path.read_bytes())
        write(out/(archive.name+'.sha256'),sha(archive)+'  '+archive.name+'\n')
        release='https://github.com/'+args.update_repository+'/releases/download/'+version+'/'
        update={'version':version,'versionCode':version_code,'zipUrl':release+archive.name,'changelog':'https://raw.githubusercontent.com/'+args.update_repository+'/updates/release-notes.md'}
        write(out/('update-'+label+'.json'),json.dumps(update,ensure_ascii=False,indent=2)+'\n')
        shutil.copy2(ROOT/'docs/RELEASE_NOTES.md',out/'CHANGELOG.md')
        print(archive)
if __name__=='__main__':main()
