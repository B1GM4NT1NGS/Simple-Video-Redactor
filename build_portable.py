"""Optional developer build. Run: python -m pip install pyinstaller; python build_portable.py"""
import os,pathlib,subprocess,sys,tempfile,shutil
import imageio_ffmpeg,PySide6

root=pathlib.Path(__file__).resolve().parent
qt=pathlib.Path(PySide6.__file__).parent
with tempfile.TemporaryDirectory(prefix='simple-video-redactor-build-') as scratch:
    ffmpeg=pathlib.Path(scratch)/'ffmpeg.exe'
    shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(),ffmpeg)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--name','Simple Video Redactor','--distpath',str(root/'dist'),'--workpath',str(pathlib.Path(scratch)/'build'),'--specpath',scratch,'--exclude-module','imageio_ffmpeg','--add-binary',str(ffmpeg)+';.']
    for name in ['VCRUNTIME140.dll','VCRUNTIME140_1.dll','MSVCP140.dll','MSVCP140_1.dll','MSVCP140_2.dll']:
        command+=['--add-binary',str(qt/name)+';.']
    command+=[str(root/'simple_video_redactor.py')]
    env=os.environ.copy()
    env['PATH']=os.pathsep.join([str(pathlib.Path(sys.executable).parent),str(pathlib.Path(os.environ['SystemRoot'])/'System32'),os.environ['SystemRoot']])
    subprocess.run(command,cwd=root,env=env,check=True)
