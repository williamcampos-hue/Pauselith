# Automated tests

Tests require a build made from [BUILD.md](BUILD.md), not a personal installation, AI service or developer's paths. They do not download dependencies.

```powershell
.\scripts\test.ps1 -Suite Fast -DependenciesFrom '..\Pauselith-build'
.\scripts\test.ps1 -Suite Full -DependenciesFrom '..\Pauselith-build'
```

Fast is the default: 38 deterministic protocol, cancellation, delivery, recovery and cleanup cases. It protects the approved engine/profile hashes and tests explicit terminal states. It does not render media.

Full discovers 50 distinct test methods, including all 38 Fast methods plus ten synthetic audiovisual regressions, high-rate secondary audio and a real WinForms/worker/process-tree integration. Fast and Full overlap; running both does not create 88 independent tests. Full covers cancellation, forced fallback, host crash/reopen recovery, unrelated process protection, original/previous-result integrity, settings roundtrip, minimum/scaled layout, notice visibility and theme contrast. Production code is loaded from this source tree. Only generated synthetic media and isolated dependency copies are used.

Dependency paths can be supplied with `-DependenciesFrom`. `-TestOutput` selects an external result root; the legacy default remains `../KiyoCut-Archivo/Pruebas/Ejecuciones` for compatibility. Each execution creates a fresh timestamp/12-character random-ID directory with summary.json, runner.log and work/. IDs leave room for NumPy license paths on legacy MAX_PATH hosts; keep the selected root reasonably short. A collision refuses to overwrite. No Windows policy is changed.

The runner rejects output inside the source, dependencies or an installation. It sets explicit tool paths and disables source bytecode writes. Missing/mismatched dependencies are errors, not silent skips. Reports distinguish passed, failed, errors, omitted and not-run cases.

```powershell
.\scripts\test.ps1 -Suite Full -DependenciesFrom '..\Pauselith-build' -CheckOnly
.\scripts\test.ps1 -DependenciesFrom '..\Pauselith-build' -SelfTestFailure
```

CheckOnly checks configuration/discovery without audiovisual setup; it is not a Full pass. SelfTestFailure runs one deliberate runner failure without changing production code. Exit 0 means success/configuration-only success, 1 a test failure/error, and 2 an infrastructure/configuration/discovery error. An empty suite is rejected.

The last behavior-changing revision passed Fast 38/38 and Full 50/50 locally, including 150% programmatic layout scaling. Publication documentation changes preserve application/worker/profile/test behavior and do not claim a new local audiovisual run. Remote CI results are reported separately in GitHub Actions. These host results do not certify every Windows/CPU/DPI combination.

The optional tests/VisualScenario.cs harness labels its injected partial/minimum scenario explicitly. It uses a verified synthetic result to inspect UI warning behavior and is not compiled into the product.
