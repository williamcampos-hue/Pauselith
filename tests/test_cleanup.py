import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import delivery
class CleanupTests(unittest.TestCase):
    def test_owned_media_removed_logs_originals_and_unknown_files_preserved(self):
        root=Path(tempfile.mkdtemp(dir=os.environ['UC001_TEST_OUTPUT'],prefix='clean_'));source=root/'source';source.write_bytes(b'original')
        output=delivery.create_output(root/'job.json',source,root/'results');other=delivery.create_output(root/'other.json',source,root/'results')
        work=output/delivery.STAGE/'Analisis/Trabajo';work.mkdir(parents=True)
        for name in ('video_001.mp4','clip_001.wav','Pista_Original_01.pcm','videos.ffconcat','video_001.log','unknown.mp4'):(work/name).write_bytes(b'keep or discard')
        primary=output/delivery.PRIMARY;primary.write_bytes(b'valid');foreign=other/'video_001.mp4';foreign.write_bytes(b'other job')
        result=delivery.cleanup(output)
        self.assertEqual(len(result['removed']),4);self.assertTrue((work/'video_001.log').exists());self.assertTrue((work/'unknown.mp4').exists())
        self.assertEqual(source.read_bytes(),b'original');self.assertEqual(primary.read_bytes(),b'valid');self.assertEqual(foreign.read_bytes(),b'other job')
    def test_cleanup_refuses_unknown_directory(self):
        root=Path(tempfile.mkdtemp(dir=os.environ['UC001_TEST_OUTPUT'],prefix='foreign_'));(root/'video_001.mp4').write_bytes(b'foreign')
        with self.assertRaises(OSError):delivery.cleanup(root)
        self.assertEqual((root/'video_001.mp4').read_bytes(),b'foreign')
    def test_locked_temporary_is_preserved_and_reported(self):
        root=Path(tempfile.mkdtemp(dir=os.environ['UC001_TEST_OUTPUT'],prefix='locked_'));source=root/'source';source.write_bytes(b'original')
        output=delivery.create_output(root/'job.json',source,root/'results');work=output/delivery.STAGE/'Analisis/Trabajo';work.mkdir(parents=True);temp=work/'video_001.mp4';temp.write_bytes(b'locked')
        unlink=Path.unlink
        def fail(path,*a,**kw):
            if path==temp:raise PermissionError('injected locked file')
            return unlink(path,*a,**kw)
        with patch.object(Path,'unlink',fail):result=delivery.cleanup(output)
        self.assertTrue(temp.exists());self.assertTrue(result['warnings'])
