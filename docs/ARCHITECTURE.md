# Architecture

`C# WinForms -> JSON job + supervised Python worker -> frozen Python/NumPy engine -> FFmpeg/FFprobe`.

The interface owns the queue and a Windows Job Object for the current worker and descendants. It snapshots settings and consumes structured KIYO events. Confirmed terminal states distinguish complete/partial/error/cancelled. Cancellation is cooperative with bounded fallback; unrelated processes are not terminated.

`motor_original.py` retains detection, frame planning and rendering. `worker.py` coordinates stages/audio/reports, `validation.py` checks media/timing, and `delivery.py` handles ownership, staging, publication and recovery. Packaging does not replace these components.

Application assets use the executable directory. Installed state uses `%LOCALAPPDATA%\KiyoCut`; portable state uses `data/` beside a `portable.mode` marker. `KIYOCUT_DATA_DIR` explicitly overrides state for tests. The host passes the same location to workers/recovery. Worker bytecode writes are disabled. Intermediate media stay in the unique output/staging directory at the selected destination.

`build/` locks inputs; `scripts/` builds/tests/packages; `packaging/` defines setup; `tests/` generates synthetic fixtures; `licenses/` retains notices. Git excludes binaries, caches, settings, jobs, logs and recordings.
