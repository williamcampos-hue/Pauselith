# Build Pauselith from source

Use Windows x64 and 64-bit PowerShell 5.1 or newer. .NET Framework 4.8.1 must supply the documented family-4.8 C# compiler and reference assemblies. The validated host used compiler 4.8.9221.0 (C# 5) and PowerShell 7.6.9. A completely clean Windows machine has not been tested.

## Inputs obtained externally

The source export contains **no runtime binaries**. build/dependencies.lock.json fixes URLs and SHA-256 for CPython 3.11.9 embeddable x64, NumPy 2.4.6 cp311-win_amd64 and Gyan FFmpeg/FFprobe 9.0.2 essentials. The build either reads those exact archives from a caller-selected cache or downloads missing archives with explicit `-DownloadDependencies`. It does not choose latest or use a personal application installation.

```powershell
.\scripts\build.ps1 -OutputDirectory '..\Pauselith-build' -CacheDirectory '..\Pauselith-cache' -DownloadDependencies
.\scripts\test.ps1 -Suite Fast -DependenciesFrom '..\Pauselith-build'
.\scripts\test.ps1 -Suite Full -DependenciesFrom '..\Pauselith-build'
```

OutputDirectory must be new and separate from the cache/source. For offline builds, obtain the three locked archives from their providers, place them in CacheDirectory and omit `-DownloadDependencies`. End users do not need a separately installed Python, NumPy or FFmpeg; this preparation creates the local runtime for development/use. External dependency licenses apply independently: local building does not clear redistribution of the resulting binary bundle.

The legacy technical output remains `KiyoCut.exe`; its displayed product/window name is Pauselith. The build also creates app/, runtime/python/, tools/ffmpeg/, the approved profile, LICENSE/notices/docs, empty jobs/logs and build-manifest.json.

CompilerPath and ReferenceDirectory can explicitly select compatible tools; no compiler or Python is taken implicitly from PATH. build/toolchain.json lists compiler flags, sources, references and Python paths. SourceRevision records a commit/tree identifier.

Compilation checks assembly metadata, locked executable hashes, isolated application/NumPy imports, a native NumPy operation and FFmpeg/FFprobe versions. No recording is rendered during a build. The manifest records inputs, source/output hashes and actual compiler/framework versions.

The procedure and archive inputs are pinned; legacy C# PE timestamps/MVID are not binary deterministic. Framework servicing versions are recorded, not replaced. See [testing](TESTING.md) and [license limits](LICENSING.md). No installer or public binary is created by this command.
