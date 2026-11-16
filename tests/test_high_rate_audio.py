"""192 kHz extensible WAV regression: exact-rate lossless secondary audio."""
import contextlib,importlib,io,json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from fractions import Fraction
from unittest.mock import patch
from fixtures import FFMPEG,FFPROBE,run,probe
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import worker
class HighRateAudioTests(unittest.TestCase):
    def test_extensible_high_rate_secondary_keeps_rate_depth_samples_and_phase(self):
        root=Path(tempfile.mkdtemp(dir=os.environ['UC001_TEST_OUTPUT'],prefix='highrate_'));work=root/'Analisis/Trabajo';work.mkdir(parents=True)
        source=root/'source.mkv'
        run([FFMPEG,'-v','error','-n','-f','lavfi','-i','testsrc2=size=64x64:rate=30:duration=1','-f','lavfi','-i','sine=frequency=443:sample_rate=192000:duration=1','-f','lavfi','-i','sine=frequency=130:sample_rate=48000:duration=1','-map','0:v','-map','1:a','-map','2:a','-c:v','libx264','-preset','ultrafast','-threads','1','-c:a','pcm_s24le',source])
        # The final principal is independently valid; the extra track is all frames.
        final=root/'Video_Sin_Silencios.mp4'
        run([FFMPEG,'-v','error','-n','-i',source,'-map','0:v','-map','0:a:1','-c:v','copy','-c:a','aac','-b:a','256k',final])
        plan=dict(fps='30',keep_frames=[[0,30]],output_duration=1,config=dict(aac_bitrate='256k'))
        log=io.StringIO()
        with patch.object(worker,'FFM',FFMPEG),patch.object(worker,'PROBE',FFPROBE),patch.object(worker,'CURRENT_PROGRESS',0),patch.object(worker,'PROGRESS_PHASE','render'),contextlib.redirect_stdout(log):
            result=worker.extra_tracks(source,root,probe(source),1,plan,SimpleNamespace(Fraction=Fraction))
        self.assertEqual(result['sample_rates_hz'],[48000,192000]);self.assertEqual(result['codecs'],['aac','alac'])
        def decoded(path,mapping):return run([FFMPEG,'-v','error','-i',path,'-map',mapping,'-c:a','pcm_s32le','-f','s32le','pipe:1'])
        self.assertEqual(decoded(source,'0:a:0'),decoded(final,'0:a:1'),'High-rate/24-bit samples changed')
        messages=[json.loads(line[5:]).get('message','') for line in log.getvalue().splitlines() if line.startswith('KIYO:')]
        self.assertTrue(any('Conservando' in m for m in messages));self.assertFalse(any('Decodificando' in m or 'Comparando' in m for m in messages))
