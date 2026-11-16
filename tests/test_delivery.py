"""UC-001 finalization contract tests, with explicit injected stage failures.

These exercise real worker finalization/report persistence, not GUI interaction or
media encoding. Audiovisual integration lives in test_validation.py.
"""
import importlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))


class DeliveryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker = importlib.import_module("worker")
        parent = os.environ.get("UC001_TEST_OUTPUT")
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix="uc001_delivery_", dir=parent))
        cls.results = {}

    def setUp(self):
        self.folder = self.root / self._testMethodName
        self.folder.mkdir()
        self.output = self.folder / "output"
        (self.output / "Analisis").mkdir(parents=True)
        self.source = self.folder / "source.mock"
        self.source.write_bytes(b"unchanged mock source")
        self.primary = self.output / "Video_Sin_Silencios.mp4"
        self.primary.write_bytes(b"primary placeholder; decoding is injected in contract tests")
        self.primary_before = self.primary.read_bytes()
        self.info = {"streams": [{"codec_type": "video"}, {"codec_type": "audio"}, {"codec_type": "audio"}]}
        self.plan = {
            "keep_frames": [[0, 120]], "remove_frames": [], "fps": "30",
            "expected_frames": 120, "output_duration": 4.0, "duration": 4.0,
            "source_sha256": "unchanged", "config": {"aac_bitrate": "256k"},
        }
        self.settings = {
            "audio_track": 2, "threshold_db": -50, "min_silence": .6,
            "margin": .2, "min_clip": .65, "crf": 16,
            "preset": "medium", "aac_bitrate": "256k",
        }
        self.job = {"preserve_other_audio": True}
        self.engine = SimpleNamespace(sha=lambda p: "unchanged")
        self.verification = {
            "status": "pass", "passed": True, "primary_playable": True,
            "check_results": {"full_decode_no_errors": {"status": "pass", "reason": "injected contract result"}},
        }
        self.engine.validate = lambda *args: dict(self.verification)
        self.deliver = Mock(return_value={
            "preserved_audio_tracks": 2, "primary_source_track": 2,
            "additional_audio": True, "order": [2, 1], "durations_s": [4.0, 4.0],
        })

    def finish(self, **kwargs):
        result = self.worker.finish_delivery(
            self.source, self.output, self.info, self.plan, self.settings, self.job,
            self.engine, deliver=kwargs.pop("deliver", self.deliver), **kwargs)
        self.assertEqual(self.primary.read_bytes(), self.primary_before,
                         "A failed auxiliary stage must not delete/overwrite the principal")
        self.assertEqual(self.source.read_bytes(), b"unchanged mock source")
        self.results[self._testMethodName] = result
        (self.root / "delivery_results.json").write_text(
            json.dumps(self.results, indent=2, allow_nan=False), encoding="utf-8")
        return result

    def test_01_all_required_stages_complete(self):
        result = self.finish()
        self.assertEqual(result["state"], "completed", result)
        self.assertTrue(result["primary_available"])
        self.assertTrue(all(stage["status"] == "pass" for stage in result["stages"].values()))
        self.assertEqual(result["audio"]["preserved_audio_tracks"], 2)
        self.deliver.assert_called_once()
        self.assertIn("Estado: completed", (self.output / "Informe.txt").read_text(encoding="utf-8-sig"))

    def test_02_secondary_track_failure_is_partial_and_still_reports(self):
        self.deliver.side_effect = OSError("injected secondary audio delivery failure")
        result = self.finish()
        self.assertEqual(result["state"], "partial", result)
        self.assertTrue(result["primary_available"])
        self.assertEqual(result["stages"]["secondary_audio"]["status"], "fail")
        self.assertEqual(result["stages"]["report"]["status"], "pass")
        text = (self.output / "Informe.txt").read_text(encoding="utf-8-sig")
        self.assertIn("Estado: partial", text)
        self.assertIn("injected secondary audio delivery failure", text)

    def test_03_report_failure_is_partial_not_complete(self):
        reporter = Mock(side_effect=OSError("injected report write failure"))
        result = self.finish(reporter=reporter)
        self.assertEqual(result["state"], "partial", result)
        self.assertTrue(result["primary_available"])
        self.assertEqual(result["stages"]["secondary_audio"]["status"], "pass")
        self.assertEqual(result["stages"]["report"]["status"], "fail")
        self.assertFalse((self.output / "Informe.txt").exists())
        reporter.assert_called_once()

    def test_04_not_evaluated_verification_still_delivers_tracks(self):
        self.verification.update(status="not_evaluated", passed=False,
                                 reason="injected unavailable visual comparison")
        result = self.finish()
        self.assertEqual(result["state"], "partial", result)
        self.assertTrue(result["primary_available"])
        self.assertEqual(result["validation_status"], "not_evaluated")
        self.deliver.assert_called_once()
        self.assertEqual(result["stages"]["secondary_audio"]["status"], "pass")
        self.assertTrue((self.output / "Informe.txt").is_file())

    def test_05_actual_validation_failure_is_error_not_partial(self):
        self.verification.update(status="fail", passed=False,
                                 reason="injected wrong picture")
        result = self.finish()
        self.assertEqual(result["state"], "error", result)
        self.assertFalse(result["primary_available"])
        self.deliver.assert_not_called()
        self.assertEqual(result["stages"]["secondary_audio"]["status"], "not_evaluated")
        self.assertIn("Estado: error", (self.output / "Informe.txt").read_text(encoding="utf-8-sig"))

    def test_06_source_hash_change_is_error(self):
        self.engine.sha = lambda p: "changed"
        result = self.finish()
        self.assertEqual(result["state"], "error", result)
        self.assertFalse(result["primary_available"])
        self.assertEqual(result["stages"]["verification"]["status"], "fail")

    def test_07_auxiliary_validator_exception_keeps_playable_principal(self):
        validator = Mock(side_effect=RuntimeError("injected validator crash"))
        with patch.object(self.worker, "run", return_value=b"") as decode:
            result = self.finish(validator=validator)
        self.assertEqual(result["state"], "partial", result)
        self.assertTrue(result["primary_available"])
        self.assertEqual(result["validation_status"], "not_evaluated")
        self.deliver.assert_called_once()
        decode.assert_called_once()
        self.assertIn("-xerror", [str(x) for x in decode.call_args.args[0]])

    def test_08_nonfinite_json_rejected_without_touching_existing_file(self):
        path = self.output / "Estado.json"
        existing = b'{"state":"completed","verified":true}'
        path.write_bytes(existing)
        with self.assertRaises(ValueError):
            self.worker.write_json(path, {"state": "completed", "metric": -math.inf})
        self.assertEqual(path.read_bytes(), existing)
        self.assertEqual(list(self.output.glob("Estado.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)