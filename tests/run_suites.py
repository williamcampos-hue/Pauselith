"""Standard-library runner for existing KiyoCut tests; no production mutations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
FAST_MODULES = ("test_delivery", "test_protocol", "test_cancellation", "test_safe_delivery", "test_recovery", "test_cleanup")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def test_ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from test_ids(test)
        else:
            yield test.id()


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successes = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test.id())


class ControlledFailure(unittest.TestCase):
    def runTest(self):
        self.fail("Controlled runner self-test: exit code must be nonzero.")


def case_ids(entries):
    # unittest stores a failed subtest separately; count its parent only once.
    return {getattr(test, "test_case", test).id() for test, _ in entries}


def check_dependencies(dependencies, full):
    lock = json.loads((ROOT / "build/dependencies.lock.json").read_text(encoding="utf8"))
    if sys.version.split()[0] != lock["pythonVersion"]:
        raise RuntimeError("Python " + lock["pythonVersion"] + " required; use a UC-002A build.")
    if digest(Path(sys.executable)) != lock["requiredBinaryHashes"]["runtime/python/python.exe"]:
        raise RuntimeError("Python binary does not match dependencies.lock.json.")
    if not full:
        return
    try:
        import numpy
    except (ImportError, OSError) as error:
        raise RuntimeError("Missing NumPy; use the complete UC-002A build.") from error
    if numpy.__version__ != lock["numpyVersion"]:
        raise RuntimeError("NumPy " + lock["numpyVersion"] + " required.")
    for name, variable in (("ffmpeg", "KIYOCUT_FFMPEG"), ("ffprobe", "KIYOCUT_FFPROBE")):
        path = dependencies / "tools/ffmpeg" / (name + ".exe")
        if not path.is_file():
            raise RuntimeError("Missing " + name + "; use the complete UC-002A build.")
        if digest(path) != lock["requiredBinaryHashes"]["tools/ffmpeg/" + name + ".exe"]:
            raise RuntimeError(name + " binary does not match dependencies.lock.json.")
        version = subprocess.run([str(path), "-version"], capture_output=True, text=True,
                                 timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if version.returncode or not version.stdout.startswith(name + " version " + lock["ffmpegVersion"]):
            raise RuntimeError("Unsupported " + name + " version.")
        os.environ[variable] = str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("Fast", "Full"), default="Fast")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--self-test-failure", action="store_true")
    args = parser.parse_args()
    output, dependencies = args.output.resolve(), args.dependencies.resolve()
    # Validate before writing, including junction-resolved paths.
    if output == ROOT or ROOT in output.parents or output == dependencies or dependencies in output.parents:
        parser.error("Test output must be outside source and dependencies.")
    if any((parent / "KiyoCut.exe").exists() or (parent / ".git").exists()
           for parent in (output, *output.parents)):
        parser.error("Test output cannot be in a KiyoCut installation or repository.")
    if (output / "summary.json").exists():
        parser.error("An existing test result cannot be overwritten.")
    output.mkdir(parents=True, exist_ok=True)
    summary = dict(suite="ControlledFailure" if args.self_test_failure else args.suite,
                   status="configuration_error", selected=0, tests_run=0, passed=0,
                   failed=0, errors=0, skipped=0, not_run=0, exit_code=2)
    try:
        work = output / "work"
        work.mkdir(exist_ok=False)
        os.environ["UC001_TEST_OUTPUT"] = str(work)
        os.environ["KIYOCUT_DATA_DIR"] = str(work / "state")
        os.environ["TEMP"] = os.environ["TMP"] = str(work)
        tempfile.tempdir = str(work)
        sys.path.insert(0, str(TESTS))
        check_dependencies(dependencies, args.suite == "Full" and not args.self_test_failure)
        loader = unittest.TestLoader()
        if args.self_test_failure:
            suite = unittest.TestSuite([ControlledFailure()])
        elif args.suite == "Fast":
            suite = loader.loadTestsFromNames(FAST_MODULES)
        else:
            suite = loader.discover(str(TESTS), pattern="test_*.py")
        if loader.errors:
            raise RuntimeError("Test discovery failed:\n" + "\n".join(loader.errors))
        summary["test_ids"] = list(test_ids(suite))
        summary["selected"] = suite.countTestCases()
        if not summary["selected"]:
            raise RuntimeError("No tests selected; refusing an empty success.")
        if args.check_only:
            summary.update(status="configured_not_executed", not_run=summary["selected"], exit_code=0)
            print(f"Configured {args.suite}: {summary['selected']} selected, 0 executed.")
        else:
            result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, resultclass=Result).run(suite)
            summary.update(status="pass" if result.wasSuccessful() else "fail",
                           tests_run=result.testsRun, passed=len(result.successes),
                           failed=len(case_ids(result.failures) | {t.id() for t in result.unexpectedSuccesses}),
                           errors=len(case_ids(result.errors)), not_run=max(0, summary["selected"] - result.testsRun),
                           skipped=len(case_ids(result.skipped)),
                           expected_failures=len(case_ids(result.expectedFailures)),
                           unexpected_successes=len(result.unexpectedSuccesses),
                           exit_code=0 if result.wasSuccessful() else 1)
            print("Summary: {passed} passed, {failed} failed, {errors} errors, {skipped} skipped.".format(**summary))
    except Exception as error:
        summary.update(status="configuration_error", errors=1, message=str(error), exit_code=2)
        print("ERROR: " + str(error))
        traceback.print_exc(file=sys.stdout)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf8")
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
