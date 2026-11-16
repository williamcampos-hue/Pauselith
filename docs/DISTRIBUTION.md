# Distribution and storage

Portable ZIP: extract completely into a writable directory. `portable.mode` selects a local `data/` folder. Do not run inside a ZIP or protected system folder.

Inno Setup Preview: per-user, no elevation, default `%LOCALAPPDATA%\Programs\KiyoCutPreview`. Start menu entries are automatic; desktop shortcut is optional. Setup refuses unrelated nonempty targets, checks .NET Framework 4.8.1, and bundles Python/NumPy/FFmpeg. It does not download Windows components or add telemetry/services.

Installed state is `%LOCALAPPDATA%\KiyoCut`, outside application files, and is retained during updates/uninstall. Tests can set `KIYOCUT_DATA_DIR`. Python bytecode is disabled for workers. Output/staging media require writable space at the chosen destination. Close the app before updating; data-location changes during future rebranding need explicit migration.

The standard uninstaller removes installed files, shortcuts and its registry entry; it does not recursively erase arbitrary output/data folders. A same-candidate reinstall test establishes retention, not every future version migration. Preview identity is separate from the old personal installation.

Unsigned candidates are not publicly cleared. Clean Windows, other CPUs/DPI, reputation behavior and runtime licensing remain release work. A local install test is not a clean-machine test. See RELEASING.md.
