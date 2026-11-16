#requires -Version 5.1
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$OutputDirectory,
 [Parameter(Mandatory=$true)][string]$CacheDirectory,
 [string]$CompilerPath,
 [string]$ReferenceDirectory,
 [string]$SourceRevision='unspecified',
 [switch]$DownloadDependencies
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
$nl=[Environment]::NewLine
$repoRoot=Split-Path $PSScriptRoot -Parent
$config=Get-Content -LiteralPath (Join-Path $repoRoot 'build\toolchain.json') -Raw | ConvertFrom-Json
$lock=Get-Content -LiteralPath (Join-Path $repoRoot 'build\dependencies.lock.json') -Raw | ConvertFrom-Json
function FullPath([string]$value){
 if(-not [IO.Path]::IsPathRooted($value)){$value=Join-Path $PWD.Path $value}
 return [IO.Path]::GetFullPath($value).TrimEnd('\')
}
function Hash([string]$path){return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function CheckHash([string]$path,[string]$expected){
 if((Hash $path) -ne $expected.ToLowerInvariant()){throw "SHA256 mismatch: $path"}
}
$out=FullPath $OutputDirectory
$cache=FullPath $CacheDirectory
if([Environment]::OSVersion.Platform -ne 'Win32NT' -or -not [Environment]::Is64BitProcess){throw 'Windows x64 and 64-bit PowerShell required'}
if(Test-Path -LiteralPath $out){throw 'OutputDirectory must not exist; existing installations are never overwritten'}
if($out -eq $cache -or $cache.StartsWith($out+'\',[StringComparison]::OrdinalIgnoreCase) -or $out.StartsWith($cache+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Cache and output directories must be separate'}
if(-not $CompilerPath){$CompilerPath=Join-Path ([Environment]::GetFolderPath('Windows')) $config.compiler.relativePath}
$CompilerPath=FullPath $CompilerPath
$compiler=Get-Item -LiteralPath $CompilerPath
if(-not $compiler.VersionInfo.ProductVersion.StartsWith($config.compiler.versionFamily+'.')){throw 'Unsupported compiler family; see build/toolchain.json'}
if(-not $ReferenceDirectory){$ReferenceDirectory=$compiler.DirectoryName}
$ReferenceDirectory=FullPath $ReferenceDirectory
$framework=Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full'
if($framework.Release -lt $config.framework.minimumRelease){throw '.NET Framework 4.8.1 required'}
$references=@()
foreach($name in $config.framework.references){
 $path=Join-Path $ReferenceDirectory $name
 if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw "Missing framework reference: $name"}
 $references+=@{name=$name;sha256=(Hash $path);fileVersion=(Get-Item -LiteralPath $path).VersionInfo.FileVersion}
}
New-Item -ItemType Directory -Path $cache -Force | Out-Null
foreach($archive in $lock.archives){
 $path=Join-Path $cache $archive.file
 if(-not(Test-Path -LiteralPath $path)){
  if(-not $DownloadDependencies){throw "Missing cached archive: $($archive.file). Use -DownloadDependencies to fetch locked inputs."}
  $temporary=$path+'.'+[Guid]::NewGuid().ToString('N')+'.download'
  Invoke-WebRequest -Uri $archive.url -OutFile $temporary -UseBasicParsing
  CheckHash $temporary $archive.sha256
  [IO.File]::Move($temporary,$path)
 }
 CheckHash $path $archive.sha256
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
New-Item -ItemType Directory -Path $out,(Join-Path $out 'app'),(Join-Path $out 'runtime\python'),(Join-Path $out 'tools\ffmpeg'),(Join-Path $out 'jobs'),(Join-Path $out 'logs') | Out-Null
$pythonArchive=$lock.archives | Where-Object {$_.id -eq 'python'}
$numpyArchive=$lock.archives | Where-Object {$_.id -eq 'numpy'}
$ffmpegArchive=$lock.archives | Where-Object {$_.id -eq 'ffmpeg'}
$pythonRoot=Join-Path $out 'runtime\python'
[IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $cache $pythonArchive.file),$pythonRoot)
$site=Join-Path $pythonRoot 'Lib\site-packages'
New-Item -ItemType Directory -Path $site -Force | Out-Null
[IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $cache $numpyArchive.file),$site)
[IO.File]::WriteAllText((Join-Path $pythonRoot 'python311._pth'),(($config.pythonPath -join $nl)+$nl),[Text.UTF8Encoding]::new($false))
$zip=[IO.Compression.ZipFile]::OpenRead((Join-Path $cache $ffmpegArchive.file))
try{
 foreach($entrySpec in $lock.ffmpegEntries){
  $entry=$zip.GetEntry($entrySpec.entry)
  if(-not $entry){throw "Missing FFmpeg archive entry: $($entrySpec.entry)"}
  [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,(Join-Path $out $entrySpec.destination),$false)
 }
}finally{$zip.Dispose()}
foreach($property in $lock.requiredBinaryHashes.PSObject.Properties){CheckHash (Join-Path $out $property.Name) $property.Value}
foreach($name in $config.runtimeFiles){Copy-Item -LiteralPath (Join-Path $repoRoot $name) -Destination (Join-Path $out $name)}
foreach($name in @('README.md','LICENSE','THIRD_PARTY_NOTICES.md','DISTRIBUTION_STATUS.txt','CONTRIBUTING.md','CHANGELOG.md')){
 New-Item -ItemType Directory -Path (Split-Path (Join-Path $out $name) -Parent) -Force | Out-Null
 Copy-Item -LiteralPath (Join-Path $repoRoot $name) -Destination (Join-Path $out $name)
}
Copy-Item -LiteralPath (Join-Path $repoRoot 'licenses') -Destination (Join-Path $out 'licenses') -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs') -Destination (Join-Path $out 'docs') -Recurse
$argsList=@($config.compiler.arguments)
foreach($name in $config.framework.references){$argsList+='/reference:'+(Join-Path $ReferenceDirectory $name)}
$argsList+='/out:'+(Join-Path $out 'KiyoCut.exe')
foreach($name in $config.compiler.sources){$argsList+=Join-Path $repoRoot $name}
& $CompilerPath @argsList
if($LASTEXITCODE -ne 0){throw "C# compilation failed: $LASTEXITCODE"}
[Reflection.AssemblyName]::GetAssemblyName((Join-Path $out 'KiyoCut.exe')) | Out-Null
$release=Get-Content -LiteralPath (Join-Path $repoRoot 'build/release.json') -Raw | ConvertFrom-Json
if((Get-Item -LiteralPath (Join-Path $out 'KiyoCut.exe')).VersionInfo.FileVersion -ne $release.fileVersion){throw 'Assembly file version differs from build/release.json'}
$smoke=@'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'app'))
import numpy as np
import worker,motor_original,validation
assert sys.version.split()[0]==sys.argv[2],sys.version
assert np.__version__==sys.argv[3],np.__version__
assert (np.ones((2,2))@np.ones((2,2))==2).all()
modules=(np,worker,motor_original,validation)
for module in modules:
 assert root in Path(module.__file__).resolve().parents,module.__file__
assert worker.ROOT==root
print(json.dumps(dict(python=sys.version.split()[0],numpy=np.__version__,isolated=sys.flags.isolated,imports=[m.__name__ for m in modules],native_numpy_operation=True)))
'@
$python=Join-Path $pythonRoot 'python.exe'
$smokeOutput=(& $python -I -B -c $smoke $out $lock.pythonVersion $lock.numpyVersion) -join $nl
if($LASTEXITCODE -ne 0){throw 'Bundled Python/NumPy or application imports failed'}
$smokeResult=$smokeOutput | ConvertFrom-Json
$ffmpegVersion=(& (Join-Path $out 'tools\ffmpeg\ffmpeg.exe') -version | Select-Object -First 1)
if($LASTEXITCODE -ne 0 -or -not $ffmpegVersion.StartsWith('ffmpeg version '+$lock.ffmpegVersion+' ')){throw 'FFmpeg version check failed'}
$ffprobeVersion=(& (Join-Path $out 'tools\ffmpeg\ffprobe.exe') -version | Select-Object -First 1)
if($LASTEXITCODE -ne 0 -or -not $ffprobeVersion.StartsWith('ffprobe version '+$lock.ffmpegVersion+' ')){throw 'FFprobe version check failed'}
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\BUILD.md') -Destination (Join-Path $out 'BUILD.md')
[IO.File]::WriteAllText((Join-Path $out 'LEEME.txt'),("Pauselith - Automatic Silence Remover"+$nl+"Open KiyoCut.exe (legacy technical filename), add videos and process the queue."+$nl+"Original files are preserved. See BUILD.md and LICENSE for requirements, licensing scope and limitations."+$nl),[Text.UTF8Encoding]::new($false))
$files=[ordered]@{}
Get-ChildItem -LiteralPath $out -Recurse -File | Sort-Object FullName | ForEach-Object {$relative=$_.FullName.Substring($out.Length+1).Replace('\','/');$files[$relative]=Hash $_.FullName}
$sourceHashes=[ordered]@{}
foreach($name in @($config.runtimeFiles)+@('build/toolchain.json','build/dependencies.lock.json','scripts/build.ps1','docs/BUILD.md')){$sourceHashes[$name]=Hash (Join-Path $repoRoot $name)}
$manifest=[ordered]@{
 schema=1;sourceRevision=$SourceRevision
 version=$release.version
 compiler=@{version=$compiler.VersionInfo.ProductVersion;sha256=(Hash $CompilerPath);language=$config.compiler.language}
 framework=@{target=$config.framework.target;hostRelease=$framework.Release;references=$references}
 powershell=$PSVersionTable.PSVersion.ToString()
 inputs=$lock.archives;sourceFiles=$sourceHashes;files=$files
 smoke=@{python=$smokeResult;ffmpeg=$ffmpegVersion;ffprobe=$ffprobeVersion;managedAssembly='pass'}
 reproducibility='Pinned dependency archives and explicit build procedure; legacy C# PE timestamps/MVID are not binary deterministic.'
}
[IO.File]::WriteAllText((Join-Path $out 'build-manifest.json'),($manifest | ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
Write-Output "PASS: built and checked $out"
