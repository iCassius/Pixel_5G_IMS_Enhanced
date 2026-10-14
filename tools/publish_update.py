"""Publish verified release metadata to the updates branch, only after a release exists."""
import argparse,base64,json,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
def validate(update,repo,tag,asset_names):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Invalid repository')
    if update.get('version')!=tag or type(update.get('versionCode')) is not int or update['versionCode']<=0:
        raise ValueError('Invalid release version')
    prefix='https://github.com/'+repo+'/releases/download/'+tag+'/'
    for key in ('zipUrl','changelog'):
        url=update.get(key,'')
        if not url.startswith(prefix) or url[len(prefix):] not in asset_names:raise ValueError('Release asset missing: '+key)
    if not update['zipUrl'].endswith('-framework.zip'):raise ValueError('Public feed accepts only framework packages')
def api(path,method='GET',data=None,missing=False):
    cmd=['gh','api',path]
    if method!='GET':cmd+=['--method',method]
    if data is not None:cmd+=['--input','-']
    result=subprocess.run(cmd,input=json.dumps(data) if data is not None else None,capture_output=True,text=True)
    if result.returncode:
        if missing and '404' in result.stderr:return None
        raise RuntimeError('GitHub API request failed: '+path)
    return json.loads(result.stdout)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',required=True);parser.add_argument('--tag',required=True)
    args=parser.parse_args()
    props=dict(line.split('=',1) for line in (ROOT/'module/module.prop').read_text(encoding='utf-8').splitlines() if '=' in line)
    if args.tag!=props['version']:raise ValueError('Tag/module version mismatch')
    update=json.loads((ROOT/'dist/release'/args.tag/'update-framework.json').read_text(encoding='utf-8'))
    prefix='repos/'+args.repo
    release=api(prefix+'/releases/tags/'+args.tag)
    if release.get('draft') or release.get('tag_name')!=args.tag:raise ValueError('Release must be published first')
    validate(update,args.repo,args.tag,{a['name'] for a in release['assets']})
    remote=api(prefix+'/git/ref/heads/updates',missing=True)
    if remote is None:
        repository=api(prefix);branch=api(prefix+'/git/ref/heads/'+repository['default_branch'])
        api(prefix+'/git/refs','POST',{'ref':'refs/heads/updates','sha':branch['object']['sha']})
    existing=api(prefix+'/contents/update-framework.json?ref=updates',missing=True)
    data={'message':'Update framework feed to '+args.tag,'branch':'updates',
        'content':base64.b64encode((json.dumps(update,indent=2)+'\n').encode()).decode(),
        'author':{'name':'iCassius','email':'6694980+iCassius@users.noreply.github.com'}}
    if existing is not None:
        prior=json.loads(base64.b64decode(existing['content']))
        if prior['versionCode']>update['versionCode']:raise ValueError('Refusing feed downgrade')
        if prior['versionCode']==update['versionCode']:
            if prior==update:print('Update feed already matches');return
            raise ValueError('VersionCode already used by a different release')
        data['sha']=existing['sha']
    api(prefix+'/contents/update-framework.json','PUT',data)
    print('Published framework update feed for '+args.tag)
if __name__=='__main__':main()
