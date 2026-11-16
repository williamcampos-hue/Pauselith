import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import delivery

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(dir=os.environ['UC001_TEST_OUTPUT'],prefix='recover_'))
        self.source=self.root/'input.mp4';self.source.write_bytes(b'original')
        self.job=self.root/'job.json';self.job.write_text('{}')
        self.output=delivery.create_output(self.job,self.source,self.root/'results')
        self.stage=self.output/delivery.STAGE;(self.stage/'Analisis').mkdir()
        (self.stage/delivery.PRIMARY).write_bytes(b'verified')
    def publish(self):
        return delivery.publish(self.output,dict(state='completed',primary_available=True,stages={}),{},{},lambda *a:None)
    def test_crash_after_publication_recovers_completed_without_changing_video(self):
        self.publish();before=delivery.sha(self.output/delivery.PRIMARY)
        result=delivery.recover_one(self.job)
        self.assertEqual(result['state'],'completed');self.assertEqual(delivery.sha(self.output/delivery.PRIMARY),before)
        self.assertEqual(delivery.recover_all(self.root),[])
    def test_crash_between_components_recovers_partial_verified_principal(self):
        class Crash(BaseException):pass
        move=delivery.move_new
        def fail(src,dst):move(src,dst);raise Crash()
        with patch.object(delivery,'move_new',fail),self.assertRaises(Crash):self.publish()
        result=delivery.recover_one(self.job)
        self.assertEqual(result['state'],'partial');self.assertTrue(result['primary_available'])
        self.assertEqual(self.source.read_bytes(),b'original')
        other=delivery.create_output(self.root/'next.json',self.source,self.root/'results');self.assertTrue(other.exists())
    def test_incomplete_staged_media_is_not_exposed(self):
        result=delivery.recover_one(self.job)
        self.assertEqual(result['state'],'error');self.assertFalse(result['primary_available'])
        self.assertFalse((self.output/delivery.PRIMARY).exists());self.assertTrue((self.stage/delivery.PRIMARY).exists())
    def test_changed_published_media_never_recovers_completed(self):
        self.publish();(self.output/delivery.PRIMARY).write_bytes(b'truncated')
        result=delivery.recover_one(self.job);self.assertEqual(result['state'],'error')
        self.assertEqual((self.output/delivery.PRIMARY).read_bytes(),b'truncated')
    def test_live_job_is_not_recovered(self):
        with delivery.JobLease(self.job):
            notices=delivery.recover_all(self.root)
        self.assertEqual(notices[0]['state'],'recovery_warning')
        self.assertEqual(delivery.read_json(self.output/'Estado.json')['state'],'processing')
    def test_foreign_pointer_is_not_modified(self):
        pointer=delivery.read_json(delivery.job_state(self.job));pointer['token']='wrong';delivery.write_json(delivery.job_state(self.job),pointer)
        notices=delivery.recover_all(self.root);self.assertEqual(notices[0]['state'],'recovery_warning')
        self.assertEqual(delivery.read_json(self.output/'Estado.json')['state'],'processing')
    def test_cancelled_job_keeps_cancelled_but_committed_result_wins_late_cancel(self):
        result=delivery.recover_one(self.job,'cancelled');self.assertEqual(result['state'],'cancelled')
        self.publish();result=delivery.recover_one(self.job,'cancelled');self.assertEqual(result['state'],'completed')

    def test_malformed_json_object_does_not_block_other_jobs(self):
        bad=self.root/'bad.json.state.json';bad.write_text('[]')
        notices=delivery.recover_all(self.root)
        self.assertEqual(len(notices),2)
        self.assertTrue(any(n['state']=='recovery_warning' for n in notices))
        self.assertTrue(any(n.get('output')==str(self.output) for n in notices))
    def test_recovery_downgrades_only_authenticated_report(self):
        (self.stage/'Informe.txt').write_text('Estado: completed')
        self.publish();(self.output/'Entrega.json').unlink()
        result=delivery.recover_one(self.job)
        self.assertEqual(result['state'],'partial')
        self.assertIn('Estado: partial',(self.output/'Informe.txt').read_text(encoding='utf-8-sig'))
    def test_finalization_downgrade_reconciles_commit_and_checksums(self):
        result=self.publish();result['state']='partial';result['stages']['finalization']={'status':'fail','reason':'injected sidecar write error'}
        (self.output/'Informe.txt').write_text('Estado: partial')
        delivery.reconcile(self.output,result)
        commit=delivery.read_json(self.output/'Entrega.json');self.assertEqual(commit['result']['state'],'partial')
        recovered=delivery.recover_one(self.job);self.assertEqual(recovered['state'],'partial')

    def test_interruption_before_worker_creates_output_is_detected(self):
        early=self.root/'early.json'
        delivery.write_json(delivery.job_state(early),dict(schema=1,job=str(early.resolve()),input=str(self.source),output=None,state='processing'))
        result=delivery.recover_one(early)
        self.assertEqual(result['state'],'error');self.assertEqual(result['output'],'')
        self.assertEqual(self.source.read_bytes(),b'original')
