"""Executable integration tests; all media is generated locally, never private."""
import importlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures import FFMPEG, FFPROBE, make_source, make_reference_audio, make_export, probe, run, sha


class ValidationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FFMPEG.is_file() or not FFPROBE.is_file():
            raise RuntimeError("Set KIYOCUT_FFMPEG and KIYOCUT_FFPROBE to the pinned binaries")
        cls.validation = importlib.import_module("validation")
        parent = os.environ.get("UC001_TEST_OUTPUT")
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix="uc001_validation_", dir=parent))
        cls.results = {}
        for name, frames in [("normal", 120), ("gap3", 120), ("vfr", 123)]:
            folder = cls.root / name
            src = make_source(folder, name)
            wav = make_reference_audio(src, folder, frames)
            final = make_export(src, wav, folder, frames)
            cls.results[name] = (src, wav, final, frames)
        cls.summary = {"output_directory": str(cls.root), "cases": {}}

    def check_export(self, name, final_override=None, analysis_blockers=()):
        src, wav, final, frames = self.results[name]
        final = final_override or final
        analysis = self.root / (self._testMethodName + "_analysis")
        analysis.mkdir()
        for filename in analysis_blockers:
            (analysis / filename).mkdir()
        fn = self.validation.validate_export
        kwargs = dict(run=run, probe=probe, sha=sha)
        parameters = inspect.signature(fn).parameters
        if "ffmpeg" in parameters:
            kwargs.update(ffmpeg=FFMPEG, ffprobe=FFPROBE)
        else:
            self.validation.FFM = FFMPEG
            self.validation.PROBE = FFPROBE
        before = sha(src)
        result = fn(src, final, probe(src), [(0, frames)], 30.0, frames, wav,
                    analysis, before, **kwargs)
        self.assertEqual(before, sha(src), "Validator modified its input")
        self.summary["cases"][self._testMethodName] = result
        (self.root / "validation_results.json").write_text(
            json.dumps(self.summary, indent=2, allow_nan=False), encoding="utf-8")
        return result

    def test_01_normal_export_passes(self):
        result = self.check_export("normal")
        self.assertEqual(result["status"], "pass", result)
        self.assertTrue(result["passed"])

    def test_02_three_missing_tail_frames_are_not_decode_indices(self):
        src, _, _, _ = self.results["gap3"]
        timeline = self.validation.read_timeline(FFPROBE, src, run)
        self.assertEqual(len(timeline), 117)
        self.assertAlmostEqual(timeline[-1], 119 / 30, places=3)
        mapped = self.validation.match_time(timeline, 119 / 30, 1 / 60 + .001)
        self.assertEqual(mapped, 116)
        self.assertNotEqual(mapped, 119)
        result = self.check_export("gap3")
        self.assertEqual(result["status"], "pass", result)
        self.assertTrue(result["passed"])

    def test_03_unavailable_timestamp_is_not_arbitrarily_clamped(self):
        timeline = [0.0, 1 / 30, 2 / 30, 1.0]
        self.assertIsNone(self.validation.match_time(timeline, 0.5, 1 / 60))
        self.assertIsNone(self.validation.match_time(timeline, 2.0, 1 / 60))
        self.assertEqual(self.validation.match_time(timeline, 1.0, .001), 3)

    def test_04_variable_pts_timeline_is_handled_explicitly(self):
        src, _, _, _ = self.results["vfr"]
        timeline = self.validation.read_timeline(FFPROBE, src, run)
        self.assertTrue(any(abs((b-a)-1/30)>.01 for a,b in zip(timeline,timeline[1:])))
        result = self.check_export("vfr")
        # The production preflight retains its CFR restriction. The validator
        # itself must not silently accept an unsupported/incomplete mapping.
        self.assertIn(result["status"], ("pass", "not_evaluated"), result)
        if result["status"] == "not_evaluated":
            self.assertFalse(result["passed"])

    def test_05_wrong_picture_is_rejected(self):
        src, wav, _, frames = self.results["normal"]
        bad = make_export(src, wav, self.root / "normal", frames, black=True)
        result = self.check_export("normal", bad)
        self.assertEqual(result["status"], "fail", result)
        self.assertFalse(result["passed"])

    def test_06_wrong_audio_is_rejected(self):
        src, wav, _, frames = self.results["normal"]
        bad = make_export(src, wav, self.root / "normal", frames, muted=True)
        result = self.check_export("normal", bad)
        self.assertEqual(result["status"], "fail", result)
        self.assertFalse(result["passed"])

    def test_07_truncated_export_is_rejected_without_uncaught_error(self):
        src, _, final, _ = self.results["normal"]
        bad = self.root / "truncated.mp4"
        bad.write_bytes(final.read_bytes()[:100])
        result = self.check_export("normal", bad)
        self.assertEqual(result["status"], "fail", result)
        self.assertFalse(result["passed"])

    def test_08_source_pts_gap_at_sample_is_not_evaluated(self):
        # A request truly inside a discontinuity is distinct from the mapped
        # final picture. This guards against choosing an arbitrary nearby frame.
        src, _, _, _ = self.results["gap3"]
        timeline = self.validation.read_timeline(FFPROBE, src, run)
        self.assertIsNone(self.validation.match_time(timeline, 117 / 30, 1 / 60))

    def test_09_metadata_write_failure_is_incomplete_not_corrupt(self):
        result = self.check_export("normal", analysis_blockers=("FFprobe_Final.json",))
        self.assertEqual(result["status"], "not_evaluated", result)
        self.assertTrue(result["primary_playable"])
        self.assertTrue(result["checks"]["full_decode_no_errors"])
        self.assertTrue(result["checks"]["cut_frames_match_source"])
        self.assertIsNone(result["checks"]["validation_evidence"])

    def test_10_decode_log_write_failure_is_incomplete_not_corrupt(self):
        result = self.check_export("normal", analysis_blockers=("Decodificacion_Completa.log",))
        self.assertEqual(result["status"], "not_evaluated", result)
        self.assertTrue(result["primary_playable"])
        self.assertTrue(result["checks"]["full_decode_no_errors"])
        self.assertTrue(result["checks"]["audio_correlation_correct"])
        self.assertIsNone(result["checks"]["validation_evidence"])


if __name__ == "__main__":
    unittest.main(verbosity=2)