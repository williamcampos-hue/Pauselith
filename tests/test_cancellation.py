"""Fast cancellation contracts: real child pipes, terminal state and fallback escape."""
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
worker=importlib.import_module("worker")

class CancellationTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix="cancel_",dir=os.environ["UC001_TEST_OUTPUT"]))
        self.request=self.root/"cancel"

    def test_running_child_reaped_under_pipe_pressure_and_reuse(self):
        marker=self.root/"started"
        processes=[]
        popen=subprocess.Popen
        def launch(*args,**kwargs):
            process=popen(*args,**kwargs);processes.append(process);return process
        def request():
            deadline=time.monotonic()+5
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
            self.request.touch()
        thread=threading.Thread(target=request);thread.start()
        script="from pathlib import Path; import os,time; Path({!r}).touch(); os.write(1,b'x'*500000); os.write(2,b'y'*500000); time.sleep(60)".format(str(marker))
        try:
            with patch.object(worker,"CANCEL_FILE",self.request),patch.object(worker.subprocess,"Popen",launch):
                with self.assertRaises(worker.Cancelled):worker.run([sys.executable,"-I","-B","-c",script])
            self.assertTrue(marker.exists(),"Cancellation must occur during a live child")
            self.assertEqual(len(processes),1)
            self.assertIsNotNone(processes[0].poll(),"Child still alive after cancellation")
            with patch.object(worker,"CANCEL_FILE",None):
                self.assertEqual(worker.run([sys.executable,"-I","-B","-c","print('reusable')"]).strip(),b"reusable")
        finally:
            thread.join(6)
            for process in processes:
                if process.poll() is None:process.kill();process.wait(timeout=3)

    def test_request_before_launch_never_starts_child(self):
        self.request.touch()
        with patch.object(worker,"CANCEL_FILE",self.request),patch.object(worker.subprocess,"Popen") as launch:
            with self.assertRaises(worker.Cancelled):worker.run(["not-launched"])
            launch.assert_not_called()

    def test_cancellation_bypasses_delivery_error_fallbacks(self):
        def cancel(*args):raise worker.Cancelled()
        plan=dict(keep_frames=[[0,30]],fps="30",expected_frames=30,source_sha256="unused")
        with self.assertRaises(worker.Cancelled),patch.object(worker,"run") as fallback:
            worker.finish_delivery(self.root/"source",self.root,{},plan,{}, {},SimpleNamespace(validate=cancel))
        fallback.assert_not_called()

    def test_cancelled_terminal_preserves_files_and_closes_log(self):
        original=self.root/"original.mp4";original.write_bytes(b"unchanged original")
        valid=self.root/"other-valid.mp4";valid.write_bytes(b"previous valid task")
        output=self.root/"cancelled-output";output.mkdir()
        diagnostic=output/"segment.tmp";diagnostic.write_bytes(b"retain for diagnosis")
        log=io.StringIO()
        with patch.object(worker,"LOG",log),patch.object(worker,"LOG_ERROR",None),contextlib.redirect_stdout(io.StringIO()):
            ack=worker.emit("cancelled",**worker.record_cancelled(output,self.root/"worker.log"))
        self.assertTrue(log.closed)
        self.assertEqual((ack["event"],ack["state"]),("cancelled","cancelled"))
        self.assertFalse(ack["primary_available"])
        self.assertEqual(json.loads((output/"Estado.json").read_text(encoding="utf8"))["state"],"cancelled")
        self.assertEqual(original.read_bytes(),b"unchanged original")
        self.assertEqual(valid.read_bytes(),b"previous valid task")
        self.assertTrue(diagnostic.exists())
