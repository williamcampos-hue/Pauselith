"""Terminal-event regressions and frozen detector/render baseline guards."""
import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))


class FrozenEngineTests(unittest.TestCase):
    def test_detector_plan_and_render_are_exact_baseline(self):
        text = (REPO / "app/motor_original.py").read_text(encoding="utf8")
        start = text.index("    src=(args.input")
        end = text.index("    print('Exportacion completa. Validando...'")
        block = text[start:end].replace("    if args.render_only: return\n", "")
        self.assertEqual(hashlib.sha256(block.encode()).hexdigest(),
                         "9210159cea81c6e52c2e9f7d3a5426f6cb26eb16e59402adda4501eafe0d42df",
                         "Detector, plan or render changed from uc001-baseline; review rather than refresh the golden")

    def test_approved_profile_is_exact_baseline(self):
        text = (REPO / "perfil_probado.json").read_text(encoding="utf8")
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),
                         "05177a397c57cee0cbd5ce091309ceb3bd8f35bf8978f9d4ccc1acc0eb453f8e")


class TerminalProtocolTests(unittest.TestCase):
    def exercise(self, failure=None):
        worker = importlib.import_module("worker")
        parent = os.environ.get("UC001_TEST_OUTPUT")
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="uc001_protocol_", dir=parent))
        (output / "Analisis").mkdir()
        (output / "Informe.txt").write_text("Estado: completed\n", encoding="utf8")
        result = dict(state="completed", output=str(output), primary_available=True,
                      stages={"finalization": {"status": "pass", "reason": ""}})
        worker.write_json(output / "Estado.json", result)
        worker.write_json(output / "Analisis/Validacion_Final.json", result)

        class Log:
            def write(self, text):
                if failure == "write": raise OSError("injected log write")
            def flush(self):
                if failure == "flush": raise OSError("injected log flush")
            def close(self):
                if failure == "close": raise OSError("injected log close")

        stream = io.StringIO()
        with patch.object(worker, "LOG", Log()), patch.object(worker, "LOG_ERROR", None):
            with contextlib.redirect_stdout(stream):
                ack = worker.emit("done", message="Terminado", **result)
        records = [json.loads(line[5:]) for line in stream.getvalue().splitlines() if line.startswith("KIYO:")]
        self.assertEqual(len(records), 1, records)
        self.assertEqual(ack, records[0])
        return ack, output

    def test_success_emits_one_completed_event(self):
        ack, _ = self.exercise()
        self.assertEqual((ack["event"], ack["state"]), ("done", "completed"))

    def test_log_failure_never_emits_completed_and_reconciles_files(self):
        for failure in ("write", "flush", "close"):
            with self.subTest(operation=failure):
                ack, output = self.exercise(failure)
                self.assertEqual((ack["event"], ack["state"]), ("partial", "partial"))
                self.assertTrue(ack["primary_available"])
                self.assertEqual(ack["stages"]["finalization"]["status"], "fail")
                for path in (output / "Estado.json", output / "Analisis/Validacion_Final.json"):
                    self.assertEqual(json.loads(path.read_text(encoding="utf8"))["state"], "partial")
                self.assertIn("ESTADO FINAL: ENTREGA PARCIAL", (output / "Informe.txt").read_text(encoding="utf8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
