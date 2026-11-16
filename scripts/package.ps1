#requires -Version 5.1
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$BuildDirectory,
 [Parameter(Mandatory=$true)][string]$OutputDirectory,
 [Parameter(Mandatory=$true)][string]$ISCCPath,
 [switch]$Public
)
$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$release=Get-Content -LiteralPath (Join-Path $repo 'build\release.json') -Raw | ConvertFrom-Json
if($Public){throw 'Public packaging is blocked: complete and review corresponding source, source license and clean-machine validation first. See docs/RELEASING.md.'}
$build=[IO.Path]::GetFullPath($BuildDirectory).TrimEnd('\')
$out=[IO.Path]::GetFullPath($OutputDirectory).TrimEnd('\')
if(Test-Path -LiteralPath $out){throw 'OutputDirectory must be new; no existing files are overwritten'}
if($out.StartsWith($build+'\',[StringComparison]::OrdinalIgnoreCase) -or $build.StartsWith($out+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Build and output must be separate'}
if(-not(Test-Path -LiteralPath $ISCCPath -PathType Leaf)){throw 'Missing Inno Setup compiler. See build/installer.lock.json and docs/RELEASING.md.'}
$manifest=Get-Content -LiteralPath (Join-Path $build 'build-manifest.json') -Raw | ConvertFrom-Json
foreach($file in $manifest.files.PSObject.Properties){
 $path=Join-Path $build $file.Name
 if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.Value){throw "Build manifest mismatch: $($file.Name)"}
}
if((Get-Item -LiteralPath (Join-Path $build 'KiyoCut.exe')).VersionInfo.FileVersion -ne $release.fileVersion){throw 'Executable version does not match build/release.json'}
$installerLock=Get-Content -LiteralPath (Join-Path $repo 'build/installer.lock.json') -Raw | ConvertFrom-Json
foreach($file in $installerLock.compilerHashes.PSObject.Properties){
 if((Get-FileHash -LiteralPath (Join-Path (Split-Path $ISCCPath -Parent) $file.Name)).Hash.ToLowerInvariant() -ne $file.Value){throw 'Use the pinned Inno Setup 6.7.4 compiler files'}
}
New-Item -ItemType Directory -Path $out | Out-Null
$portable=Join-Path $out 'portable\KiyoCut'
$payload=Join-Path $out 'installer-payload\KiyoCut'
foreach($target in @($portable,$payload)){
 New-Item -ItemType Directory -Path $target -Force | Out-Null
 foreach($file in $manifest.files.PSObject.Properties){
  $destination=Join-Path $target $file.Name
  New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $build $file.Name) -Destination $destination
 }
 Copy-Item -LiteralPath (Join-Path $build 'build-manifest.json') -Destination $target
}
[IO.File]::WriteAllText((Join-Path $portable 'portable.mode'),'Keep user data in the data subdirectory.')
[IO.File]::WriteAllText((Join-Path $payload 'kiyocut-preview.marker'),'9F7A96A3-86C8-4538-AC32-3C02E511B658')
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=Join-Path $out ('KiyoCut-'+$release.version+'-windows-x64-portable.zip')
[IO.Compression.ZipFile]::CreateFromDirectory((Split-Path $portable -Parent),$zip,[IO.Compression.CompressionLevel]::Fastest,$false)
& $ISCCPath ('/DPayload='+$payload) ('/DOutputRoot='+$out) ('/DProductVersion='+$release.version) (Join-Path $repo 'packaging\KiyoCut.iss') *> (Join-Path $out 'installer-build.log')
if($LASTEXITCODE -ne 0){throw "Installer compilation failed; see $out\installer-build.log"}
$artifacts=Get-ChildItem -LiteralPath $out -File | Where-Object {$_.Extension -in @('.zip','.exe')}
$artifacts | ForEach-Object {((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant())+'  '+$_.Name} | Set-Content -LiteralPath (Join-Path $out 'SHA256SUMS.txt') -Encoding ascii
[ordered]@{version=$release.version;status='internal_candidate_not_for_publication';sourceRevision=$manifest.sourceRevision;installerCompiler='Inno Setup 6.7.4';artifacts=@($artifacts.Name)} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $out 'package-manifest.json') -Encoding utf8
Write-Output "PASS: internal portable and installer candidates prepared in $out"
