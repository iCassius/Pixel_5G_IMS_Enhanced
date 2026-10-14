"""Host tool locations for Windows and GitHub Linux runners; no machine credentials."""
import os, pathlib, shutil
def java_tool(name):
    suffix='.exe' if os.name=='nt' else ''
    home=os.environ.get('JAVA_HOME')
    if home:return str(pathlib.Path(home)/'bin'/(name+suffix))
    found=shutil.which(name)
    if found:return found
    if os.name=='nt':return str(pathlib.Path(r'C:\Program Files\Microsoft\jdk-21.0.11.10-hotspot\bin')/(name+suffix))
    raise RuntimeError('Set JAVA_HOME or add Java tools to PATH')
def android_sdk():
    home=os.environ.get('ANDROID_SDK_ROOT') or os.environ.get('ANDROID_HOME')
    if home:return pathlib.Path(home)
    if os.name=='nt':return pathlib.Path.home()/'AppData/Local/Android/Sdk'
    raise RuntimeError('Set ANDROID_HOME or ANDROID_SDK_ROOT')
def bash_tool():
    if os.environ.get('PIXELIMS_BASH'):return os.environ['PIXELIMS_BASH']
    if os.name=='nt':return r'C:\Program Files\Git\bin\bash.exe'
    found=shutil.which('bash')
    if found:return found
    raise RuntimeError('Bash required for shell fixtures')
