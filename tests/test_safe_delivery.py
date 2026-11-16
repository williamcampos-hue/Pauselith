"""Filesystem fault injection; synthetic bytes, no personal files or renders."""
import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import delivery

class SafeDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(dir=os.environ['UC001_TEST_OUTPUT'],prefix='delivery_'))
        self.source=self.root/'source.mp4';self.source.write_bytes(b'original')
        self.job=self.root/'job.json';self.job.write_text('{}')
        self.output=delivery.create_output(self.job,self.source,self.root/'results')
        self.stage=self.output/delivery.STAGE;(self.stage/'Analisis').mkdir()
        (self.stage/delivery.PRIMARY).write_bytes(b'verified media')
        self.result=dict(state='completed',primary_available=True,stages=dict(report={'status':'pass'}))
    def publish(self):
        def report(folder,result,*args):delivery.atomic_bytes(folder/'Informe.txt',result['state'].encode())
        return delivery.publish(self.output,self.result,{}, {},report)
    def test_duplicate_inputs_get_distinct_owned_outputs(self):
        other=delivery.create_output(self.root/'other.json',self.source,self.root/'results')
        self.assertNotEqual(other,self.output);self.assertEqual(self.source.read_bytes(),b'original')
    def test_existing_exact_output_and_original_directory_are_untouched(self):
        (self.output/'Estado.json').write_bytes(b'unchanged')
        with self.assertRaises(FileExistsError):delivery.create_output(self.job,self.source,self.root,exact=self.output)
        self.assertEqual((self.output/'Estado.json').read_bytes(),b'unchanged')
        with self.assertRaises(ValueError):delivery.create_output(self.job,self.source,self.root,exact=self.source.parent)
    def test_unverified_media_is_not_published(self):
        self.result.update(state='error',primary_available=False);result=self.publish()
        self.assertFalse((self.output/delivery.PRIMARY).exists());self.assertTrue((self.stage/delivery.PRIMARY).exists())
        self.assertEqual(result['state'],'error')
    def test_collision_never_overwrites_foreign_file(self):
        (self.output/delivery.PRIMARY).write_bytes(b'foreign')
        result=self.publish();self.assertEqual(result['state'],'error')
        self.assertEqual((self.output/delivery.PRIMARY).read_bytes(),b'foreign')
    def test_commit_tracks_exact_published_files_and_report(self):
        result=self.publish();commit=delivery.read_json(self.output/'Entrega.json')
        self.assertEqual(result['state'],'completed')
        for c in commit['components']:self.assertEqual(delivery.sha(self.output/c['path']),c['sha256'])
        self.assertEqual((self.output/'Informe.txt').read_text(),'completed')
    def test_interrupted_publication_retains_intent_and_verified_media(self):
        class Crash(BaseException):pass
        move=delivery.move_new
        def interrupted(src,dst):
            move(src,dst)
            if Path(dst).name==delivery.PRIMARY:raise Crash()
        with patch.object(delivery,'move_new',interrupted),self.assertRaises(Crash):self.publish()
        self.assertTrue((self.output/'Publicacion.json').exists());self.assertFalse((self.output/'Entrega.json').exists())
        self.assertEqual((self.output/delivery.PRIMARY).read_bytes(),b'verified media')
    def test_atomic_write_failure_preserves_old_bytes_and_removes_own_temp(self):
        target=self.root/'settings.json';target.write_bytes(b'previous')
        with patch.object(delivery.os,'replace',side_effect=OSError('disk full')),self.assertRaises(OSError):delivery.write_json(target,{'new':True})
        self.assertEqual(target.read_bytes(),b'previous');self.assertEqual(list(self.root.glob('*.tmp')),[])
    def test_commit_failure_cannot_report_completed(self):
        write=delivery.write_json
        def fail(path,value):
            if Path(path).name=='Entrega.json':raise OSError('injected disk full')
            return write(path,value)
        with patch.object(delivery,'write_json',fail):result=self.publish()
        self.assertEqual(result['state'],'partial');self.assertTrue(result['primary_available'])
