"""Full: exercise the real WinForms queue, worker and FFmpeg in an isolated copy."""
import ctypes,time
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from fixtures import FFMPEG, make_source, run

REPO=Path(__file__).resolve().parents[1]

class CancellationIntegrationTests(unittest.TestCase):
    def test_queue_cancellation_process_ownership_and_recovery(self):
        root=Path(tempfile.mkdtemp(prefix="cancel_ui_",dir=os.environ["UC001_TEST_OUTPUT"]))
        harness_env=dict(os.environ,KIYOCUT_DATA_DIR=str(root/"userdata"))
        for name in ("app","jobs","logs"):(root/name).mkdir()
        for name in ("worker.py","motor_original.py","validation.py","delivery.py"):
            shutil.copyfile(REPO/"app"/name,root/"app"/name)
        shutil.copyfile(REPO/"perfil_probado.json",root/"perfil_probado.json")
        # Copies require no junction privileges and never write to the dependency build.
        shutil.copytree(Path(sys.executable).parents[1],root/"runtime")
        shutil.copytree(FFMPEG.parent.parent,root/"tools")
        compiler=Path(os.environ["WINDIR"])/"Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        if not compiler.is_file():raise RuntimeError("Full cancellation integration requires the documented .NET Framework C# compiler")
        config=json.loads((REPO/"build/toolchain.json").read_text(encoding="utf8"))
        command=[str(compiler),"/nologo","/target:exe","/main:CancellationHarness","/langversion:5","/codepage:65001","/noconfig","/nostdlib+","/out:"+str(root/"CancellationHarness.exe")]
        command += ["/reference:"+str(compiler.parent/reference) for reference in config["framework"]["references"]]
        command += [str(REPO/name) for name in config["compiler"]["sources"]]+[str(REPO/"tests/CancellationHarness.cs")]
        build=subprocess.run(command,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        (root/"compiler.log").write_bytes(build.stdout+build.stderr)
        self.assertEqual(build.returncode,0,build.stdout.decode("utf8","replace"))
        short=make_source(root/"short")
        long=root/"long.mp4"
        run([FFMPEG,"-hide_banner","-nostdin","-v","error","-n","-f","lavfi","-i","testsrc2=size=160x90:rate=30:duration=120","-f","lavfi","-i","sine=frequency=443:sample_rate=44100:duration=120","-c:v","libx264","-preset","ultrafast","-crf","32","-threads","1","-pix_fmt","yuv420p","-c:a","aac",long])
        common='''import argparse,json,subprocess,time,sys
if '--recover' in sys.argv:raise SystemExit(0)
if '--settle-job' in sys.argv:
    from pathlib import Path
    state=Path(sys.argv[sys.argv.index('--settle-job')+1]+'.state.json')
    data=json.loads(state.read_text());data['state']='cancelled';state.write_text(json.dumps(data))
    raise SystemExit(0)
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--job',type=Path);parser.add_argument('--ready-file',type=Path)
a=parser.parse_args();root=Path(__file__).resolve().parents[1]
while not a.ready_file.exists():time.sleep(.01)
'''
        (root/"unresponsive.py").write_text(common+'''
output=root/'forced-output';output.mkdir()
(output/'Estado.json').write_text(json.dumps(dict(state='processing')))
child=subprocess.Popen([str(root/'tools/ffmpeg/ffmpeg.exe'),'-hide_banner','-nostdin','-v','error','-re','-f','lavfi','-i','sine=frequency=443:duration=90','-f','null','NUL'])
print('KIYO:'+json.dumps(dict(event='started',output=str(output))),flush=True)
child.wait()
''',encoding="utf8")
        (root/"completed.py").write_text(common+'''
output=Path((root/'valid-result-path.txt').read_text()).parent
state=Path(str(a.job)+'.state.json');data=json.loads(state.read_text());data['state']='completed';state.write_text(json.dumps(data))
print('KIYO:'+json.dumps(dict(event='done',state='completed',output=str(output))),flush=True)
time.sleep(.5)
''',encoding="utf8")
        with (root/"harness.log").open("wb") as log:
            result=subprocess.run([str(root/"CancellationHarness.exe"),str(long),str(short)],stdout=log,stderr=subprocess.STDOUT,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW,env=harness_env)
        self.assertEqual(result.returncode,0,(root/"harness.log").read_text(encoding="utf8",errors="replace")+"\nDiagnostics: "+str(root))
        # Keep measured visibility evidence in CI's text-only runner artifact on success too.
        for line in (root/"harness.log").read_text(encoding="utf8",errors="replace").splitlines():
            if line.startswith("NOTICE "):
                print(line)
        valid=Path((root/"valid-result-path.txt").read_text())
        self.assertTrue(valid.is_file())
        run([FFMPEG,"-v","error","-xerror","-i",valid,"-map","0:v:0","-map","0:a:0","-f","null","NUL"])

        # Kill the actual GUI host with a live worker: Job Object closes its tree.
        with (root/"crash-harness.log").open("wb") as log:
            process=subprocess.Popen([str(root/"CancellationHarness.exe"),str(long),str(short),"--crash"],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=harness_env)
            try:
                deadline=time.monotonic()+20
                while not (root/"crash-ready.json").exists():
                    if process.poll() is not None:raise RuntimeError("Crash harness ended before ready")
                    if time.monotonic()>deadline:raise TimeoutError("Crash fixture startup timeout")
                    time.sleep(.01)
                ready=json.loads((root/"crash-ready.json").read_text())
            finally:
                if process.poll() is None:process.kill()
                process.wait(timeout=5)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        for pid in ready['pids']:
            handle=kernel.OpenProcess(0x100000,False,pid)
            if handle:
                try:self.assertEqual(kernel.WaitForSingleObject(handle,5000),0,'Process survived host crash: '+str(pid))
                finally:kernel.CloseHandle(handle)
        with (root/"reopen-harness.log").open("wb") as log:
            reopened=subprocess.run([str(root/"CancellationHarness.exe"),str(long),str(short),"--reopen"],stdout=log,stderr=subprocess.STDOUT,timeout=35,creationflags=subprocess.CREATE_NO_WINDOW,env=harness_env)
        self.assertEqual(reopened.returncode,0,(root/"reopen-harness.log").read_text(encoding='utf8',errors='replace'))
